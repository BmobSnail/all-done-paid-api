"""幂等服务纯逻辑单测：payload hash + key 命名稳定性。

DB/Redis 路径放到 integration。
"""
from __future__ import annotations

import os

os.environ.setdefault("PAID_API_KEY_PEPPER", "test_pepper_for_unit_tests_long_enough")

from app.services import idempotency  # noqa: E402


def test_hash_payload_dict_order_independent() -> None:
    a = idempotency._hash_payload({"a": 1, "b": 2})
    b = idempotency._hash_payload({"b": 2, "a": 1})
    assert a == b


def test_hash_payload_value_change_detected() -> None:
    a = idempotency._hash_payload({"a": 1})
    b = idempotency._hash_payload({"a": 2})
    assert a != b


def test_redis_key_namespace_includes_tenant() -> None:
    k1 = idempotency._redis_key("tenant_a", "req-1")
    k2 = idempotency._redis_key("tenant_b", "req-1")
    assert k1 != k2
    assert "tenant_a" in k1 and "tenant_b" in k2
    assert k1.startswith("paid:idem:")
