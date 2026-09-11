"""ChatStreamStore 的单测，用内存假 Redis 验证行为，不连真实服务。"""

import json

import pytest

from app.service.chat_stream_store import ChatStreamStore


class FakeRedis:
    """最小可用的内存版 async Redis，只实现 store 用到的命令。"""

    def __init__(self):
        self.hashes: dict[str, dict] = {}
        self.lists: dict[str, list] = {}
        self.ttls: dict[str, int] = {}

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def hgetall(self, key):
        return self.hashes.get(key, {})

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        end = None if end == -1 else end + 1
        return items[start:end]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl

    async def aclose(self):
        pass


@pytest.fixture
def store() -> ChatStreamStore:
    return ChatStreamStore(client=FakeRedis(), ttl_seconds=600)


@pytest.mark.asyncio
async def test_start_then_finish_records_status(store):
    await store.start("m1", model="qwen3.8-max")
    await store.finish("m1", "completed", content="完整回复")

    result = await store.read("m1")
    assert result is not None
    assert result["status"]["status"] == "completed"
    assert result["status"]["content"] == "完整回复"
    assert result["status"]["model"] == "qwen3.8-max"


@pytest.mark.asyncio
async def test_append_returns_increasing_seq(store):
    s1 = await store.append("m1", "message.delta", {"content": "根"})
    s2 = await store.append("m1", "message.delta", {"content": "据"})
    s3 = await store.append("m1", "message.delta", {"content": "制度"})

    assert (s1, s2, s3) == (1, 2, 3)


@pytest.mark.asyncio
async def test_read_replays_events_after_from_seq(store):
    for text in ["根", "据", "制", "度"]:
        await store.append("m1", "message.delta", {"content": text})

    result = await store.read("m1", from_seq=2)
    contents = [e["data"]["content"] for e in result["events"]]
    assert contents == ["制", "度"]


@pytest.mark.asyncio
async def test_events_keep_event_name_and_data(store):
    await store.append("m1", "message.delta", {"seq": 1, "content": "根"})

    result = await store.read("m1")
    frame = result["events"][0]
    assert frame["event"] == "message.delta"
    assert frame["data"] == {"seq": 1, "content": "根"}


@pytest.mark.asyncio
async def test_finish_sets_ttl_on_both_keys(store):
    await store.start("m1", model="m")
    await store.append("m1", "message.delta", {"content": "x"})
    await store.finish("m1", "completed")

    fake = store._client
    assert fake.ttls["chat:msg:m1"] == 600
    assert fake.ttls["chat:msg:m1:events"] == 600


@pytest.mark.asyncio
async def test_unknown_message_returns_none(store):
    assert await store.read("nope") is None
