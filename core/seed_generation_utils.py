"""
Seed 生成辅助工具。

放置与具体风格、结构目录无关的通用 helper，
让生成器主文件专注在项目装配与生成流程本身。
"""

from __future__ import annotations

import random
from typing import List, Tuple, Union


def get_rng_from_seed(seed: Union[int, str]) -> random.Random:
    """
    根据 seed 构造一个独立的随机数发生器。

    - 同一版本中：相同 seed -> 生成结果完全一致。
    - seed 可以是数字或字符串，内部统一转成字符串再 seed。
    """

    rng = random.Random()
    rng.seed(str(seed))
    return rng


def _pick_with_weights(rng: random.Random, choices: List[Tuple[int, float]]) -> int:
    """从 `(value, weight)` 列表中按权重选择一个值。"""

    total = sum(weight for _, weight in choices)
    pick = rng.random() * total
    acc = 0.0
    for value, weight in choices:
        acc += weight
        if pick <= acc:
            return value
    return choices[-1][0]


__all__ = ["_pick_with_weights", "get_rng_from_seed"]
