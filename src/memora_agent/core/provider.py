from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from memora_agent.core.config import LLMProviderConfig, get_settings
from memora_agent.schema.config import ModelConfig, ProviderConfig, ProviderType


class LLMProvider:
    def __init__(self, config: LLMProviderConfig | None = None):
        self.config = config or get_settings().llm

    def get_model(self, provider_type: ProviderType, model_name: str) -> BaseChatModel:
        provider = self._get_provider(provider_type)
        model = self._get_model_config(provider, provider_type, model_name)
        think = provider.think if model.think is None else model.think
        temperature = (
            provider.temperature if model.temperature is None else model.temperature
        )

        if provider_type == "ollama":
            return ChatOllama(
                base_url=provider.base_url,
                model=model.name,
                reasoning=think,
                temperature=temperature,
                client_kwargs={"trust_env": False},
            )

        if provider_type == "openai":
            if not provider.api_key_env:
                raise ValueError("OpenAI Provider 未配置 api_key_env")
            api_key = get_settings().api_key(provider.api_key_env)
            if not api_key:
                raise ValueError(f"环境变量 {provider.api_key_env} 未配置或为空")
            return ChatOpenAI(
                api_key=api_key,
                base_url=provider.base_url,
                model=model.name,
                temperature=temperature,
                extra_body={
                    "thinking": {"type": "enabled" if think else "disabled"}
                },
            )

        raise ValueError(f"不支持的 Provider 类型: {provider_type}")

    def _get_provider(self, provider_type: ProviderType) -> ProviderConfig:
        provider = self.config.providers.get(provider_type)
        if provider is None:
            raise ValueError(f"未配置 Provider: {provider_type}")
        return provider

    def _get_model_config(
        self,
        provider: ProviderConfig,
        provider_type: ProviderType,
        model_name: str,
    ) -> ModelConfig:
        for model in provider.models:
            if model.name == model_name:
                return model
        raise ValueError(f"Provider {provider_type} 未配置模型: {model_name}")


llm_provider = LLMProvider()
