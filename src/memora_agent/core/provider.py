from memora_agent.core.config import llm_provider_config
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

class LLMProvider:
    def __init__(self,model_name: str = "ollama"):
        self.providers = {
            provider.provider_name: provider for provider in llm_provider_config.providers
        }
        self.current_model = self.get_provider(model_name)
    
    def get_provider(self, provider_name: str = "ollama"):
        provider_config = self.providers.get(provider_name)
        if not provider_config:
            raise ValueError(f"Provider {provider_name} not found")
        
        if provider_name == "ollama":
            return ChatOllama(
                base_url=provider_config.base_url.replace("localhost", "127.0.0.1"),
                model=provider_config.model_name, 
                reasoning=provider_config.think, 
                temperature=provider_config.temperature,
                client_kwargs={"trust_env": False},
            )
        elif provider_name == "deepseek":
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
            raise ValueError(f"Provider {provider_name} not supported")

llm_provider = LLMProvider()