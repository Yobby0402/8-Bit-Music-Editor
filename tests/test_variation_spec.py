from core.seed_style_catalog import SeedMusicStyle
from core.variation_spec import (
    VariationSpec,
    build_rng_family,
    filter_motifs_by_bank,
    parse_ai_seed_response,
    parse_knob_line,
    variation_salt_from_description,
)


def test_variation_salt_from_description_stable():
    a = variation_salt_from_description("hello")
    b = variation_salt_from_description("hello")
    assert a == b
    assert len(a) == 16
    assert variation_salt_from_description("") == ""


def test_parse_knob_line():
    assert parse_knob_line("K:1,2,3,4") == (1, 2, 3, 4)
    assert parse_knob_line("  k: 0 , 9 , 3 , 1  \n") == (0, 9, 3, 1)
    assert parse_knob_line("not a knob") is None


def test_parse_ai_seed_response():
    raw = "my seed phrase\nK:5,4,3,2"
    seed, knobs = parse_ai_seed_response(raw)
    assert seed == "my seed phrase"
    assert knobs == (5, 4, 3, 2)


def test_build_rng_family_legacy_single_instance():
    spec = VariationSpec()
    assert not spec.is_active()
    fam = build_rng_family("s", SeedMusicStyle.CALM.value, spec)
    assert fam.structure is fam.melody is fam.bass


def test_build_rng_family_multi_streams():
    v = VariationSpec(variation_salt="abc", knobs=(1, 2, 3, 4))
    fam = build_rng_family("seed", SeedMusicStyle.BATTLE.value, v)
    assert fam.structure is not fam.melody
    a = fam.melody.random()
    b = fam.drums.random()
    assert isinstance(a, float) and isinstance(b, float)


def test_filter_motifs_by_bank_non_empty():
    motifs = [[1], [2], [3], [4]]
    out = filter_motifs_by_bank(motifs, bank=1, n_banks=3)
    assert out == [[2]]


def test_variation_spec_knob_default():
    v = VariationSpec(knobs=(9, 8, 7, 6))
    assert v.knob(0) == 9
    assert v.knob(99, 3) == 3
