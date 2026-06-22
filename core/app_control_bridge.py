"""Local app command bridge used by UI actions and future MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from time import time
from typing import Any, Callable, Literal

from core.command import AddNoteCommand, AddTrackCommand, BatchCommand, ModifyTrackCommand
from core.models import Project, Track, TrackRole, TrackType
from core.project_service import export_audio_document, export_audio_range_document
from core.sequencer import Sequencer
from core.sfx_generator import (
    SfxKind,
    SfxSpec,
    build_sfx_notes,
    build_sfx_spec,
    find_sfx_track,
    list_sfx_presets,
    make_sfx_track,
    sfx_spec_from_dict,
)

AppCommandName = Literal[
    "get_project_state",
    "get_ui_context",
    "get_operation_log",
    "list_sfx_presets",
    "generate_sfx_spec",
    "insert_sfx",
    "insert_sfx_spec",
    "preview_playback",
    "stop_playback",
    "export_audio",
    "export_audio_range",
    "undo",
]


@dataclass(frozen=True)
class AppCommandResult:
    command: AppCommandName
    ok: bool
    message: str
    data: dict[str, Any]
    changed: bool = False
    dry_run: bool = False


def summarize_project(project: Project) -> dict[str, Any]:
    """Return a compact project summary suitable for AI tools."""
    tracks = []
    for index, track in enumerate(project.tracks):
        tracks.append(
            {
                "index": index,
                "name": track.name,
                "track_type": track.track_type.value if track.track_type else TrackType.NOTE_TRACK.value,
                "role": track.role.value if track.role else None,
                "enabled": track.enabled,
                "volume": track.volume,
                "pan": track.pan,
                "note_count": len(track.notes),
                "drum_event_count": len(track.drum_events),
            }
        )

    return {
        "name": project.name,
        "bpm": project.bpm,
        "original_bpm": project.original_bpm,
        "resolution": project.resolution,
        "duration_seconds": project.get_total_duration(),
        "track_count": len(project.tracks),
        "tracks": tracks,
    }


def summarize_playback_context(sequencer: Sequencer) -> dict[str, Any]:
    """Return playback context available without a UI window."""
    state = sequencer.playback_state
    current_time = float(state.current_time or 0.0)
    return {
        "playhead_time": current_time,
        "playhead_beat": sequencer.project.seconds_to_beats(current_time),
        "is_playing": bool(state.is_playing),
        "loop_start": state.loop_start,
        "loop_end": state.loop_end,
        "end_time": state.end_time,
        "selected_track": None,
        "selected_tracks": [],
        "selected_item_count": 0,
    }


def sfx_spec_to_dict(kind: SfxKind) -> dict[str, Any]:
    """Return a JSON-ready SFX spec preview."""
    spec = build_sfx_spec(kind)
    return {
        "kind": spec.kind,
        "label": spec.label,
        "duration_beats": spec.duration_beats,
        "notes": [
            {
                "pitch": note.pitch,
                "start_beat": note.start_beat,
                "duration_beats": note.duration_beats,
                "velocity": note.velocity,
                "waveform": note.waveform.value,
                "duty_cycle": note.duty_cycle,
                "adsr": note.adsr.to_dict(),
                "vibrato": note.vibrato.to_dict() if note.vibrato else None,
            }
            for note in spec.notes
        ],
        "filter_params": spec.filter_params.to_dict() if spec.filter_params else None,
        "delay_params": spec.delay_params.to_dict() if spec.delay_params else None,
        "tremolo_params": spec.tremolo_params.to_dict() if spec.tremolo_params else None,
        "vibrato_params": spec.vibrato_params.to_dict() if spec.vibrato_params else None,
    }


def build_insert_sfx_command(
    sequencer: Sequencer,
    start_beat: float,
    spec: SfxSpec,
) -> tuple[BatchCommand, Track, dict[str, Any]]:
    """Build an undoable command that inserts an SFX spec."""
    project = sequencer.project
    track = find_sfx_track(project.tracks)
    created_track = track is None
    commands = []

    if track is None:
        track = make_sfx_track()
        commands.append(AddTrackCommand(sequencer, track))

    effect_updates = {
        key: value
        for key, value in {
            "filter_params": spec.filter_params,
            "delay_params": spec.delay_params,
            "tremolo_params": spec.tremolo_params,
            "vibrato_params": spec.vibrato_params,
        }.items()
        if value is not None
    }
    if effect_updates:
        commands.append(ModifyTrackCommand(sequencer, track, **effect_updates))

    notes = build_sfx_notes(project, spec, start_beat)
    commands.extend(AddNoteCommand(sequencer, track, note) for note in notes)
    summary = {
        "kind": spec.kind,
        "label": spec.label,
        "track_index": project.tracks.index(track) if track in project.tracks else len(project.tracks),
        "track_name": track.name,
        "track_role": track.role.value if track.role else TrackRole.EFFECT.value,
        "created_track": created_track,
        "start_beat": max(0.0, float(start_beat)),
        "note_count": len(notes),
        "duration_beats": spec.duration_beats,
        "track_effects": sorted(effect_updates.keys()),
    }
    return BatchCommand(commands, f"Insert SFX: {spec.label}"), track, summary


class AppControlBridge:
    """Command boundary for local app control."""

    def __init__(self, sequencer: Sequencer):
        self.sequencer = sequencer
        if not hasattr(sequencer, "_app_control_lock"):
            sequencer._app_control_lock = RLock()
        if not hasattr(sequencer, "_app_control_log"):
            sequencer._app_control_log = []

    def _record_result(self, result: AppCommandResult) -> AppCommandResult:
        log = getattr(self.sequencer, "_app_control_log", None)
        if log is None:
            return result
        log.append(
            {
                "timestamp": time(),
                "command": result.command,
                "ok": result.ok,
                "message": result.message,
                "changed": result.changed,
                "dry_run": result.dry_run,
            }
        )
        del log[:-100]
        return result

    def _busy_result(self, command: AppCommandName) -> AppCommandResult:
        return AppCommandResult(
            command=command,
            ok=False,
            message="Another app-control operation is already running",
            data={},
        )

    def _run_locked(
        self,
        command: AppCommandName,
        callback: Callable[[], AppCommandResult],
    ) -> AppCommandResult:
        lock = self.sequencer._app_control_lock
        if not lock.acquire(blocking=False):
            return self._record_result(self._busy_result(command))
        try:
            return self._record_result(callback())
        finally:
            lock.release()

    def get_project_state(self) -> AppCommandResult:
        return self._record_result(
            AppCommandResult(
                command="get_project_state",
                ok=True,
                message="Project state",
                data=summarize_project(self.sequencer.project),
            )
        )

    def get_ui_context(self) -> AppCommandResult:
        return self._record_result(
            AppCommandResult(
                command="get_ui_context",
                ok=True,
                message="UI context",
                data=summarize_playback_context(self.sequencer),
            )
        )

    def get_operation_log(self, limit: int = 20) -> AppCommandResult:
        log = list(getattr(self.sequencer, "_app_control_log", []))
        limit = max(1, min(100, int(limit)))
        return self._record_result(
            AppCommandResult(
                command="get_operation_log",
                ok=True,
                message="Operation log",
                data={"entries": log[-limit:]},
            )
        )

    def list_sfx_presets(self) -> AppCommandResult:
        return self._record_result(
            AppCommandResult(
                command="list_sfx_presets",
                ok=True,
                message="SFX presets",
                data={"presets": list_sfx_presets()},
            )
        )

    def generate_sfx_spec(self, kind: SfxKind = "coin") -> AppCommandResult:
        return self._record_result(
            AppCommandResult(
                command="generate_sfx_spec",
                ok=True,
                message=f"Generated SFX spec: {kind}",
                data=sfx_spec_to_dict(kind),
            )
        )

    def insert_sfx(
        self,
        kind: SfxKind = "coin",
        *,
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> AppCommandResult:
        def run() -> AppCommandResult:
            command, _track, summary = build_insert_sfx_command(
                self.sequencer,
                start_beat,
                build_sfx_spec(kind),
            )
            if dry_run:
                return AppCommandResult(
                    command="insert_sfx",
                    ok=True,
                    message=f"Would insert SFX: {summary['label']}",
                    data=summary,
                    changed=False,
                    dry_run=True,
                )

            self.sequencer.command_history.execute_command(command)
            if auto_preview:
                preview = self.preview_playback(
                    start_beat=summary["start_beat"],
                    end_beat=summary["start_beat"] + summary["duration_beats"],
                )
                summary["preview_result"] = preview.data
            return AppCommandResult(
                command="insert_sfx",
                ok=True,
                message=f"Inserted SFX: {summary['label']}",
                data=summary,
                changed=True,
            )

        return self._run_locked("insert_sfx", run)

    def insert_sfx_spec(
        self,
        spec_payload: dict[str, Any],
        *,
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> AppCommandResult:
        def run() -> AppCommandResult:
            try:
                spec = sfx_spec_from_dict(spec_payload)
                command, _track, summary = build_insert_sfx_command(
                    self.sequencer,
                    start_beat,
                    spec,
                )
            except (TypeError, ValueError) as exc:
                return AppCommandResult(
                    command="insert_sfx_spec",
                    ok=False,
                    message=f"Invalid SFX spec: {exc}",
                    data={},
                )

            if dry_run:
                return AppCommandResult(
                    command="insert_sfx_spec",
                    ok=True,
                    message=f"Would insert SFX spec: {summary['label']}",
                    data=summary,
                    changed=False,
                    dry_run=True,
                )

            self.sequencer.command_history.execute_command(command)
            if auto_preview:
                preview = self.preview_playback(
                    start_beat=summary["start_beat"],
                    end_beat=summary["start_beat"] + summary["duration_beats"],
                )
                summary["preview_result"] = preview.data
            return AppCommandResult(
                command="insert_sfx_spec",
                ok=True,
                message=f"Inserted SFX spec: {summary['label']}",
                data=summary,
                changed=True,
            )

        return self._run_locked("insert_sfx_spec", run)

    def stop_playback(self) -> AppCommandResult:
        def run() -> AppCommandResult:
            self.sequencer.stop()
            return AppCommandResult(
                command="stop_playback",
                ok=True,
                message="Stopped playback",
                data={},
                changed=False,
            )

        return self._run_locked("stop_playback", run)

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
            try:
                started = bool(
                    self.sequencer.play(
                        start_time=start_time,
                        loop=loop,
                        end_time=end_time,
                    )
                )
            except Exception as exc:
                return AppCommandResult(
                    command="preview_playback",
                    ok=False,
                    message=f"Preview playback failed: {exc}",
                    data={"start_beat": resolved_start_beat, "end_beat": resolved_end_beat},
                )

            data = {
                "start_beat": resolved_start_beat,
                "end_beat": resolved_end_beat,
                "start_time": start_time,
                "end_time": end_time,
                "loop": bool(loop),
            }
            if not started:
                return AppCommandResult(
                    command="preview_playback",
                    ok=False,
                    message="No playable audio for preview",
                    data=data,
                )
            return AppCommandResult(
                command="preview_playback",
                ok=True,
                message="Started preview playback",
                data=data,
            )

        return self._run_locked("preview_playback", run)

    def export_audio(
        self,
        file_path: str,
        *,
        format: str = "wav",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> AppCommandResult:
        def run() -> AppCommandResult:
            path = Path(file_path).expanduser()
            if not path.is_absolute():
                return AppCommandResult(
                    command="export_audio",
                    ok=False,
                    message="Export path must be absolute",
                    data={"file_path": str(path)},
                )
            exists = path.exists()
            data = {
                "file_path": str(path),
                "format": (format or "wav").lower(),
                "exists": exists,
                "overwrite": bool(overwrite),
            }
            if exists and not overwrite:
                return AppCommandResult(
                    command="export_audio",
                    ok=False,
                    message="Export target exists; set overwrite=true to replace it",
                    data=data,
                )
            if dry_run:
                return AppCommandResult(
                    command="export_audio",
                    ok=True,
                    message="Would export audio",
                    data=data,
                    dry_run=True,
                )

            path.parent.mkdir(parents=True, exist_ok=True)
            export_result = export_audio_document(
                self.sequencer.project,
                self.sequencer.audio_engine,
                str(path),
                format=data["format"],
            )
            data.update(
                {
                    "file_path": export_result.file_path,
                    "format": export_result.format,
                }
            )
            return AppCommandResult(
                command="export_audio",
                ok=True,
                message=f"Exported audio: {export_result.file_path}",
                data=data,
                changed=False,
            )

        return self._run_locked("export_audio", run)

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
        def run() -> AppCommandResult:
            resolved_start_beat = max(0.0, float(start_beat))
            resolved_end_beat = float(end_beat)
            if resolved_end_beat <= resolved_start_beat:
                return AppCommandResult(
                    command="export_audio_range",
                    ok=False,
                    message="Export end beat must be after start beat",
                    data={"start_beat": resolved_start_beat, "end_beat": resolved_end_beat},
                )

            path = Path(file_path).expanduser()
            if not path.is_absolute():
                return AppCommandResult(
                    command="export_audio_range",
                    ok=False,
                    message="Export path must be absolute",
                    data={"file_path": str(path)},
                )
            start_time = self.sequencer.project.beats_to_seconds(resolved_start_beat)
            end_time = self.sequencer.project.beats_to_seconds(resolved_end_beat)
            exists = path.exists()
            data = {
                "file_path": str(path),
                "format": (format or "wav").lower(),
                "exists": exists,
                "overwrite": bool(overwrite),
                "start_beat": resolved_start_beat,
                "end_beat": resolved_end_beat,
                "start_time": start_time,
                "end_time": end_time,
                "sfx_only": bool(sfx_only),
            }
            if exists and not overwrite:
                return AppCommandResult(
                    command="export_audio_range",
                    ok=False,
                    message="Export target exists; set overwrite=true to replace it",
                    data=data,
                )
            if dry_run:
                return AppCommandResult(
                    command="export_audio_range",
                    ok=True,
                    message="Would export audio range",
                    data=data,
                    dry_run=True,
                )

            path.parent.mkdir(parents=True, exist_ok=True)
            export_result = export_audio_range_document(
                self.sequencer.project,
                self.sequencer.audio_engine,
                str(path),
                start_time=start_time,
                end_time=end_time,
                format=data["format"],
                sfx_only=bool(sfx_only),
            )
            data.update(
                {
                    "file_path": export_result.file_path,
                    "format": export_result.format,
                }
            )
            return AppCommandResult(
                command="export_audio_range",
                ok=True,
                message=f"Exported audio range: {export_result.file_path}",
                data=data,
                changed=False,
            )

        return self._run_locked("export_audio_range", run)

    def undo(self) -> AppCommandResult:
        def run() -> AppCommandResult:
            result = self.sequencer.undo()
            if result is None:
                return AppCommandResult(
                    command="undo",
                    ok=False,
                    message="Nothing to undo",
                    data={},
                )
            return AppCommandResult(
                command="undo",
                ok=True,
                message=f"Undid: {result.description}",
                data={"description": result.description},
                changed=True,
            )

        return self._run_locked("undo", run)


__all__ = [
    "AppCommandName",
    "AppCommandResult",
    "AppControlBridge",
    "build_insert_sfx_command",
    "summarize_playback_context",
    "sfx_spec_to_dict",
    "summarize_project",
]
