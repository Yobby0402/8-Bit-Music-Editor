from core.models import ADSRParams, WaveformType
from core.seed_style_catalog import (
    SeedMusicStyle,
    StyleParams,
    clear_style_runtime_override,
    get_style_meta,
    get_style_params,
    get_style_variants,
    set_style_runtime_override,
)


def test_style_catalog_has_params_and_meta_for_all_styles():
    for style in SeedMusicStyle:
        params = get_style_params(style)
        meta = get_style_meta(style)

        assert isinstance(params, StyleParams)
        assert meta["default_bpm"] > 0
        assert meta["mood"]
        assert meta["short_desc"]


def test_style_runtime_override_can_replace_and_clear_params():
    style = SeedMusicStyle.CALM
    original = get_style_params(style)
    overridden = StyleParams(
        melody_waveform=WaveformType.SAWTOOTH,
        melody_duty=0.3,
        melody_adsr=ADSRParams(attack=0.01, decay=0.12, sustain=0.6, release=0.2),
        bass_waveform=WaveformType.TRIANGLE,
        bass_duty=0.45,
        bass_adsr=ADSRParams(attack=0.02, decay=0.15, sustain=0.7, release=0.3),
        harmony_waveform=WaveformType.SINE,
        harmony_duty=0.5,
        harmony_adsr=ADSRParams(attack=0.03, decay=0.2, sustain=0.8, release=0.4),
        drum_velocity_scale=0.9,
    )

    set_style_runtime_override(style, overridden)
    try:
        assert get_style_params(style) == overridden
    finally:
        clear_style_runtime_override(style)

    assert get_style_params(style) == original


def test_workshop_style_variants_fall_back_to_default_entry():
    assert get_style_variants(SeedMusicStyle.WORKSHOP) == [
        {
            "id": "default",
            "name": "默认",
            "desc": "",
        }
    ]
