from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI

from memora_agent.core.config import Config, config
from memora_agent.schema.config import ProviderConfig, ProviderType


class LLMProvider:
    def __init__(self, app_config: Config | None = None):
        self.app_config = app_config or config
        self.providers = self.app_config.llm

    def list_providers(self) -> dict[str, list[str]]:
        return {
            name: list(provider.models)
            for name, provider in self.providers.items()
        }

    def get_model(self, provider_type: ProviderType, model_name: str) -> BaseChatModel:
        provider = self._get_provider(provider_type)
        if model_name not in provider.models:
            raise ValueError(f"Provider {provider_type} 未配置模型: {model_name}")

        if provider_type == "ollama":
            return ChatOllama(
                base_url=provider.base_url,
                model=model_name,
                reasoning=provider.think,
                temperature=provider.temperature,
                client_kwargs={"trust_env": False},
            )

        if provider_type == "openai":
            if not provider.api_key_env:
                raise ValueError("OpenAI Provider 未配置 api_key_env")
            api_key = self.app_config.get(provider.api_key_env)
            if not api_key:
                raise ValueError(f"环境变量 {provider.api_key_env} 未配置或为空")
            return ChatOpenAI(
                api_key=api_key,
                base_url=provider.base_url,
                model=model_name,
                temperature=provider.temperature,
                extra_body={
                    "thinking": {"type": "enabled" if provider.think else "disabled"}
                },
            )

        raise ValueError(f"不支持的供应商 {provider_type}")

    def get_embeddings(self, provider_type: ProviderType, model_name: str) -> Embeddings:
        provider = self._get_provider(provider_type)
        if model_name not in provider.embed_models:
            raise ValueError(f"Provider {provider_type} 未配置模型: {model_name}")

        if provider_type == "ollama":
            return OllamaEmbeddings(
                base_url=provider.base_url,
                model=model_name,
                client_kwargs={"trust_env": False},
            )

        raise ValueError(f"不支持的供应商 {provider_type}")

    def _get_provider(self, provider_type: str) -> ProviderConfig:
        provider = self.providers.get(provider_type)
        if provider is None:
            raise ValueError(f"未配置 Provider: {provider_type}")
        return provider
