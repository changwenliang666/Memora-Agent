from memora_agent.core.provider import LLMProvider
from langchain_core.documents import Document


class EmbeddingService:
    def __init__(self):
        self.provider = LLMProvider()
        self.embeddings = self.provider.get_embeddings(
            "ollama", "mxbai-embed-large:latest"
        )

    def embed_query(self, text: str):
        return self.embeddings.embed_query(text)
    # 批量获取embedding
    async def get_batch_embedding(self, documents: list[Document]):
        return await self.embeddings.aembed_documents([document.page_content for document in documents])
