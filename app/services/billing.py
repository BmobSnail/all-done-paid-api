"""计费服务：billing_events 不可变账本 + 状态机 + 异步聚合 paid_usage_hourly。

状态机：
    pending → committed   (业务成功后由 commit() 推进)
    pending → failed      (业务失败由 fail() 推进，不计入 usage)
    committed → reversed  (后台冲正，仅由 reverse() 推进)

API：
- start(...)      INSERT 一条 pending 事件，返回 event_id (UUID)
- commit(...)     UPDATE 状态 + token/cost 字段
- fail(...)       UPDATE 状态为 failed
- aggregate_into_usage(...)  后台任务：把已 committed 的事件按小时桶累加到 paid_usage_hourly
- recompute_usage(...)  对账重算（清空目标小时桶后从 billing_events 重建）
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.infra.database import session_scope
from app.models.billing_event import BillingEvent
from app.models.usage import UsageHourly


@dataclass(frozen=True, slots=True)
class StartResult:
    request_id: str
    event_id: int


def new_request_id() -> str:
    return uuid.uuid4().hex


async def start(
    *,
    tenant_id: str,
    api_key_id: int,
    endpoint: str,
    idempotency_key: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
) -> StartResult:
    rid = request_id or new_request_id()
    async with session_scope() as session:
        evt = BillingEvent(
            request_id=rid,
            tenant_id=tenant_id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            status="pending",
            model=model,
        )
        session.add(evt)
        await session.flush()
        return StartResult(request_id=rid, event_id=evt.id)


async def commit(
    *,
    request_id: str,
    token_in: int = 0,
    token_out: int = 0,
    cost_cents: int = 0,
    raw_meta_json: str | None = None,
) -> None:
    async with session_scope() as session:
        await session.execute(
            update(BillingEvent)
            .where(
                BillingEvent.request_id == request_id,
                BillingEvent.status == "pending",
            )
            .values(
                status="committed",
                token_in=token_in,
                token_out=token_out,
                cost_cents=cost_cents,
                raw_meta_json=raw_meta_json,
                committed_at=datetime.now(timezone.utc),
            )
        )


async def fail(*, request_id: str, error_code: str | None = None) -> None:
    async with session_scope() as session:
        await session.execute(
            update(BillingEvent)
            .where(
                BillingEvent.request_id == request_id,
                BillingEvent.status == "pending",
            )
            .values(status="failed", error_code=error_code)
        )


async def reverse(*, request_id: str, reason: str | None = None) -> None:
    async with session_scope() as session:
        await session.execute(
            update(BillingEvent)
            .where(
                BillingEvent.request_id == request_id,
                BillingEvent.status == "committed",
            )
            .values(status="reversed", error_code=reason)
        )


async def aggregate_into_usage(*, since: datetime, until: datetime) -> int:
    """把 [since, until) 内 committed 事件按小时桶累加到 paid_usage_hourly。

    返回写入/更新的桶数量。供后台任务（cron / ARQ）调用。
    """
    bucket_expr = func.date_trunc("hour", BillingEvent.created_at).label("hour_bucket")
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(
                    BillingEvent.tenant_id,
                    BillingEvent.endpoint,
                    bucket_expr,
                    func.count().label("req_count"),
                    func.coalesce(func.sum(BillingEvent.token_in), 0).label("token_in"),
                    func.coalesce(func.sum(BillingEvent.token_out), 0).label("token_out"),
                    func.coalesce(func.sum(BillingEvent.cost_cents), 0).label("cost_cents"),
                )
                .where(
                    BillingEvent.status == "committed",
                    BillingEvent.created_at >= since,
                    BillingEvent.created_at < until,
                )
                .group_by(BillingEvent.tenant_id, BillingEvent.endpoint, bucket_expr)
            )
        ).all()

        for r in rows:
            stmt = pg_insert(UsageHourly).values(
                tenant_id=r.tenant_id,
                endpoint=r.endpoint,
                hour_bucket=r.hour_bucket,
                req_count=r.req_count,
                token_in=r.token_in,
                token_out=r.token_out,
                cost_cents=r.cost_cents,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_paid_usage_bucket",
                set_={
                    "req_count": stmt.excluded.req_count,
                    "token_in": stmt.excluded.token_in,
                    "token_out": stmt.excluded.token_out,
                    "cost_cents": stmt.excluded.cost_cents,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            await session.execute(stmt)
        return len(rows)
