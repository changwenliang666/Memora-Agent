from pathlib import Path

import pytest

from memora_agent.core.config import get_settings

R2_ENV_NAMES = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_KEY_PREFIX",
)


@pytest.fixture
def isolated_env(
    isolated_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    for name in R2_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("MINERU_API_KEY", raising=False)
    get_settings.cache_clear()
    return isolated_env_file


def test_missing_r2_config_fields_are_none(isolated_env: Path) -> None:
    settings = get_settings()
    config = settings.r2

    assert config.account_id is None
    assert config.access_key_id is None
    assert config.secret_access_key is None
    assert config.bucket_name is None
    assert config.key_prefix is None
    assert config.endpoint_url is None
    assert config.is_complete() is False
    assert settings.mineru.api_key is None


def test_blank_r2_env_values_are_none(isolated_env: Path) -> None:
    isolated_env.write_text("R2_ACCOUNT_ID=   \nMINERU_API_KEY=\n")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.r2.account_id is None
    assert settings.r2.is_complete() is False
    assert settings.mineru.api_key is None


def test_complete_r2_config_builds_endpoint(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "memora-files")
    monkeypatch.setenv("R2_KEY_PREFIX", "knowledge-base")
    get_settings.cache_clear()

    config = get_settings().r2

    assert config.is_complete() is True
    assert config.key_prefix == "knowledge-base"
    assert config.endpoint_url == "https://acct123.r2.cloudflarestorage.com"


def test_process_env_overrides_dotenv(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_env.write_text("R2_ACCOUNT_ID=from-file\n")
    monkeypatch.setenv("R2_ACCOUNT_ID", "from-process")
    get_settings.cache_clear()

    assert get_settings().r2.account_id == "from-process"


def test_model_catalog_loads_from_toml(isolated_env: Path) -> None:
    settings = get_settings()
    ollama_models = [
        model.name for model in settings.llm.providers["ollama"].models
    ]
    openai_models = [
        model.name for model in settings.llm.providers["openai"].models
    ]
    assert ollama_models == ["qwen3.5:4b-mlx", "qwen3.5:2b"]
    assert openai_models == ["deepseek-v4-flash", "deepseek-chat"]
    assert settings.mysql_host == "127.0.0.1"
    assert settings.redis_port == 6379
    assert settings.rabbitmq_port == 5672
    assert settings.qdrant_host == "127.0.0.1"
    assert settings.qdrant_port == 6333


def test_process_env_overrides_qdrant_dotenv(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_env.write_text("QDRANT_HOST=from-file\nQDRANT_PORT=6333\n")
    monkeypatch.setenv("QDRANT_HOST", "from-process")
    monkeypatch.setenv("QDRANT_PORT", "6334")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.qdrant_host == "from-process"
    assert settings.qdrant_port == 6334
