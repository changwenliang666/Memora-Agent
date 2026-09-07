from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from memora_agent.schema.tools import ToolsDictList

ProviderType = Literal["ollama", "openai"]


class MysqlConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str | None = None
    database: str


class RedisConfig(BaseModel):
    host: str
    port: int
    password: str | None = None


class RabbitMQConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str | None = None


class QdrantConfig(BaseModel):
    host: str
    port: int


class R2Config(BaseModel):
    account_id: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    bucket_name: str | None = None
    key_prefix: str | None = None

    @property
    def endpoint_url(self) -> str | None:
        if self.account_id is None:
            return None
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def is_complete(self) -> bool:
        return all(
            (
                self.account_id,
                self.access_key_id,
                self.secret_access_key,
                self.bucket_name,
            )
        )


class MineruConfig(BaseModel):
    api_key: str | None = None


class ProviderConfig(BaseModel):
    base_url: str
    api_key_env: str | None = None
    think: bool = False
    temperature: float = Field(default=0.7, ge=0, le=2)
    models: list[str] = Field(min_length=1)
    embed_models: list[str] = Field(default_factory=list)


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

class FeishuConfig(BaseModel):
    webhook_url: str