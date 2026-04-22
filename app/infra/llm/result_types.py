"""LLM 输出的强类型 schema。

cast_signature 作为强约束字段：Agent 必须回显起卦数据的 hash，
业务层在拿到结果后会核对，不一致则拒绝（防 LLM 幻觉改卦）。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class MeihuaInterpret(BaseModel):
    """梅花易数 LLM 解读结果。"""

    ben_gua_meaning: str = Field(..., description="本卦卦义与象征")
    bian_gua_meaning: str = Field(..., description="变卦卦义与发展方向")
    hu_gua_meaning: str = Field(..., description="互卦卦义与潜在因素")
    dong_yao_insight: str = Field(..., description="动爻分析与关键转折")
    advice: str = Field(..., description="针对提问的综合建议")
    cast_signature: str = Field(
        ...,
        description=(
            "起卦数据的不可变签名。必须原样回显传入的 cast_signature，"
            "不得重新计算或修改。后端会核对，若不一致则拒绝结果。"
        ),
    )


class SixGodInterpret(BaseModel):
    """小六壬解读（Phase 4 可选扩展，先占位）。"""

    palace_name: str
    palace_meaning: str
    advice: str
    cast_signature: str
