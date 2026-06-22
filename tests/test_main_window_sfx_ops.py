from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication

from core.models import Project
from ui.main_window_sfx_ops import resolve_sfx_insert_beat
from ui.sfx_editor_dialog import SfxEditorDialog


def _app():
    app = QApplication.instance()
    if app is not None and not isinstance(app, QApplication):
        pytest.skip("A non-GUI QCoreApplication is already active")
    if app is None:
        app = QApplication([])
    return app


def test_resolve_sfx_insert_beat_uses_playhead_time():
    window = SimpleNamespace(
        sequencer=SimpleNamespace(project=Project(bpm=120.0)),
        sequence_widget=SimpleNamespace(playhead_time=1.0),
    )

    assert resolve_sfx_insert_beat(window) == 2.0


def test_sfx_editor_dialog_exposes_selected_options():
    app = _app()
    dialog = SfxEditorDialog(start_beat=2.5)

    try:
        dialog.preset_combo.setCurrentIndex(dialog.preset_combo.findData("laser"))
        dialog.auto_preview_checkbox.setChecked(False)

        assert dialog.selected_kind() == "laser"
        assert dialog.start_beat() == 2.5
        assert dialog.auto_preview() is False
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
