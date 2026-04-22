"""对账重算：删除指定时间范围的 paid_usage_hourly 行，从 billing_events 重建。

用法：
    python -m scripts.recompute_usage --since 2026-04-22T00:00 --until 2026-04-23T00:00
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import delete

from app.infra import database
from app.models.usage import UsageHourly
from app.services import billing


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def _async_main(since: datetime, until: datetime) -> None:
    database.init_engine()
    try:
        async with database.session_scope() as session:
            await session.execute(
                delete(UsageHourly).where(
                    UsageHourly.hour_bucket >= since,
                    UsageHourly.hour_bucket < until,
                )
            )
        affected = await billing.aggregate_into_usage(since=since, until=until)
        print(f"[recompute] rebuilt {affected} bucket(s) for [{since}, {until})")
    finally:
        await database.dispose_engine()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--since", required=True, help="ISO8601 UTC")
    p.add_argument("--until", required=True, help="ISO8601 UTC")
    args = p.parse_args()
    asyncio.run(_async_main(_parse(args.since), _parse(args.until)))


if __name__ == "__main__":
    main()
