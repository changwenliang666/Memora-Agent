from qdrant_client import QdrantClient
from memora_agent.core.config import config
from qdrant_client.models import Distance, VectorParams, Filter


class QdrantService:
    def __init__(self,collection_name:str = "knowledge_base",vector_size:int = 1024):
        self.collection_name = collection_name
        self.vector_size = vector_size
        # 关闭 trust_env，避免 httpx 把本地 Qdrant 请求送到系统代理后返回 502。
        self.client = QdrantClient(
            host=config.qdrant.host,
            port=config.qdrant.port,
            trust_env=False,
            check_compatibility=False,
        )
        
    def initQdrant(self):
        try:
            exist = self.client.collection_exists(self.collection_name)
            if not exist:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
            print(f"✅ Qdrant 初始化成功")
        except Exception as e:
            print(e)
    
    def search(self, vector, limit=5):
        return self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
        )

    def upsert(self, points):
        return self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
    def delete(self):
        return self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(),
        )
qdrantService = QdrantService()