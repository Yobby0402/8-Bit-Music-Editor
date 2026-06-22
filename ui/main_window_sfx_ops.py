"""Main window sound-effect generation actions."""

from __future__ import annotations

from core.app_control_bridge import AppControlBridge
from core.sfx_generator import SfxKind
from ui.sfx_editor_dialog import SfxEditorDialog


def resolve_sfx_insert_beat(window) -> float:
    """Use the current playhead position as the default SFX insertion point."""
    sequence_widget = getattr(window, "sequence_widget", None)
    playhead_time = float(getattr(sequence_widget, "playhead_time", 0.0) or 0.0)
    project = window.sequencer.project
    return max(0.0, project.seconds_to_beats(playhead_time))


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
        dialog = SfxEditorDialog(self, start_beat=resolve_sfx_insert_beat(self))
        if dialog.exec_() != SfxEditorDialog.Accepted:
            return
        self._insert_sfx_preset_at(
            dialog.selected_kind(),
            dialog.start_beat(),
            auto_preview=dialog.auto_preview(),
        )

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
