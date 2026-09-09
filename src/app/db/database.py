from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import config


DATABASE_URL = (
    f"mysql+asyncmy://{config.mysql.user}:{quote_plus(config.mysql.password or '')}"
    f"@{config.mysql.host}:{config.mysql.port}/{config.mysql.database}"
)


engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"connect_timeout": 5},
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass