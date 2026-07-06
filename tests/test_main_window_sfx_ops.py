from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QPushButton

from core.models import Project, TrackRole
from core.sfx_generator import SfxNoteSpec, SfxSpec
from ui.main_window_sfx_ops import (
    build_sfx_preview_project,
    export_sfx_spec_audio,
    resolve_sfx_insert_beat,
)
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
        assert dialog.note_table.rowCount() == 3
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_sfx_editor_dialog_uses_compact_detail_grid():
    app = _app()
    dialog = SfxEditorDialog(start_beat=0.0)

    try:
        assert dialog.note_detail_grid.rowCount() == 5
        assert dialog.note_detail_grid.columnCount() == 4
        assert dialog.note_table.alternatingRowColors() is True
        assert dialog.preview_button.text() == "试听当前编辑音效"
        assert dialog.export_button.text() == "SFX-only 导出"
        assert dialog.insert_button.property("primaryAction") is True
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_sfx_editor_dialog_is_manual_editor_without_ai_prompt_controls():
    app = _app()
    dialog = SfxEditorDialog(start_beat=0.0)

    try:
        assert not hasattr(dialog, "ai_generate_button")
        assert not hasattr(dialog, "ai_prompt_edit")
        assert not dialog.findChildren(QPlainTextEdit)
        assert all("AI" not in button.text() for button in dialog.findChildren(QPushButton))
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_sfx_editor_dialog_returns_edited_note_spec():
    app = _app()
    dialog = SfxEditorDialog(start_beat=0.0)

    try:
        dialog.note_table.item(0, 0).setText("90")
        dialog.note_table.item(0, 4).setText("triangle")
        dialog.note_table.item(0, 6).setText("0.01")
        spec = dialog.spec()

        assert spec.notes[0].pitch == 90
        assert spec.notes[0].waveform.value == "triangle"
        assert spec.notes[0].adsr.attack == 0.01
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_sfx_editor_detail_controls_write_back_to_note_spec():
    app = _app()
    dialog = SfxEditorDialog(start_beat=0.0)

    try:
        dialog.note_table.selectRow(0)
        dialog.pitch_spin.setValue(91)
        dialog.note_start_spin.setValue(0.125)
        dialog.note_duration_spin.setValue(0.25)
        dialog.velocity_spin.setValue(99)
        dialog.waveform_combo.setCurrentIndex(dialog.waveform_combo.findData("noise"))
        dialog.attack_spin.setValue(0.02)
        dialog.decay_spin.setValue(0.03)
        dialog.sustain_spin.setValue(0.4)
        dialog.release_spin.setValue(0.05)

        spec = dialog.spec()

        assert spec.notes[0].pitch == 91
        assert spec.notes[0].start_beat == pytest.approx(0.125)
        assert spec.notes[0].duration_beats == pytest.approx(0.25)
        assert spec.notes[0].velocity == 99
        assert spec.notes[0].waveform.value == "noise"
        assert spec.notes[0].adsr.attack == pytest.approx(0.02)
        assert spec.notes[0].adsr.decay == pytest.approx(0.03)
        assert spec.notes[0].adsr.sustain == pytest.approx(0.4)
        assert spec.notes[0].adsr.release == pytest.approx(0.05)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_sfx_editor_dialog_applies_external_spec():
    app = _app()
    dialog = SfxEditorDialog(start_beat=0.0)

    try:
        spec = SfxSpec(
            kind="coin_ai",
            label="AI coin",
            notes=(SfxNoteSpec(88, 0.0, 0.12),),
        )
        dialog.apply_external_spec(spec)

        edited = dialog.spec()
        assert edited.kind == "coin_ai"
        assert edited.label == "AI coin"
        assert edited.notes[0].pitch == 88
        assert dialog.note_table.rowCount() == 1
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_build_sfx_preview_project_contains_only_effect_track():
    spec = SfxSpec(
        kind="card_ssr",
        label="SSR reveal",
        notes=(SfxNoteSpec(84, 0.0, 0.1),),
    )

    project = build_sfx_preview_project(spec, 120.0)

    assert project.bpm == 120.0
    assert len(project.tracks) == 1
    assert project.tracks[0].role == TrackRole.EFFECT
    assert project.tracks[0].notes[0].pitch == 84


def test_export_sfx_spec_audio_uses_sfx_only_range(monkeypatch, tmp_path):
    spec = SfxSpec(
        kind="card_ssr",
        label="SSR reveal",
        notes=(SfxNoteSpec(84, 0.0, 0.1),),
    )
    captured = {}

    def fake_export(project, audio_engine, file_path, *, start_time, end_time, format, sfx_only):
        captured.update(
            {
                "project": project,
                "audio_engine": audio_engine,
                "file_path": file_path,
                "start_time": start_time,
                "end_time": end_time,
                "format": format,
                "sfx_only": sfx_only,
            }
        )
        return SimpleNamespace(file_path=file_path, format=format)

    monkeypatch.setattr("ui.main_window_sfx_ops.export_audio_range_document", fake_export)
    engine = SimpleNamespace()
    target = tmp_path / "ssr.wav"

    result = export_sfx_spec_audio(spec, engine, str(target), bpm=120.0)

    assert result.file_path == str(target)
    assert captured["audio_engine"] is engine
    assert captured["start_time"] == 0.0
    assert captured["end_time"] > 0.0
    assert captured["format"] == "wav"
    assert captured["sfx_only"] is True
    assert captured["project"].tracks[0].role == TrackRole.EFFECT
