"""Pydantic AI Agent 工厂。

对业务层暴露：
- build_meihua_agent(tier=...) → Agent
- build_six_god_agent(tier=...) → Agent

工厂内部使用 OpenAIChatModel + OpenAIProvider（OpenAI 兼容协议，指向 SiliconFlow）。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.infra.llm.provider import ModelTier, ProviderConfig
from app.infra.llm.result_types import MeihuaInterpret, SixGodInterpret
from app.infra.llm.siliconflow import KeyPool, build_siliconflow_config

_MEIHUA_SYSTEM_PROMPT = """你是一位精通梅花易数的易学解读师。

严格要求：
1. 你必须基于用户提供的起卦结果（本卦/互卦/变卦/动爻）进行解读，禁止重新起卦或篡改卦名/卦序/动爻位置。
2. 结合用户的具体提问，给出针对性的解读与建议，避免泛泛空话。
3. 必须在 cast_signature 字段中原样回显用户传入的起卦签名，不得修改。
4. 语气平实，不使用迷信、恐吓式表达；保持专业与尊重。
5. 所有字段必须用中文回答。"""

_SIX_GOD_SYSTEM_PROMPT = """你是一位精通小六壬的易学解读师。
严格要求同梅花易数：基于给定宫位解读、原样回显 cast_signature、中文回答。"""


def _build_model(cfg: ProviderConfig, pool: KeyPool, tier: ModelTier) -> OpenAIChatModel:
    return OpenAIChatModel(
        cfg.pick_model(tier),
        provider=OpenAIProvider(
            base_url=cfg.base_url,
            api_key=pool.next(),
        ),
    )


@lru_cache(maxsize=1)
def _get_pool() -> KeyPool:
    cfg = build_siliconflow_config()
    return KeyPool(cfg.api_keys)


@lru_cache(maxsize=1)
def _get_cfg() -> ProviderConfig:
    return build_siliconflow_config()


def build_meihua_agent(tier: ModelTier = ModelTier.PRIMARY) -> Agent[None, MeihuaInterpret]:
    model = _build_model(_get_cfg(), _get_pool(), tier)
    return Agent(
        model,
        output_type=MeihuaInterpret,
        system_prompt=_MEIHUA_SYSTEM_PROMPT,
    )


def build_six_god_agent(tier: ModelTier = ModelTier.PRIMARY) -> Agent[None, SixGodInterpret]:
    model = _build_model(_get_cfg(), _get_pool(), tier)
    return Agent(
        model,
        output_type=SixGodInterpret,
        system_prompt=_SIX_GOD_SYSTEM_PROMPT,
    )
