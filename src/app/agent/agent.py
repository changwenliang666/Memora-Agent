from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.schema.config import AgentConfig
from app.core.provider import LLMProvider
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class StreamEvent:
    """Agent 流式循环产出的一帧逻辑事件。

    ``seq`` 由上层（Redis 缓冲）在落库时分配，Agent 只管事件名与载荷。
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)


def _chunk_text(chunk: AIMessageChunk) -> str:
    """取 chunk 的纯文本增量。content 可能是 str 或块列表，统一成 str。"""
    content = chunk.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""

class Agent:
    def __init__(self, agent_config: AgentConfig):
        self.current_model = LLMProvider().get_model(
            agent_config.provider_type,
            agent_config.model_name,
        )
        self.tools = agent_config.tools
        self.history_messages = agent_config.history_messages
        self.system_prompt = agent_config.system_prompt
        self.human_input_message = agent_config.human_input_message
        self.max_round = agent_config.max_round
        self.stream = agent_config.stream
        # 存在工具，进行绑定
        if len(self.tools.tools_list) > 0:
            self.current_model =  self.current_model.bind_tools(self.tools.tools_list)
    # 构建大模型提示词
    @property
    def build_system_prompt(self) -> str:
       system_prompt = f"{self.system_prompt}"
       if len(self.tools.tools_list) > 0:
           system_prompt += f"\n可使用的工具列表：{self.tools.tools_prompt}"
    #    if len(self.history_messages) > 0:
    #        system_prompt += f"\n历史对话记录：{self.history_messages}"
       return system_prompt
    # 执行工具
    async def execute_tool(self, tool_name: str, tool_args: dict):
        target_tool:BaseTool | None = None
        for tool in self.tools.tools_list:
            if tool.name == tool_name:
                target_tool = tool
                break
        if target_tool is None:
            return f"工具{tool_name}不存在"
        print(f"调用工具：{tool_name}，参数：{tool_args}")
        return await target_tool.ainvoke(tool_args)
    # 运行循环
    async def run_loop(self):
        self.history_messages.append(HumanMessage(content=self.human_input_message))
        while self.max_round > 0:
            response = await self.current_model.ainvoke([SystemMessage(content=self.build_system_prompt),*self.history_messages])
            self.max_round -= 1
            # response 本身就是 AIMessage，直接入历史，才能带上 tool_calls
            self.history_messages.append(response)
            # 如果模型返回了工具调用，则需要调用工具
            if len(response.tool_calls) > 0:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args")
                    tool_result = await self.execute_tool(tool_name, tool_args)
                    self.history_messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call.get("id")))
            else:
                print(f"token花费：{response.usage_metadata}")
                return response.content
    # 执行一次大模型非流式调用
    async def run_invoke(self):
       response = await self.current_model.ainvoke([SystemMessage(content=self.build_system_prompt),*self.history_messages])
       return response.content

    def _prompt_messages(self) -> list[BaseMessage]:
        """system + 历史。流式与非流式共用。"""
        return [SystemMessage(content=self.build_system_prompt), *self.history_messages]

    # 流式循环：产出逻辑事件，工具在服务端执行但不对外发 tool 事件
    async def run_stream(self) -> AsyncIterator[StreamEvent]:
        """按轮 astream，把文本增量作为 message.delta 产出。

        每轮先把 AIMessageChunk 累加成完整 AIMessage 再入历史，保证 tool_calls
        完整后再决定是否调工具。仅非空文本产出 delta；tool_call_chunks 不产出。
        无工具时产出 message.completed 结束；异常 / 轮次耗尽产出 message.failed。
        """
        self.history_messages.append(HumanMessage(content=self.human_input_message))
        remaining = self.max_round
        try:
            while remaining > 0:
                remaining -= 1
                gathered: AIMessageChunk | None = None
                async for chunk in self.current_model.astream(self._prompt_messages()):
                    if not isinstance(chunk, AIMessageChunk):
                        continue
                    gathered = chunk if gathered is None else gathered + chunk
                    text = _chunk_text(chunk)
                    if text:
                        yield StreamEvent("message.delta", {"content": text})

                if gathered is None:
                    yield StreamEvent("message.failed", {"message": "模型未返回内容"})
                    return

                final = AIMessage(
                    content=gathered.content,
                    tool_calls=gathered.tool_calls,
                )
                self.history_messages.append(final)

                if not final.tool_calls:
                    yield StreamEvent("message.completed", {})
                    return

                for tool_call in final.tool_calls:
                    tool_result = await self.execute_tool(
                        tool_call.get("name"), tool_call.get("args")
                    )
                    self.history_messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call.get("id"),
                        )
                    )

            yield StreamEvent("message.failed", {"message": "已达到最大工具轮次"})
        except Exception as exc:
            yield StreamEvent("message.failed", {"message": "生成失败"})