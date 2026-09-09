"""知识库入库 worker：从 RabbitMQ 拉任务，现场签发下载 URL，再跑建库。

跟 FastAPI 拆开是因为 uvicorn --reload 会杀掉进程里正在跑的 MinerU。
启动：``uv run python -m app.worker``
"""

import asyncio
import json

import aio_pika

from app.core.config import config
from app.queue.ingest import amqp_url, declare_ingest_topology
from app.service.knowledge_file_service import knowledgeFileService
from app.service.rag_service import RagService
from app.storage.r2 import R2Storage


def get_r2_storage() -> R2Storage:
    return R2Storage(config.r2)


async def handle_ingest_payload(payload: dict) -> str:
    """处理一条入库消息。返回 skip / done / failed，供测试断言、调用方决定 ack。

    已经 done / failed 的行 skip，避免 redeliver 把成功文件再嵌入一遍。
    业务失败（MinerU、向量写入）写 failed 后返回 failed，由调用方 ack，不重入队。
    预签名必须在消费时签发：complete 当时的 GET URL 在队列里一待就会过期。
    """
    file_id = payload["knowledge_file_id"]
    outcome = await knowledgeFileService.begin_processing(file_id)
    if outcome == "skip":
        return "skip"
    try:
        # 现场签发，不信任消息里的任何 URL
        download = get_r2_storage().presign_get(payload["object_key"])
        await RagService.build_knowledge_base(
            download.download_url,
            payload["object_key"],
            payload["filename"],
            payload["user_id"],
            payload["username"],
            payload["size"],
            file_id,
        )
        return "done"
    except Exception as exc:
        print(exc)
        # build_knowledge_base 失败时自己也会 mark_failed；这里再兜一层
        # （例如 presign_get 在调用建库之前就炸了）
        await knowledgeFileService.mark_failed(file_id, "建库失败")
        return "failed"


async def consume_forever() -> None:
    """阻塞消费。prefetch=1：MinerU 很重，一次只啃一个文件。

    ``message.process(requeue=True)``：handle 正常返回（含业务 failed）就 ack；
    解析 JSON / 数据库挂掉之类没接住的异常会 nack 并重入队。
    """
    connection = await aio_pika.connect_robust(amqp_url())
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    _exchange, queue = await declare_ingest_topology(channel)

    async with queue.iterator() as iterator:
        async for message in iterator:
            async with message.process(requeue=True):
                payload = json.loads(message.body.decode("utf-8"))
                await handle_ingest_payload(payload)


def main() -> None:
    asyncio.run(consume_forever())


if __name__ == "__main__":
    main()
