from langchain_core.documents import Document
from langchain_mineru import MinerULoader
from langchain_text_splitters import (MarkdownHeaderTextSplitter,RecursiveCharacterTextSplitter)
from memora_agent.core.config import config
from memora_agent.service.embedding_service import EmbeddingService
from memora_agent.service.qdrant_service import qdrantService
from qdrant_client.models import PointStruct, UpdateStatus
import uuid
from memora_agent.service.webhook_service import WebhookService

class RagService:
    def __init__(self):
        pass
    def build_points_data(documents:list[Document],embedding:list[float]) -> list[PointStruct]:
        points = []
        for document,embedding in zip(documents,embedding):
            points.append(PointStruct(
                id=uuid.uuid4(),
                vector=embedding,
                payload= {**document.metadata, "content": document.page_content}
            ))
        return points
    # 离线建库方法
    @staticmethod
    async def build_knowledge_base(file_url:str,object_key:str,filename:str):
        try:
            mineru_config = config.mineru
            sessions:list[Document] = []
            final_docs:list[Document] = []

            if mineru_config.api_key is None:
                return {
                    "message":"mineru api key 不存在"
                }

            loader = MinerULoader(
                source=file_url,
                mode="precision", 
                token=mineru_config.api_key
            )

            docs = loader.load()
            
            text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ])

            for doc in docs:
                sessions.extend(text_splitter.split_text(doc.page_content))
            for session in sessions:
                session.metadata = {"source": object_key,"filename":filename}

            recursive_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500, 
                chunk_overlap=50,
                separators=["\n\n", "\n", "。", "；",";",". ", " ", ""]
            )

            for session in sessions:
                if len(session.page_content) > 500:
                    final_docs.extend(recursive_splitter.split_documents([session]))
                else:
                    final_docs.append(session)

            if len(final_docs) > 0:
                # 生成向量数据
                embedding = await EmbeddingService().get_batch_embedding(final_docs)
                # 构建点数据
                points = RagService.build_points_data(final_docs,embedding)
                # 插入 Qdrant 数据
                update_status = qdrantService.upsert(points)
                if update_status.status == UpdateStatus.COMPLETED:
                    print("✅ 文档建库成功")
                    WebhookService.send_knowledge_base_build_success(filename)
                else:
                    raise Exception("建库失败")
               
        except Exception as e:
            print(e)
            raise Exception("建库失败")
           

       