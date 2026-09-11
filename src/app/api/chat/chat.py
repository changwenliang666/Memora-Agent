from pathlib import Path
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage,AIMessage

from app.core.auth import get_current_user
from app.core.config import config
from app.schema.chat import (
    ChatRequest,
    ConversationListData,
    ConversationSummary,
    StoredChatMessage,
    StoredMessageListData,
)
from app.schema.response import ResponseStructure
from app.tools.tools import Tools
from app.agent.agent import Agent
from app.schema.config import AgentConfig
from app.rule.rule import Rule
from app.intent_classify.intent_classify import IntentClassify
from langchain_mineru import MinerULoader
from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from app.service.embedding_service import EmbeddingService
from app.service.qdrant_service import QdrantService
from app.service.chat_history_service import chatHistoryService
from app.service.chat_stream_store import chatStreamStore
from app.service.webhook_service import WebhookService

chat_router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)
conversations_router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, data: dict) -> str:
    """序列化一帧 SSE：event 行 + data 行。"""
    import json

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _history_to_messages(history) -> list:
    """客户端可选 history 还原成 LangChain 消息；只认 user / assistant。"""
    messages = []
    for item in history:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content))
        else:
            messages.append(AIMessage(content=item.content))
    return messages


def _stored_to_messages(rows) -> list:
    """MySQL 历史行还原成 Agent 输入。"""
    messages = []
    for row in rows:
        if row.role == "user":
            messages.append(HumanMessage(content=row.content))
        else:
            messages.append(AIMessage(content=row.content))
    return messages


@chat_router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天：Agent 边生成边以 SSE 推 message.* 事件，事件同时进 Redis 供断线续传。

    有 conversation_id 或两者都空时落 MySQL 历史；只带 history 时保持无状态。
    """
    if request.provider_type is None or request.model_name is None:
        return JSONResponse(
            status_code=400,
            content={"message": "error", "error": "需要提供 provider_type 和 model_name"},
        )

    user = get_current_user()
    persist = False
    conversation_id: int | None = None
    history_messages = _history_to_messages(request.history)

    if request.conversation_id is not None:
        conversation = await chatHistoryService.get_for_user(
            user.id, request.conversation_id
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        stored = await chatHistoryService.all_messages(user.id, conversation.id)
        history_messages = _stored_to_messages(stored or [])
        persist = True
        conversation_id = conversation.id
    elif not request.history:
        conversation = await chatHistoryService.create_conversation(
            user.id, request.message
        )
        persist = True
        conversation_id = conversation.id
        history_messages = []

    if persist:
        await chatHistoryService.append_message(
            user.id, conversation_id, "user", request.message
        )

    try:
        agent = Agent(
            AgentConfig(
                provider_type=request.provider_type,
                model_name=request.model_name,
                tools=Tools().get_all_tools(),
                history_messages=history_messages,
                system_prompt="你是一个ai助手,根据用户的提问，简洁明了的回答用户的问题.",
                human_input_message=request.message,
                stream=True,
                max_round=10,
            )
        )
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"message": "error", "error": str(exc)},
        )

    async def generate():
        message_id = uuid.uuid4().hex
        store = chatStreamStore
        await store.start(message_id, model=request.model_name)
        started = {"message_id": message_id}
        if conversation_id is not None:
            started["conversation_id"] = conversation_id
        yield _sse("message.started", started)

        final_status = "failed"
        final_content_parts: list[str] = []
        try:
            async for event in agent.run_stream():
                if event.event == "message.delta":
                    seq = await store.append(message_id, event.event, event.data)
                    final_content_parts.append(event.data["content"])
                    yield _sse(event.event, {"seq": seq, **event.data})
                else:
                    # 终态不落 Redis 事件流，只写状态 hash；回放时由结尾按 status 补发。
                    yield _sse(event.event, event.data)
                    if event.event == "message.completed":
                        final_status = "completed"
        except Exception:
            final_status = "failed"
            yield _sse("message.failed", {"message": "生成失败"})
        finally:
            full_text = "".join(final_content_parts)
            await store.finish(message_id, final_status, content=full_text)
            if persist and final_status == "completed" and full_text:
                await chatHistoryService.append_message(
                    user.id, conversation_id, "assistant", full_text
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@chat_router.get("/messages/{message_id}")
async def resume_message(message_id: str, from_seq: int = Query(default=0, ge=0)):
    """断线续传：回放 message_id 在 from_seq 之后已缓存的事件。不存在/过期返回 404。"""
    record = await chatStreamStore.read(message_id, from_seq=from_seq)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"message": "error", "error": "消息不存在或已过期"},
        )

    async def generate():
        for frame in record["events"]:
            yield _sse(frame["event"], frame["data"])
        status = record["status"].get("status")
        # 已结束的轮次补发终态；仍在生成的轮次在 TTL 窗口内继续等新事件
        if status == "completed":
            yield _sse("message.completed", {})
        elif status == "failed":
            yield _sse("message.failed", {"message": record["status"].get("content", "")})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@conversations_router.get("/", response_model=ResponseStructure[ConversationListData])
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """当前用户的会话列表，最近更新的在前。"""
    user = get_current_user()
    rows, total = await chatHistoryService.list_for_user(user.id, limit, offset)
    return ResponseStructure[ConversationListData](
        message="查询成功",
        data=ConversationListData(
            items=[
                ConversationSummary(
                    id=row.id,
                    title=row.title,
                    message_count=row.message_count,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            total=total,
        ),
    )


@conversations_router.get(
    "/{conversation_id}/messages",
    response_model=ResponseStructure[StoredMessageListData],
)
async def list_conversation_messages(
    conversation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """当前用户某个会话的消息，按 seq 正序。别人的 id 与不存在都是 404。"""
    user = get_current_user()
    listed = await chatHistoryService.list_messages(
        user.id, conversation_id, limit, offset
    )
    if listed is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    rows, total = listed
    return ResponseStructure[StoredMessageListData](
        message="查询成功",
        data=StoredMessageListData(
            items=[
                StoredChatMessage(
                    id=row.id,
                    role=row.role,
                    content=row.content,
                    seq=row.seq,
                    created_at=row.created_at,
                )
                for row in rows
            ],
            total=total,
        ),
    )


@chat_router.post("/agent")
async def agent(request: ChatRequest):
    try:
        if request.provider_type is None or request.model_name is None:
            return {"message": "error", "error": "需要提供 provider_type 和 model_name"}
        tools = Tools()
        agent = Agent(AgentConfig(
            provider_type=request.provider_type,
            model_name=request.model_name,
            tools=tools.get_all_tools(),
            history_messages=[
                HumanMessage("你好,我叫大伟,我是一个agent工程师"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我喜欢用macbook air电脑来进行开发,真的很舒服,屏幕和键盘,触摸板,反馈都挺好的,续航很强"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我今年26岁，出生在北方的男性,喜欢生活在南方,喜欢吃西瓜,喜欢看电影，喜欢打篮球,我曾经获得过内蒙古自治区乌兰察布市篮球比赛冠军"),
                AIMessage("好的,我记住了,有什么可以帮助您的"),
                HumanMessage("我大伟,就是喜欢写代码，每天至少写2小时，我热爱的语言是python,因为它语法简单,而且社区活跃,而且我是一个agent工程师,所以我会使用python来开发agent"),
                ],

            system_prompt="你是一个ai助手,根据用户的提问，简洁明了的回答用户的问题.",
            human_input_message=request.message,
            stream=False,
            max_round=10,
        ))
        print(agent.build_system_prompt)
        response = await agent.run_loop()
    except Exception as e:
        return {"message": "error", "error": str(e)}
    
    return {"message": "hello world", "agent": response}
@chat_router.post("/rule")
async def rule(request: ChatRequest):
    rule = Rule(request.message)
    return {"message": "hello world", "rule": rule.check_rule_validity(), "hit_category": rule.hit_category, "hit_topic": rule.hit_topic, "hit_intent": rule.hit_intent}

@chat_router.post("/intent")
async def intent(request: ChatRequest):
    intent = await IntentClassify().get_intent(request.message)
    return {"message": "hello world", "intent": intent}
@chat_router.get("/test-mineru")
async def test_mineru():
    mineru_config = config.mineru
    if mineru_config.api_key is None:
        return {
            "message":"mineru api key 不存在"
        }
    loader = MinerULoader(
        source=str(Path(__file__).with_name("公司员工考核制度.pdf")),
        mode="precision", 
        token=mineru_config.api_key
    )
    docs = loader.load()

    text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ])
    sessions:list[Document] = []

    for doc in docs:
        sessions.extend(text_splitter.split_text(doc.page_content))
    for session in sessions:
        session.metadata = {**session.metadata, "source": docs[0].metadata.get("source", "")}
    
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, 
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；",";",". ", " ", ""]
    )
    final_docs:list[Document] = []

    for session in sessions:
        if len(session.page_content) > 500:
            final_docs.extend(recursive_splitter.split_documents([session]))
        else:
            final_docs.append(session)

    embedding = await EmbeddingService().get_batch_embedding(final_docs)
    print(embedding)

    return {
        "message":"hello world"
    }
@chat_router.post("/test-embeddings")
def test_embeddings(request: ChatRequest):
    embedding = EmbeddingService().embed_query(request.message)
    return {
        "message":"hello world",
        "embedding":embedding
    }
@chat_router.post("/test-qdrant")
async def test_qdrant():
    qdrant = QdrantService()
    return {
        "message":"hello world",
        "qdrant":qdrant.client.get_collections()
    }
@chat_router.post("/test-webhook")
async def test_webhook():
    WebhookService.send_knowledge_base_build_success()
    return {
        "message":"hello world"
    }