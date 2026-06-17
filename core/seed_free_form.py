"""
自由编排：弱化固定乐句划分与循环和声进行，增加程序化动机片段。

仅在 ``VariationSpec.free_form_layout`` 为真时由 ``seed_music_generator`` 调用。
"""

from __future__ import annotations

import random
from typing import List, Sequence, Tuple


def random_intro_bars(length_bars: int, rng: random.Random) -> int:
    """Intro 小节数：0～2，随总长略约束。"""
    if length_bars < 4:
        return 0
    return rng.randint(0, min(2, max(1, length_bars // 6)))


def random_phrase_partition(main_bars: int, rng: random.Random) -> List[int]:
    """
    将 main_bars（不含 Intro）拆成若干乐句长度，每段 2～8 小节，总和严格等于 main_bars。
    """
    if main_bars <= 0:
        return []
    parts: List[int] = []
    rem = main_bars
    while rem > 0:
        if rem <= 8:
            if rem == 1 and parts:
                parts[-1] += 1
            else:
                parts.append(rem)
            break
        lo, hi = 2, min(8, rem - 2)
        chunk = rem if lo > hi else rng.randint(lo, hi)
        parts.append(chunk)
        rem -= chunk
    return parts


def merge_progression_degrees(templates: Sequence[Sequence[int]], rng: random.Random) -> List[int]:
    """把所有和弦进行模板里的级数摊平，供每小节随机抽取。"""
    pool: List[int] = []
    for t in templates:
        pool.extend(int(x) for x in t)
    if not pool:
        return [1, 4, 5, 1]
    rng.shuffle(pool)
    return pool


def bars_progression_free(
    length_bars: int,
    degree_pool: List[int],
    rng: random.Random,
) -> List[int]:
    """每小节独立随机一个和弦级数（仍在调性体系内由生成器解释）。"""
    if not degree_pool:
        degree_pool = [1, 4, 5, 6, 2, 3]
    return [rng.choice(degree_pool) for _ in range(length_bars)]


def expand_motifs_with_procedural_fragments(
    motifs: List[List[Tuple[int, float]]],
    rng: random.Random,
    extra: int = 14,
) -> List[List[Tuple[int, float]]]:
    """追加若干程序化短动机（相对度数 + 拍长），扩充可选池。"""
    out: List[List[Tuple[int, float]]] = list(motifs)
    for _ in range(extra):
        piece: List[Tuple[int, float]] = []
        t = 0.0
        rel = 0
        while t < 4.0 - 1e-6 and len(piece) < 10:
            rel += rng.choice([-3, -2, -1, 0, 1, 2, 3, 4])
            rel %= 7
            dur = float(rng.choice([0.25, 0.5, 0.5, 1.0, 1.0, 1.5]))
            if t + dur > 4.0:
                dur = max(0.25, 4.0 - t)
            piece.append((rel, dur))
            t += dur
        if len(piece) >= 2:
            out.append(piece)
    return out


__all__ = [
    "bars_progression_free",
    "expand_motifs_with_procedural_fragments",
    "merge_progression_degrees",
    "random_intro_bars",
    "random_phrase_partition",
]
