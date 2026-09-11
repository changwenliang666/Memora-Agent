"""流式聊天 HTTP 接口测试。用假 Agent / 假 store / 假 history，不打真实 LLM、Redis、MySQL。"""

from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.chat.chat as chat_module
from app.agent.agent import StreamEvent
from app.core.auth import create_access_token
from app.main import app
from app.service.chat_history_service import title_from_message


def bearer_headers(user_id: int = 1, username: str = "tester") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, username)}"}


class FakeStore:
    """内存版事件缓存，记录 append 并支撑 read。"""

    def __init__(self):
        self.events: dict[str, list] = {}
        self.status: dict[str, dict] = {}

    async def start(self, message_id, model):
        self.status[message_id] = {"status": "streaming", "model": model}
        self.events[message_id] = []

    async def append(self, message_id, event, data):
        self.events.setdefault(message_id, []).append({"event": event, "data": data})
        return len(self.events[message_id])

    async def finish(self, message_id, status, content=""):
        self.status[message_id]["status"] = status
        self.status[message_id]["content"] = content

    async def read(self, message_id, from_seq=0):
        if message_id not in self.events:
            return None
        return {
            "status": self.status.get(message_id, {}),
            "events": self.events[message_id][from_seq:],
            "from_seq": from_seq,
        }


class FakeHistory:
    """内存会话库，避免默认空 history 的流式请求打到真实 MySQL。"""

    def __init__(self):
        self.next_id = 1
        self.next_msg_id = 1
        self.conversations: dict[int, SimpleNamespace] = {}
        self.messages: dict[int, list] = {}

    async def create_conversation(self, user_id, title):
        cid = self.next_id
        self.next_id += 1
        now = datetime.now()
        row = SimpleNamespace(
            id=cid,
            user_id=user_id,
            title=title_from_message(title),
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        self.conversations[cid] = row
        self.messages[cid] = []
        return row

    async def get_for_user(self, user_id, conversation_id):
        row = self.conversations.get(conversation_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    async def append_message(self, user_id, conversation_id, role, content):
        conv = await self.get_for_user(user_id, conversation_id)
        if conv is None:
            return None
        seq = len(self.messages[conversation_id]) + 1
        now = datetime.now()
        row = SimpleNamespace(
            id=self.next_msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            seq=seq,
            created_at=now,
        )
        self.next_msg_id += 1
        self.messages[conversation_id].append(row)
        conv.message_count = len(self.messages[conversation_id])
        conv.updated_at = now
        return row

    async def list_for_user(self, user_id, limit, offset):
        rows = [c for c in self.conversations.values() if c.user_id == user_id]
        rows.sort(key=lambda c: (c.updated_at, c.id), reverse=True)
        return rows[offset : offset + limit], len(rows)

    async def list_messages(self, user_id, conversation_id, limit, offset):
        conv = await self.get_for_user(user_id, conversation_id)
        if conv is None:
            return None
        rows = self.messages[conversation_id]
        return rows[offset : offset + limit], len(rows)

    async def all_messages(self, user_id, conversation_id):
        listed = await self.list_messages(user_id, conversation_id, 10_000, 0)
        if listed is None:
            return None
        rows, _total = listed
        return rows


def _patch_store(monkeypatch) -> FakeStore:
    store = FakeStore()
    monkeypatch.setattr(chat_module, "chatStreamStore", store)
    return store


def _patch_history(monkeypatch) -> FakeHistory:
    history = FakeHistory()
    monkeypatch.setattr(chat_module, "chatHistoryService", history)
    return history


def _patch_agent(monkeypatch, events):
    """让 Agent 产出固定事件序列。"""

    class FakeAgent:
        def __init__(self, config):
            self.config = config

        async def run_stream(self):
            for event in events:
                yield event

    monkeypatch.setattr(chat_module, "Agent", FakeAgent)


def _parse_sse(body: str):
    """把 SSE 文本解析成 (event, data_json) 列表。"""
    import json

    frames = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        frames.append((event, data))
    return frames


def test_stream_requires_token() -> None:
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"message": "你好", "provider_type": "qwen", "model_name": "qwen3.8-max"},
    )
    assert response.status_code == 401


def test_stream_rejects_missing_model(monkeypatch) -> None:
    _patch_store(monkeypatch)
    _patch_history(monkeypatch)
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"message": "你好"},
        headers=bearer_headers(),
    )
    assert response.status_code == 400
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_stream_emits_started_delta_completed(monkeypatch) -> None:
    _patch_store(monkeypatch)
    _patch_history(monkeypatch)
    _patch_agent(monkeypatch, [
        StreamEvent("message.delta", {"content": "根据"}),
        StreamEvent("message.delta", {"content": "制度"}),
        StreamEvent("message.completed", {}),
    ])
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"message": "你好", "provider_type": "qwen", "model_name": "qwen3.8-max"},
        headers=bearer_headers(),
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"

    frames = _parse_sse(response.text)
    events = [e for e, _ in frames]
    assert events[0] == "message.started"
    assert events[-1] == "message.completed"
    assert "message_id" in frames[0][1]
    assert frames[0][1]["conversation_id"] == 1

    deltas = [d for e, d in frames if e == "message.delta"]
    assert [d["content"] for d in deltas] == ["根据", "制度"]
    assert [d["seq"] for d in deltas] == [1, 2]


def test_stream_error_after_start_sends_failed(monkeypatch) -> None:
    _patch_store(monkeypatch)
    _patch_history(monkeypatch)
    _patch_agent(monkeypatch, [
        StreamEvent("message.delta", {"content": "半截"}),
        StreamEvent("message.failed", {"message": "生成失败"}),
    ])
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={"message": "你好", "provider_type": "qwen", "model_name": "qwen3.8-max"},
        headers=bearer_headers(),
    )
    frames = _parse_sse(response.text)
    events = [e for e, _ in frames]
    assert "message.failed" in events
    assert "message.completed" not in events


def test_resume_unknown_message_404(monkeypatch) -> None:
    _patch_store(monkeypatch)
    client = TestClient(app)
    response = client.get(
        "/chat/messages/nope",
        headers=bearer_headers(),
    )
    assert response.status_code == 404
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_resume_replays_after_from_seq(monkeypatch) -> None:
    store = _patch_store(monkeypatch)
    # 预置一轮已完成的消息
    import anyio

    async def seed():
        await store.start("m1", model="m")
        await store.append("m1", "message.delta", {"seq": 1, "content": "根"})
        await store.append("m1", "message.delta", {"seq": 2, "content": "据"})
        await store.append("m1", "message.delta", {"seq": 3, "content": "制"})
        await store.finish("m1", "completed", content="根据制")

    anyio.run(seed)

    client = TestClient(app)
    response = client.get(
        "/chat/messages/m1?from_seq=1",
        headers=bearer_headers(),
    )
    assert response.status_code == 200
    frames = _parse_sse(response.text)
    deltas = [d for e, d in frames if e == "message.delta"]
    assert [d["content"] for d in deltas] == ["据", "制"]
    assert frames[-1][0] == "message.completed"


def test_resume_without_token_rejected(monkeypatch) -> None:
    _patch_store(monkeypatch)
    client = TestClient(app)
    response = client.get("/chat/messages/m1")
    assert response.status_code == 401
