import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QScrollArea, QSizePolicy, QWidget

from ui.main_window_shell_ops import (
    MAIN_WINDOW_MIN_HEIGHT,
    MAIN_WINDOW_MIN_WIDTH,
    RIGHT_PANEL_MIN_WIDTH,
    RIGHT_PANEL_NAV_LABELS,
    RIGHT_PANEL_PAGES,
    build_right_panel_shell,
    calculate_default_center_splitter_sizes,
    calculate_default_window_geometry,
    configure_splitter_pane,
    resolve_locked_dock_width,
    wrap_right_panel_page,
)


def _app():
    app = QApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        pytest.skip("A non-GUI QCoreApplication is already active")
    if app is None:
        app = QApplication([])
    return app


def test_calculate_default_window_geometry_uses_expected_ratio():
    geometry = calculate_default_window_geometry(1920, 1080)

    assert geometry == (192, 108, 1536, 864)


def test_main_window_minimum_size_leaves_room_for_right_panel():
    assert MAIN_WINDOW_MIN_WIDTH >= RIGHT_PANEL_MIN_WIDTH + 520
    assert MAIN_WINDOW_MIN_HEIGHT >= 650


def test_resolve_locked_dock_width_prefers_current_width_when_available():
    assert resolve_locked_dock_width(360, 320) == 360


def test_resolve_locked_dock_width_respects_minimum_width():
    assert resolve_locked_dock_width(360, RIGHT_PANEL_MIN_WIDTH) == RIGHT_PANEL_MIN_WIDTH


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


def test_build_right_panel_shell_uses_compact_top_nav():
    app = _app()
    container, stack, buttons = build_right_panel_shell(None)

    try:
        layout = container.layout()
        nav = layout.itemAt(0).widget()
        assert stack.count() == 0
        assert stack.objectName() == "rightPanelStack"
        assert nav.objectName() == "rightPanelNav"
        assert set(buttons) == {key for key, _label in RIGHT_PANEL_PAGES}
        assert buttons["property"].text() == RIGHT_PANEL_NAV_LABELS["property"]
        assert buttons["playback"].minimumHeight() == 30
        assert buttons["playback"].sizePolicy().horizontalPolicy() == QSizePolicy.Expanding
        assert buttons["property"].toolTip() == "属性"
    finally:
        container.close()
        container.deleteLater()
        app.processEvents()


def test_wrap_right_panel_page_uses_resizable_scroll_area():
    app = _app()
    page = QWidget()
    scroll_area = wrap_right_panel_page(page)

    try:
        assert isinstance(scroll_area, QScrollArea)
        assert scroll_area.objectName() == "rightPanelPageScroll"
        assert scroll_area.widget() is page
        assert scroll_area.widgetResizable() is True
        assert scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    finally:
        scroll_area.close()
        scroll_area.deleteLater()
        app.processEvents()
