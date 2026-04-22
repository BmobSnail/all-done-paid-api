"""Redis 基础设施：async client 单例。"""
from redis.asyncio import ConnectionPool, Redis

from app.core.config import get_settings

_pool: ConnectionPool | None = None
_client: Redis | None = None


def init_redis() -> None:
    global _pool, _client
    s = get_settings()
    _pool = ConnectionPool.from_url(
        s.PAID_REDIS_URL,
        max_connections=s.PAID_REDIS_MAX_CONNECTIONS,
        decode_responses=True,
    )
    _client = Redis(connection_pool=_pool)


async def dispose_redis() -> None:
    if _client is not None:
        await _client.aclose()
    if _pool is not None:
        await _pool.aclose()


def get_client() -> Redis:
    if _client is None:
        raise RuntimeError("Redis not initialised; call init_redis() first")
    return _client


async def ping() -> bool:
    if _client is None:
        return False
    try:
        return bool(await _client.ping())
    except Exception:
        return False
