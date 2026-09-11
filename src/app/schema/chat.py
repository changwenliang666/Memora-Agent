from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    """客户端可传入的一轮历史消息。role 只允许 user / assistant。"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    provider_type: str | None = None
    model_name: str | None = Field(default=None, min_length=1)
    history: list[ChatHistoryMessage] = Field(default_factory=list)
    conversation_id: int | None = Field(default=None, ge=1)


# --- SSE 事件载荷 ---
# 事件名走 SSE 的 event 字段；这里是各事件的 data 形状。

class MessageStartedEvent(BaseModel):
    """流式一轮开始。message_id 供 Redis 续传；conversation_id 在落库时给出。"""

    message_id: str
    conversation_id: int | None = None


class MessageDeltaEvent(BaseModel):
    """一个文本增量。seq 单调递增，供断线 from_seq 续传。"""

    seq: int
    content: str


class MessageCompletedEvent(BaseModel):
    """一轮正常结束。"""


class MessageFailedEvent(BaseModel):
    """一轮失败。message 是给前端的可读文案。"""

    message: str


class ConversationSummary(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListData(BaseModel):
    items: list[ConversationSummary]
    total: int


class StoredChatMessage(BaseModel):
    id: int
    role: str
    content: str
    seq: int
    created_at: datetime


class StoredMessageListData(BaseModel):
    items: list[StoredChatMessage]
    total: int
