from PyQt5.QtWidgets import QSizePolicy

from ui.main_window_shell_ops import (
    calculate_default_center_splitter_sizes,
    calculate_default_window_geometry,
    configure_splitter_pane,
    resolve_locked_dock_width,
)


def test_calculate_default_window_geometry_uses_expected_ratio():
    geometry = calculate_default_window_geometry(1920, 1080)

    assert geometry == (192, 108, 1536, 864)


def test_resolve_locked_dock_width_prefers_current_width_when_available():
    assert resolve_locked_dock_width(360, 320) == 360


def test_resolve_locked_dock_width_falls_back_to_minimum_width():
    assert resolve_locked_dock_width(0, 320) == 320


def test_calculate_default_center_splitter_sizes_prefers_track_area():
    editor_height, track_height = calculate_default_center_splitter_sizes(900)

    assert (editor_height, track_height) == (315, 585)


class _FakeSizePolicy:
    def __init__(self):
        self._vertical_policy = QSizePolicy.Expanding

    def setVerticalPolicy(self, policy):
        self._vertical_policy = policy

    def verticalPolicy(self):
        return self._vertical_policy


class _FakeWidget:
    def __init__(self):
        self._minimum_height = None
        self._size_policy = _FakeSizePolicy()

    def setMinimumHeight(self, value):
        self._minimum_height = value

    def minimumHeight(self):
        return self._minimum_height

    def sizePolicy(self):
        return self._size_policy

    def setSizePolicy(self, policy):
        self._size_policy = policy


def test_configure_splitter_pane_allows_vertical_shrink():
    widget = _FakeWidget()

    configured = configure_splitter_pane(
        widget,
        vertical_policy=QSizePolicy.Ignored,
    )

    assert configured is widget
    assert widget.minimumHeight() == 0
    assert widget.sizePolicy().verticalPolicy() == QSizePolicy.Ignored
