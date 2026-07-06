import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QWidget,
)

from core.models import Track
from ui.playback_settings_widget import PlaybackSettingsWidget
from ui.property_panel_widget import PropertyPanelWidget
from ui.sfx_editor_dialog import SfxEditorWidget
from ui.style_params_widget import StyleParamsWidget


def _app():
    app = QApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        pytest.skip("A non-GUI QCoreApplication is already active")
    if app is None:
        app = QApplication([])
    return app


def _delete_widget(app, widget):
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_property_panel_exposes_shared_inspector_style_hooks():
    app = _app()
    panel = PropertyPanelWidget()

    try:
        assert panel.objectName() == "propertyPanel"
        assert panel.scroll_area.objectName() == "propertyPanelScroll"
        assert panel.scroll_area.frameShape() == QFrame.NoFrame
        assert panel.empty_label.objectName() == "emptyState"
        assert panel.multi_select_label.objectName() == "selectionSummary"

        for group in (
            panel.properties_group,
            panel.track_edit_group,
            panel.batch_edit_group,
            panel.note_effects_group,
            panel.effects_group,
        ):
            assert group.property("inspectorGroup") is True

        inner_titles = {
            group.title()
            for group in panel.findChildren(QGroupBox)
            if group.property("innerGroup") is True
        }
        assert {"ADSR包络", "滤波器", "延迟", "颤音 (Tremolo)"} <= inner_titles
    finally:
        _delete_widget(app, panel)


def test_playback_settings_uses_compact_track_rows():
    app = _app()
    panel = PlaybackSettingsWidget()
    track = Track(name="A very long lead melody track name")

    try:
        panel.set_tracks([track])
        track_id = id(track)
        row_data = panel.track_widgets[track_id]

        assert panel.objectName() == "playbackSettingsPanel"
        assert panel.info_label.objectName() == "panelSummary"
        assert panel.batch_apply_button.property("primaryAction") is True
        assert panel.scroll_area.objectName() == "playbackTrackScroll"
        assert panel.scroll_area.frameShape() == QFrame.NoFrame
        assert row_data["widget"].property("trackVolumeRow") is True
        assert row_data["label"].property("metricPill") is True
        assert row_data["name_label"].minimumWidth() == 0
        assert row_data["name_label"].sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
    finally:
        _delete_widget(app, panel)


def test_style_params_panel_uses_shared_group_and_action_styles():
    app = _app()
    panel = StyleParamsWidget()

    try:
        assert panel.objectName() == "styleParamsPanel"
        assert panel.summary_label.objectName() == "panelSummary"
        assert panel.apply_button.property("primaryAction") is True
        assert panel.preset_combo.minimumWidth() == 0

        toolbars = [
            widget
            for widget in panel.findChildren(QWidget)
            if widget.property("panelToolbar") is True
        ]
        groups = [
            group
            for group in panel.findChildren(QGroupBox)
            if group.property("inspectorGroup") is True
        ]

        assert toolbars
        assert len(groups) >= 4
    finally:
        _delete_widget(app, panel)


def test_sfx_editor_panel_is_manual_compact_editor():
    app = _app()
    panel = SfxEditorWidget()

    try:
        assert panel.objectName() == "sfxEditorPanel"
        assert panel.insert_button.property("primaryAction") is True
        assert not panel.findChildren(QPlainTextEdit)

        titles = [
            label.text()
            for label in panel.findChildren(QLabel)
            if label.objectName() == "panelTitle"
        ]
        toolbars = [
            widget
            for widget in panel.findChildren(QWidget)
            if widget.property("panelToolbar") is True
        ]

        assert "音效编辑" in titles
        assert "选中音符" in titles
        assert toolbars
    finally:
        _delete_widget(app, panel)
