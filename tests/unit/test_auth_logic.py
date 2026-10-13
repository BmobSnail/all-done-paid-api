"""auth 服务的纯逻辑单测：bypass 路径 + Authorization 解析。

不依赖 DB / Redis：测 bypass 短路 + 缺凭证 / 格式错误的早期分支。
DB / Redis 路径放到 integration。
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("PAID_API_KEY_PEPPER", "test_pepper_for_unit_tests_long_enough")
os.environ["PAID_INTERNAL_BYPASS_ENABLED"] = "true"
os.environ.setdefault("PAID_APP_ENV", "development")

import pytest

from app.core import errors
from app.core.config import get_settings
from app.services import auth


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_bypass_short_circuits_without_authorization() -> None:
    ctx = asyncio.run(auth.authenticate(None))
    assert ctx.tenant_id == "internal"
    assert ctx.plan == "internal"
    assert ctx.qps_limit > 0


def test_bypass_disabled_then_missing_credentials(monkeypatch) -> None:
    monkeypatch.setenv("PAID_INTERNAL_BYPASS_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(errors.MissingCredentialsError):
        asyncio.run(auth.authenticate(None))


def test_authorization_must_be_bearer(monkeypatch) -> None:
    monkeypatch.setenv("PAID_INTERNAL_BYPASS_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(errors.MissingCredentialsError):
        asyncio.run(auth.authenticate("Basic abc"))


def test_invalid_key_format(monkeypatch) -> None:
    monkeypatch.setenv("PAID_INTERNAL_BYPASS_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(errors.InvalidApiKeyError):
        asyncio.run(auth.authenticate("Bearer not_a_real_key"))
