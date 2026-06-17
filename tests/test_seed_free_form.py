"""seed_free_form：乐句拆分守恒与随机性边界。"""

import random

import pytest

from core.seed_free_form import random_intro_bars, random_phrase_partition


@pytest.mark.parametrize("main_bars", [1, 4, 7, 8, 16, 23, 31])
def test_random_phrase_partition_sums_to_main_bars(main_bars: int):
    rng = random.Random(42)
    for trial in range(80):
        rng.seed(1000 + trial)
        parts = random_phrase_partition(main_bars, rng)
        assert sum(parts) == main_bars
        for p in parts:
            assert p >= 1


def test_random_intro_bars_within_range():
    rng = random.Random(0)
    for length in range(8, 33):
        for _ in range(50):
            intro = random_intro_bars(length, rng)
            assert 0 <= intro <= 2
            assert intro <= length
