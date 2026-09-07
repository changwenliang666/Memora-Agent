from pathlib import Path

import pytest

import memora_agent.core.provider as provider_module
from memora_agent.core.config import Config, MODELS_CONFIG_FILE
from memora_agent.core.provider import LLMProvider


MODELS_TOML = """
[ollama]
base_url = "http://localhost:11434"
temperature = 0.7
models = ["small", "large"]
embed_models = ["mxbai-embed-large:latest"]

[openai]
base_url = "https://api.example.com"
api_key_env = "TEST_OPENAI_API_KEY"
think = true
models = ["online-small", "online-large"]
"""


def make_config(tmp_path: Path, env: str = "") -> Config:
    env_file = tmp_path / ".env"
    models_file = tmp_path / "models.toml"
    env_file.write_text(env)
    models_file.write_text(MODELS_TOML)
    return Config(env_file=env_file, models_file=models_file)


def test_list_providers_returns_chat_models_only(tmp_path: Path) -> None:
    listing = LLMProvider(make_config(tmp_path)).list_providers()

    assert listing == {
        "ollama": ["small", "large"],
        "openai": ["online-small", "online-large"],
    }
    assert "mxbai-embed-large:latest" not in listing["ollama"]


def test_toml_loads_multiple_models_per_provider(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("")
    app_config = Config(env_file=env_file, models_file=MODELS_CONFIG_FILE)

    listing = LLMProvider(app_config).list_providers()

    assert listing["ollama"] == ["qwen3.5:4b-mlx", "qwen3.5:2b"]
    assert listing["openai"] == ["deepseek-v4-flash", "deepseek-chat"]


def test_ollama_model_uses_provider_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        provider_module,
        "ChatOllama",
        lambda **kwargs: captured.append(kwargs) or object(),
    )
    provider = LLMProvider(make_config(tmp_path))

    provider.get_model("ollama", "small")
    provider.get_model("ollama", "large")

    assert captured[0]["model"] == "small"
    assert captured[0]["temperature"] == 0.7
    assert captured[1]["model"] == "large"
    assert captured[1]["temperature"] == 0.7
    assert captured[1]["base_url"] == "http://localhost:11434"


def test_openai_model_uses_configured_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.delenv("TEST_OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        provider_module,
        "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    app_config = make_config(tmp_path, "TEST_OPENAI_API_KEY=test-key\n")
    LLMProvider(app_config).get_model("openai", "online-large")

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "online-large"
    assert captured["base_url"] == "https://api.example.com"
    assert captured["extra_body"]["thinking"]["type"] == "enabled"


def test_unknown_model_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置模型"):
        LLMProvider(make_config(tmp_path)).get_model("ollama", "missing")


def test_unknown_provider_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置 Provider"):
        LLMProvider(make_config(tmp_path)).get_model(  # type: ignore[arg-type]
            "anthropic", "claude"
        )


def test_openai_model_requires_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="TEST_OPENAI_API_KEY"):
        LLMProvider(make_config(tmp_path)).get_model("openai", "online-small")


def test_get_embeddings_uses_embed_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        provider_module,
        "OllamaEmbeddings",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    LLMProvider(make_config(tmp_path)).get_embeddings(
        "ollama", "mxbai-embed-large:latest"
    )

    assert captured["model"] == "mxbai-embed-large:latest"
    assert captured["base_url"] == "http://localhost:11434"


def test_get_model_rejects_embedding_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置模型"):
        LLMProvider(make_config(tmp_path)).get_model(
            "ollama", "mxbai-embed-large:latest"
        )
