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


def _env_value(name: str) -> str | None:
    value = get_secret(name)
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


class LLMProviderConfig(BaseModel):
    providers: dict[ProviderType, ProviderConfig]


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


def load_llm_provider_config() -> LLMProviderConfig:
    with MODELS_CONFIG_FILE.open("rb") as file:
        return LLMProviderConfig.model_validate(tomllib.load(file))


def load_r2_config() -> R2Config:
    # 桶名和密钥属于运行环境：写进 TOML 会和模型清单混在一起，也更容易被提交进仓库。
    # 缺省返回空字段而不是抛错，这样 import 本模块、跑校验单测都不依赖真实 R2。
    return R2Config(
        account_id=_env_value("R2_ACCOUNT_ID"),
        access_key_id=_env_value("R2_ACCESS_KEY_ID"),
        secret_access_key=_env_value("R2_SECRET_ACCESS_KEY"),
        bucket_name=_env_value("R2_BUCKET_NAME"),
        key_prefix=_env_value("R2_KEY_PREFIX"),
    )


llm_provider_config = load_llm_provider_config()
