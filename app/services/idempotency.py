"""幂等键服务：双层缓存（Redis 短期 + PG 长期），保护重试/SSE 重连不重复扣费。

合约：
- 客户端可主动传 Idempotency-Key header；不传则跳过幂等保护
- 同一 (tenant_id, key) 在 TTL 内重放：返回首次的响应（status_code + body）
- 不同 request_hash 的同 key 视为冲突，返回 422

返回值：
- check_and_get(...) → IdempotencyResult，可能含 cached_response
- save(...) 在请求完成后由调用方写回
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core import errors
from app.core.config import get_settings
from app.infra import redis as redis_infra
from app.infra.database import session_scope
from app.models.idempotency import IdempotencyKey


@dataclass(frozen=True, slots=True)
class CachedResponse:
    status_code: int
    body: str  # JSON 序列化后的 body


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    """check_and_reserve 返回值。"""

    request_hash: str  # 计算后的 hash，调用方需在 save() 时回传
    cached: CachedResponse | None  # 命中则非 None


def _redis_key(tenant_id: str, key: str) -> str:
    return f"paid:idem:{tenant_id}:{key}"


def _hash_payload(payload: dict[str, Any] | str) -> str:
    raw = json.dumps(payload, sort_keys=True) if isinstance(payload, dict) else payload
    return hashlib.sha256(raw.encode()).hexdigest()


async def check(
    *,
    tenant_id: str,
    idempotency_key: str | None,
    request_payload: dict[str, Any],
) -> IdempotencyResult | None:
    """请求开始时调用：返回 None 表示未启用幂等；否则返回结果。

    若命中已完成响应，调用方应直接返回 cached_response 不再执行业务。
    若 request_hash 与已存在记录冲突，抛 ValidationApiError(409 等价)。
    """
    if not idempotency_key:
        return None

    request_hash = _hash_payload(request_payload)
    client = redis_infra.get_client()

    # Redis 命中
    cached_raw = await client.get(_redis_key(tenant_id, idempotency_key))
    if cached_raw:
        cached = json.loads(cached_raw)
        if cached["request_hash"] != request_hash:
            raise errors.ValidationApiError(
                "Idempotency-Key conflict: payload differs from original",
                idempotency_key=idempotency_key,
            )
        if cached.get("status_code") is not None:
            return IdempotencyResult(
                request_hash=request_hash,
                cached=CachedResponse(
                    status_code=cached["status_code"],
                    body=cached["body"],
                ),
            )
        # 占位但未完成：让请求继续，后续 save 会刷新
        return IdempotencyResult(request_hash=request_hash, cached=None)

    # Redis 未命中：查 PG（重启 / 跨节点场景）
    async with session_scope() as session:
        row = (
            await session.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.tenant_id == tenant_id,
                    IdempotencyKey.key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            if row.expires_at <= datetime.now(timezone.utc):
                # 过期，可复用 key
                pass
            else:
                if row.request_hash != request_hash:
                    raise errors.ValidationApiError(
                        "Idempotency-Key conflict: payload differs from original",
                        idempotency_key=idempotency_key,
                    )
                if row.response_body is not None and row.status_code is not None:
                    cached = CachedResponse(
                        status_code=row.status_code, body=row.response_body
                    )
                    return IdempotencyResult(
                        request_hash=request_hash, cached=cached
                    )

    # 占位 reserve：写一个 placeholder 到 Redis 防并发冲突
    s = get_settings()
    placeholder = json.dumps(
        {"request_hash": request_hash, "status_code": None, "body": None}
    )
    await client.set(
        _redis_key(tenant_id, idempotency_key),
        placeholder,
        ex=s.PAID_IDEMPOTENCY_TTL_SECONDS,
        nx=True,  # 已存在则不覆盖（防与并发请求竞争）
    )
    return IdempotencyResult(request_hash=request_hash, cached=None)


async def save(
    *,
    tenant_id: str,
    idempotency_key: str | None,
    request_hash: str,
    status_code: int,
    body: str,
) -> None:
    """请求完成后调用：双写 Redis + PG。"""
    if not idempotency_key:
        return
    s = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=s.PAID_IDEMPOTENCY_TTL_SECONDS)
    response_hash = hashlib.sha256(body.encode()).hexdigest()

    payload = json.dumps(
        {
            "request_hash": request_hash,
            "status_code": status_code,
            "body": body,
            "response_hash": response_hash,
        }
    )
    client = redis_infra.get_client()
    await client.set(
        _redis_key(tenant_id, idempotency_key),
        payload,
        ex=s.PAID_IDEMPOTENCY_TTL_SECONDS,
    )

    async with session_scope() as session:
        stmt = pg_insert(IdempotencyKey).values(
            key=idempotency_key,
            tenant_id=tenant_id,
            request_hash=request_hash,
            response_hash=response_hash,
            response_body=body,
            status_code=status_code,
            expires_at=expires_at,
        )
        # 同 (tenant_id, key) 已存在则更新（覆盖 placeholder 或刷新）
        stmt = stmt.on_conflict_do_update(
            constraint="uq_paid_idempotency_tenant_key",
            set_={
                "request_hash": request_hash,
                "response_hash": response_hash,
                "response_body": body,
                "status_code": status_code,
                "expires_at": expires_at,
            },
        )
        await session.execute(stmt)
