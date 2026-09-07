import os
import tomllib
from pathlib import Path

from dotenv import dotenv_values

from memora_agent.schema.config import (
    MineruConfig,
    MysqlConfig,
    ProviderConfig,
    QdrantConfig,
    R2Config,
    RabbitMQConfig,
    RedisConfig,
    FeishuConfig,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_CONFIG_FILE = PROJECT_ROOT / "config" / "models.toml"
ENV_FILE = PROJECT_ROOT / ".env"


class Config:
    def __init__(
        self,
        env_file: Path = ENV_FILE,
        models_file: Path = MODELS_CONFIG_FILE,
    ) -> None:
        self.env_file = env_file
        self.models_file = models_file
        self.values = self.load_env()

        self.app_env = self.get("APP_ENV", "dev")
        self.mysql = self.load_mysql()
        self.redis = self.load_redis()
        self.rabbitmq = self.load_rabbitmq()
        self.qdrant = self.load_qdrant()
        self.r2 = self.load_r2()
        self.mineru = self.load_mineru()
        self.llm = self.load_llm()
        self.feishu = self.load_feishu()
    def load_env(self) -> dict[str, str | None]:
        values = dict(dotenv_values(self.env_file))
        values.update(os.environ)
        return values

    def get(self, name: str, default: str | None = None) -> str | None:
        value = self.values.get(name)
        if value is None or not value.strip():
            return default
        return value.strip()

    def get_int(self, name: str, default: int) -> int:
        value = self.get(name)
        if value is None:
            return default
        return int(value)

    def load_mysql(self) -> MysqlConfig:
        return MysqlConfig(
            host=self.get("MYSQL_HOST", "127.0.0.1"),
            port=self.get_int("MYSQL_PORT", 3306),
            user=self.get("MYSQL_USER", "memora"),
            password=self.get("MYSQL_PASSWORD"),
            database=self.get("MYSQL_DATABASE", "memora"),
        )

    def load_redis(self) -> RedisConfig:
        return RedisConfig(
            host=self.get("REDIS_HOST", "127.0.0.1"),
            port=self.get_int("REDIS_PORT", 6379),
            password=self.get("REDIS_PASSWORD"),
        )

    def load_rabbitmq(self) -> RabbitMQConfig:
        return RabbitMQConfig(
            host=self.get("RABBITMQ_HOST", "127.0.0.1"),
            port=self.get_int("RABBITMQ_PORT", 5672),
            user=self.get("RABBITMQ_USER", "memora"),
            password=self.get("RABBITMQ_PASSWORD"),
        )

    def load_qdrant(self) -> QdrantConfig:
        return QdrantConfig(
            host=self.get("QDRANT_HOST", "127.0.0.1"),
            port=self.get_int("QDRANT_PORT", 6333),
        )

    def load_r2(self) -> R2Config:
        return R2Config(
            account_id=self.get("R2_ACCOUNT_ID"),
            access_key_id=self.get("R2_ACCESS_KEY_ID"),
            secret_access_key=self.get("R2_SECRET_ACCESS_KEY"),
            bucket_name=self.get("R2_BUCKET_NAME"),
            key_prefix=self.get("R2_KEY_PREFIX"),
        )

    def load_mineru(self) -> MineruConfig:
        return MineruConfig(api_key=self.get("MINERU_API_KEY"))

    def load_llm(self) -> dict[str, ProviderConfig]:
        with self.models_file.open("rb") as file:
            raw = tomllib.load(file)

        providers: dict[str, ProviderConfig] = {}
        for name, provider in raw.items():
            providers[name] = ProviderConfig.model_validate(provider)
        return providers
    def load_feishu(self) -> FeishuConfig:
        return FeishuConfig(
            webhook_url=self.get("FEISHU_WEBHOOK_URL"),
        )


config = Config()
