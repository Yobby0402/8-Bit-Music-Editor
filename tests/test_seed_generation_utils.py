from core import seed_music_generator
from core.seed_generation_utils import _pick_with_weights, get_rng_from_seed


def test_get_rng_from_seed_is_deterministic_and_normalizes_seed_type():
    rng_a = get_rng_from_seed(123)
    rng_b = get_rng_from_seed("123")

    values_a = [rng_a.random() for _ in range(5)]
    values_b = [rng_b.random() for _ in range(5)]

    assert values_a == values_b


def test_pick_with_weights_returns_only_nonzero_weight_choice():
    rng = get_rng_from_seed("weights-demo")

    choice = _pick_with_weights(rng, [(1, 0.0), (2, 1.0), (3, 0.0)])

    assert choice == 2


def test_seed_music_generator_keeps_generation_utils_re_exports():
    assert seed_music_generator.get_rng_from_seed is get_rng_from_seed
    assert seed_music_generator._pick_with_weights is _pick_with_weights
