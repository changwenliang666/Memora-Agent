from pathlib import Path

import pytest

import memora_agent.core.provider as provider_module
from memora_agent.core.config import Config, MODELS_CONFIG_FILE
from memora_agent.core.provider import LLMProvider


MODELS_TOML = """
[ollama]
type = "ollama"
base_url = "http://localhost:11434"
temperature = 0.7
models = ["small", "large"]
embed_models = ["mxbai-embed-large:latest"]

[deepseek]
type = "openai"
base_url = "https://api.deepseek.example.com"
api_key_env = "DEEPSEEK_API_KEY"
think = true
models = ["online-small", "online-large"]

[qwen]
type = "openai"
base_url = "https://api.qwen.example.com"
api_key_env = "QWEN_API_KEY"
models = ["qwen-small"]
embed_models = ["qwen-embed"]
"""


def make_config(tmp_path: Path, env: str = "", models: str = MODELS_TOML) -> Config:
    env_file = tmp_path / ".env"
    models_file = tmp_path / "models.toml"
    env_file.write_text(env)
    models_file.write_text(models)
    return Config(env_file=env_file, models_file=models_file)


def test_list_providers_returns_chat_models_only(tmp_path: Path) -> None:
    listing = LLMProvider(make_config(tmp_path)).list_providers()

    assert listing == {
        "ollama": ["small", "large"],
        "deepseek": ["online-small", "online-large"],
        "qwen": ["qwen-small"],
    }
    assert "mxbai-embed-large:latest" not in listing["ollama"]


def test_toml_loads_named_instances(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("")
    app_config = Config(env_file=env_file, models_file=MODELS_CONFIG_FILE)

    listing = LLMProvider(app_config).list_providers()

    assert listing["ollama"] == ["qwen3.5:4b-mlx", "qwen3.5:2b"]
    assert listing["deepseek"] == ["deepseek-v4-flash", "deepseek-chat"]
    assert listing["qwen"] == ["qwen3.8-max", "qwen3.5-plus"]
    assert app_config.llm["deepseek"].api_key_env == "DEEPSEEK_API_KEY"
    assert app_config.llm["qwen"].api_key_env == "QWEN_API_KEY"
    assert app_config.llm["qwen"].embed_models == [
        "qwen3.7-text-embedding",
        "qwen3.7-text-rerank",
    ]
    assert app_config.llm["qwen"].base_url == (
        "https://ws-g07nrgi2vqgr2idm.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    )


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


def test_openai_type_instances_keep_separate_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setattr(
        provider_module,
        "ChatOpenAI",
        lambda **kwargs: captured.append(kwargs.copy()) or object(),
    )

    app_config = make_config(
        tmp_path,
        "DEEPSEEK_API_KEY=deepseek-key\nQWEN_API_KEY=qwen-key\n",
    )
    provider = LLMProvider(app_config)
    provider.get_model("deepseek", "online-large")
    provider.get_model("qwen", "qwen-small")

    assert captured[0]["api_key"] == "deepseek-key"
    assert captured[0]["model"] == "online-large"
    assert captured[0]["base_url"] == "https://api.deepseek.example.com"
    assert captured[0]["extra_body"]["thinking"]["type"] == "enabled"
    assert captured[1]["api_key"] == "qwen-key"
    assert captured[1]["model"] == "qwen-small"
    assert captured[1]["base_url"] == "https://api.qwen.example.com"
    assert captured[1]["extra_body"]["thinking"]["type"] == "disabled"


def test_unknown_model_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置模型"):
        LLMProvider(make_config(tmp_path)).get_model("ollama", "missing")


def test_unknown_provider_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置 Provider"):
        LLMProvider(make_config(tmp_path)).get_model("anthropic", "claude")


def test_retired_openai_instance_name_is_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置 Provider: openai"):
        LLMProvider(make_config(tmp_path)).get_model("openai", "online-small")


def test_qwen_model_requires_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    with pytest.raises(ValueError, match="QWEN_API_KEY"):
        LLMProvider(make_config(tmp_path)).get_model("qwen", "qwen-small")


def test_missing_type_prevents_config(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Provider ollama 配置无效"):
        make_config(
            tmp_path,
            models="""
[ollama]
base_url = "http://localhost:11434"
models = ["small"]
""",
        )


def test_unsupported_type_prevents_config(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Provider bad 配置无效"):
        make_config(
            tmp_path,
            models="""
[bad]
type = "anthropic"
base_url = "http://localhost:1"
models = ["m"]
""",
        )


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


def test_get_embeddings_openai_type_uses_instance_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setattr(
        provider_module,
        "OpenAIEmbeddings",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    LLMProvider(
        make_config(tmp_path, "QWEN_API_KEY=qwen-key\n")
    ).get_embeddings("qwen", "qwen-embed")

    assert captured["api_key"] == "qwen-key"
    assert captured["model"] == "qwen-embed"
    assert captured["base_url"] == "https://api.qwen.example.com"
    assert captured["check_embedding_ctx_length"] is False


def test_get_embeddings_openai_type_requires_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QWEN_API_KEY", raising=False)

    with pytest.raises(ValueError, match="QWEN_API_KEY"):
        LLMProvider(make_config(tmp_path)).get_embeddings("qwen", "qwen-embed")


def test_get_model_rejects_embedding_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未配置模型"):
        LLMProvider(make_config(tmp_path)).get_model(
            "ollama", "mxbai-embed-large:latest"
        )
