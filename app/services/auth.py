"""API Key 鉴权服务：解析 Bearer + Redis 缓存校验结果。

缓存策略：
- key: paid:auth:{key_id}
- value: JSON {tenant_id, plan, status, qps_limit, concurrency_limit, quota_daily, secret_hash, expires_at}
- TTL: 300s（短期，便于及时反映吊销/改 plan）
- 命中后仍校验 secret + status + expires_at（数据可能在 TTL 内被改）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.core import errors, security
from app.core.config import get_settings
from app.infra import redis as redis_infra
from app.infra.database import session_scope
from app.models.api_key import ApiKey

CACHE_TTL_SECONDS = 300


@dataclass(frozen=True, slots=True)
class AuthContext:
    """鉴权成功后注入到 request.state.auth。"""

    api_key_id: int
    key_id: str
    tenant_id: str
    plan: str
    qps_limit: int
    concurrency_limit: int
    quota_daily: int


def _cache_key(key_id: str) -> str:
    return f"paid:auth:{key_id}"


async def _load_from_db(key_id: str) -> dict | None:
    async with session_scope() as session:
        row = (
            await session.execute(select(ApiKey).where(ApiKey.key_id == key_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "key_id": row.key_id,
            "tenant_id": row.tenant_id,
            "plan": row.plan,
            "status": row.status,
            "qps_limit": row.qps_limit,
            "concurrency_limit": row.concurrency_limit,
            "quota_daily": row.quota_daily,
            "secret_hash": row.secret_hash,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }


async def _load_with_cache(key_id: str) -> dict | None:
    client = redis_infra.get_client()
    cached = await client.get(_cache_key(key_id))
    if cached:
        return json.loads(cached)
    fresh = await _load_from_db(key_id)
    if fresh is not None:
        await client.set(_cache_key(key_id), json.dumps(fresh), ex=CACHE_TTL_SECONDS)
    return fresh


async def authenticate(authorization: str | None) -> AuthContext:
    """根据 Authorization header 鉴权，失败抛 ApiError。"""
    s = get_settings()
    if s.PAID_INTERNAL_BYPASS_ENABLED and not s.is_production:
        return AuthContext(
            api_key_id=0,
            key_id="bypass",
            tenant_id="internal",
            plan="internal",
            qps_limit=10**6,
            concurrency_limit=10**6,
            quota_daily=10**9,
        )

    if not authorization:
        raise errors.MissingCredentialsError()
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise errors.MissingCredentialsError("Authorization header must be 'Bearer <key>'")

    parsed = security.parse_key(parts[1].strip())
    if parsed is None:
        raise errors.InvalidApiKeyError()
    _prefix, key_id, secret = parsed

    record = await _load_with_cache(key_id)
    if record is None:
        raise errors.InvalidApiKeyError()
    if not security.verify_secret(secret, record["secret_hash"]):
        raise errors.InvalidApiKeyError()
    if record["status"] != "active":
        raise errors.ApiKeyDisabledError()
    if record["expires_at"]:
        expires_at = datetime.fromisoformat(record["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            raise errors.ApiKeyDisabledError("API key has expired")

    return AuthContext(
        api_key_id=record["id"],
        key_id=record["key_id"],
        tenant_id=record["tenant_id"],
        plan=record["plan"],
        qps_limit=record["qps_limit"],
        concurrency_limit=record["concurrency_limit"],
        quota_daily=record["quota_daily"],
    )


async def invalidate_cache(key_id: str) -> None:
    """吊销 / rotate / 改配额时调用，强制刷新。"""
    client = redis_infra.get_client()
    await client.delete(_cache_key(key_id))


def to_dict(ctx: AuthContext) -> dict:
    return asdict(ctx)
