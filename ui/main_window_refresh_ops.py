"""
主窗口中的信号连接、播放头同步与整页刷新逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

from PyQt5.QtCore import QTimer

from core.models import Track
from ui.main_window_view_ops import filter_render_tracks, get_enabled_tracks

OSC_REFRESH_CLEAR = "clear"
OSC_REFRESH_RENDER = "render"
UI_REFRESH_PROFILE_THRESHOLD_MS = 100.0


@dataclass(frozen=True)
class OscilloscopeRefreshPlan:
    """描述 refresh_ui 中示波器需要执行的刷新动作。"""

    action: str
    tracks: list[Track]
    selected_track: Track | None = None
    selected_tracks_override: list[Track] | None = None


def build_oscilloscope_refresh_plan(
    enabled_tracks: Sequence[Track],
    user_selected_tracks: Sequence[Track] | None,
    selected_track: Track | None,
) -> OscilloscopeRefreshPlan:
    """根据当前状态决定示波器刷新方案。"""
    if user_selected_tracks:
        filtered_tracks = filter_render_tracks(user_selected_tracks, enabled_tracks)
        if filtered_tracks:
            resolved_tracks = list(filtered_tracks)
            return OscilloscopeRefreshPlan(
                OSC_REFRESH_RENDER,
                resolved_tracks,
                selected_tracks_override=resolved_tracks,
            )
        return OscilloscopeRefreshPlan(OSC_REFRESH_CLEAR, [])

    if not enabled_tracks:
        return OscilloscopeRefreshPlan(OSC_REFRESH_CLEAR, [])

    enabled_track_ids = {id(track) for track in enabled_tracks}
    if selected_track is not None and id(selected_track) in enabled_track_ids:
        return OscilloscopeRefreshPlan(
            OSC_REFRESH_RENDER,
            list(enabled_tracks),
            selected_track=selected_track,
        )

    if len(enabled_tracks) <= 3:
        return OscilloscopeRefreshPlan(OSC_REFRESH_RENDER, list(enabled_tracks))

    default_tracks = list(enabled_tracks[:3])
    return OscilloscopeRefreshPlan(
        OSC_REFRESH_RENDER,
        default_tracks,
        selected_tracks_override=default_tracks,
    )


class MainWindowRefreshOpsMixin:
    """承载 MainWindow 中的信号连接、播放头同步与整页刷新逻辑。"""

    def _log_refreshable_widgets_profile(
        self,
        *,
        preserve_selection: bool,
        force_full_refresh: bool,
        **stage_timings_ms: float,
    ) -> None:
        """Print a stage breakdown when a full UI refresh is slow."""
        total_ms = sum(stage_timings_ms.values())
        if total_ms < UI_REFRESH_PROFILE_THRESHOLD_MS:
            return

        project = self.sequencer.project
        track_count = len(project.tracks)
        note_count = sum(len(track.notes) for track in project.tracks)
        stage_parts = " ".join(
            f"{name}={elapsed_ms:.1f}ms"
            for name, elapsed_ms in stage_timings_ms.items()
        )
        print(
            "[PROFILE] ui.refresh_widgets "
            f"total={total_ms:.1f}ms "
            f"{stage_parts} "
            f"track_count={track_count} "
            f"note_count={note_count} "
            f"preserve_selection={preserve_selection} "
            f"force_full_refresh={force_full_refresh}"
        )

    def connect_signals(self):
        """连接信号。"""
        self.unified_editor.add_melody_note.connect(self.on_add_melody_note)
        self.unified_editor.add_bass_event.connect(self.on_add_bass_event)
        self.unified_editor.add_drum_event.connect(self.on_add_drum_event)

        self.sequence_widget.note_clicked.connect(self.on_note_selected)
        self.sequence_widget.note_position_changed.connect(self.on_note_position_changed)
        self.sequence_widget.note_deleted.connect(self.on_note_deleted)
        self.sequence_widget.notes_deleted.connect(self.on_notes_deleted)

        self.property_panel.property_changed.connect(self.on_property_changed)
        self.property_panel.property_update_requested.connect(self.on_property_update_requested)
        self.property_panel.batch_property_changed.connect(self.on_batch_property_changed)
        self.property_panel.track_property_changed.connect(self.on_track_property_changed)

        if hasattr(self, "score_panel"):
            self.score_panel.request_create_from_selection.connect(self.on_score_create_from_selection)
            self.score_panel.snippet_apply_requested.connect(self.on_score_apply_snippet)
            self.score_panel.snippet_delete_requested.connect(self.on_score_delete_snippet)
            self.score_panel.snippet_preview_requested.connect(self.on_score_preview_snippet)

        self.sequence_widget.selection_changed.connect(self.on_selection_changed)
        self.sequence_widget.track_clicked.connect(self.on_track_clicked)
        self.sequence_widget.track_enabled_changed.connect(self.on_track_enabled_changed)
        self.sequence_widget.playhead_time_changed.connect(self.on_playhead_time_changed)
        self.sequence_widget.track_deleted.connect(self.on_track_deleted)
        self.sequence_widget.render_waveform_requested.connect(self.on_render_waveform_requested)

    def on_playhead_time_changed(self, time: float):
        """播放线时间改变（用户拖动进度条时）。"""
        if self.sequencer.playback_state.is_playing:
            self.sequencer.stop()
            self.statusBar().showMessage("已停止播放")

        self.sequence_widget.set_playhead_time(time)
        self.playback_start_offset = time

    def _update_refreshable_widgets(self, preserve_selection: bool, force_full_refresh: bool):
        """刷新序列编辑器、统一编辑器和各类面板。"""
        project = self.sequencer.project
        tracks = project.tracks
        bpm = self.sequencer.get_bpm()

        stage_started_at = perf_counter()
        if hasattr(self.sequence_widget, "set_project"):
            self.sequence_widget.set_project(project)
        if hasattr(self, "property_panel") and hasattr(self.property_panel, "set_project"):
            self.property_panel.set_project(project)
        project_binding_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.sequence_widget.set_tracks(
            tracks,
            preserve_selection=preserve_selection,
            refresh=False,
        )
        set_tracks_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.sequence_widget.set_bpm(bpm, refresh=False)
        set_bpm_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.sequence_widget.refresh(force_full_refresh=force_full_refresh)
        sequence_refresh_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        if hasattr(self.sequence_widget, "progress_bar"):
            total_duration = project.get_total_duration()
            self.sequence_widget.progress_bar.set_total_time(total_duration)
        progress_bar_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.unified_editor.set_bpm(bpm)
        unified_editor_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        if hasattr(self, "playback_settings_panel"):
            if hasattr(self.playback_settings_panel, "set_state"):
                self.playback_settings_panel.set_state(
                    tracks,
                    self.sequencer.playback_volume_ratios,
                )
            else:
                self.playback_settings_panel.set_tracks(tracks)
                self.playback_settings_panel.set_volume_ratios(
                    self.sequencer.playback_volume_ratios
                )
        playback_settings_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        if hasattr(self, "bpm_editor_panel"):
            self.bpm_editor_panel.set_project(project)
        bpm_editor_ms = (perf_counter() - stage_started_at) * 1000.0

        self._log_refreshable_widgets_profile(
            preserve_selection=preserve_selection,
            force_full_refresh=force_full_refresh,
            project_binding_ms=project_binding_ms,
            set_tracks_ms=set_tracks_ms,
            set_bpm_ms=set_bpm_ms,
            sequence_refresh_ms=sequence_refresh_ms,
            progress_bar_ms=progress_bar_ms,
            unified_editor_ms=unified_editor_ms,
            playback_settings_ms=playback_settings_ms,
            bpm_editor_ms=bpm_editor_ms,
        )

    def _update_sequence_duration_widgets(self):
        """Update lightweight timeline widgets after local note edits."""
        if hasattr(self.sequence_widget, "progress_bar"):
            total_duration = self.sequencer.project.get_total_duration()
            self.sequence_widget.progress_bar.set_total_time(total_duration)

    def _is_oscilloscope_view_active(self) -> bool:
        """Return whether waveform view is currently active."""
        return hasattr(self, "view_stack") and self.view_stack.currentIndex() == 1

    def _refresh_note_related_views(self) -> None:
        """Keep secondary note views in sync after local sequence updates."""
        if self._is_oscilloscope_view_active() and hasattr(self, "_refresh_oscilloscope_widget"):
            self._refresh_oscilloscope_widget()

    def _can_use_lightweight_note_refresh(self, track: Track | None = None) -> bool:
        """Return whether the current UI state can use local block sync instead of full refresh."""
        if not hasattr(self, "sequence_widget") or not hasattr(self.sequence_widget, "sync_note_block"):
            return False
        if track is None:
            return True
        if track not in getattr(self.sequence_widget, "tracks", []):
            return False
        track_index = self.sequence_widget.tracks.index(track)
        return track_index < len(getattr(self.sequence_widget, "track_groups", []))

    def _sync_note_block_ui(self, note, track, *, highlight_track: bool = False) -> bool:
        """Update a single note block and lightweight timeline widgets."""
        if not self._can_use_lightweight_note_refresh(track):
            return False
        if not self.sequence_widget.sync_note_block(note, track):
            return False
        self._update_sequence_duration_widgets()
        if highlight_track:
            self.sequence_widget.set_highlighted_track(track)
        return True

    def _sync_note_blocks_ui(self, notes_and_tracks: list[tuple[object, Track]]) -> bool:
        """Update multiple note blocks with one lightweight widget pass."""
        if not notes_and_tracks:
            return False
        if not self._can_use_lightweight_note_refresh():
            return False
        if not hasattr(self.sequence_widget, "sync_note_blocks"):
            return False
        if not all(self._can_use_lightweight_note_refresh(track) for _, track in notes_and_tracks):
            return False
        if not self.sequence_widget.sync_note_blocks(notes_and_tracks):
            return False
        self._update_sequence_duration_widgets()
        return True

    def _remove_note_block_ui(self, note, track) -> bool:
        """Remove a single note block and lightweight timeline widgets."""
        if not self._can_use_lightweight_note_refresh(track):
            return False
        if not self.sequence_widget.remove_note_block(note, track):
            return False
        self._update_sequence_duration_widgets()
        return True

    def _remove_note_blocks_ui(self, notes_and_tracks: list[tuple[object, Track]]) -> bool:
        """Remove multiple note blocks with one lightweight widget pass."""
        if not notes_and_tracks:
            return False
        if not self._can_use_lightweight_note_refresh():
            return False
        if not hasattr(self.sequence_widget, "remove_note_blocks"):
            return False
        if not all(self._can_use_lightweight_note_refresh(track) for _, track in notes_and_tracks):
            return False
        if not self.sequence_widget.remove_note_blocks(notes_and_tracks):
            return False
        self._update_sequence_duration_widgets()
        return True

    def _sync_track_ui(self, track: Track) -> bool:
        """Refresh track labels and related panels without rebuilding the scene."""
        handled = False

        if (
            hasattr(self, "sequence_widget")
            and hasattr(self.sequence_widget, "sync_track_presentation")
            and self.sequence_widget.sync_track_presentation(track)
        ):
            handled = True

        if hasattr(self, "property_panel"):
            if getattr(self.property_panel, "current_track_for_edit", None) is track:
                self.property_panel.set_track(track)
                handled = True

        if hasattr(self, "playback_settings_panel"):
            if hasattr(self.playback_settings_panel, "set_state"):
                self.playback_settings_panel.set_state(
                    self.sequencer.project.tracks,
                    self.sequencer.playback_volume_ratios,
                )
            else:
                self.playback_settings_panel.set_tracks(self.sequencer.project.tracks)
                self.playback_settings_panel.set_volume_ratios(
                    self.sequencer.playback_volume_ratios
                )
            handled = True

        if hasattr(self, "_refresh_oscilloscope_widget"):
            self._refresh_oscilloscope_widget()
            handled = True

        return handled

    def _refresh_oscilloscope_widget(self):
        """根据当前视图和选择状态刷新示波器。"""
        if not hasattr(self, "oscilloscope_widget") or not hasattr(self, "view_stack"):
            return

        bpm = self.sequencer.get_bpm()
        if self.view_stack.currentIndex() != 1:
            self.oscilloscope_widget.set_bpm(bpm)
            return

        user_selected_tracks = list(
            getattr(self.oscilloscope_widget, "_selected_tracks_for_render", []) or []
        )
        playback_enabled = getattr(self.sequencer, "playback_enabled_tracks", {})
        enabled_tracks = get_enabled_tracks(self.sequencer.project.tracks, playback_enabled)
        selected_track = self._get_selected_track()
        plan = build_oscilloscope_refresh_plan(
            enabled_tracks,
            user_selected_tracks,
            selected_track,
        )

        if plan.action == OSC_REFRESH_CLEAR:
            if getattr(self.oscilloscope_widget, "tracks", []):
                self.oscilloscope_widget.set_tracks([])
            self.oscilloscope_widget.set_bpm(bpm)
            return

        if plan.selected_tracks_override is not None:
            self.oscilloscope_widget.set_selected_tracks(plan.selected_tracks_override)

        if plan.selected_track is not None:
            self.oscilloscope_widget.set_tracks(plan.tracks, selected_track=plan.selected_track)
        else:
            self.oscilloscope_widget.set_tracks(plan.tracks)
        self.oscilloscope_widget.set_bpm(bpm)

    def refresh_ui(self, preserve_selection: bool = False, force_full_refresh: bool = False):
        """刷新 UI 显示。"""
        current_size = self.size()

        self._update_refreshable_widgets(preserve_selection, force_full_refresh)
        self._refresh_oscilloscope_widget()

        if current_size.isValid():
            QTimer.singleShot(0, lambda: self._restore_window_size(current_size))
