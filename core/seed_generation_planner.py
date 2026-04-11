"""
Seed 生成阶段的规划辅助。

集中管理乐句结构分析、风格变体行为和安静小节规划，
让生成器主函数更专注于音符与轨道装配流程。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .seed_style_catalog import SeedMusicStyle


@dataclass(frozen=True)
class VariantBehavior:
    """描述某个风格变体对应的生成期开关。"""

    is_battle_melody: bool = False
    is_battle_drums: bool = False
    is_suspense_dense: bool = False
    is_suspense_sparse: bool = False
    quiet_bars: frozenset[int] = frozenset()


@dataclass(frozen=True)
class PhrasePlan:
    """描述 Intro 之后的乐句布局。"""

    intro_bars: int
    phrase_lengths: tuple[int, ...]
    phrase_starts: tuple[int, ...]

    @property
    def total_phrases(self) -> int:
        return len(self.phrase_lengths)

    def phrase_index_at_bar(self, bar_idx: int) -> int:
        """返回某个绝对小节号对应的乐句索引；Intro 返回 `-1`。"""

        if bar_idx < self.intro_bars or not self.phrase_starts:
            return -1

        adjusted_bar_idx = bar_idx - self.intro_bars
        for index, start in enumerate(self.phrase_starts):
            if index == len(self.phrase_starts) - 1:
                return index
            if start <= adjusted_bar_idx < self.phrase_starts[index + 1]:
                return index
        return len(self.phrase_starts) - 1

    def phrase_role(self, phrase_idx: int) -> str:
        """返回乐句角色；Intro 使用 `intro`。"""

        if phrase_idx < 0:
            return "intro"
        return get_phrase_role(phrase_idx, self.total_phrases)

    def phrase_role_at_bar(self, bar_idx: int) -> str:
        """返回某个绝对小节号对应的乐句角色。"""

        return self.phrase_role(self.phrase_index_at_bar(bar_idx))

    def phrase_start_bar(self, phrase_idx: int) -> int:
        """返回某个乐句对应的绝对起始小节号。"""

        return self.intro_bars + self.phrase_starts[phrase_idx]

    def phrase_length(self, phrase_idx: int) -> int:
        """返回某个乐句的小节数。"""

        return self.phrase_lengths[phrase_idx]

    def phrase_progress_at_bar(self, bar_idx: int, phrase_idx: int | None = None) -> float:
        """返回某个绝对小节号在当前乐句中的进度。"""

        if phrase_idx is None:
            phrase_idx = self.phrase_index_at_bar(bar_idx)

        if phrase_idx < 0:
            return bar_idx / max(1, self.intro_bars) if self.intro_bars else 0.0

        phrase_length = self.phrase_length(phrase_idx)
        if phrase_length <= 0:
            return 0.5
        return (bar_idx - self.phrase_start_bar(phrase_idx)) / phrase_length

    def is_phrase_end(self, bar_idx: int, phrase_idx: int | None = None) -> bool:
        """返回某个绝对小节号是否位于当前乐句末尾。"""

        if phrase_idx is None:
            phrase_idx = self.phrase_index_at_bar(bar_idx)

        if phrase_idx < 0:
            return bool(self.intro_bars) and bar_idx == self.intro_bars - 1

        return bar_idx == self.phrase_start_bar(phrase_idx) + self.phrase_length(phrase_idx) - 1


def chord_root_degree(scale_degree: int) -> int:
    """将和弦级数映射到 0-based 音阶 degree。"""

    return (scale_degree - 1) % 7


def get_phrase_role(phrase_idx: int, total_phrases: int) -> str:
    """返回乐句在整体结构中的角色。"""

    if total_phrases == 1:
        return "statement"
    if total_phrases == 2:
        return "question" if phrase_idx == 0 else "answer"
    if total_phrases == 3:
        roles = ["statement", "development", "variation"]
        return roles[min(phrase_idx, 2)]
    if total_phrases == 4:
        roles = ["statement", "development", "variation", "resolution"]
        return roles[min(phrase_idx, 3)]
    roles = ["statement", "development", "variation", "resolution"]
    return roles[phrase_idx % 4]


def build_phrase_plan(length_bars: int, intro_bars: int, phrase_lengths: Sequence[int]) -> PhrasePlan:
    """根据总长度与 Intro 长度构建乐句规划。"""

    normalized_lengths = list(phrase_lengths)
    phrase_starts: list[int] = []
    current_bar = 0
    for phrase_len in normalized_lengths:
        phrase_starts.append(current_bar)
        current_bar += phrase_len

    main_bars = max(0, length_bars - intro_bars)
    if phrase_starts and normalized_lengths:
        last_start = phrase_starts[-1]
        target_last_length = max(0, main_bars - last_start)
        if target_last_length and last_start + normalized_lengths[-1] != main_bars:
            normalized_lengths[-1] = target_last_length

    return PhrasePlan(
        intro_bars=intro_bars,
        phrase_lengths=tuple(normalized_lengths),
        phrase_starts=tuple(phrase_starts),
    )


def build_variant_behavior(
    style: SeedMusicStyle,
    variant_id: str,
    rng: random.Random,
    length_bars: int,
) -> VariantBehavior:
    """根据风格与变体，返回生成期需要使用的行为开关。"""

    is_battle_melody = style == SeedMusicStyle.BATTLE and variant_id == "battle_melody"
    is_battle_drums = style == SeedMusicStyle.BATTLE and variant_id == "battle_drums"
    is_suspense_dense = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_dense"
    is_suspense_sparse = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_sparse"

    quiet_bars: set[int] = set()
    if style == SeedMusicStyle.SUSPENSE:
        base_prob = 0.4
        if is_suspense_dense:
            base_prob = 0.12
        elif is_suspense_sparse:
            base_prob = 0.75

        for bar_idx in range(length_bars):
            if bar_idx % 4 in (1, 3) and rng.random() < base_prob:
                quiet_bars.add(bar_idx)

    return VariantBehavior(
        is_battle_melody=is_battle_melody,
        is_battle_drums=is_battle_drums,
        is_suspense_dense=is_suspense_dense,
        is_suspense_sparse=is_suspense_sparse,
        quiet_bars=frozenset(quiet_bars),
    )


__all__ = [
    "PhrasePlan",
    "VariantBehavior",
    "build_phrase_plan",
    "build_variant_behavior",
    "chord_root_degree",
    "get_phrase_role",
]
