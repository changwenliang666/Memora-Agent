"""ChatHistoryService 单测。用内存 FakeSession，不连真实 MySQL。"""

import asyncio
import re
from datetime import datetime

from app.db.models.conversation import Conversation, Message
from app.service.chat_history_service import ChatHistoryService, title_from_message


class MemoryDb:
    def __init__(self):
        self.conversations: list[Conversation] = []
        self.messages: list[Message] = []
        self.conv_id = 0
        self.msg_id = 0


class FakeResult:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, db: MemoryDb):
        self.db = db
        self.pending: list = []

    async def get(self, model, ident):
        if model is Conversation:
            return next((c for c in self.db.conversations if c.id == ident), None)
        return None

    def add(self, obj) -> None:
        self.pending.append(obj)

    async def commit(self) -> None:
        now = datetime.now()
        for obj in self.pending:
            if isinstance(obj, Conversation):
                if obj.id is None:
                    self.db.conv_id += 1
                    obj.id = self.db.conv_id
                    obj.created_at = obj.created_at or now
                    obj.updated_at = obj.updated_at or now
                    self.db.conversations.append(obj)
            elif isinstance(obj, Message):
                if obj.id is None:
                    self.db.msg_id += 1
                    obj.id = self.db.msg_id
                    obj.created_at = obj.created_at or now
                    self.db.messages.append(obj)
        self.pending.clear()

    async def refresh(self, obj) -> None:
        return None

    def _sql(self, stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()

    def _int(self, sql: str, column: str) -> int | None:
        match = re.search(rf"{column}\s*=\s*(\d+)", sql)
        return int(match.group(1)) if match else None

    def _slice(self, rows: list, sql: str) -> list:
        limit_m = re.search(r"limit\s+(\d+)", sql)
        offset_m = re.search(r"offset\s+(\d+)", sql)
        offset = int(offset_m.group(1)) if offset_m else 0
        if limit_m:
            limit = int(limit_m.group(1))
            return rows[offset : offset + limit]
        return rows[offset:]

    async def scalar(self, stmt):
        sql = self._sql(stmt)
        if "count(" in sql and "conversations" in sql:
            user_id = self._int(sql, "user_id")
            return sum(1 for c in self.db.conversations if user_id is None or c.user_id == user_id)
        if "count(" in sql and "messages" in sql:
            cid = self._int(sql, "conversation_id")
            return sum(1 for m in self.db.messages if cid is None or m.conversation_id == cid)
        if "max(" in sql:
            cid = self._int(sql, "conversation_id")
            seqs = [m.seq for m in self.db.messages if cid is None or m.conversation_id == cid]
            return max(seqs) if seqs else None
        return None

    async def execute(self, stmt):
        sql = self._sql(stmt)
        if "from conversations" in sql:
            user_id = self._int(sql, "user_id")
            rows = [c for c in self.db.conversations if user_id is None or c.user_id == user_id]
            rows = sorted(rows, key=lambda c: (c.updated_at, c.id), reverse=True)
            return FakeResult(self._slice(rows, sql))
        if "from messages" in sql:
            cid = self._int(sql, "conversation_id")
            rows = [m for m in self.db.messages if cid is None or m.conversation_id == cid]
            rows = sorted(rows, key=lambda m: m.seq)
            return FakeResult(self._slice(rows, sql))
        return FakeResult([])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _service(monkeypatch, db: MemoryDb | None = None) -> tuple[ChatHistoryService, MemoryDb]:
    db = db or MemoryDb()
    monkeypatch.setattr(
        "app.service.chat_history_service.AsyncSessionLocal",
        lambda: FakeSession(db),
    )
    return ChatHistoryService(), db


def test_title_from_message_truncates() -> None:
    assert title_from_message("短问") == "短问"
    long_text = "这是一个很长的问题" * 10
    assert len(title_from_message(long_text)) == 40


def test_create_and_append_increments_seq(monkeypatch) -> None:
    service, _db = _service(monkeypatch)

    async def _run():
        conv = await service.create_conversation(1, "员工考核怎么算")
        m1 = await service.append_message(1, conv.id, "user", "员工考核怎么算")
        m2 = await service.append_message(1, conv.id, "assistant", "按制度第3条")
        return conv, m1, m2

    conv, m1, m2 = asyncio.run(_run())
    assert conv.user_id == 1
    assert conv.title == "员工考核怎么算"
    assert m1.seq == 1 and m1.role == "user"
    assert m2.seq == 2 and m2.role == "assistant"
    assert conv.message_count == 2


def test_other_user_cannot_read_or_write(monkeypatch) -> None:
    service, _db = _service(monkeypatch)

    async def _run():
        conv = await service.create_conversation(1, "我的会话")
        await service.append_message(1, conv.id, "user", "秘密")
        stolen = await service.get_for_user(2, conv.id)
        listed = await service.list_messages(2, conv.id, 20, 0)
        written = await service.append_message(2, conv.id, "user", "篡改")
        mine, total = await service.list_for_user(1, 20, 0)
        others, other_total = await service.list_for_user(2, 20, 0)
        return stolen, listed, written, mine, total, others, other_total

    stolen, listed, written, mine, total, others, other_total = asyncio.run(_run())
    assert stolen is None
    assert listed is None
    assert written is None
    assert total == 1 and mine[0].title == "我的会话"
    assert other_total == 0 and others == []


def test_messages_come_back_in_seq_order(monkeypatch) -> None:
    service, _db = _service(monkeypatch)

    async def _run():
        conv = await service.create_conversation(1, "顺序")
        await service.append_message(1, conv.id, "user", "一")
        await service.append_message(1, conv.id, "assistant", "二")
        await service.append_message(1, conv.id, "user", "三")
        return await service.list_messages(1, conv.id, 50, 0)

    rows, total = asyncio.run(_run())
    assert total == 3
    assert [m.content for m in rows] == ["一", "二", "三"]
    assert [m.seq for m in rows] == [1, 2, 3]
