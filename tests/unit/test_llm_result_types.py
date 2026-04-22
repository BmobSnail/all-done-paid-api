"""LLM result schema 单元测试（不依赖真实 pydantic_ai runtime）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.infra.llm.result_types import MeihuaInterpret


def _make_payload(**overrides):
    base = {
        "ben_gua_meaning": "乾为天，刚健中正",
        "bian_gua_meaning": "变卦为姤，一阴始生",
        "hu_gua_meaning": "互卦显示潜在因素",
        "dong_yao_insight": "九五动爻，飞龙在天",
        "advice": "把握时机，审时度势",
        "cast_signature": "abc123",
    }
    base.update(overrides)
    return base


def test_meihua_interpret_roundtrip() -> None:
    m = MeihuaInterpret(**_make_payload())
    assert m.cast_signature == "abc123"
    assert m.model_dump()["ben_gua_meaning"].startswith("乾为天")


def test_meihua_interpret_missing_field() -> None:
    bad = _make_payload()
    del bad["cast_signature"]
    with pytest.raises(ValidationError):
        MeihuaInterpret(**bad)


def test_meihua_interpret_signature_mismatch_detected_by_caller() -> None:
    """schema 本身不校验签名一致性，由调用方（client.py）校验。

    这里只是保证字段可被任意字符串覆盖，调用方拿到后比对。
    """
    m = MeihuaInterpret(**_make_payload(cast_signature="tampered"))
    expected = "abc123"
    assert m.cast_signature != expected  # 调用方应基于此断言拒绝
