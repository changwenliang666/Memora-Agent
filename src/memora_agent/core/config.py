import os
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from memora_agent.schema.config import ProviderConfig, ProviderType

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_CONFIG_FILE = PROJECT_ROOT / "config" / "models.toml"
ENV_FILE = PROJECT_ROOT / ".env"


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def _merged_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for key, raw in dotenv_values(ENV_FILE).items():
            if raw is not None:
                values[key] = raw
    values.update(os.environ)
    return values


def _int_or_default(raw: str | None, default: int) -> int:
    value = _blank_to_none(raw)
    if value is None:
        return default
    return int(value)


class LLMProviderConfig(BaseModel):
    providers: dict[ProviderType, ProviderConfig]


def _load_llm_provider_config() -> LLMProviderConfig:
    with MODELS_CONFIG_FILE.open("rb") as file:
        return LLMProviderConfig.model_validate(tomllib.load(file))


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


class Settings(BaseSettings):
    """运行时配置的唯一入口：环境映射构建一次，TOML 在同一次构造里载入。"""

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "dev"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "memora"
    mysql_password: str | None = None
    mysql_database: str = "memora"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str | None = None
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "memora"
    rabbitmq_password: str | None = None
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_key_prefix: str | None = None
    mineru_api_key: str | None = None
    llm: LLMProviderConfig

    _env_map: dict[str, str] = PrivateAttr(default_factory=dict)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # 字段和 api_key() 共用 _merged_env()，避免 BaseSettings 再读一遍环境。
        return (init_settings,)

    def api_key(self, name: str) -> str | None:
        return _blank_to_none(self._env_map.get(name))

    @property
    def r2(self) -> R2Config:
        return R2Config(
            account_id=self.r2_account_id,
            access_key_id=self.r2_access_key_id,
            secret_access_key=self.r2_secret_access_key,
            bucket_name=self.r2_bucket_name,
            key_prefix=self.r2_key_prefix,
        )

    @property
    def mineru(self) -> MineruConfig:
        return MineruConfig(api_key=self.mineru_api_key)


@lru_cache
def get_settings() -> Settings:
    env_map = _merged_env()
    settings = Settings.model_validate(
        {
            "app_env": _blank_to_none(env_map.get("APP_ENV")) or "dev",
            "mysql_host": _blank_to_none(env_map.get("MYSQL_HOST")) or "127.0.0.1",
            "mysql_port": _int_or_default(env_map.get("MYSQL_PORT"), 3306),
            "mysql_user": _blank_to_none(env_map.get("MYSQL_USER")) or "memora",
            "mysql_password": _blank_to_none(env_map.get("MYSQL_PASSWORD")),
            "mysql_database": _blank_to_none(env_map.get("MYSQL_DATABASE")) or "memora",
            "redis_host": _blank_to_none(env_map.get("REDIS_HOST")) or "127.0.0.1",
            "redis_port": _int_or_default(env_map.get("REDIS_PORT"), 6379),
            "redis_password": _blank_to_none(env_map.get("REDIS_PASSWORD")),
            "rabbitmq_host": _blank_to_none(env_map.get("RABBITMQ_HOST"))
            or "127.0.0.1",
            "rabbitmq_port": _int_or_default(env_map.get("RABBITMQ_PORT"), 5672),
            "rabbitmq_user": _blank_to_none(env_map.get("RABBITMQ_USER")) or "memora",
            "rabbitmq_password": _blank_to_none(env_map.get("RABBITMQ_PASSWORD")),
            "qdrant_host": _blank_to_none(env_map.get("QDRANT_HOST")) or "127.0.0.1",
            "qdrant_port": _int_or_default(env_map.get("QDRANT_PORT"), 6333),
            "r2_account_id": _blank_to_none(env_map.get("R2_ACCOUNT_ID")),
            "r2_access_key_id": _blank_to_none(env_map.get("R2_ACCESS_KEY_ID")),
            "r2_secret_access_key": _blank_to_none(env_map.get("R2_SECRET_ACCESS_KEY")),
            "r2_bucket_name": _blank_to_none(env_map.get("R2_BUCKET_NAME")),
            "r2_key_prefix": _blank_to_none(env_map.get("R2_KEY_PREFIX")),
            "mineru_api_key": _blank_to_none(env_map.get("MINERU_API_KEY")),
            "llm": _load_llm_provider_config(),
        }
    )
    object.__setattr__(settings, "_env_map", env_map)
    return settings
