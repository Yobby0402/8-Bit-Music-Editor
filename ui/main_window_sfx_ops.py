"""Main window sound-effect generation actions."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox

from core.app_control_bridge import AppControlBridge
from core.sfx_ai_service import build_sfx_generation_messages, extract_json_object
from core.sfx_generator import SfxKind, sfx_spec_from_dict, sfx_spec_to_dict
from ui.background_tasks import LlmHttpThread
from ui.settings_manager import get_settings_manager
from ui.sfx_editor_dialog import SfxEditorDialog


def resolve_sfx_insert_beat(window) -> float:
    """Use the current playhead position as the default SFX insertion point."""
    sequence_widget = getattr(window, "sequence_widget", None)
    playhead_time = float(getattr(sequence_widget, "playhead_time", 0.0) or 0.0)
    project = window.sequencer.project
    return max(0.0, project.seconds_to_beats(playhead_time))


class MainWindowSfxOpsMixin:
    """Sound-effect generation actions for MainWindow."""

    def _cleanup_sfx_llm_thread(self) -> None:
        thread = getattr(self, "_sfx_llm_thread", None)
        if thread is None:
            return
        if thread.isRunning():
            thread.wait(120000)
        self._sfx_llm_thread = None
        thread.deleteLater()

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
        dialog = SfxEditorDialog(self, start_beat=resolve_sfx_insert_beat(self))
        dialog.ai_generate_button.clicked.disconnect()
        dialog.ai_generate_button.clicked.connect(lambda: self._request_sfx_ai_generation(dialog))
        accepted = dialog.exec_() == SfxEditorDialog.Accepted
        self._cleanup_sfx_llm_thread()
        if not accepted:
            return
        try:
            spec = dialog.spec()
        except ValueError as exc:
            self.statusBar().showMessage(str(exc))
            return
        self._insert_sfx_spec_at(
            sfx_spec_to_dict(spec),
            dialog.start_beat(),
            auto_preview=dialog.auto_preview(),
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

    def _request_sfx_ai_generation(self, dialog: SfxEditorDialog) -> None:
        sm = get_settings_manager()
        if not sm.is_ai_enabled():
            QMessageBox.information(self, "SFX AI", "Enable local AI in Settings first.")
            return
        model = sm.get_ai_model()
        if not model:
            QMessageBox.warning(self, "SFX AI", "Set a local AI model ID in Settings first.")
            return
        prompt = dialog.ai_prompt()
        if not prompt:
            QMessageBox.information(self, "SFX AI", "Describe the sound effect first.")
            return

        try:
            messages = build_sfx_generation_messages(prompt)
        except ValueError as exc:
            dialog.show_ai_error(str(exc))
            return

        self._cleanup_sfx_llm_thread()
        dialog.set_ai_busy(True)
        thread = LlmHttpThread(
            sm.get_ai_base_url(),
            model,
            messages,
            api_key=sm.get_ai_api_key(),
            timeout_sec=float(sm.get_ai_timeout_sec()),
            temperature=0.4,
            parent=None,
        )
        self._sfx_llm_thread = thread
        thread.success.connect(lambda text: self._on_sfx_ai_success(dialog, text), type=Qt.QueuedConnection)
        thread.failed.connect(lambda err: self._on_sfx_ai_failed(dialog, err), type=Qt.QueuedConnection)
        thread.finished.connect(self._on_sfx_ai_thread_finished, type=Qt.QueuedConnection)
        thread.start()

    def _on_sfx_ai_success(self, dialog: SfxEditorDialog, text: str) -> None:
        try:
            spec = sfx_spec_from_dict(extract_json_object(text))
        except Exception as exc:
            dialog.show_ai_error(f"Invalid SFX AI response: {exc}")
            return
        dialog.apply_ai_spec(spec)
        dialog.set_ai_busy(False)
        self.statusBar().showMessage(f"Generated SFX spec: {spec.label}")

    def _on_sfx_ai_failed(self, dialog: SfxEditorDialog, err: object) -> None:
        dialog.show_ai_error(f"SFX AI request failed: {err}")

    def _on_sfx_ai_thread_finished(self) -> None:
        thread = getattr(self, "_sfx_llm_thread", None)
        if thread is None:
            return
        self._sfx_llm_thread = None
        thread.deleteLater()

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
    "resolve_sfx_insert_beat",
]
