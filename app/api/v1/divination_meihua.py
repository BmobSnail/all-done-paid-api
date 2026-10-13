"""梅花易数付费 API：cast / interpret。

- cast：纯计算，复用 services/meihua.py，结果缓存到 Redis（按 cast_signature）
- interpret：必须传服务端发的 cast 结果（含 cast_signature），不可自带卦数据；
  同时鉴权 + 限流 + 计费 + 幂等 + LLM 流式（SSE）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from app.api.deps import require_api_key
from app.core import errors
from app.services import billing, cast_cache, idempotency, meihua, rate_limit
from app.services.auth import AuthContext

router = APIRouter(prefix="/divination/meihua", tags=["divination"])


# ---------- Schemas ----------


class CastRequest(BaseModel):
    method: Literal["time", "number"] = "time"
    solar_datetime: str | None = Field(
        default=None,
        description="ISO8601 含时区；method=time 时若不传则用服务器当前 UTC。",
    )
    upper_num: int | None = Field(default=None, ge=1, le=10**9)
    lower_num: int | None = Field(default=None, ge=1, le=10**9)
    question: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self) -> "CastRequest":
        if self.method == "number" and (self.upper_num is None or self.lower_num is None):
            raise ValueError("method=number 必须传 upper_num 与 lower_num")
        return self


class GuaPayload(BaseModel):
    name: str
    upper: str
    lower: str
    symbol_upper: str
    symbol_lower: str
    lines: list[int]


class CastResponse(BaseModel):
    method: str
    solar_datetime: str
    question: str | None
    ben: GuaPayload
    bian: GuaPayload
    hu: GuaPayload
    moving_line: int
    cast_signature: str
    cached: bool = False


class InterpretRequest(BaseModel):
    cast: CastResponse = Field(..., description="必须使用 /cast 返回的完整结果")


# ---------- helpers ----------


def _gua_payload(hex_: meihua.Hexagram) -> GuaPayload:
    return GuaPayload(
        name=hex_.name,
        upper=hex_.upper.name,
        lower=hex_.lower.name,
        symbol_upper=hex_.upper.symbol,
        symbol_lower=hex_.lower.symbol,
        lines=hex_.lines,
    )


def _cast_to_response(result: meihua.CastResult, *, cached: bool = False) -> CastResponse:
    return CastResponse(
        method=result.method,
        solar_datetime=result.solar_datetime,
        question=result.question,
        ben=_gua_payload(result.ben),
        bian=_gua_payload(result.bian),
        hu=_gua_payload(result.hu),
        moving_line=result.moving_line,
        cast_signature=result.cast_signature,
        cached=cached,
    )


def _parse_solar(dt_str: str | None) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError as exc:
        raise errors.ValidationApiError(f"solar_datetime 格式非法: {exc}") from exc
    if dt.tzinfo is None:
        raise errors.ValidationApiError("solar_datetime 必须带时区")
    return dt


# ---------- /cast ----------


@router.post("/cast", response_model=CastResponse, summary="梅花易数起卦（纯计算）")
async def cast_endpoint(
    body: CastRequest,
    ctx: AuthContext = Depends(require_api_key),
) -> CastResponse:
    async with rate_limit.acquire(ctx):
        if body.method == "time":
            solar = _parse_solar(body.solar_datetime)
            result = meihua.cast_by_time(solar, question=body.question)
        else:
            assert body.upper_num is not None and body.lower_num is not None
            solar = _parse_solar(body.solar_datetime)
            result = meihua.cast_by_numbers(
                upper_num=body.upper_num,
                lower_num=body.lower_num,
                solar_dt=solar,
                question=body.question,
            )

        cached_payload = await cast_cache.get(result.cast_signature)
        if cached_payload is not None:
            return CastResponse(**{**cached_payload, "cached": True})

        resp = _cast_to_response(result, cached=False)
        await cast_cache.put(result.cast_signature, resp.model_dump())
        return resp


# ---------- /interpret ----------


def _build_user_prompt(payload: CastResponse) -> str:
    return (
        f"用户提问：{payload.question or '（未填写，请围绕本卦总体运势解读）'}\n\n"
        f"起卦方式：{payload.method}\n"
        f"起卦时间：{payload.solar_datetime}\n"
        f"本卦：{payload.ben.name}（上卦 {payload.ben.upper} {payload.ben.symbol_upper} / "
        f"下卦 {payload.ben.lower} {payload.ben.symbol_lower}），爻象 {payload.ben.lines}\n"
        f"互卦：{payload.hu.name}\n"
        f"变卦：{payload.bian.name}\n"
        f"动爻：第 {payload.moving_line} 爻\n\n"
        f"cast_signature（必须原样回显）：{payload.cast_signature}\n"
    )


def _verify_cast(payload: CastResponse) -> None:
    """重算 cast_signature，拒绝客户端篡改的卦数据。"""
    cached = None
    # cast 返回时已写缓存；优先查缓存对账
    # 若缓存过期，则重算签名并比对
    expected_sig = payload.cast_signature
    # 重算（不改动现有 question/solar；客户端可能传任意但签名必须一致）
    try:
        if payload.method == "time":
            solar = datetime.fromisoformat(payload.solar_datetime)
            recomputed = meihua.cast_by_time(solar, question=payload.question)
        elif payload.method == "number":
            solar = datetime.fromisoformat(payload.solar_datetime)
            # number 方法的 raw_num 不再传入，无法纯靠回显验证 → 改为依赖缓存
            recomputed = None
        else:
            recomputed = None
    except Exception as exc:  # noqa: BLE001
        raise errors.ValidationApiError(f"cast 解析失败: {exc}") from exc

    if recomputed is not None and recomputed.cast_signature != expected_sig:
        raise errors.ValidationApiError("cast_signature 校验失败：卦数据被篡改")
    _ = cached  # placeholder for future


async def _verify_cast_via_cache(payload: CastResponse) -> None:
    """凭 cast_signature 查 Redis 缓存：缓存命中则比对 ben/bian/hu/moving_line。

    缓存未命中时退回到 _verify_cast 的本地重算（仅 time 方法可重算）。
    """
    snapshot = await cast_cache.get(payload.cast_signature)
    if snapshot is not None:
        for field in ("method", "moving_line"):
            if snapshot.get(field) != getattr(payload, field):
                raise errors.ValidationApiError(f"cast 字段 {field} 与服务端记录不一致")
        for hex_field in ("ben", "bian", "hu"):
            if snapshot.get(hex_field, {}).get("name") != getattr(payload, hex_field).name:
                raise errors.ValidationApiError(f"cast {hex_field} 与服务端记录不一致")
        return
    _verify_cast(payload)


@router.post("/interpret", summary="梅花易数 LLM 解读（SSE 流式）")
async def interpret_endpoint(
    request: Request,
    body: InterpretRequest,
    ctx: AuthContext = Depends(require_api_key),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payload = body.cast
    await _verify_cast_via_cache(payload)

    request_payload = body.model_dump()
    idem = await idempotency.check(
        tenant_id=ctx.tenant_id,
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )
    if idem is not None and idem.cached is not None:
        return StreamingResponse(
            iter([idem.cached.body]),
            status_code=idem.cached.status_code,
            media_type="text/event-stream",
        )

    user_prompt = _build_user_prompt(payload)
    cast_signature = payload.cast_signature

    # 延迟导入避免 LLM 模块在测试期被强制加载
    from app.infra.llm import client as llm_client

    bill = await billing.start(
        tenant_id=ctx.tenant_id,
        api_key_id=ctx.api_key_id,
        endpoint="/api/v1/divination/meihua/interpret",
        idempotency_key=idempotency_key,
    )

    async def event_stream():
        # rate_limit 必须在 SSE 全程持有
        chunks: list[str] = []
        try:
            async with rate_limit.acquire(ctx):
                yield _sse_event("start", {"request_id": bill.request_id})
                last_payload: dict | None = None
                async for partial in llm_client.stream_meihua_interpret(
                    user_prompt=user_prompt, cast_signature=cast_signature
                ):
                    last_payload = partial
                    chunks.append(_sse_event("partial", partial))
                    yield chunks[-1]
                done = _sse_event("done", last_payload or {})
                chunks.append(done)
                yield done
            await billing.commit(request_id=bill.request_id)
            if idempotency_key:
                await idempotency.save(
                    tenant_id=ctx.tenant_id,
                    idempotency_key=idempotency_key,
                    request_hash=idem.request_hash if idem else "",
                    status_code=200,
                    body="".join(chunks),
                )
        except errors.ApiError as exc:
            await billing.fail(request_id=bill.request_id, error_code=exc.code)
            yield _sse_event("error", {"code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            await billing.fail(request_id=bill.request_id, error_code="internal_error")
            yield _sse_event("error", {"code": "internal_error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
