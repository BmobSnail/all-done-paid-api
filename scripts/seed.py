"""一键创建默认 tenant + admin api key。仅 dev/test 环境可执行。

用法：
    python -m scripts.seed                # 增量创建（已存在则跳过）
    python -m scripts.seed --reset        # 清空 paid_* 表后重建
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, text

from app.core import security
from app.core.config import get_settings
from app.infra import database
from app.models.api_key import ApiKey, ApiKeyAuditLog, ApiKeyRollover
from app.models.billing_event import BillingEvent
from app.models.idempotency import IdempotencyKey
from app.models.usage import UsageHourly

DEFAULT_TENANT = "internal"
DEFAULT_PLAN = "internal"


async def _reset_tables() -> None:
    async with database.session_scope() as session:
        for tbl in [
            BillingEvent.__tablename__,
            UsageHourly.__tablename__,
            IdempotencyKey.__tablename__,
            ApiKeyAuditLog.__tablename__,
            ApiKeyRollover.__tablename__,
            ApiKey.__tablename__,
        ]:
            await session.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
    print("[seed] truncated paid_* tables")


async def _ensure_admin_key() -> None:
    async with database.session_scope() as session:
        existing = (
            await session.execute(
                select(ApiKey).where(
                    ApiKey.tenant_id == DEFAULT_TENANT, ApiKey.plan == DEFAULT_PLAN
                )
            )
        ).scalar_one_or_none()
        if existing:
            print(
                f"[seed] admin key exists: key_id={existing.key_id} (full key not retrievable)"
            )
            return

        gen = security.generate_key()
        record = ApiKey(
            key_id=gen.key_id,
            key_prefix=gen.key_prefix,
            last4=gen.last4,
            secret_hash=gen.secret_hash,
            tenant_id=DEFAULT_TENANT,
            plan=DEFAULT_PLAN,
            status="active",
            qps_limit=100,
            concurrency_limit=200,
            quota_daily=100_000,
            note="seeded admin key for local/test",
        )
        session.add(record)
        await session.flush()
        session.add(
            ApiKeyAuditLog(
                api_key_id=record.id,
                actor="seed-script",
                action="create",
                target=record.key_id,
            )
        )
        print("[seed] created admin key")
        print(f"[seed]   key_id  : {gen.key_id}")
        print(f"[seed]   FULL KEY: {gen.full_key}")
        print("[seed]   ⚠ 请立即保存，secret 仅一次性展示")


async def _async_main(reset: bool) -> None:
    s = get_settings()
    if s.is_production:
        sys.exit("seed script refuses to run in production environment")
    database.init_engine()
    try:
        if reset:
            await _reset_tables()
        await _ensure_admin_key()
    finally:
        await database.dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="seed default tenant + admin key")
    parser.add_argument("--reset", action="store_true", help="truncate paid_* tables first")
    args = parser.parse_args()
    asyncio.run(_async_main(reset=args.reset))


if __name__ == "__main__":
    main()
