"""
主窗口中的播放控制与播放状态同步相关操作。
"""

import time

from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QStyle

from core.tempo_map import has_variable_tempo
from ui.background_tasks import PlaybackPrepareWorker
from ui.performance_utils import begin_profile_span, finish_profile_span


class MainWindowPlaybackOpsMixin:
    """承载 MainWindow 的播放控制、音量和播放状态同步逻辑。"""

    def _begin_playback_prepare_profile(self, request_id: int, start_time: float, loop: bool) -> None:
        """Start tracking playback-prepare latency for this request."""
        tokens = getattr(self, "_playback_prepare_profile_tokens", None)
        if tokens is None:
            tokens = {}
            self._playback_prepare_profile_tokens = tokens
        tokens[request_id] = begin_profile_span(
            self,
            "playback.prepare",
            start_time=round(start_time, 3),
            loop=loop,
        )

    def _finish_playback_prepare_profile(self, request_id: int, *, outcome: str) -> None:
        """Finish tracking playback-prepare latency for this request."""
        tokens = getattr(self, "_playback_prepare_profile_tokens", None)
        if not tokens:
            return
        token = tokens.pop(request_id, None)
        finish_profile_span(self, token, outcome=outcome)

    def _set_preview_enabled(self, enabled: bool):
        """统一控制编辑器预览状态。"""
        self.unified_editor.set_preview_enabled(enabled)

    def _set_play_button_state(self, is_playing: bool):
        """统一更新播放按钮文本和提示。"""
        if not hasattr(self, "play_stop_button"):
            return
        icon_name = QStyle.SP_MediaPause if is_playing else QStyle.SP_MediaPlay
        self.play_stop_button.setIcon(self.style().standardIcon(icon_name))
        self.play_stop_button.setToolTip("暂停" if is_playing else "播放")

    def _set_oscilloscope_playing(self, is_playing: bool):
        """同步示波器播放状态。"""
        if hasattr(self, "oscilloscope_widget"):
            self.oscilloscope_widget.set_playing(is_playing)

    def _retarget_playback_restart_timer(self, callback, delay_ms: int):
        """更新播放设置防抖定时器的目标回调。"""
        self._playback_settings_restart_timer.stop()
        try:
            self._playback_settings_restart_timer.timeout.disconnect()
        except TypeError:
            pass
        self._playback_settings_restart_timer.timeout.connect(callback)
        self._playback_settings_restart_timer.start(delay_ms)

    def _has_pending_playback_prepare(self) -> bool:
        """Return whether playback audio is still being prepared."""
        thread = getattr(self, "_playback_prepare_thread", None)
        return thread is not None and thread.isRunning()

    def _set_playback_prepare_controls(self, preparing: bool):
        """Toggle lightweight UI state while playback is being prepared."""
        if hasattr(self, "play_stop_button"):
            self.play_stop_button.setEnabled(not preparing)

    def _get_current_playback_time(self) -> float:
        """Return the UI playhead time that matches the active audio buffer."""
        if self.playback_start_time is None:
            return float(getattr(self.sequence_widget, "playhead_time", 0.0))

        elapsed_time = time.time() - self.playback_start_time
        actual_playback_time = self.playback_start_offset + elapsed_time

        project = self.sequencer.project
        original_bpm = getattr(project, "original_bpm", None) or project.bpm
        current_bpm = project.bpm
        uses_tempo_map = has_variable_tempo(getattr(project, "bpm_segments", []))
        if (
            not uses_tempo_map
            and original_bpm > 0
            and current_bpm > 0
            and original_bpm != current_bpm
        ):
            return actual_playback_time / (original_bpm / current_bpm)
        return actual_playback_time

    def _cleanup_playback_prepare_task(self, thread: QThread):
        """Release references after a playback prepare request completes."""
        if getattr(self, "_playback_prepare_thread", None) is not thread:
            return

        self._playback_prepare_thread = None
        self._playback_prepare_worker = None
        self._set_playback_prepare_controls(False)

    def _request_playback_prepare(
        self,
        start_time: float,
        *,
        loop: bool = False,
        completion_message: str = "播放中...",
    ):
        """Render playback audio in the background before starting pygame."""
        if self._has_pending_playback_prepare():
            self.statusBar().showMessage("正在准备播放，请稍候...")
            return

        request_id = getattr(self, "_playback_prepare_request_id", 0) + 1
        self._playback_prepare_request_id = request_id
        self._begin_playback_prepare_profile(request_id, start_time, loop)

        worker = PlaybackPrepareWorker(
            self.sequencer.project,
            self.sequencer.audio_engine.sample_rate,
            start_time=start_time,
            loop=loop,
            loop_end=self.sequencer.playback_state.loop_end,
            playback_enabled_tracks=self.sequencer.playback_enabled_tracks,
            playback_volume_ratios=self.sequencer.playback_volume_ratios,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda plan, rid=request_id, seek_time=start_time, message=completion_message: (
                self._on_playback_prepare_finished(rid, plan, seek_time, message)
            )
        )
        worker.failed.connect(
            lambda exc, rid=request_id: self._on_playback_prepare_failed(rid, exc)
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda current_thread=thread: self._cleanup_playback_prepare_task(current_thread)
        )

        self._playback_prepare_thread = thread
        self._playback_prepare_worker = worker
        self._set_playback_prepare_controls(True)
        self._set_preview_enabled(False)
        self.statusBar().showMessage("正在准备播放...")
        thread.start()

    def _cancel_pending_playback_prepare(self):
        """Cancel the current playback prepare result without killing the thread."""
        if not self._has_pending_playback_prepare():
            return

        self._finish_playback_prepare_profile(
            getattr(self, "_playback_prepare_request_id", 0),
            outcome="cancelled",
        )
        self._playback_prepare_request_id += 1
        self._set_preview_enabled(True)
        self._set_playback_prepare_controls(False)

    def _on_playback_prepare_finished(
        self,
        request_id: int,
        plan,
        start_time: float,
        completion_message: str,
    ):
        """Start playback once the background render finishes."""
        if request_id != getattr(self, "_playback_prepare_request_id", 0):
            return

        try:
            playback_started = False if plan is None else self.sequencer.start_prepared_playback(plan)
        except Exception as exc:
            self._on_playback_prepare_failed(request_id, exc)
            return

        if not playback_started:
            self.playback_start_time = None
            self.playback_start_offset = start_time
            self._set_preview_enabled(True)
            self._set_play_button_state(False)
            self._set_oscilloscope_playing(False)
            self.statusBar().showMessage("没有可播放的音频")
            self._finish_playback_prepare_profile(request_id, outcome="empty")
            return

        self.playback_start_time = time.time()
        self.playback_start_offset = start_time
        self.sequence_widget.set_playhead_time(start_time)
        self._set_play_button_state(True)
        self._set_oscilloscope_playing(True)
        self.statusBar().showMessage(completion_message)
        self._finish_playback_prepare_profile(request_id, outcome="ok")

    def _on_playback_prepare_failed(self, request_id: int, exc: Exception):
        """Handle playback preparation failures."""
        if request_id != getattr(self, "_playback_prepare_request_id", 0):
            return

        self.playback_start_time = None
        self._set_preview_enabled(True)
        self._set_play_button_state(False)
        self._set_oscilloscope_playing(False)
        self.statusBar().showMessage(f"播放准备失败: {exc}")
        self._finish_playback_prepare_profile(request_id, outcome="failed")

    def toggle_play_stop(self):
        """切换播放/停止状态。"""
        if self.sequencer.playback_state.is_playing or self._has_pending_playback_prepare():
            self.stop()
        else:
            self.play()

    def toggle_play_pause(self):
        """切换播放/暂停。"""
        if self.sequencer.playback_state.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """播放。"""
        if self.sequencer.playback_state.is_playing or self._has_pending_playback_prepare():
            return

        current_time = self.sequence_widget.playhead_time
        self.playback_start_offset = current_time
        self._request_playback_prepare(current_time)

    def pause(self):
        """暂停。"""
        if not self.sequencer.playback_state.is_playing or self._has_pending_playback_prepare():
            return

        current_time = self._get_current_playback_time()
        self.sequencer.pause()
        self.sequencer.playback_state.current_time = current_time
        self.sequence_widget.set_playhead_time(current_time)
        if hasattr(self.sequence_widget, "progress_bar"):
            self.sequence_widget.progress_bar.set_current_time(current_time)
        self.playback_start_time = None
        self.playback_start_offset = current_time
        self._set_preview_enabled(True)
        self.statusBar().showMessage("已暂停")
        self._set_oscilloscope_playing(False)
        self._set_play_button_state(False)

    def stop(self):
        """停止。"""
        if self._has_pending_playback_prepare():
            self._cancel_pending_playback_prepare()
            self.playback_start_time = None
            self.playback_start_offset = 0.0
            self.sequence_widget.set_playhead_time(0.0)
            self._set_play_button_state(False)
            self._set_oscilloscope_playing(False)
            self.statusBar().showMessage("已取消播放准备")
            return

        self.sequencer.stop()
        self.statusBar().showMessage("已停止")

        self.sequence_widget.set_playhead_time(0.0)
        self.playback_start_time = None

        self._set_preview_enabled(True)
        self._set_play_button_state(False)
        self._set_oscilloscope_playing(False)

    def on_playback_volume_ratios_changed(self, ratios: dict):
        """播放音量占比改变。"""
        self.sequencer.playback_volume_ratios = ratios

        if self.sequencer.playback_state.is_playing:
            self._retarget_playback_restart_timer(
                self._restart_playback_from_current_position,
                self._playback_settings_restart_delay,
            )
        else:
            self.statusBar().showMessage("播放音量占比已更新")

    def _update_playback_volumes_realtime(self):
        """Apply playback-volume changes through the single-buffer restart path."""
        if not self.sequencer.playback_state.is_playing or self._has_pending_playback_prepare():
            return

        self._retarget_playback_restart_timer(
            self._restart_playback_from_current_position,
            self._playback_settings_restart_delay,
        )

    def on_playback_track_selection_changed(self, enabled_tracks: dict):
        """播放设置面板音轨勾选状态改变。"""
        if not hasattr(self.sequencer, "playback_enabled_tracks"):
            self.sequencer.playback_enabled_tracks = {}
        self.sequencer.playback_enabled_tracks = enabled_tracks

        if self.sequencer.playback_state.is_playing:
            self._retarget_playback_restart_timer(
                self._restart_playback_from_current_position,
                self._playback_settings_restart_delay,
            )
            self.statusBar().showMessage("播放音轨启用状态已更新，正在重新准备播放")
        else:
            self.statusBar().showMessage("播放音轨启用状态已更新")

    def _restart_playback_from_current_position(self):
        """从当前位置重新开始播放（用于实时应用播放设置更改）。"""
        if not self.sequencer.playback_state.is_playing:
            return

        current_time = self._get_current_playback_time()
        QTimer.singleShot(0, lambda: self._do_restart_playback(current_time))

    def _do_restart_playback(self, current_time: float):
        """实际执行重新播放（在主线程中）。"""
        if not self.sequencer.playback_state.is_playing:
            return

        self.playback_start_offset = current_time
        self.playback_start_time = None
        self.sequencer.stop()
        self._set_play_button_state(False)
        self._set_oscilloscope_playing(False)
        if hasattr(self, "sequence_widget"):
            self.sequence_widget.set_playhead_time(current_time)

        self._request_playback_prepare(
            current_time,
            completion_message="播放设置已实时应用",
        )

    def on_bpm_changed(self, value: int):
        """BPM 改变。"""
        if self.sequencer.playback_state.is_playing:
            current_bpm = int(self.sequencer.get_bpm())
            self.bpm_spinbox.blockSignals(True)
            self.bpm_spinbox.setValue(current_bpm)
            self.bpm_spinbox.blockSignals(False)
            self.statusBar().showMessage("播放期间不能调整BPM，请先停止播放")
            return

        self._sync_project_bpm_to_ui(float(value), refresh_sequence_widget=False)
        self.refresh_ui()

    def on_volume_changed(self, value: int):
        """音量改变（实时更新）。"""
        volume = value / 100.0
        self.sequencer.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{value}%")
        if self.sequencer.playback_state.is_playing:
            self._retarget_playback_restart_timer(
                self._restart_playback_from_current_position,
                self._playback_settings_restart_delay,
            )

    def on_volume_slider_released(self):
        """播放音量改变（实时更新，不需要重新播放）。"""
        value = self.volume_slider.value()
        volume = value / 100.0
        self.sequencer.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{value}%")

    def update_playback_status(self):
        """更新播放状态和播放头。"""
        if self.sequencer.playback_state.is_playing and self.playback_start_time:
            project = self.sequencer.project
            original_bpm = getattr(project, "original_bpm", None) or project.bpm
            current_bpm = project.bpm
            uses_tempo_map = has_variable_tempo(getattr(project, "bpm_segments", []))

            if (
                not uses_tempo_map
                and original_bpm > 0
                and current_bpm > 0
                and original_bpm != current_bpm
            ):
                bpm_ratio = original_bpm / current_bpm
            else:
                bpm_ratio = 1.0
            current_time = self._get_current_playback_time()

            should_update_playhead = True
            if hasattr(self.sequence_widget, "progress_bar"):
                if self.sequence_widget.progress_bar.is_dragging:
                    should_update_playhead = False
                else:
                    self.sequence_widget.progress_bar.set_current_time(current_time)

            if should_update_playhead:
                self.sequence_widget.set_playhead_time(current_time)

            if hasattr(self, "oscilloscope_widget"):
                self.oscilloscope_widget.set_current_time(current_time)

            if self.unified_editor.preview_enabled:
                self._set_preview_enabled(False)

            total_duration_actual = (
                self.sequencer.playback_state.end_time or self.sequencer.project.get_total_duration()
            )
            total_duration = (
                total_duration_actual / bpm_ratio
                if not uses_tempo_map and original_bpm > 0 and current_bpm > 0 and original_bpm != current_bpm
                else total_duration_actual
            )
            if current_time >= total_duration:
                self.stop()
        elif (
            not self.sequencer.playback_state.is_playing
            and not self.unified_editor.preview_enabled
            and not self._has_pending_playback_prepare()
        ):
            self._set_preview_enabled(True)
