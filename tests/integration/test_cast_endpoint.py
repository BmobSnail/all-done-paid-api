"""集成测试：cast 接口走 bypass 鉴权 + 真 Redis 缓存路径。

需要本地 Redis 在 PAID_REDIS_URL（默认 redis://localhost:6380/0）。
跑法：
    docker compose -f docker-compose.yml up -d redis postgres
    PAID_INTERNAL_BYPASS_ENABLED=true pytest tests/integration -q -m integration

未启用 redis 时整组 skip。
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("PAID_API_KEY_PEPPER", "test_pepper_for_integration_long_enough")
os.environ["PAID_INTERNAL_BYPASS_ENABLED"] = "true"
os.environ.setdefault("PAID_APP_ENV", "development")
os.environ.setdefault("PAID_REDIS_URL", "redis://localhost:6380/0")


pytestmark = pytest.mark.integration


def _redis_available() -> bool:
    try:
        import redis  # type: ignore[import-untyped]

        client = redis.Redis.from_url(os.environ["PAID_REDIS_URL"], socket_connect_timeout=1)
        client.ping()
        return True
    except Exception:
        return False


if not _redis_available():
    pytest.skip("Redis not available on PAID_REDIS_URL", allow_module_level=True)


from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.infra import redis as redis_infra  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    get_settings.cache_clear()
    redis_infra.init_redis()
    app = create_app()
    with TestClient(app) as c:
        yield c
    asyncio.run(redis_infra.dispose_redis())


def test_cast_time_returns_signature_and_caches(client: TestClient) -> None:
    payload = {
        "method": "time",
        "solar_datetime": "2026-04-22T10:00:00+00:00",
        "question": "工作运势",
    }
    r1 = client.post("/api/v1/divination/meihua/cast", json=payload)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["cast_signature"]
    assert body1["cached"] is False

    r2 = client.post("/api/v1/divination/meihua/cast", json=payload)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["cast_signature"] == body1["cast_signature"]
    assert body2["cached"] is True


def test_cast_number_requires_both_nums(client: TestClient) -> None:
    bad = {"method": "number", "upper_num": 7, "solar_datetime": "2026-04-22T10:00:00+00:00"}
    r = client.post("/api/v1/divination/meihua/cast", json=bad)
    assert r.status_code == 422, r.text


def test_cast_solar_must_have_tz(client: TestClient) -> None:
    bad = {"method": "time", "solar_datetime": "2026-04-22T10:00:00"}
    r = client.post("/api/v1/divination/meihua/cast", json=bad)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "validation_error"


def test_interpret_rejects_tampered_cast(client: TestClient) -> None:
    cast = client.post(
        "/api/v1/divination/meihua/cast",
        json={
            "method": "time",
            "solar_datetime": "2026-04-22T10:00:00+00:00",
            "question": "财运",
        },
    ).json()

    # 篡改 ben.name 但保留原 cast_signature
    tampered = dict(cast)
    tampered["ben"] = dict(cast["ben"], name="坤坤")
    r = client.post(
        "/api/v1/divination/meihua/interpret",
        json={"cast": tampered},
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "validation_error"
