"""梅花易数起卦算法（时间起卦法，纯 Python 实现）。

参考传统"年月日时"起卦：
- 上卦 = (年地支序号 + 月 + 日) mod 8，余 0 取 8
- 下卦 = (年地支序号 + 月 + 日 + 时辰序号) mod 8，余 0 取 8
- 动爻 = (年地支序号 + 月 + 日 + 时辰序号) mod 6，余 0 取 6

本模块只做"起卦数据"的确定性计算，解读交给 LLM（见 app/infra/llm/client.py）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# 地支 12 支
_EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 八卦：序号 1-8，按先天八卦数 乾1 兑2 离3 震4 巽5 坎6 艮7 坤8
_BAGUA_NAME = {
    1: "乾", 2: "兑", 3: "离", 4: "震",
    5: "巽", 6: "坎", 7: "艮", 8: "坤",
}
_BAGUA_SYMBOL = {
    1: "☰", 2: "☱", 3: "☲", 4: "☳",
    5: "☴", 6: "☵", 7: "☶", 8: "☷",
}
# 八卦对应的阴阳线（从下到上 3 位，1=阳 0=阴）
_BAGUA_LINES = {
    1: [1, 1, 1],   # 乾
    2: [1, 1, 0],   # 兑
    3: [1, 0, 1],   # 离
    4: [1, 0, 0],   # 震
    5: [0, 1, 1],   # 巽
    6: [0, 1, 0],   # 坎
    7: [0, 0, 1],   # 艮
    8: [0, 0, 0],   # 坤
}

CastMethod = Literal["time", "number", "manual"]


@dataclass(frozen=True, slots=True)
class Gua:
    """单卦（3 爻）。"""

    num: int  # 1-8
    name: str
    symbol: str
    lines: list[int]  # 从下到上 3 位

    @classmethod
    def from_num(cls, num: int) -> "Gua":
        n = ((num - 1) % 8) + 1
        return cls(num=n, name=_BAGUA_NAME[n], symbol=_BAGUA_SYMBOL[n], lines=list(_BAGUA_LINES[n]))


@dataclass(frozen=True, slots=True)
class Hexagram:
    """六爻卦：上卦 + 下卦，共 6 爻（从下到上：下卦 3 爻 + 上卦 3 爻）。"""

    upper: Gua
    lower: Gua
    lines: list[int]  # 长度 6，从下到上

    @classmethod
    def from_upper_lower(cls, upper: Gua, lower: Gua) -> "Hexagram":
        return cls(upper=upper, lower=lower, lines=lower.lines + upper.lines)

    @property
    def name(self) -> str:
        return f"{self.upper.name}{self.lower.name}"


@dataclass(frozen=True, slots=True)
class CastResult:
    """起卦结果：本卦 / 变卦 / 互卦 / 动爻 + 签名。"""

    method: CastMethod
    solar_datetime: str  # ISO8601
    question: str | None

    # 计算输入
    upper_num_raw: int
    lower_num_raw: int
    moving_line_raw: int

    # 产出
    ben: Hexagram
    bian: Hexagram
    hu: Hexagram
    moving_line: int  # 1-6，从下到上
    cast_signature: str  # 起卦不可变签名，供 LLM 回显校验


def _year_branch_index(year: int) -> int:
    """返回年的地支序号，1=子，12=亥。

    约定：公元 4 年为子年（子=1）。
    """
    # 公元 4 年是子年（甲子）。index = ((year - 4) % 12) + 1
    return ((year - 4) % 12) + 1


def _flip_line(lines: list[int], idx: int) -> list[int]:
    """把第 idx 位（1-based，从下到上）取反。"""
    out = list(lines)
    out[idx - 1] = 1 - out[idx - 1]
    return out


def _hu_gua(lines: list[int]) -> Hexagram:
    """互卦：取本卦的 2-4 爻作下卦，3-5 爻作上卦。"""
    lower_lines = lines[1:4]  # 2,3,4（0-based index 1..3）
    upper_lines = lines[2:5]  # 3,4,5
    lower_num = _lines_to_num(lower_lines)
    upper_num = _lines_to_num(upper_lines)
    return Hexagram.from_upper_lower(Gua.from_num(upper_num), Gua.from_num(lower_num))


def _lines_to_num(lines: list[int]) -> int:
    """三爻阴阳线映射回 1-8 卦号。"""
    for num, pat in _BAGUA_LINES.items():
        if pat == lines:
            return num
    raise ValueError(f"invalid gua lines: {lines}")


def _compute_signature(payload: dict) -> str:
    import json

    s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def cast_by_time(solar_dt: datetime, question: str | None = None) -> CastResult:
    """时间起卦法。solar_dt 必须带时区。"""
    year = solar_dt.year
    month = solar_dt.month
    day = solar_dt.day
    hour = solar_dt.hour
    # 时辰：子时 23:00-00:59=1，丑时 1:00-2:59=2 ...
    hour_branch = ((hour + 1) // 2) % 12 + 1  # 返回 1-12
    year_branch = _year_branch_index(year)

    upper_raw = year_branch + month + day
    lower_raw = year_branch + month + day + hour_branch
    moving_raw = lower_raw

    upper = Gua.from_num(upper_raw)
    lower = Gua.from_num(lower_raw)
    ben = Hexagram.from_upper_lower(upper, lower)

    moving = ((moving_raw - 1) % 6) + 1
    bian_lines = _flip_line(ben.lines, moving)
    bian_lower = Gua.from_num(_lines_to_num(bian_lines[0:3]))
    bian_upper = Gua.from_num(_lines_to_num(bian_lines[3:6]))
    bian = Hexagram.from_upper_lower(bian_upper, bian_lower)

    hu = _hu_gua(ben.lines)

    sig_payload = {
        "method": "time",
        "solar": solar_dt.isoformat(),
        "ben": ben.name,
        "ben_lines": ben.lines,
        "bian": bian.name,
        "hu": hu.name,
        "moving_line": moving,
    }
    return CastResult(
        method="time",
        solar_datetime=solar_dt.isoformat(),
        question=question,
        upper_num_raw=upper_raw,
        lower_num_raw=lower_raw,
        moving_line_raw=moving_raw,
        ben=ben,
        bian=bian,
        hu=hu,
        moving_line=moving,
        cast_signature=_compute_signature(sig_payload),
    )


def cast_by_numbers(
    upper_num: int, lower_num: int, solar_dt: datetime, question: str | None = None
) -> CastResult:
    """数字起卦法：用户给两个数字，分别取模得上/下卦。"""
    upper = Gua.from_num(upper_num)
    lower = Gua.from_num(lower_num)
    ben = Hexagram.from_upper_lower(upper, lower)
    moving_raw = upper_num + lower_num
    moving = ((moving_raw - 1) % 6) + 1
    bian_lines = _flip_line(ben.lines, moving)
    bian_lower = Gua.from_num(_lines_to_num(bian_lines[0:3]))
    bian_upper = Gua.from_num(_lines_to_num(bian_lines[3:6]))
    bian = Hexagram.from_upper_lower(bian_upper, bian_lower)
    hu = _hu_gua(ben.lines)

    sig_payload = {
        "method": "number",
        "upper_num": upper_num,
        "lower_num": lower_num,
        "ben": ben.name,
        "ben_lines": ben.lines,
        "bian": bian.name,
        "hu": hu.name,
        "moving_line": moving,
    }
    return CastResult(
        method="number",
        solar_datetime=solar_dt.isoformat(),
        question=question,
        upper_num_raw=upper_num,
        lower_num_raw=lower_num,
        moving_line_raw=moving_raw,
        ben=ben,
        bian=bian,
        hu=hu,
        moving_line=moving,
        cast_signature=_compute_signature(sig_payload),
    )
