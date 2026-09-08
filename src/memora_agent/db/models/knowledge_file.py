from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from memora_agent.db.database import Base


class KnowledgeFile(Base):
    __tablename__ = "knowledge_files"

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
    size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    image_keys: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    markdown: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    plain_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ocr_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )
