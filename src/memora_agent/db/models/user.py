from datetime import datetime
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from memora_agent.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    nickname: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=lambda: f"用户_{str(uuid.uuid4())[:8]}",
        unique=True,
    )

    password:Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )