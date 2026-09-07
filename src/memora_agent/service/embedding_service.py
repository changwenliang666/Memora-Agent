from memora_agent.core.provider import LLMProvider


class EmbeddingService:
    def __init__(self):
        self.provider = LLMProvider()
        self.embeddings = self.provider.get_embeddings(
            "ollama", "mxbai-embed-large:latest"
        )

    def embed_query(self, text: str):
        return self.embeddings.embed_query(text)
