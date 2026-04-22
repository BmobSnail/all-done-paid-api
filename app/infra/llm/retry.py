"""LLM 调用治理：tenacity 重试 + asyncio.Semaphore 并发 + 简易熔断 + 档位 fallback。

业务代码调用方式：
    from app.infra.llm import client
    result = await client.run_structured(agent, user_prompt, ...)
    async for delta in client.run_stream_structured(agent, user_prompt, ...):
        ...

本模块只负责调用侧治理。Agent 工厂见 agents.py。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core import errors
from app.infra.llm import observability as obs
from app.infra.llm.provider import ModelTier


class ProviderCallError(Exception):
    """可重试的 provider 异常。"""


@dataclass(slots=True)
class CircuitBreaker:
    """非常简单的单实例熔断：连续失败 N 次进 open，冷却后 half-open。"""

    failure_threshold: int = 5
    cool_down_seconds: int = 30
    _failures: int = 0
    _opened_at: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allow(self) -> bool:
        async with self._lock:
            if self._failures < self.failure_threshold:
                return True
            if time.time() - self._opened_at >= self.cool_down_seconds:
                # half-open：放行一次，成功则清零
                self._failures = self.failure_threshold - 1
                return True
            return False

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures == self.failure_threshold:
                self._opened_at = time.time()


_semaphore: asyncio.Semaphore | None = None
_breakers: dict[ModelTier, CircuitBreaker] = {}


def init_governance(max_concurrency: int) -> None:
    global _semaphore
    _semaphore = asyncio.Semaphore(max_concurrency)
    for tier in ModelTier:
        _breakers[tier] = CircuitBreaker()


def _get_semaphore() -> asyncio.Semaphore:
    if _semaphore is None:
        raise RuntimeError("LLM governance not initialised; call init_governance() first")
    return _semaphore


def _get_breaker(tier: ModelTier) -> CircuitBreaker:
    return _breakers.setdefault(tier, CircuitBreaker())


async def call_with_governance(
    tier: ModelTier,
    max_retries: int,
    timeout_seconds: int,
    func,
    *args,
    **kwargs,
):
    """统一的治理壳：并发 + 熔断 + 重试 + 超时。

    func 必须是 async callable，返回结构化结果；失败抛 ProviderCallError。
    """
    breaker = _get_breaker(tier)
    if not await breaker.allow():
        raise errors.UpstreamUnavailableError(
            f"Circuit open for tier={tier.value}"
        )

    sem = _get_semaphore()
    async with sem:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_retries),
                wait=wait_exponential_jitter(initial=0.5, max=4),
                retry=retry_if_exception_type(ProviderCallError),
                reraise=True,
            ):
                with attempt:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=timeout_seconds
                    )
            await breaker.record_success()
            return result
        except asyncio.TimeoutError as exc:
            await breaker.record_failure()
            obs.warn("llm.timeout", tier=tier.value)
            raise ProviderCallError("LLM call timed out") from exc
        except ProviderCallError:
            await breaker.record_failure()
            raise
        except Exception as exc:
            await breaker.record_failure()
            obs.error("llm.unexpected", tier=tier.value, error=str(exc))
            raise


async def call_with_fallback(
    max_retries: int,
    timeout_seconds: int,
    tiers: list[ModelTier],
    func_factory,
):
    """按 tiers 顺序尝试；全部失败时抛 UpstreamUnavailableError。

    func_factory(tier) → async callable，每次调用返回结构化结果。
    """
    last_error: Exception | None = None
    for tier in tiers:
        try:
            return await call_with_governance(
                tier,
                max_retries,
                timeout_seconds,
                func_factory(tier),
            )
        except (ProviderCallError, errors.UpstreamUnavailableError) as exc:
            last_error = exc
            obs.warn("llm.fallback", from_tier=tier.value)
            continue
    raise errors.UpstreamUnavailableError(
        f"All tiers failed: {tiers} (last={last_error})"
    )
