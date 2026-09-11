"""会话历史 HTTP 接口。用假 Agent / 假 store / 假 history，不打真实 LLM、Redis、MySQL。"""

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
    """内存会话库，按 user_id 隔离。"""

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


def _patch_history(monkeypatch, history: FakeHistory | None = None) -> FakeHistory:
    history = history or FakeHistory()
    monkeypatch.setattr(chat_module, "chatHistoryService", history)
    return history


def _patch_agent(monkeypatch, events, captured: list | None = None):
    class FakeAgent:
        def __init__(self, config):
            self.config = config
            if captured is not None:
                captured.append(config)

        async def run_stream(self):
            for event in events:
                yield event

    monkeypatch.setattr(chat_module, "Agent", FakeAgent)


def _parse_sse(body: str):
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


_STREAM_BODY = {
    "message": "员工考核怎么算",
    "provider_type": "qwen",
    "model_name": "qwen3.8-max",
}


def test_conversations_require_token() -> None:
    client = TestClient(app)
    assert client.get("/conversations").status_code == 401
    assert client.get("/conversations/1/messages").status_code == 401


def test_list_conversations_only_own(monkeypatch) -> None:
    history = _patch_history(monkeypatch)

    async def seed():
        mine = await history.create_conversation(1, "我的会话")
        await history.append_message(1, mine.id, "user", "你好")
        other = await history.create_conversation(2, "别人的")
        await history.append_message(2, other.id, "user", "秘密")

    import anyio

    anyio.run(seed)

    client = TestClient(app)
    response = client.get("/conversations", headers=bearer_headers(1))
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "查询成功"
    assert body["data"]["total"] == 1
    assert [item["title"] for item in body["data"]["items"]] == ["我的会话"]

    other = client.get("/conversations", headers=bearer_headers(2, "other"))
    assert other.json()["data"]["total"] == 1
    assert other.json()["data"]["items"][0]["title"] == "别人的"


def test_list_messages_in_seq_order(monkeypatch) -> None:
    history = _patch_history(monkeypatch)

    async def seed():
        conv = await history.create_conversation(1, "顺序")
        await history.append_message(1, conv.id, "user", "一")
        await history.append_message(1, conv.id, "assistant", "二")
        await history.append_message(1, conv.id, "user", "三")
        return conv.id

    import anyio

    cid = anyio.run(seed)
    client = TestClient(app)
    response = client.get(
        f"/conversations/{cid}/messages",
        headers=bearer_headers(),
    )
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [item["content"] for item in items] == ["一", "二", "三"]
    assert [item["seq"] for item in items] == [1, 2, 3]


def test_list_messages_paginates(monkeypatch) -> None:
    history = _patch_history(monkeypatch)

    async def seed():
        conv = await history.create_conversation(1, "分页")
        for text in ("一", "二", "三"):
            await history.append_message(1, conv.id, "user", text)
        return conv.id

    import anyio

    cid = anyio.run(seed)
    client = TestClient(app)
    response = client.get(
        f"/conversations/{cid}/messages?limit=1&offset=1",
        headers=bearer_headers(),
    )
    body = response.json()["data"]
    assert body["total"] == 3
    assert [item["content"] for item in body["items"]] == ["二"]


def test_other_users_messages_are_404(monkeypatch) -> None:
    history = _patch_history(monkeypatch)

    async def seed():
        conv = await history.create_conversation(2, "别人的")
        await history.append_message(2, conv.id, "user", "秘密")
        return conv.id

    import anyio

    cid = anyio.run(seed)
    client = TestClient(app)
    response = client.get(
        f"/conversations/{cid}/messages",
        headers=bearer_headers(1),
    )
    assert response.status_code == 404


def test_stream_creates_conversation_when_id_omitted(monkeypatch) -> None:
    _patch_store(monkeypatch)
    history = _patch_history(monkeypatch)
    _patch_agent(
        monkeypatch,
        [
            StreamEvent("message.delta", {"content": "按制度"}),
            StreamEvent("message.completed", {}),
        ],
    )
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json=_STREAM_BODY,
        headers=bearer_headers(),
    )
    frames = _parse_sse(response.text)
    started = frames[0][1]
    assert frames[0][0] == "message.started"
    assert "message_id" in started
    assert started["conversation_id"] == 1

    conv = history.conversations[1]
    assert conv.user_id == 1
    assert conv.title == "员工考核怎么算"
    contents = [(m.role, m.content) for m in history.messages[1]]
    assert contents == [("user", "员工考核怎么算"), ("assistant", "按制度")]


def test_stream_failed_does_not_store_assistant(monkeypatch) -> None:
    _patch_store(monkeypatch)
    history = _patch_history(monkeypatch)
    _patch_agent(
        monkeypatch,
        [
            StreamEvent("message.delta", {"content": "半截"}),
            StreamEvent("message.failed", {"message": "生成失败"}),
        ],
    )
    client = TestClient(app)
    client.post("/chat/stream", json=_STREAM_BODY, headers=bearer_headers())
    contents = [(m.role, m.content) for m in history.messages[1]]
    assert contents == [("user", "员工考核怎么算")]


def test_stream_with_history_stays_stateless(monkeypatch) -> None:
    _patch_store(monkeypatch)
    history = _patch_history(monkeypatch)
    captured: list = []
    _patch_agent(
        monkeypatch,
        [
            StreamEvent("message.delta", {"content": "好"}),
            StreamEvent("message.completed", {}),
        ],
        captured=captured,
    )
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={
            **_STREAM_BODY,
            "history": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好，有什么可以帮你"},
            ],
        },
        headers=bearer_headers(),
    )
    started = _parse_sse(response.text)[0][1]
    assert "conversation_id" not in started
    assert history.conversations == {}
    assert captured[0].history_messages[0].content == "你好"


def test_stream_uses_stored_history_and_ignores_body_history(monkeypatch) -> None:
    _patch_store(monkeypatch)
    history = _patch_history(monkeypatch)
    captured: list = []

    async def seed():
        conv = await history.create_conversation(1, "旧会话")
        await history.append_message(1, conv.id, "user", "库里的用户")
        await history.append_message(1, conv.id, "assistant", "库里的助手")
        return conv.id

    import anyio

    cid = anyio.run(seed)
    _patch_agent(
        monkeypatch,
        [
            StreamEvent("message.delta", {"content": "接着说"}),
            StreamEvent("message.completed", {}),
        ],
        captured=captured,
    )
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={
            **_STREAM_BODY,
            "conversation_id": cid,
            "history": [{"role": "user", "content": "客户端伪造的历史"}],
        },
        headers=bearer_headers(),
    )
    started = _parse_sse(response.text)[0][1]
    assert started["conversation_id"] == cid
    assert [m.content for m in captured[0].history_messages] == [
        "库里的用户",
        "库里的助手",
    ]
    roles = [m.role for m in history.messages[cid]]
    assert roles == ["user", "assistant", "user", "assistant"]


def test_stream_rejects_other_users_conversation(monkeypatch) -> None:
    _patch_store(monkeypatch)
    history = _patch_history(monkeypatch)

    async def seed():
        conv = await history.create_conversation(2, "别人的")
        return conv.id

    import anyio

    cid = anyio.run(seed)
    _patch_agent(monkeypatch, [StreamEvent("message.completed", {})])
    client = TestClient(app)
    response = client.post(
        "/chat/stream",
        json={**_STREAM_BODY, "conversation_id": cid},
        headers=bearer_headers(1),
    )
    assert response.status_code == 404
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert history.messages[cid] == []
