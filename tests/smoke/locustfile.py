"""Locust smoke 压测：cast 高频 + interpret 低频（SSE 真消费）。

跑法：
    pip install locust
    locust -f tests/smoke/locustfile.py \\
        --host https://api-paid-test.all-done.cn \\
        -u 20 -r 5 -t 2m \\
        --headless --csv=smoke

环境变量：
    PAID_SMOKE_API_KEY=sk_live_xxx          # 必填，从 seed.py 拿
    PAID_SMOKE_QUESTION="工作运势"          # 可选

目标：cast P95 < 50ms（不调 LLM）；interpret 首 token < 3s。
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone

from locust import HttpUser, between, events, task

API_KEY = os.environ.get("PAID_SMOKE_API_KEY", "")
QUESTION = os.environ.get("PAID_SMOKE_QUESTION", "工作运势")


@events.test_start.add_listener
def _on_start(**_kw) -> None:
    if not API_KEY:
        print("[smoke] WARN: PAID_SMOKE_API_KEY not set — server 必须开 PAID_INTERNAL_BYPASS_ENABLED=true 才能跑")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}


def _solar_dt() -> str:
    # 加一个随机分钟扰动，避免每个虚拟用户落到同一缓存
    rand_min = random.randint(0, 59)
    now = datetime.now(timezone.utc).replace(minute=rand_min, second=0, microsecond=0)
    return now.isoformat()


class PaidApiUser(HttpUser):
    wait_time = between(0.2, 1.0)

    @task(10)
    def cast(self) -> None:
        body = {
            "method": "time",
            "solar_datetime": _solar_dt(),
            "question": QUESTION,
        }
        with self.client.post(
            "/api/v1/divination/meihua/cast",
            json=body,
            headers=_auth_headers(),
            name="POST /cast",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"cast {resp.status_code}: {resp.text[:120]}")

    @task(1)
    def interpret(self) -> None:
        cast_resp = self.client.post(
            "/api/v1/divination/meihua/cast",
            json={
                "method": "time",
                "solar_datetime": _solar_dt(),
                "question": QUESTION,
            },
            headers=_auth_headers(),
            name="POST /cast (warmup)",
        )
        if cast_resp.status_code != 200:
            return
        cast = cast_resp.json()
        with self.client.post(
            "/api/v1/divination/meihua/interpret",
            json={"cast": cast},
            headers={**_auth_headers(), "Accept": "text/event-stream"},
            name="POST /interpret (SSE)",
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"interpret {resp.status_code}: {resp.text[:120]}")
                return
            saw_done = False
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith(b"event: done"):
                    saw_done = True
                if line.startswith(b"event: error"):
                    resp.failure(f"sse error: {line!r}")
                    return
            if not saw_done:
                resp.failure("interpret: SSE 未收到 done 事件")


_ = json  # keep import for future payload assertions
