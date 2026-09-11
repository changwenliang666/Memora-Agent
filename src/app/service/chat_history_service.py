"""会话与消息的 MySQL 读写。按 user_id 隔离，别人的 id 返回 None / 空列表。"""

from datetime import datetime

from sqlalchemy import func, select

from app.db.database import AsyncSessionLocal
from app.db.models.conversation import Conversation, Message

_TITLE_MAX = 40


def title_from_message(text: str) -> str:
    """用首条用户问题生成会话标题，截断到列宽。"""
    stripped = text.strip().replace("\n", " ")
    if len(stripped) <= _TITLE_MAX:
        return stripped or "新对话"
    return stripped[:_TITLE_MAX]


class ChatHistoryService:
    async def create_conversation(self, user_id: int, title: str) -> Conversation:
        async with AsyncSessionLocal() as session:
            row = Conversation(
                user_id=user_id,
                title=title_from_message(title),
                message_count=0,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_for_user(
        self, user_id: int, conversation_id: int
    ) -> Conversation | None:
        async with AsyncSessionLocal() as session:
            row = await session.get(Conversation, conversation_id)
            if row is None or row.user_id != user_id:
                return None
            return row

    async def list_for_user(
        self, user_id: int, limit: int, offset: int
    ) -> tuple[list[Conversation], int]:
        async with AsyncSessionLocal() as session:
            owner = Conversation.user_id == user_id
            total = await session.scalar(
                select(func.count()).select_from(Conversation).where(owner)
            )
            result = await session.execute(
                select(Conversation)
                .where(owner)
                .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), int(total or 0)

    async def append_message(
        self,
        user_id: int,
        conversation_id: int,
        role: str,
        content: str,
    ) -> Message | None:
        """在会话末尾追加一条消息。非本人或不存在返回 None。"""
        async with AsyncSessionLocal() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.user_id != user_id:
                return None
            max_seq = await session.scalar(
                select(func.max(Message.seq)).where(
                    Message.conversation_id == conversation_id
                )
            )
            seq = int(max_seq or 0) + 1
            now = datetime.now()
            row = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                seq=seq,
                created_at=now,
            )
            session.add(row)
            conv.message_count = int(conv.message_count or 0) + 1
            conv.updated_at = now
            await session.commit()
            await session.refresh(row)
            return row

    async def list_messages(
        self,
        user_id: int,
        conversation_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[Message], int] | None:
        """按 seq 正序分页。非本人会话返回 None，接口层变 404。"""
        async with AsyncSessionLocal() as session:
            conv = await session.get(Conversation, conversation_id)
            if conv is None or conv.user_id != user_id:
                return None
            total = await session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
            )
            result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.seq.asc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), int(total or 0)

    async def all_messages(
        self, user_id: int, conversation_id: int
    ) -> list[Message] | None:
        """整段会话消息，供 Agent 构造历史。非本人返回 None。"""
        listed = await self.list_messages(
            user_id, conversation_id, limit=10_000, offset=0
        )
        if listed is None:
            return None
        rows, _total = listed
        return rows


chatHistoryService = ChatHistoryService()
