from types import SimpleNamespace

from core.seed_style_catalog import SeedMusicStyle
from ui.main_window_seed_ops import (
    build_seed_generation_request,
    build_seed_generation_settings,
    build_seed_status_message,
    build_seed_window_title,
)


def make_selection(**overrides):
    data = {
        "seed": "minecraft",
        "length_bars": 16,
        "style": SeedMusicStyle.BATTLE,
        "variant_id": "boss",
        "use_harmony": True,
        "use_drums": True,
        "length_index": 0,
        "style_index": 2,
        "variant_index": 1,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_build_seed_generation_settings_keeps_dialog_state():
    selection = make_selection(seed="demo", use_harmony=False, variant_index=3)

    settings = build_seed_generation_settings(selection)

    assert settings == {
        "seed": "demo",
        "length_index": 0,
        "style_index": 2,
        "variant_index": 3,
        "harmony": False,
        "drums": True,
    }


def test_build_seed_generation_request_returns_normalized_request():
    selection = make_selection(seed="  demo-seed  ", variant_id="")

    request = build_seed_generation_request(selection)

    assert request is not None
    assert request.seed == "demo-seed"
    assert request.variant_id == "default"
    assert request.style is SeedMusicStyle.BATTLE


def test_build_seed_generation_request_returns_none_for_blank_seed():
    selection = make_selection(seed="   ")

    assert build_seed_generation_request(selection) is None


def test_build_seed_text_helpers():
    assert build_seed_window_title("8bit", "demo") == "8bit - Seed: demo"
    assert build_seed_status_message("demo") == "已基于 Seed “demo” 生成一个新的项目"
