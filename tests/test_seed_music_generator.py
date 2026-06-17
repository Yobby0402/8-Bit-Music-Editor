from core.models import TrackType
from core.seed_music_generator import generate_simple_project_from_seed
from core.seed_style_catalog import SeedMusicStyle
from core.variation_spec import VariationSpec


def test_seed_generation_is_deterministic_for_same_inputs():
    project_a = generate_simple_project_from_seed(
        seed="minecraft",
        length_bars=16,
        style=SeedMusicStyle.BATTLE,
    )
    project_b = generate_simple_project_from_seed(
        seed="minecraft",
        length_bars=16,
        style=SeedMusicStyle.BATTLE,
    )

    assert project_a.to_dict() == project_b.to_dict()


def test_variation_spec_changes_deterministic_output():
    p1 = generate_simple_project_from_seed(
        "same-seed",
        length_bars=8,
        style=SeedMusicStyle.CLASSIC_8BIT,
    )
    p2 = generate_simple_project_from_seed(
        "same-seed",
        length_bars=8,
        style=SeedMusicStyle.CLASSIC_8BIT,
        variation=VariationSpec(variation_salt="extra-salt", knobs=(9, 9, 0, 0)),
    )
    assert p1.to_dict() != p2.to_dict()


def test_seed_generation_can_disable_optional_tracks():
    project = generate_simple_project_from_seed(
        seed="calm-demo",
        length_bars=8,
        style=SeedMusicStyle.CALM,
        enable_harmony=False,
        enable_drums=False,
    )

    assert [track.name for track in project.tracks] == [
        "Seed 主旋律",
        "Seed 低音",
    ]
    assert all(track.track_type == TrackType.NOTE_TRACK for track in project.tracks)
