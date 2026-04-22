"""Provider 抽象：统一不同 LLM 厂商的差异，为未来切换 LiteLLM Proxy 留口。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    """模型档位。业务按 plan 映射到具体档位，档位再映射到模型名。"""

    PRIMARY = "primary"
    FALLBACK = "fallback"
    CHEAP = "cheap"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    name: str
    base_url: str
    api_keys: list[str]
    model_primary: str
    model_fallback: str
    model_cheap: str
    timeout_seconds: int
    max_retries: int
    max_concurrency: int
    stream_timeout_seconds: int

    def pick_model(self, tier: ModelTier) -> str:
        return {
            ModelTier.PRIMARY: self.model_primary,
            ModelTier.FALLBACK: self.model_fallback,
            ModelTier.CHEAP: self.model_cheap,
        }[tier]
