from core import seed_music_generator
from core.models import ADSRParams, WaveformType
from core.seed_style_catalog import (
    SeedMusicStyle,
    StyleParams,
    clear_style_runtime_override,
    set_style_runtime_override,
)
from core.seed_style_configs import (
    BattleStyleConfig,
    Classic8bitStyleConfig,
    WorkshopStyleConfig,
    get_style_config,
)


def test_get_style_config_returns_expected_config_classes():
    assert isinstance(get_style_config(SeedMusicStyle.CLASSIC_8BIT), Classic8bitStyleConfig)
    assert isinstance(get_style_config(SeedMusicStyle.BATTLE), BattleStyleConfig)
    assert isinstance(get_style_config(SeedMusicStyle.WORKSHOP), WorkshopStyleConfig)


def test_get_style_config_uses_runtime_overridden_style_params():
    style = SeedMusicStyle.WORKSHOP
    params = StyleParams(
        melody_waveform=WaveformType.SQUARE,
        melody_duty=0.55,
        melody_adsr=ADSRParams(attack=0.02, decay=0.1, sustain=0.7, release=0.2),
        bass_waveform=WaveformType.TRIANGLE,
        bass_duty=0.45,
        bass_adsr=ADSRParams(attack=0.01, decay=0.15, sustain=0.8, release=0.25),
        harmony_waveform=WaveformType.SAWTOOTH,
        harmony_duty=0.4,
        harmony_adsr=ADSRParams(attack=0.03, decay=0.2, sustain=0.75, release=0.3),
        drum_velocity_scale=1.1,
    )

    set_style_runtime_override(style, params)
    try:
        config = get_style_config(style)
        assert config.style is style
        assert config.style_params == params
    finally:
        clear_style_runtime_override(style)


def test_seed_music_generator_keeps_style_config_re_exports():
    assert seed_music_generator.get_style_config is get_style_config
    assert seed_music_generator.Classic8bitStyleConfig is Classic8bitStyleConfig
    assert seed_music_generator.BattleStyleConfig is BattleStyleConfig
