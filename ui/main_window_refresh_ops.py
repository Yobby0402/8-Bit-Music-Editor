"""
主窗口中的信号连接、播放头同步与整页刷新逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PyQt5.QtCore import QTimer

from core.models import Track
from ui.main_window_view_ops import filter_render_tracks, get_enabled_tracks

OSC_REFRESH_BPM_ONLY = "bpm_only"
OSC_REFRESH_CLEAR = "clear"
OSC_REFRESH_RENDER = "render"


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
            return OscilloscopeRefreshPlan(OSC_REFRESH_BPM_ONLY, [])
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
        self.sequence_widget.set_tracks(
            self.sequencer.project.tracks,
            preserve_selection=preserve_selection,
        )
        self.sequence_widget.set_bpm(self.sequencer.get_bpm())

        if force_full_refresh:
            self.sequence_widget.refresh(force_full_refresh=True)

        if hasattr(self.sequence_widget, "progress_bar"):
            total_duration = self.sequencer.project.get_total_duration()
            self.sequence_widget.progress_bar.set_total_time(total_duration)

        self.unified_editor.set_bpm(self.sequencer.get_bpm())

        if hasattr(self, "playback_settings_panel"):
            self.playback_settings_panel.set_tracks(self.sequencer.project.tracks)
            self.playback_settings_panel.set_volume_ratios(self.sequencer.playback_volume_ratios)

        if hasattr(self, "bpm_editor_panel"):
            self.bpm_editor_panel.set_project(self.sequencer.project)

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

        if plan.action == OSC_REFRESH_BPM_ONLY:
            self.oscilloscope_widget.set_bpm(bpm)
            return

        if plan.action == OSC_REFRESH_CLEAR:
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
