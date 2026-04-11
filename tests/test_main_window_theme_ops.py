from ui.main_window_theme_ops import (
    MainWindowThemeOpsMixin,
    build_main_background_style,
    has_significant_size_change,
    sync_locked_dock_width,
)
from ui.theme import theme_manager


class FakeDock:
    def __init__(self):
        self.minimum_width = None
        self.maximum_width = None

    def setMinimumWidth(self, value):
        self.minimum_width = value

    def setMaximumWidth(self, value):
        self.maximum_width = value


class FakeSize:
    def __init__(self, width, height):
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


def test_build_main_background_style_returns_plain_color_without_gradient():
    style = build_main_background_style(
        "#FAFAFA",
        gradient_enabled=False,
        gradient_color2="#FFFFFF",
        gradient_mode="diagonal",
    )

    assert style == "background-color: #FAFAFA;"


def test_build_main_background_style_supports_known_gradient_modes():
    style = build_main_background_style(
        "#111111",
        gradient_enabled=True,
        gradient_color2="#222222",
        gradient_mode="center",
    )

    assert "background-color: #111111;" in style
    assert "qradialgradient" in style
    assert "#222222" in style


def test_sync_locked_dock_width_updates_all_docks():
    first = FakeDock()
    second = FakeDock()

    result = sync_locked_dock_width((first, None, second), 320, 360)

    assert result == 360
    assert first.minimum_width == 360
    assert first.maximum_width == 360
    assert second.minimum_width == 360
    assert second.maximum_width == 360


def test_sync_locked_dock_width_ignores_invalid_or_same_width():
    dock = FakeDock()

    unchanged = sync_locked_dock_width((dock,), 320, 320)
    invalid = sync_locked_dock_width((dock,), 320, 0)

    assert unchanged == 320
    assert invalid == 320
    assert dock.minimum_width is None
    assert dock.maximum_width is None


def test_has_significant_size_change_respects_threshold():
    current_size = FakeSize(800, 600)
    similar_size = FakeSize(808, 605)
    changed_size = FakeSize(820, 600)

    assert has_significant_size_change(current_size, similar_size) is False
    assert has_significant_size_change(current_size, changed_size) is True


class FakeThemeWindow(MainWindowThemeOpsMixin):
    def __init__(self):
        self.refresh_calls = []
        self.repaint_calls = 0
        self.settings_manager = type(
            "SettingsManager",
            (),
            {"get_playhead_refresh_interval": lambda self: 33},
        )()
        self.update_timer = None
        self.sequence_widget = None
        self.unified_editor = None
        self.oscilloscope_widget = None

    def apply_theme(self):
        self.applied_theme = theme_manager.current_theme

    def apply_display_settings_from_settings(self, *args, **kwargs):
        self.display_settings_applied = True

    def refresh_ui(self, preserve_selection=False, force_full_refresh=False):
        self.refresh_calls.append((preserve_selection, force_full_refresh))

    def repaint(self):
        self.repaint_calls += 1


def test_refresh_theme_from_settings_uses_incremental_refresh():
    window = FakeThemeWindow()

    window.refresh_theme_from_settings()

    assert window.refresh_calls == [(True, False)]
    assert window.repaint_calls == 1
