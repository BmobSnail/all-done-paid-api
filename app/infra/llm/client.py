"""LLM 客户端门面：把 Agent + 治理 + 可观测包成业务侧易用 API。

业务层仅需：
    from app.infra.llm import client
    result = await client.run_meihua_interpret(prompt, cast_signature)
    async for partial in client.stream_meihua_interpret(prompt, cast_signature):
        ...
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core import errors
from app.infra.llm import agents as agent_factory
from app.infra.llm import observability as obs
from app.infra.llm.provider import ModelTier
from app.infra.llm.result_types import MeihuaInterpret
from app.infra.llm.retry import (
    ProviderCallError,
    call_with_fallback,
    init_governance,
)
from app.infra.llm.siliconflow import build_siliconflow_config

_initialised = False


def init() -> None:
    """应用启动调用：初始化治理层（信号量 / 熔断）+ 可观测。"""
    global _initialised
    if _initialised:
        return
    cfg = build_siliconflow_config()
    init_governance(cfg.max_concurrency)
    obs.setup()
    _initialised = True


async def run_meihua_interpret(
    *, user_prompt: str, cast_signature: str
) -> MeihuaInterpret:
    """同步阻塞版（一次返回完整结构）。失败自动 fallback。"""
    if not _initialised:
        init()
    cfg = build_siliconflow_config()

    def factory(tier: ModelTier):
        async def _call() -> MeihuaInterpret:
            agent = agent_factory.build_meihua_agent(tier)
            try:
                with obs.span("llm.meihua.interpret", tier=tier.value):
                    result = await agent.run(user_prompt)
            except Exception as exc:  # noqa: BLE001
                raise ProviderCallError(f"{tier.value}: {exc}") from exc
            if result.output.cast_signature != cast_signature:
                raise errors.ValidationApiError(
                    "LLM output cast_signature mismatch",
                    expected=cast_signature,
                )
            return result.output

        return _call

    return await call_with_fallback(
        max_retries=cfg.max_retries,
        timeout_seconds=cfg.timeout_seconds,
        tiers=[ModelTier.PRIMARY, ModelTier.FALLBACK, ModelTier.CHEAP],
        func_factory=factory,
    )


async def stream_meihua_interpret(
    *, user_prompt: str, cast_signature: str
) -> AsyncIterator[dict]:
    """流式版：按 Pydantic AI stream_output 逐步产出 partial 结果。

    注意：流式不做 fallback（一旦首 token 出来再失败代价太高），仅走 primary tier，
    失败由上层（业务层）兜底提示。
    """
    if not _initialised:
        init()
    agent = agent_factory.build_meihua_agent(ModelTier.PRIMARY)

    with obs.span("llm.meihua.interpret.stream", tier=ModelTier.PRIMARY.value):
        async with agent.run_stream(user_prompt) as result:
            last: dict | None = None
            async for partial in result.stream_output():
                # partial 是 dict/TypedDict，可能字段不全
                if isinstance(partial, MeihuaInterpret):
                    partial_dict = partial.model_dump()
                else:
                    partial_dict = (
                        partial.model_dump() if hasattr(partial, "model_dump") else dict(partial)
                    )
                last = partial_dict
                yield partial_dict

    # 签名校验放最后
    if last is None or last.get("cast_signature") != cast_signature:
        raise errors.ValidationApiError(
            "LLM stream output cast_signature mismatch",
            expected=cast_signature,
            got=(last or {}).get("cast_signature"),
        )
