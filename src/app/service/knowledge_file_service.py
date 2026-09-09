"""知识文件行的状态机与查询。

complete 时插入 pending 行，worker 再把同一行推进 processing / done / failed。
状态迁移的纯函数（``apply_*``）和 IO（查库、提交）分开，方便单测不碰 MySQL。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from app.db.database import AsyncSessionLocal
from app.db.models.knowledge_file import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    TERMINAL_STATUSES,
    KnowledgeFile,
)


def _ocr_payload(ocr_results: list[Any]) -> list[dict]:
    """把 OCR 结果收成可落 JSON 的 dict 列表。

    建库路径传 ``ImageOcrItem``，测试或重入可能已经是 dict，两种都认。
    """
    payload: list[dict] = []
    for item in ocr_results:
        if isinstance(item, dict):
            payload.append(item)
        else:
            payload.append({"image_key": item.image_key, "text": item.text})
    return payload


def _elapsed_ms(start: datetime, end: datetime) -> int:
    """两时刻之差，毫秒；时钟回拨时按 0 而不是负数。"""
    return max(0, int((end - start).total_seconds() * 1000))


class KnowledgeFileService:
    """KnowledgeFile 的写入与按用户查询。

    ``apply_*`` 只改内存对象；``begin_processing`` / ``mark_done`` / ``mark_failed``
    负责读行、调用 apply、提交。终态消息 redeliver 时 ``apply_processing`` 返回 skip，
    worker 直接 ack，避免把已成功的文件再跑一遍 MinerU。
    """

    @staticmethod
    def apply_processing(row: KnowledgeFile, now: datetime) -> str:
        """把行推进 processing。返回 ``run`` 或 ``skip``。

        首次从 pending 进入时写 ``started_at`` 和 ``queue_wait_ms``。
        已是 processing 的 redeliver 不改这两个字段，否则排队耗时会被重算。
        已经 done / failed 的行直接 skip。
        """
        if row.status in TERMINAL_STATUSES:
            return "skip"
        if row.status == STATUS_PENDING:
            row.status = STATUS_PROCESSING
            row.started_at = now
            row.queue_wait_ms = _elapsed_ms(row.created_at, now)
        return "run"

    @staticmethod
    def apply_done(
        row: KnowledgeFile,
        now: datetime,
        *,
        image_keys: list[str],
        markdown: str | None,
        plain_text: str | None,
        ocr_results: list[Any],
    ) -> None:
        """标 done，回填正文，并按 started_at 计算处理耗时。

        入队失败会在还没 started_at 时就标 failed，那种情况不写 duration_ms。
        成功路径一定经过 processing，started_at 有值。
        """
        row.status = STATUS_DONE
        row.error_message = None
        row.finished_at = now
        if row.started_at is not None:
            row.duration_ms = _elapsed_ms(row.started_at, now)
        row.image_keys = image_keys
        row.markdown = markdown
        row.plain_text = plain_text
        row.ocr_results = _ocr_payload(ocr_results)

    @staticmethod
    def apply_failed(row: KnowledgeFile, now: datetime, error_message: str) -> None:
        """标 failed。error_message 截断到列宽，不把 traceback 塞给前端。"""
        row.status = STATUS_FAILED
        row.error_message = error_message[:512]
        row.finished_at = now
        if row.started_at is not None:
            row.duration_ms = _elapsed_ms(row.started_at, now)

    async def create_pending(
        self,
        user_id: int,
        filename: str,
        object_key: str,
        size: int,
        content_type: str,
    ) -> KnowledgeFile:
        """complete 时插入 pending 行。refresh 是为了拿到自增 id 再去发队列。"""
        async with AsyncSessionLocal() as session:
            row = KnowledgeFile(
                user_id=user_id,
                filename=filename,
                object_key=object_key,
                size=size,
                content_type=content_type,
                status=STATUS_PENDING,
                image_keys=[],
                ocr_results=[],
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get_for_user(self, user_id: int, file_id: int) -> KnowledgeFile | None:
        """按 id 取当前用户的文件。别人的 id 走同一条查询，返回 None，接口层变 404。"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KnowledgeFile).where(
                    KnowledgeFile.id == file_id,
                    KnowledgeFile.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: int, limit: int, offset: int
    ) -> tuple[list[KnowledgeFile], int]:
        """当前用户的一页文件 + 该用户全部条数。

        total 按用户过滤后的总数，不受 limit/offset 影响，给前端算页数。
        id 作第二排序，避免 created_at 相同时顺序不稳。
        """
        async with AsyncSessionLocal() as session:
            owner = KnowledgeFile.user_id == user_id
            total = await session.scalar(
                select(func.count()).select_from(KnowledgeFile).where(owner)
            )
            result = await session.execute(
                select(KnowledgeFile)
                .where(owner)
                .order_by(KnowledgeFile.created_at.desc(), KnowledgeFile.id.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all()), int(total or 0)

    async def begin_processing(self, file_id: int) -> str:
        """worker 开工：pending → processing。找不到行视为 skip，避免毒消息死循环。"""
        async with AsyncSessionLocal() as session:
            row = await session.get(KnowledgeFile, file_id)
            if row is None:
                return "skip"
            now = datetime.now()
            outcome = self.apply_processing(row, now)
            if outcome == "run":
                await session.commit()
            return outcome

    async def mark_done(
        self,
        file_id: int,
        *,
        image_keys: list[str],
        markdown: str | None,
        plain_text: str | None,
        ocr_results: list[Any],
    ) -> None:
        """向量写入成功（或空文件无需写入）后回填同一行。"""
        async with AsyncSessionLocal() as session:
            row = await session.get(KnowledgeFile, file_id)
            if row is None:
                return
            self.apply_done(
                row,
                datetime.now(),
                image_keys=image_keys,
                markdown=markdown,
                plain_text=plain_text,
                ocr_results=ocr_results,
            )
            await session.commit()

    async def mark_failed(self, file_id: int, error_message: str) -> None:
        """业务失败或入队失败时把同一行标 failed，不再插第二行。"""
        async with AsyncSessionLocal() as session:
            row = await session.get(KnowledgeFile, file_id)
            if row is None:
                return
            self.apply_failed(row, datetime.now(), error_message)
            await session.commit()


knowledgeFileService = KnowledgeFileService()
