import pytest

import memora_agent.core.provider as provider_module
from memora_agent.core.config import LLMProviderConfig, llm_provider_config
from memora_agent.core.provider import LLMProvider


def make_config() -> LLMProviderConfig:
    return LLMProviderConfig(
        providers={
            "ollama": {
                "base_url": "http://localhost:11434",
                "temperature": 0.7,
                "models": [
                    {"name": "small", "temperature": 0.1},
                    {"name": "large"},
                ],
            },
            "openai": {
                "base_url": "https://api.example.com",
                "api_key_env": "TEST_OPENAI_API_KEY",
                "models": [
                    {"name": "online-small"},
                    {"name": "online-large", "think": True},
                ],
            },
        }
    )


def test_toml_loads_multiple_models_per_provider() -> None:
    ollama_models = [
        model.name for model in llm_provider_config.providers["ollama"].models
    ]
    openai_models = [
        model.name for model in llm_provider_config.providers["openai"].models
    ]
    assert ollama_models == ["qwen3.5:4b-mlx", "qwen3.5:2b"]
    assert openai_models == ["deepseek-v4-flash", "deepseek-chat"]


def test_ollama_model_uses_model_override_and_provider_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        provider_module,
        "ChatOllama",
        lambda **kwargs: captured.append(kwargs) or object(),
    )
    provider = LLMProvider(make_config())

    provider.get_model("ollama", "small")
    provider.get_model("ollama", "large")

    assert captured[0]["model"] == "small"
    assert captured[0]["temperature"] == 0.1
    assert captured[1]["model"] == "large"
    assert captured[1]["temperature"] == 0.7
    assert captured[1]["base_url"] == "http://127.0.0.1:11434"


def test_openai_model_uses_configured_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.setenv("TEST_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        provider_module,
        "ChatOpenAI",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    LLMProvider(make_config()).get_model("openai", "online-large")

    assert captured["api_key"] == "test-key"
    assert captured["model"] == "online-large"
    assert captured["extra_body"]["thinking"]["type"] == "enabled"


def test_unknown_model_has_clear_error() -> None:
    with pytest.raises(ValueError, match="未配置模型"):
        LLMProvider(make_config()).get_model("ollama", "missing")


def test_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="未配置 Provider"):
        LLMProvider(make_config()).get_model("anthropic", "claude")  # type: ignore[arg-type]


def test_openai_model_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="TEST_OPENAI_API_KEY"):
        LLMProvider(make_config()).get_model("openai", "online-small")
