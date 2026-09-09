from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    provider_type: str | None = None
    model_name: str | None = Field(default=None, min_length=1)
