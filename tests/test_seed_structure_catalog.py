from core import seed_music_generator
from core.seed_structure_catalog import MUSIC_STRUCTURE_PRESETS, get_structure_for_bars


def test_get_structure_for_exact_bar_count_returns_copy():
    structure = get_structure_for_bars(16)

    assert structure == MUSIC_STRUCTURE_PRESETS[16]
    assert structure is not MUSIC_STRUCTURE_PRESETS[16]


def test_get_structure_for_smaller_bar_count_truncates_phrases():
    structure = get_structure_for_bars(12)

    assert structure["phrases"] == [4, 4, 4]


def test_get_structure_for_larger_bar_count_extends_last_phrase():
    structure = get_structure_for_bars(20)

    assert structure["phrases"] == [4, 4, 4, 4, 4]


def test_seed_music_generator_keeps_structure_catalog_re_exports():
    assert seed_music_generator.MUSIC_STRUCTURE_PRESETS is MUSIC_STRUCTURE_PRESETS
    assert seed_music_generator.get_structure_for_bars is get_structure_for_bars
