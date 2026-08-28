from pydantic import BaseModel

class ProviderConfig(BaseModel):
    provider_name: str
    base_url: str
    api_key: str | None = None
    model_name: str
    think:bool = False
    temperature: float = 0.7