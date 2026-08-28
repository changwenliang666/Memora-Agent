from memora_agent.schema.config import AgentConfig
from memora_agent.core.provider import LLMProvider
from langchain_core.messages import SystemMessage,HumanMessage,ToolMessage,AIMessage
from langchain_core.tools import BaseTool

class Agent:
    def __init__(self, agent_config: AgentConfig):
        self.current_model = LLMProvider().get_provider(agent_config.provider_type)
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
       if len(self.history_messages) > 0:
           system_prompt += f"\n历史对话记录：{self.history_messages}"
       return system_prompt
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

    async def run_loop(self):
        while self.max_round > 0:
            response = await self.current_model.ainvoke([SystemMessage(content=self.build_system_prompt),HumanMessage(content=self.human_input_message)])
            self.max_round -= 1
            # 如果模型返回了工具调用，则需要调用工具
            if len(response.tool_calls) > 0:
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args")
                    tool_result = await self.execute_tool(tool_name, tool_args)
                    self.history_messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call.get("id")))
            else:
                self.history_messages.append(AIMessage(content=response.content))
                return response.content 