from fastapi import FastAPI
from memora_agent.api.chat.chat import chat_router

app = FastAPI(
    title="Memora Agent",
    version="0.1.0",
)

app.include_router(chat_router)