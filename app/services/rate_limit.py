"""Redis 令牌桶限流：QPS / 分钟 burst / 日 quota / 并发四维度，全部 Lua 原子。

设计：
- QPS: 滑动窗口（1s 内不超过 qps_limit），用 sliding-log（ZSET 时间戳）
- Burst: 1 分钟内不超过 qps_limit * 60 * 0.7（防短时拉满）
- Daily Quota: 自然日累计请求数 ≤ quota_daily
- Concurrency: 当前在执行的请求 ≤ concurrency_limit（acquire/release pattern）

key 命名（前缀走 PAID_RATE_LIMIT_REDIS_PREFIX）：
- {prefix}:qps:{tenant}:{key_id}      ZSET，score=timestamp_ms
- {prefix}:min:{tenant}:{key_id}      INT counter w/ TTL 60s
- {prefix}:day:{tenant}:{key_id}:{YYYYMMDD}  INT counter w/ TTL 86400s
- {prefix}:conc:{tenant}:{key_id}     INT counter (不带 TTL，由 release 维护)
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from app.core import errors
from app.core.config import get_settings
from app.infra import redis as redis_infra
from app.services.auth import AuthContext

# Lua: 原子检查 4 维度并计数；超限返回 (维度名, retry_after_seconds)
_ACQUIRE_LUA = """
local qps_key = KEYS[1]
local min_key = KEYS[2]
local day_key = KEYS[3]
local conc_key = KEYS[4]

local now_ms = tonumber(ARGV[1])
local qps_limit = tonumber(ARGV[2])
local burst_limit = tonumber(ARGV[3])
local daily_limit = tonumber(ARGV[4])
local concurrency_limit = tonumber(ARGV[5])
local day_ttl = tonumber(ARGV[6])

-- 1) QPS 滑动窗口：清理 1s 前的记录，再统计
redis.call('ZREMRANGEBYSCORE', qps_key, 0, now_ms - 1000)
local qps_now = redis.call('ZCARD', qps_key)
if qps_now >= qps_limit then
    return {'qps', 1}
end

-- 2) 分钟 burst
local min_now = tonumber(redis.call('GET', min_key) or '0')
if min_now >= burst_limit then
    return {'burst', 60}
end

-- 3) 日 quota
local day_now = tonumber(redis.call('GET', day_key) or '0')
if day_now >= daily_limit then
    return {'quota', day_ttl}
end

-- 4) 并发
local conc_now = tonumber(redis.call('GET', conc_key) or '0')
if conc_now >= concurrency_limit then
    return {'concurrency', 1}
end

-- 全部通过：写入计数
redis.call('ZADD', qps_key, now_ms, now_ms)
redis.call('PEXPIRE', qps_key, 2000)
redis.call('INCR', min_key)
redis.call('EXPIRE', min_key, 60)
redis.call('INCR', day_key)
redis.call('EXPIRE', day_key, day_ttl)
redis.call('INCR', conc_key)

return {'ok', 0}
"""


def _bucket_keys(tenant_id: str, key_id: str) -> tuple[str, str, str, str]:
    s = get_settings()
    p = s.PAID_RATE_LIMIT_REDIS_PREFIX
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return (
        f"{p}:qps:{tenant_id}:{key_id}",
        f"{p}:min:{tenant_id}:{key_id}",
        f"{p}:day:{tenant_id}:{key_id}:{today}",
        f"{p}:conc:{tenant_id}:{key_id}",
    )


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(timezone.utc)
    midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_midnight = midnight_today + timedelta(days=1)
    return int((next_midnight - now).total_seconds())


async def _acquire(client: Redis, ctx: AuthContext) -> tuple[str, int]:
    qps_key, min_key, day_key, conc_key = _bucket_keys(ctx.tenant_id, ctx.key_id)
    burst_limit = max(ctx.qps_limit * 60 * 7 // 10, ctx.qps_limit)
    result = await client.eval(
        _ACQUIRE_LUA,
        4,
        qps_key,
        min_key,
        day_key,
        conc_key,
        int(time.time() * 1000),
        ctx.qps_limit,
        burst_limit,
        ctx.quota_daily,
        ctx.concurrency_limit,
        _seconds_until_midnight_utc(),
    )
    # redis-py decode_responses=True 时返回 [str, int]
    dim, retry = result[0], int(result[1])
    return dim, retry


async def _release(client: Redis, ctx: AuthContext) -> None:
    _qps, _min, _day, conc_key = _bucket_keys(ctx.tenant_id, ctx.key_id)
    # 用 Lua 防止减到负数
    await client.eval(
        "local v = tonumber(redis.call('GET', KEYS[1]) or '0'); "
        "if v > 0 then redis.call('DECR', KEYS[1]) end; return v",
        1,
        conc_key,
    )


@asynccontextmanager
async def acquire(ctx: AuthContext):
    """付费请求开始时 acquire，结束时自动 release。

    用法：
        async with rate_limit.acquire(ctx):
            ... 业务代码 ...
    """
    client = redis_infra.get_client()
    dim, retry = await _acquire(client, ctx)
    if dim != "ok":
        if dim == "quota":
            raise errors.QuotaExceededError(
                "Daily quota exceeded", retry_after=retry
            )
        raise errors.RateLimitedError(
            f"Rate limited on dimension={dim}", retry_after=retry
        )
    try:
        yield
    finally:
        try:
            await _release(client, ctx)
        except Exception:
            # release 失败不影响业务返回
            pass
