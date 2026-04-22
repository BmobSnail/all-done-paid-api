"""数据库基础设施：async SQLAlchemy + asyncpg。"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """ORM 基类。"""


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    global _engine, _session_factory
    s = get_settings()
    _engine = create_async_engine(
        s.PAID_DB_URL,
        pool_size=s.PAID_DB_POOL_SIZE,
        max_overflow=s.PAID_DB_MAX_OVERFLOW,
        pool_timeout=s.PAID_DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        future=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    if _engine is not None:
        await _engine.dispose()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB engine not initialised; call init_engine() first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping() -> bool:
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
