from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from memora_agent.api.chat.chat import chat_router
from memora_agent.api.files.files import files_router
from memora_agent.service.qdrant_service import qdrantService

@asynccontextmanager
async def lifespan(app: FastAPI):
    qdrantService.initQdrant()
    yield

app = FastAPI(
    title="Memora Agent",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(chat_router)
app.include_router(files_router)