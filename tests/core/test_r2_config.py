from pathlib import Path

import pytest

import memora_agent.core.config as config_module
from memora_agent.core.config import Config, MODELS_CONFIG_FILE

ENV_NAMES = (
    "APP_ENV",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "RABBITMQ_HOST",
    "RABBITMQ_PORT",
    "RABBITMQ_USER",
    "RABBITMQ_PASSWORD",
    "QDRANT_HOST",
    "QDRANT_PORT",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_KEY_PREFIX",
    "MINERU_API_KEY",
    "JWT_SECRET",
    "JWT_EXPIRE_MINUTES",
)


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / ".env"
    path.write_text("")
    return path


def load_config(env_file: Path) -> Config:
    return Config(env_file=env_file, models_file=MODELS_CONFIG_FILE)


def test_missing_optional_config_is_none(env_file: Path) -> None:
    config = load_config(env_file)

    assert config.r2.account_id is None
    assert config.r2.access_key_id is None
    assert config.r2.secret_access_key is None
    assert config.r2.bucket_name is None
    assert config.r2.key_prefix is None
    assert config.r2.endpoint_url is None
    assert config.r2.is_complete() is False
    assert config.mineru.api_key is None


def test_blank_values_are_none(env_file: Path) -> None:
    env_file.write_text("R2_ACCOUNT_ID=   \nMINERU_API_KEY=\n")

    config = load_config(env_file)

    assert config.r2.account_id is None
    assert config.r2.is_complete() is False
    assert config.mineru.api_key is None


def test_complete_r2_config_builds_endpoint(env_file: Path) -> None:
    env_file.write_text(
        "\n".join(
            (
                "R2_ACCOUNT_ID=acct123",
                "R2_ACCESS_KEY_ID=key",
                "R2_SECRET_ACCESS_KEY=secret",
                "R2_BUCKET_NAME=memora-files",
                "R2_KEY_PREFIX=knowledge-base",
            )
        )
    )

    r2 = load_config(env_file).r2

    assert r2.is_complete() is True
    assert r2.key_prefix == "knowledge-base"
    assert r2.endpoint_url == "https://acct123.r2.cloudflarestorage.com"


def test_process_env_overrides_dotenv(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text("R2_ACCOUNT_ID=from-file\n")
    monkeypatch.setenv("R2_ACCOUNT_ID", "from-process")

    assert load_config(env_file).r2.account_id == "from-process"


def test_config_exposes_named_groups_with_defaults(env_file: Path) -> None:
    config = load_config(env_file)

    assert config.app_env == "dev"
    assert config.mysql.host == "127.0.0.1"
    assert config.mysql.port == 3306
    assert config.redis.host == "127.0.0.1"
    assert config.redis.port == 6379
    assert config.rabbitmq.host == "127.0.0.1"
    assert config.rabbitmq.port == 5672
    assert config.qdrant.host == "127.0.0.1"
    assert config.qdrant.port == 6333
    assert config.jwt.secret == "dev-only-change-me-jwt-secret-min-32b"
    assert config.jwt.expire_minutes == 10080


def test_model_catalog_loads_from_flat_toml(env_file: Path) -> None:
    config = load_config(env_file)
    ollama = config.llm["ollama"]
    openai = config.llm["openai"]

    assert ollama.models == ["qwen3.5:4b-mlx", "qwen3.5:2b"]
    assert ollama.embed_models == ["mxbai-embed-large:latest"]
    assert openai.models == ["deepseek-v4-flash", "deepseek-chat"]
    assert "mxbai-embed-large:latest" not in ollama.models


def test_process_env_overrides_qdrant_dotenv(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text("QDRANT_HOST=from-file\nQDRANT_PORT=6333\n")
    monkeypatch.setenv("QDRANT_HOST", "from-process")
    monkeypatch.setenv("QDRANT_PORT", "6334")

    config = load_config(env_file)

    assert config.qdrant.host == "from-process"
    assert config.qdrant.port == 6334


def test_dotenv_is_parsed_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []

    def fake_dotenv_values(path: Path) -> dict[str, str]:
        calls.append(path)
        return {}

    env_file = tmp_path / ".env"
    monkeypatch.setattr(config_module, "dotenv_values", fake_dotenv_values)

    Config(env_file=env_file, models_file=MODELS_CONFIG_FILE)

    assert calls == [env_file]
