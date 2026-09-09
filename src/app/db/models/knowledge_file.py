from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# 状态机四个值。终态（done/failed）被 worker redeliver 时直接 skip，不再跑入库。
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
TERMINAL_STATUSES = frozenset({STATUS_DONE, STATUS_FAILED})


class KnowledgeFile(Base):
    """一次上传对应一行。complete 插入 pending，worker 更新同一行，不另开 job 表。"""

    __tablename__ = "knowledge_files"
    __table_args__ = (
        # 列表按用户 + 创建时间倒序，避免全表扫
        Index("ix_knowledge_files_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
    )
    size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    # complete 写 pending；ALIGN 给旧成功行的默认是 done，见 schema.py
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=STATUS_PENDING,
    )
    # 给前端的短失败文案，不是 traceback
    error_message: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    image_keys: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    markdown: Mapped[str | None] = mapped_column(
        MEDIUMTEXT,
    )
    plain_text: Mapped[str | None] = mapped_column(
        MEDIUMTEXT,
    )
    ocr_results: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    # created_at = 入队；started_at = 开工；finished_at = 终态
    # queue_wait_ms = started - created；duration_ms = finished - started
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    queue_wait_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )
