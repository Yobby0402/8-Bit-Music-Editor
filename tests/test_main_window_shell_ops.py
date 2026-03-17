from ui.main_window_shell_ops import (
    calculate_default_window_geometry,
    resolve_locked_dock_width,
)


def test_calculate_default_window_geometry_uses_expected_ratio():
    geometry = calculate_default_window_geometry(1920, 1080)

    assert geometry == (192, 108, 1536, 864)


def test_resolve_locked_dock_width_prefers_current_width_when_available():
    assert resolve_locked_dock_width(360, 320) == 360


def test_resolve_locked_dock_width_falls_back_to_minimum_width():
    assert resolve_locked_dock_width(0, 320) == 320
