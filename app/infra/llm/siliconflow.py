"""SiliconFlow 实现：OpenAI 兼容协议，走多 Key 轮询。"""
from __future__ import annotations

import itertools
from threading import Lock

from app.core.config import get_settings
from app.infra.llm.provider import ProviderConfig


def build_siliconflow_config() -> ProviderConfig:
    s = get_settings()
    return ProviderConfig(
        name=s.PAID_LLM_PROVIDER,
        base_url=s.PAID_LLM_BASE_URL,
        api_keys=s.llm_api_keys_list,
        model_primary=s.PAID_LLM_MODEL_PRIMARY,
        model_fallback=s.PAID_LLM_MODEL_FALLBACK,
        model_cheap=s.PAID_LLM_MODEL_CHEAP,
        timeout_seconds=s.PAID_LLM_TIMEOUT_SECONDS,
        max_retries=s.PAID_LLM_MAX_RETRIES,
        max_concurrency=s.PAID_LLM_MAX_CONCURRENCY,
        stream_timeout_seconds=s.PAID_LLM_STREAM_TIMEOUT_SECONDS,
    )


class KeyPool:
    """线程/协程安全的 Key 轮询池。"""

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise RuntimeError(
                "PAID_LLM_API_KEYS is empty. Set it to a comma-separated list of keys."
            )
        self._lock = Lock()
        self._cycle = itertools.cycle(keys)

    def next(self) -> str:
        with self._lock:
            return next(self._cycle)
