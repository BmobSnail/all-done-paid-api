"""CircuitBreaker 单测：阈值打开 / half-open 放行。"""
from __future__ import annotations

import asyncio

from app.infra.llm.retry import CircuitBreaker


def test_breaker_allows_until_threshold() -> None:
    async def run() -> None:
        cb = CircuitBreaker(failure_threshold=3, cool_down_seconds=60)
        assert await cb.allow()
        await cb.record_failure()
        await cb.record_failure()
        assert await cb.allow()
        await cb.record_failure()
        assert not await cb.allow()

    asyncio.run(run())


def test_breaker_half_open_after_cooldown() -> None:
    async def run() -> None:
        cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=0)
        await cb.record_failure()
        await cb.record_failure()
        # cool_down=0：半开放行一次
        assert await cb.allow()

    asyncio.run(run())


def test_breaker_success_resets_counter() -> None:
    async def run() -> None:
        cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=60)
        await cb.record_failure()
        await cb.record_success()
        await cb.record_failure()
        assert await cb.allow()

    asyncio.run(run())
