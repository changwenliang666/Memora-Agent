from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Literal
from langchain_core.messages import BaseMessage
from memora_agent.schema.tools import ToolsDictList

class ProviderConfig(BaseModel):
    provider_type: Literal["ollama", "website_api"]
    base_url: str
    api_key: str | None = None
    model_name: str
    think:bool = False
    temperature: float = 0.7

class AgentConfig(BaseModel):
    provider_type: Literal["ollama", "website_api"] = Field(default="ollama")
    # 可使用的工具列表（用于调用外部工具）
    tools: ToolsDictList = Field(default=ToolsDictList(tools_prompt="",tools_list=[]))
    # 历史对话记录（用于上下文）
    history_messages: list[BaseMessage] = Field(default=[])
    # 系统提示词
    system_prompt: str = Field(default="你是一个ai助手,根据用户的提问，简洁明了的回答用户的问题.",min_length=10,max_length=1000)
    # 用户输入消息
    human_input_message: str = Field(default="",min_length=1,max_length=500)
    # 返回消息类型 流式返回还是一次性返回 默认一次性返回
    stream: bool = Field(default=False)
    # 模型循环最大轮数
    max_round: int = Field(default=10)