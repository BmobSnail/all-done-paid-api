"""梅花起卦确定性 + cast_signature 强约束单元测试。

不依赖 Redis / DB / pydantic_ai，纯算法层。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import meihua


def _dt(year=2026, month=4, day=22, hour=10) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_cast_by_time_deterministic() -> None:
    a = meihua.cast_by_time(_dt(), question="工作")
    b = meihua.cast_by_time(_dt(), question="工作")
    assert a.cast_signature == b.cast_signature
    assert a.ben.name == b.ben.name
    assert a.moving_line == b.moving_line


def test_cast_signature_changes_when_input_changes() -> None:
    a = meihua.cast_by_time(_dt(hour=10), question="工作")
    b = meihua.cast_by_time(_dt(hour=11), question="工作")
    # 时辰不同 → 下卦/动爻不同 → 签名应不同
    assert a.cast_signature != b.cast_signature


def test_cast_by_numbers_deterministic() -> None:
    a = meihua.cast_by_numbers(upper_num=7, lower_num=3, solar_dt=_dt(), question="财")
    b = meihua.cast_by_numbers(upper_num=7, lower_num=3, solar_dt=_dt(), question="财")
    assert a.cast_signature == b.cast_signature
    assert a.ben.upper.num == 7
    assert a.ben.lower.num == 3


def test_cast_by_numbers_signature_differs_from_time() -> None:
    a = meihua.cast_by_time(_dt())
    b = meihua.cast_by_numbers(upper_num=1, lower_num=1, solar_dt=_dt())
    # method 字段进入签名 payload，应不同
    assert a.cast_signature != b.cast_signature


def test_hexagram_lines_length() -> None:
    r = meihua.cast_by_time(_dt())
    assert len(r.ben.lines) == 6
    assert len(r.bian.lines) == 6
    assert len(r.hu.lines) == 6
    assert 1 <= r.moving_line <= 6


def test_bian_gua_flips_only_moving_line() -> None:
    r = meihua.cast_by_time(_dt())
    diffs = [i for i in range(6) if r.ben.lines[i] != r.bian.lines[i]]
    assert diffs == [r.moving_line - 1]


@pytest.mark.parametrize("hour", [0, 1, 7, 13, 23])
def test_cast_signature_stable_across_hours(hour: int) -> None:
    r = meihua.cast_by_time(_dt(hour=hour))
    # 签名长度恒为 16（前 16 位 sha256）
    assert len(r.cast_signature) == 16
    assert all(c in "0123456789abcdef" for c in r.cast_signature)
