"""Qt-safe localhost app control service."""

from __future__ import annotations

from queue import Queue
from typing import Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QMessageBox

from core.app_control_bridge import (
    AppCommandResult,
    AppControlBridge,
    summarize_playback_context,
)
from core.app_control_http import AppControlHttpServer


class _QtCallInvoker(QObject):
    call_requested = pyqtSignal(object)

    def __init__(
        self,
        bridge_factory: Callable[[], AppControlBridge],
        result_callback: Callable[[AppCommandResult], AppCommandResult],
        parent: QObject,
    ):
        super().__init__(parent)
        self._bridge_factory = bridge_factory
        self._result_callback = result_callback
        self.call_requested.connect(self._invoke)

    @pyqtSlot(object)
    def _invoke(self, request) -> None:
        method_name, args, kwargs, queue = request
        try:
            bridge = self._bridge_factory()
            method = getattr(bridge, method_name)
            result = method(*args, **kwargs)
            queue.put((True, self._result_callback(result)))
        except Exception as exc:
            queue.put((False, exc))


class MainWindowAppControlBridge(AppControlBridge):
    """Bridge extensions that need the live main-window UI state."""

    def __init__(self, window):
        super().__init__(window.sequencer)
        self.window = window

    def get_ui_context(self) -> AppCommandResult:
        data = summarize_playback_context(self.sequencer)
        sequence_widget = getattr(self.window, "sequence_widget", None)
        if sequence_widget is not None:
            playhead_time = float(getattr(sequence_widget, "playhead_time", data["playhead_time"]) or 0.0)
            data["playhead_time"] = playhead_time
            data["playhead_beat"] = self.sequencer.project.seconds_to_beats(playhead_time)
            selected_track = getattr(sequence_widget, "selected_track", None)
            selected_tracks = list(getattr(sequence_widget, "selected_tracks", []) or [])
            selected_items = list(getattr(sequence_widget, "selected_items", []) or [])
            if selected_track is not None:
                data["selected_track"] = self._track_summary(selected_track)
            data["selected_tracks"] = [self._track_summary(track) for track in selected_tracks]
            data["selected_item_count"] = len(selected_items)

        return self._record_result(
            AppCommandResult(
                command="get_ui_context",
                ok=True,
                message="UI context",
                data=data,
            )
        )

    def preview_playback(
        self,
        *,
        start_beat: float = 0.0,
        end_beat: float | None = None,
        loop: bool = False,
    ) -> AppCommandResult:
        def run() -> AppCommandResult:
            resolved_start_beat = max(0.0, float(start_beat))
            resolved_end_beat = None
            end_time = None
            if end_beat is not None:
                resolved_end_beat = float(end_beat)
                if resolved_end_beat <= resolved_start_beat:
                    return AppCommandResult(
                        command="preview_playback",
                        ok=False,
                        message="Preview end beat must be after start beat",
                        data={"start_beat": resolved_start_beat, "end_beat": resolved_end_beat},
                    )
                end_time = self.sequencer.project.beats_to_seconds(resolved_end_beat)

            start_time = self.sequencer.project.beats_to_seconds(resolved_start_beat)
            if hasattr(self.window, "_has_pending_playback_prepare") and self.window._has_pending_playback_prepare():
                return AppCommandResult(
                    command="preview_playback",
                    ok=False,
                    message="Playback is already preparing",
                    data={"start_beat": resolved_start_beat, "end_beat": resolved_end_beat},
                )
            if self.sequencer.playback_state.is_playing and hasattr(self.window, "stop"):
                self.window.stop()

            previous_loop_end = self.sequencer.playback_state.loop_end
            try:
                if hasattr(self.window, "_request_playback_prepare"):
                    self.sequencer.playback_state.loop_end = end_time
                    self.window.playback_start_offset = start_time
                    self.window._request_playback_prepare(
                        start_time,
                        loop=loop,
                        completion_message="AI preview playback",
                    )
                    started = True
                else:
                    started = bool(
                        self.sequencer.play(
                            start_time=start_time,
                            loop=loop,
                            end_time=end_time,
                        )
                    )
            finally:
                self.sequencer.playback_state.loop_end = previous_loop_end

            return AppCommandResult(
                command="preview_playback",
                ok=started,
                message="Started preview playback" if started else "No playable audio for preview",
                data={
                    "start_beat": resolved_start_beat,
                    "end_beat": resolved_end_beat,
                    "start_time": start_time,
                    "end_time": end_time,
                    "loop": bool(loop),
                },
            )

        return self._run_locked("preview_playback", run)

    def _track_summary(self, track) -> dict[str, object]:
        tracks = self.sequencer.project.tracks
        return {
            "index": tracks.index(track) if track in tracks else None,
            "name": track.name,
            "role": track.role.value if track.role else None,
            "track_type": track.track_type.value if track.track_type else None,
        }


class QtAppBridgeProxy(AppControlBridge):
    """Run mutating bridge commands on the Qt main thread."""

    def __init__(self, bridge_factory: Callable[[], AppControlBridge], owner: QObject):
        self._bridge_factory = bridge_factory
        self._owner = owner
        self._invoker = _QtCallInvoker(bridge_factory, self._handle_result_on_main_thread, owner)

    def _handle_result_on_main_thread(self, result: AppCommandResult) -> AppCommandResult:
        if result.ok and result.changed and hasattr(self._owner, "refresh_ui"):
            self._owner.refresh_ui(preserve_selection=True, force_full_refresh=True)
        if hasattr(self._owner, "statusBar"):
            self._owner.statusBar().showMessage(result.message)
        return result

    def _confirm_file_write(self, command_name: str, file_path: str, overwrite: bool) -> bool:
        title = "AI file export"
        action = "overwrite" if overwrite else "write"
        message = f"Allow MCP/AI command '{command_name}' to {action} this file?\n\n{file_path}"
        reply = QMessageBox.question(
            self._owner,
            title,
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _call_on_main_thread(self, method_name: str, *args, **kwargs) -> AppCommandResult:
        queue: Queue[tuple[bool, object]] = Queue(maxsize=1)
        self._invoker.call_requested.emit((method_name, args, kwargs, queue))
        ok, value = queue.get(timeout=30.0)
        if ok:
            return value
        raise value

    def get_project_state(self) -> AppCommandResult:
        return self._call_on_main_thread("get_project_state")

    def get_ui_context(self) -> AppCommandResult:
        return self._call_on_main_thread("get_ui_context")

    def get_operation_log(self, limit: int = 20) -> AppCommandResult:
        return self._call_on_main_thread("get_operation_log", limit)

    def list_sfx_presets(self) -> AppCommandResult:
        return self._call_on_main_thread("list_sfx_presets")

    def generate_sfx_spec(self, kind="coin") -> AppCommandResult:
        return self._call_on_main_thread("generate_sfx_spec", kind)

    def generate_music_spec(
        self,
        *,
        style: str = "epic",
        length_bars: int = 8,
        bpm: float | None = None,
        key: str = "C",
        intensity: float = 0.85,
    ) -> AppCommandResult:
        return self._call_on_main_thread(
            "generate_music_spec",
            style=style,
            length_bars=length_bars,
            bpm=bpm,
            key=key,
            intensity=intensity,
        )

    def insert_sfx(
        self,
        kind="coin",
        *,
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> AppCommandResult:
        return self._call_on_main_thread(
            "insert_sfx",
            kind,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def stop_playback(self) -> AppCommandResult:
        return self._call_on_main_thread("stop_playback")

    def insert_sfx_spec(
        self,
        spec_payload: dict[str, Any],
        *,
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> AppCommandResult:
        return self._call_on_main_thread(
            "insert_sfx_spec",
            spec_payload,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def insert_music_spec(
        self,
        spec_payload: dict[str, Any],
        *,
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> AppCommandResult:
        return self._call_on_main_thread(
            "insert_music_spec",
            spec_payload,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def preview_playback(
        self,
        *,
        start_beat: float = 0.0,
        end_beat: float | None = None,
        loop: bool = False,
    ) -> AppCommandResult:
        return self._call_on_main_thread(
            "preview_playback",
            start_beat=start_beat,
            end_beat=end_beat,
            loop=loop,
        )

    def export_audio(
        self,
        file_path: str,
        *,
        format: str = "wav",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> AppCommandResult:
        if not dry_run and not self._confirm_file_write("export_audio", file_path, overwrite):
            return AppCommandResult(
                command="export_audio",
                ok=False,
                message="Export cancelled by user",
                data={"file_path": file_path},
            )
        return self._call_on_main_thread(
            "export_audio",
            file_path,
            format=format,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    def export_audio_range(
        self,
        file_path: str,
        *,
        start_beat: float,
        end_beat: float,
        format: str = "wav",
        sfx_only: bool = False,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> AppCommandResult:
        if not dry_run and not self._confirm_file_write("export_audio_range", file_path, overwrite):
            return AppCommandResult(
                command="export_audio_range",
                ok=False,
                message="Export cancelled by user",
                data={"file_path": file_path},
            )
        return self._call_on_main_thread(
            "export_audio_range",
            file_path,
            start_beat=start_beat,
            end_beat=end_beat,
            format=format,
            sfx_only=sfx_only,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    def undo(self) -> AppCommandResult:
        return self._call_on_main_thread("undo")


class AppControlService(QObject):
    """Owns the localhost HTTP control server for the running app."""

    def __init__(self, window, *, port: int = 8765):
        super().__init__(window)
        self.window = window
        self._bridge_proxy = QtAppBridgeProxy(
            lambda: MainWindowAppControlBridge(self.window),
            self.window,
        )
        self.server = AppControlHttpServer(self._make_bridge, port=port)

    def _make_bridge(self) -> QtAppBridgeProxy:
        return self._bridge_proxy

    def start(self) -> None:
        self.server.start()

    def stop(self) -> None:
        self.server.stop()

    @property
    def bound_port(self) -> int:
        return self.server.bound_port
