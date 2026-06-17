from core import seed_music_generator, seed_track_builders
from core.models import TrackType
from core.seed_generation_planner import build_phrase_plan, build_variant_behavior
from core.seed_generation_utils import get_rng_from_seed
from core.seed_structure_catalog import get_structure_for_bars
from core.seed_style_catalog import SeedMusicStyle, get_style_meta
from core.seed_style_configs import get_style_config


def _build_context(
    *,
    style: SeedMusicStyle = SeedMusicStyle.CLASSIC_8BIT,
    variant_id: str = "default",
    length_bars: int = 8,
    dance_harmony_start_bar: int = 0,
):
    rng = get_rng_from_seed(f"track-builder-{style.value}-{variant_id}-{length_bars}")
    style_config = get_style_config(style)
    root_midi, _mode_name, scale_offsets = style_config.get_scale_choices(rng)
    structure = get_structure_for_bars(length_bars)
    intro_bars = 2 if length_bars >= 8 else 0
    phrase_plan = build_phrase_plan(length_bars, intro_bars, structure["phrases"])
    progression = style_config.get_chord_progression_templates(rng)[0]
    bars_progression = tuple(progression[i % len(progression)] for i in range(length_bars))
    variant_behavior = build_variant_behavior(style, variant_id, rng, length_bars)

    return seed_track_builders.TrackBuildContext(
        bass_rng=rng,
        harmony_rng=rng,
        drum_rng=rng,
        style=style,
        variant_id=variant_id,
        style_params=style_config.style_params,
        style_config=style_config,
        phrase_plan=phrase_plan,
        length_bars=length_bars,
        beats_per_bar=4.0,
        beat_duration=60.0 / get_style_meta(style)["default_bpm"],
        bars_progression=bars_progression,
        root_midi=root_midi,
        scale_offsets=tuple(scale_offsets),
        quiet_bars=variant_behavior.quiet_bars,
        dance_harmony_start_bar=dance_harmony_start_bar,
        drum_density=5,
    )


def test_build_bass_track_returns_none_when_disabled():
    context = _build_context()

    assert seed_track_builders.build_bass_track(context, enable_bass=False) is None


def test_build_bass_track_creates_note_track_when_enabled():
    context = _build_context(style=SeedMusicStyle.CALM)

    bass_track = seed_track_builders.build_bass_track(context, enable_bass=True)

    assert bass_track is not None
    assert bass_track.track_type == TrackType.NOTE_TRACK
    assert bass_track.notes


def test_build_harmony_track_respects_dance_start_bar():
    context = _build_context(
        style=SeedMusicStyle.DANCE,
        dance_harmony_start_bar=2,
    )

    harmony_track = seed_track_builders.build_harmony_track(context, enable_harmony=True)

    assert harmony_track is not None
    assert harmony_track.notes
    assert min(note.start_time for note in harmony_track.notes) >= (
        context.dance_harmony_start_bar * context.beats_per_bar * context.beat_duration
    )


def test_build_drum_track_creates_events_and_applies_style_volume():
    context = _build_context(style=SeedMusicStyle.DANCE)

    drum_track = seed_track_builders.build_drum_track(
        context,
        drum_boost=0.2,
        enable_drums=True,
    )

    assert drum_track is not None
    assert drum_track.track_type == TrackType.DRUM_TRACK
    assert drum_track.drum_events
    assert drum_track.volume == 1.4


def test_seed_music_generator_keeps_track_builder_re_exports():
    assert seed_music_generator.TrackBuildContext is seed_track_builders.TrackBuildContext
    assert seed_music_generator.build_bass_track is seed_track_builders.build_bass_track
    assert seed_music_generator.build_harmony_track is seed_track_builders.build_harmony_track
    assert seed_music_generator.build_drum_track is seed_track_builders.build_drum_track
