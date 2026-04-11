import pytest

from core.seed_generation_service import SeedGenerationRequest, generate_seed_project
from core.seed_style_catalog import SeedMusicStyle


def test_seed_generation_request_normalized_strips_seed_and_defaults_variant():
    request = SeedGenerationRequest(
        seed="  demo-seed  ",
        length_bars="16",
        style=SeedMusicStyle.CALM,
        variant_id="",
    )

    normalized = request.normalized()

    assert normalized.seed == "demo-seed"
    assert normalized.length_bars == 16
    assert normalized.variant_id == "default"


def test_generate_seed_project_returns_normalized_request_and_project():
    result = generate_seed_project(
        SeedGenerationRequest(
            seed="  calm-demo  ",
            length_bars=8,
            style=SeedMusicStyle.CALM,
            variant_id="",
            use_harmony=False,
            use_drums=False,
        )
    )

    assert result.request.seed == "calm-demo"
    assert result.request.variant_id == "default"
    assert [track.name for track in result.project.tracks] == [
        "Seed 主旋律",
        "Seed 低音",
    ]


def test_generate_seed_project_rejects_empty_seed():
    with pytest.raises(ValueError, match="seed"):
        generate_seed_project(
            SeedGenerationRequest(
                seed="   ",
                length_bars=8,
                style=SeedMusicStyle.CALM,
            )
        )


def test_generate_seed_project_rejects_non_positive_length():
    with pytest.raises(ValueError, match="length_bars"):
        generate_seed_project(
            SeedGenerationRequest(
                seed="demo",
                length_bars=0,
                style=SeedMusicStyle.CALM,
            )
        )
