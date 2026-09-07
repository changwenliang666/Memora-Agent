from langchain_core.documents import Document
from langchain_mineru import MinerULoader
from langchain_text_splitters import (MarkdownHeaderTextSplitter,RecursiveCharacterTextSplitter)
from memora_agent.core.config import config

class RagService:
    def __init__(self):
        pass
    # 离线建库方法
    @staticmethod
    def build_knowledge_base(file_url:str,object_key:str,filename:str):
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
        print("处理后的文档",final_docs)
