from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from memora_agent.schema.tools import ToolsDictList

ProviderType = Literal["ollama", "openai"]


class ModelConfig(BaseModel):
    name: str = Field(min_length=1)
    think: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)


class ProviderConfig(BaseModel):
    base_url: str
    api_key_env: str | None = None
    think: bool = False
    temperature: float = Field(default=0.7, ge=0, le=2)
    models: list[ModelConfig] = Field(min_length=1)


class AgentConfig(BaseModel):
    provider_type: ProviderType
    model_name: str = Field(min_length=1)
    tools: ToolsDictList = Field(
        default_factory=lambda: ToolsDictList(tools_prompt="", tools_list=[])
    )
    history_messages: list[BaseMessage] = Field(default_factory=list)
    system_prompt: str = Field(
        default="你是一个ai助手,根据用户的提问，简洁明了的回答用户的问题.",
        min_length=10,
        max_length=1000,
    )
    human_input_message: str = Field(default="", min_length=1, max_length=500)
    stream: bool = Field(default=False)
    max_round: int = Field(default=10)
