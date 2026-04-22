"""Logfire 可观测：按开关启停 + 脱敏 + 可迁移到 OTel。

约束：
- logfire 本身是可选依赖，关停时零副作用
- 业务代码不直接 import logfire，只调本模块的 setup/span/info
- 脱敏字段列表从 PAID_LOGFIRE_SCRUB_FIELDS 环境变量读
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings

_enabled = False
_logfire = None  # lazy import


def setup() -> None:
    """应用启动时调用。未启用时 no-op。"""
    global _enabled, _logfire
    s = get_settings()
    if not s.PAID_LOGFIRE_ENABLED or not s.PAID_LOGFIRE_TOKEN:
        _enabled = False
        return
    try:
        import logfire  # type: ignore

        scrub_fields = [f.strip() for f in s.PAID_LOGFIRE_SCRUB_FIELDS.split(",") if f.strip()]
        logfire.configure(
            token=s.PAID_LOGFIRE_TOKEN,
            environment=s.PAID_LOGFIRE_ENV,
            service_name=s.PAID_LOGFIRE_SERVICE_NAME,
            scrubbing=logfire.ScrubbingOptions(extra_patterns=scrub_fields)
            if hasattr(logfire, "ScrubbingOptions")
            else None,
        )
        _logfire = logfire
        _enabled = True
    except Exception:
        _enabled = False


def is_enabled() -> bool:
    return _enabled


@contextmanager
def span(name: str, **attrs: Any):
    """上下文 span。关停时只是 yield 原样。"""
    if not _enabled or _logfire is None:
        yield None
        return
    with _logfire.span(name, **attrs) as s:
        yield s


def info(message: str, **attrs: Any) -> None:
    if _enabled and _logfire is not None:
        _logfire.info(message, **attrs)


def warn(message: str, **attrs: Any) -> None:
    if _enabled and _logfire is not None:
        _logfire.warn(message, **attrs)


def error(message: str, **attrs: Any) -> None:
    if _enabled and _logfire is not None:
        _logfire.error(message, **attrs)
