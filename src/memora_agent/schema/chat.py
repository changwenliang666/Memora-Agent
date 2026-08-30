from pydantic import BaseModel, Field

from memora_agent.schema.config import ProviderType


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    provider_type: ProviderType | None = None
    model_name: str | None = Field(default=None, min_length=1)
