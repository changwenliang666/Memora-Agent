from memora_agent.core.config import llm_provider_config
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

class LLMProvider:
    def __init__(self):
        self.providers = {
            provider.provider_type: provider for provider in llm_provider_config.providers
        }
    # 根据provider_type获取provider (获取具体的llm模型)
    def get_provider(self, provider_type: str = "ollama"):
        provider_config = self.providers.get(provider_type)
        if not provider_config:
            raise ValueError(f"Provider {provider_type} not found")
        
        if provider_type == "ollama":
            return ChatOllama(
                base_url=provider_config.base_url.replace("localhost", "127.0.0.1"),
                model=provider_config.model_name, 
                reasoning=provider_config.think, 
                temperature=provider_config.temperature,
                client_kwargs={"trust_env": False},
            )
        elif provider_type == "website_api":
            return ChatOpenAI(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=provider_config.model_name,
                temperature=provider_config.temperature,
                extra_body={
                    "thinking": {
                        "type": "enabled" if provider_config.think else "disabled"
                    }
                },
            )
        else:
            raise ValueError(f"Provider {provider_type} not supported")


llm_provider = LLMProvider()