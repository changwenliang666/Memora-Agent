"""流式聊天的在生成事件缓存（Redis）。

职责：把某一轮（message_id）正在生成的 SSE 事件短暂存下，供断线重连按
``from_seq`` 回放。这是带 TTL 的「可续传缓冲」，不是会话历史——历史在 MySQL，
由 add-chat-history 负责。Redis 重启或 key 过期即不可恢复，客户端重新提问。

两个 key：
- ``chat:msg:{id}``        HASH   status / created_at / model / content
- ``chat:msg:{id}:events``  LIST   每帧 JSON，``seq`` 用列表长度当序号
"""

import json
from datetime import datetime

import redis.asyncio as aioredis

from app.core.config import config

# 在生成缓冲的存活时间。覆盖一次正常生成 + 前端断线重连的窗口即可。
DEFAULT_TTL_SECONDS = 600

_STATUS_KEY = "chat:msg:{id}"
_EVENTS_KEY = "chat:msg:{id}:events"


def _status_key(message_id: str) -> str:
    return _STATUS_KEY.format(id=message_id)


def _events_key(message_id: str) -> str:
    return _EVENTS_KEY.format(id=message_id)


class ChatStreamStore:
    """按 message_id 存取一轮流式事件。只认 Redis，不知道 HTTP 和 Agent。"""

    def __init__(self, client=None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._client = client
        self.ttl_seconds = ttl_seconds

    async def client(self):
        """懒加载 async Redis 客户端；测试可注入假客户端替代。"""
        if self._client is None:
            self._client = aioredis.Redis(
                host=config.redis.host,
                port=config.redis.port,
                password=config.redis.password or None,
                decode_responses=True,
            )
        return self._client

    async def start(self, message_id: str, model: str) -> None:
        """一轮开始：写入 streaming 状态与创建时间。"""
        client = await self.client()
        await client.hset(
            _status_key(message_id),
            mapping={
                "status": "streaming",
                "created_at": datetime.now().isoformat(),
                "model": model,
            },
        )

    async def append(self, message_id: str, event: str, data: dict) -> int:
        """追加一帧，返回它的 seq（列表长度即序号，天然单调）。"""
        client = await self.client()
        frame = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        await client.rpush(_events_key(message_id), frame)
        return await client.llen(_events_key(message_id))

    async def finish(self, message_id: str, status: str, content: str = "") -> None:
        """终态：写 status / content，并给两个 key 兜 TTL。"""
        client = await self.client()
        await client.hset(
            _status_key(message_id),
            mapping={"status": status, "content": content},
        )
        await client.expire(_status_key(message_id), self.ttl_seconds)
        await client.expire(_events_key(message_id), self.ttl_seconds)

    async def read(self, message_id: str, from_seq: int = 0) -> dict | None:
        """读回一轮：状态 + from_seq 之后的事件。完全没记录返回 None。

        from_seq 是「已收到的最大 seq」，回放任一 seq > from_seq 的帧。
        判断存在与否看事件列表，而不是状态 hash——只 append 未 start 的轮次
        也应能回放，不该被误判成不存在。
        """
        client = await self.client()
        raw = await client.lrange(_events_key(message_id), from_seq, -1)
        status = await client.hgetall(_status_key(message_id))
        if not raw and not status:
            return None
        events = [json.loads(frame) for frame in raw]
        return {"status": status, "events": events, "from_seq": from_seq}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


chatStreamStore = ChatStreamStore()
