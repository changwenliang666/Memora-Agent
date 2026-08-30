import os
import tomllib
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel

from memora_agent.schema.config import ProviderConfig, ProviderType

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_CONFIG_FILE = PROJECT_ROOT / "config" / "models.toml"
ENV_FILE = PROJECT_ROOT / ".env"


def get_secret(name: str) -> str | None:
    return os.getenv(name) or dotenv_values(ENV_FILE).get(name)


class LLMProviderConfig(BaseModel):
    providers: dict[ProviderType, ProviderConfig]


def load_llm_provider_config() -> LLMProviderConfig:
    with MODELS_CONFIG_FILE.open("rb") as file:
        return LLMProviderConfig.model_validate(tomllib.load(file))


llm_provider_config = load_llm_provider_config()
