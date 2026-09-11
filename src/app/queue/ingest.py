"""入库队列的拓扑与发布。

消息只带稳定字段（文件 id、object_key），不带会过期的预签名 GET。
worker 消费时再现场签发下载地址。exchange / queue 都 durable，broker 重启不丢。
"""

import json
from urllib.parse import quote_plus

import aio_pika
from aio_pika import DeliveryMode, ExchangeType

from app.core.config import config

INGEST_EXCHANGE = "memora.knowledge"
INGEST_QUEUE = "memora.knowledge.ingest"
INGEST_ROUTING_KEY = "ingest"


def amqp_url() -> str:
    """从运行时配置拼 AMQP URL。账号密码做 URL 编码，避免特殊字符拆坏连接串。"""
    user = quote_plus(config.rabbitmq.user)
    password = quote_plus(config.rabbitmq.password or "")
    return (
        f"amqp://{user}:{password}"
        f"@{config.rabbitmq.host}:{config.rabbitmq.port}/"
    )


def build_ingest_payload(
    knowledge_file_id: int,
    object_key: str,
    filename: str,
    user_id: int,
    username: str,
    size: int,
) -> dict:
    """组一条入库消息。username 必须显式带上：worker 不在 HTTP 请求里，ContextVar 是空的。"""
    return {
        "knowledge_file_id": knowledge_file_id,
        "object_key": object_key,
        "filename": filename,
        "user_id": user_id,
        "username": username,
        "size": size,
    }


def encode_ingest_message(payload: dict) -> aio_pika.Message:
    """持久化投递，broker 落盘后再确认，进程崩溃也不该丢这条。"""
    return aio_pika.Message(
        body=json.dumps(payload).encode("utf-8"),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )


async def publish_to_exchange(exchange, payload: dict) -> None:
    """真正 publish。抽出来是为了单测可以塞假 exchange，不断 broker。"""
    await exchange.publish(
        encode_ingest_message(payload),
        routing_key=INGEST_ROUTING_KEY,
    )


async def declare_ingest_topology(channel: aio_pika.abc.AbstractChannel):
    """声明交换机、队列并绑定。发布端和消费端都走这里，避免一边没 declare 就发。"""
    exchange = await channel.declare_exchange(
        INGEST_EXCHANGE,
        ExchangeType.DIRECT,
        durable=True,
    )
    queue = await channel.declare_queue(
        INGEST_QUEUE,
        durable=True,
    )
    await queue.bind(exchange, INGEST_ROUTING_KEY)
    return exchange, queue


async def publish_ingest(payload: dict) -> None:
    """complete 用的短连接发布：连上、声明拓扑、发一条、关掉。

    入库不是热点路径，懒得在 FastAPI lifespan 里养长连接。
    """
    connection = await aio_pika.connect_robust(amqp_url())
    try:
        channel = await connection.channel()
        exchange, _queue = await declare_ingest_topology(channel)
        await publish_to_exchange(exchange, payload)
    finally:
        await connection.close()