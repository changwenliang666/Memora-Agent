from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.auth.auth import auth_router
from app.api.chat.chat import chat_router
from app.api.files.files import files_router
from app.core.auth_middleware import AuthMiddleware
from app.db.database import Base, engine
from app.db.models import KnowledgeFile as _KnowledgeFile  # noqa: F401
from app.db.models import User as _User  # noqa: F401
from app.db.schema import align_knowledge_files_schema
from app.service.qdrant_service import qdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    qdrantService.initQdrant()
    # 清空向量数据库
    # qdrantService.delete()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(align_knowledge_files_schema)
    except Exception as exc:
        print(exc)
    yield


app = FastAPI(
    title="Memora Agent",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(files_router)
