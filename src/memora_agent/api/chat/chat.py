import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from memora_agent.core.provider import llm_provider
from memora_agent.schema.chat import ChatRequest

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@chat_router.post("/stream")
async def chat(request: ChatRequest):
    # provider = llm_provider.get_provider()
    # model_response_parts: list[str] = []

    # async def generate() -> AsyncIterator[str]:
    #     try:
    #         async for chunk in provider.astream(
    #             [HumanMessage(content=request.message)]
    #         ):
    #             if chunk.content:
    #                 content = str(chunk.content)
    #                 model_response_parts.append(content)
    #                 yield f"data: {json.dumps({'message': chunk.content}, ensure_ascii=False)}\n\n"
    #     except Exception as e:
    #         yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    #         return
    #     model_response_content = "".join(model_response_parts)
    #     print(model_response_content)
    #     yield "data: [DONE]\n\n"

    # return StreamingResponse(
    #     generate(),
    #     media_type="text/event-stream",
    #     headers={
    #         "Cache-Control": "no-cache",
    #         "X-Accel-Buffering": "no",
    #     },
    # )
