"""API Key 安全工具的单元测试。"""
from __future__ import annotations

import os

os.environ.setdefault("PAID_API_KEY_PEPPER", "test_pepper_for_unit_tests_long_enough")

from app.core import security  # noqa: E402


def test_generate_key_format() -> None:
    g = security.generate_key()
    assert g.full_key.startswith("sk_live_")
    assert g.key_id and len(g.key_id) >= 10
    assert len(g.last4) == 4
    assert len(g.secret_hash) == 64  # sha256 hex


def test_parse_then_verify() -> None:
    g = security.generate_key()
    parsed = security.parse_key(g.full_key)
    assert parsed is not None
    prefix, key_id, secret = parsed
    assert prefix == "sk_live_"
    assert key_id == g.key_id
    assert security.verify_secret(secret, g.secret_hash)


def test_verify_wrong_secret() -> None:
    g = security.generate_key()
    assert not security.verify_secret("not-the-real-secret", g.secret_hash)


def test_parse_bad_input() -> None:
    assert security.parse_key("nope") is None
    assert security.parse_key("sk_live_") is None
    assert security.parse_key("sk_live_kid") is None  # 缺 secret
