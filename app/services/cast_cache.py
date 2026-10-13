"""起卦结果 Redis 缓存。

key 设计：paid:cast:meihua:{prompt_version}:{model_tag}:{cast_signature}
- prompt_version 来自 settings，方便升级 prompt 后强制失效
- model_tag 预留（同一签名不同 tier 可独立缓存），暂用 "shared"
- value: cast 结果 JSON 序列化串，TTL = PAID_MEIHUA_CAST_CACHE_TTL_SECONDS

注意：缓存的是「起卦数据」（确定性输入），不是「LLM 解读」（输出有随机性）。
"""
from __future__ import annotations

import json

from app.core.config import get_settings
from app.infra import redis as redis_infra


def _key(cast_signature: str, model_tag: str = "shared") -> str:
    s = get_settings()
    return f"paid:cast:meihua:{s.PAID_PROMPT_VERSION}:{model_tag}:{cast_signature}"


async def get(cast_signature: str) -> dict | None:
    raw = await redis_infra.get_client().get(_key(cast_signature))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def put(cast_signature: str, payload: dict) -> None:
    s = get_settings()
    await redis_infra.get_client().set(
        _key(cast_signature),
        json.dumps(payload, ensure_ascii=False),
        ex=s.PAID_MEIHUA_CAST_CACHE_TTL_SECONDS,
    )
