from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from memora_agent.api.auth.auth import auth_router
from memora_agent.api.chat.chat import chat_router
from memora_agent.api.files.files import files_router
from memora_agent.core.auth_middleware import AuthMiddleware
from memora_agent.db.database import Base, engine
from memora_agent.db.models import User as _User  # noqa: F401
from memora_agent.service.qdrant_service import qdrantService


@asynccontextmanager
async def lifespan(app: FastAPI):
    qdrantService.initQdrant()
    # 清空向量数据库
    # qdrantService.delete()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
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
