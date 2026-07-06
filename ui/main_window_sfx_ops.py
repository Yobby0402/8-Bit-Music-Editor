"""Main window sound-effect generation actions."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from core.app_control_bridge import AppControlBridge
from core.models import Project
from core.project_service import (
    AudioExportDependencyError,
    EmptyAudioExportError,
    export_audio_range_document,
)
from core.sfx_generator import (
    SfxKind,
    SfxSpec,
    build_sfx_notes,
    make_sfx_track,
    sfx_spec_to_dict,
)


def resolve_sfx_insert_beat(window) -> float:
    """Use the current playhead position as the default SFX insertion point."""
    sequence_widget = getattr(window, "sequence_widget", None)
    playhead_time = float(getattr(sequence_widget, "playhead_time", 0.0) or 0.0)
    project = window.sequencer.project
    return max(0.0, project.seconds_to_beats(playhead_time))


def build_sfx_preview_project(spec: SfxSpec, bpm: float) -> Project:
    """Build a temporary project containing only the edited SFX."""
    safe_bpm = float(bpm or 120.0)
    project = Project(
        name=f"SFX Preview - {spec.label}",
        bpm=safe_bpm,
        original_bpm=safe_bpm,
    )
    track = make_sfx_track(spec.label or "SFX")
    track.notes = build_sfx_notes(project, spec, 0.0)
    track.filter_params = spec.filter_params
    track.delay_params = spec.delay_params
    track.tremolo_params = spec.tremolo_params
    track.vibrato_params = spec.vibrato_params
    project.add_track(track)
    return project


def resolve_sfx_render_end_time(project: Project, spec: SfxSpec) -> float:
    """Return a render end time with enough tail for SFX effects."""
    base_end = project.beats_to_seconds(max(0.05, spec.duration_beats))
    return max(0.25, base_end + 0.5)


def export_sfx_spec_audio(
    spec: SfxSpec,
    audio_engine,
    file_path: str,
    *,
    bpm: float,
    format: str = "wav",
):
    """Export a single edited SFX without mixing in the active project."""
    project = build_sfx_preview_project(spec, bpm)
    end_time = resolve_sfx_render_end_time(project, spec)
    return export_audio_range_document(
        project,
        audio_engine,
        file_path,
        start_time=0.0,
        end_time=end_time,
        format=format,
        sfx_only=True,
    )


def _safe_sfx_file_stem(label: str) -> str:
    stem = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in label.strip()
    ).strip("_")
    return stem or "sfx"


class MainWindowSfxOpsMixin:
    """Sound-effect generation actions for MainWindow."""

    def insert_sfx_preset(self, kind: SfxKind = "coin") -> None:
        """Generate an SFX preset and insert it at the current playhead."""
        self._insert_sfx_preset_at(kind, resolve_sfx_insert_beat(self), auto_preview=False)

    def _insert_sfx_preset_at(
        self,
        kind: SfxKind = "coin",
        start_beat: float = 0.0,
        *,
        auto_preview: bool = False,
    ) -> None:
        if self.sequencer.playback_state.is_playing:
            self.statusBar().showMessage("Stop playback before inserting SFX")
            return

        result = AppControlBridge(self.sequencer).insert_sfx(
            kind,
            start_beat=start_beat,
            auto_preview=auto_preview,
        )
        track_index = result.data.get("track_index")
        tracks = self.sequencer.project.tracks
        track = tracks[track_index] if isinstance(track_index, int) and track_index < len(tracks) else None

        if track is not None and hasattr(self, "_set_selected_editor_track"):
            self._set_selected_editor_track(track)
        self.refresh_ui(preserve_selection=True, force_full_refresh=True)
        self.statusBar().showMessage(result.message)

    def show_sfx_editor(self) -> None:
        if hasattr(self, "show_right_panel_page"):
            self.show_right_panel_page("sfx")
        if hasattr(self, "sfx_editor_panel"):
            self.sfx_editor_panel.start_beat_spin.setValue(resolve_sfx_insert_beat(self))

    def insert_sfx_from_panel(self) -> None:
        if not hasattr(self, "sfx_editor_panel"):
            return
        panel = self.sfx_editor_panel
        try:
            spec = panel.spec()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._insert_sfx_spec_at(
            sfx_spec_to_dict(spec),
            panel.start_beat(),
            auto_preview=panel.auto_preview(),
        )

    def _insert_sfx_spec_at(
        self,
        spec_payload: dict,
        start_beat: float = 0.0,
        *,
        auto_preview: bool = False,
    ) -> None:
        if self.sequencer.playback_state.is_playing:
            self.statusBar().showMessage("Stop playback before inserting SFX")
            return

        result = AppControlBridge(self.sequencer).insert_sfx_spec(
            spec_payload,
            start_beat=start_beat,
            auto_preview=auto_preview,
        )
        track_index = result.data.get("track_index")
        tracks = self.sequencer.project.tracks
        track = tracks[track_index] if isinstance(track_index, int) and track_index < len(tracks) else None
        if track is not None and hasattr(self, "_set_selected_editor_track"):
            self._set_selected_editor_track(track)
        self.refresh_ui(preserve_selection=True, force_full_refresh=True)
        self.statusBar().showMessage(result.message)

    def preview_sfx_from_panel(self) -> None:
        if not hasattr(self, "sfx_editor_panel"):
            return
        if self.sequencer.playback_state.is_playing or self._has_pending_playback_prepare():
            self.statusBar().showMessage("请先停止播放，再试听当前音效")
            return

        try:
            spec = self.sfx_editor_panel.spec()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))
            return

        try:
            project = build_sfx_preview_project(spec, self.sequencer.project.bpm)
            end_time = resolve_sfx_render_end_time(project, spec)
            audio = self.sequencer.audio_engine.generate_project_audio(
                project,
                start_time=0.0,
                end_time=end_time,
            )
            if len(audio) == 0:
                self.statusBar().showMessage("当前音效没有可试听的音频")
                return
            self.sequencer.audio_engine.stop_all()
            self.sequencer.audio_engine.play_audio(audio, loop=False, volume=1.0)
            self.statusBar().showMessage(f"正在试听音效: {spec.label}")
        except Exception as exc:
            self.statusBar().showMessage(f"试听音效失败: {exc}")

    def export_sfx_from_panel(self) -> None:
        if not hasattr(self, "sfx_editor_panel"):
            return
        try:
            spec = self.sfx_editor_panel.spec()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))
            return

        last_dir = ""
        if hasattr(self, "settings"):
            last_dir = str(self.settings.value("last_save_directory", "") or "")
        export_dir = Path(last_dir) if last_dir and Path(last_dir).exists() else Path.cwd()
        suggested_path = export_dir / f"{_safe_sfx_file_stem(spec.label)}.wav"
        file_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出当前音效",
            str(suggested_path),
            "WAV 音频 (*.wav)",
        )
        if not file_path:
            return

        path = Path(file_path).expanduser()
        if not path.suffix:
            path = path.with_suffix(".wav")
        if path.exists():
            reply = QMessageBox.question(
                self,
                "覆盖文件",
                f"文件已存在，是否覆盖？\n\n{path}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self.statusBar().showMessage("已取消导出当前音效")
                return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            result = export_sfx_spec_audio(
                spec,
                self.sequencer.audio_engine,
                str(path),
                bpm=self.sequencer.project.bpm,
                format="wav",
            )
            if hasattr(self, "settings"):
                self.settings.setValue("last_save_directory", str(path.parent))
            self.statusBar().showMessage(f"已导出当前音效: {result.file_path}")
            QMessageBox.information(self, "成功", f"SFX-only 音频已导出:\n{result.file_path}")
        except EmptyAudioExportError:
            QMessageBox.warning(self, "警告", "当前音效没有可导出的音频")
        except AudioExportDependencyError as exc:
            QMessageBox.warning(self, exc.title, exc.user_message)
        except ImportError as exc:
            QMessageBox.critical(self, "错误", f"导出失败:\n{exc}")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"导出当前音效失败:\n{exc}")

    def insert_coin_sfx(self) -> None:
        self.insert_sfx_preset("coin")

    def insert_jump_sfx(self) -> None:
        self.insert_sfx_preset("jump")

    def insert_hit_sfx(self) -> None:
        self.insert_sfx_preset("hit")

    def insert_power_up_sfx(self) -> None:
        self.insert_sfx_preset("power_up")

    def insert_laser_sfx(self) -> None:
        self.insert_sfx_preset("laser")

    def insert_explosion_sfx(self) -> None:
        self.insert_sfx_preset("explosion")

    def insert_select_sfx(self) -> None:
        self.insert_sfx_preset("select")

    def insert_error_sfx(self) -> None:
        self.insert_sfx_preset("error")

    def insert_door_sfx(self) -> None:
        self.insert_sfx_preset("door")

    def insert_heal_sfx(self) -> None:
        self.insert_sfx_preset("heal")


__all__ = [
    "MainWindowSfxOpsMixin",
    "build_sfx_preview_project",
    "export_sfx_spec_audio",
    "resolve_sfx_insert_beat",
    "resolve_sfx_render_end_time",
]
