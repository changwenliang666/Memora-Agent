from memora_agent.schema.config import ProviderConfig
from pydantic_settings import BaseSettings, SettingsConfigDict

class LLMProviderConfig(BaseSettings):
    
    ollama_base_url:str
    ollama_model_name:str
    ollama_think:bool = False
    ollama_temperature:float = 0.7

    deepseek_base_url:str
    deepseek_model_name:str
    deepseek_api_key:str
    deepseek_think:bool = False
    deepseek_temperature:float = 0.7

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def providers(self) -> list[ProviderConfig]:
        return [
            ProviderConfig(
                provider_name="ollama",
                base_url=self.ollama_base_url,
                model_name=self.ollama_model_name,
                think=self.ollama_think,
                temperature=self.ollama_temperature
            ),
            ProviderConfig(
                provider_name="deepseek",
                base_url=self.deepseek_base_url,
                api_key=self.deepseek_api_key,
                model_name=self.deepseek_model_name,
                think=self.deepseek_think,
                temperature=self.deepseek_temperature
            ),
        ]

llm_provider_config = LLMProviderConfig()