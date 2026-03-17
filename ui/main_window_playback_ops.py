"""
主窗口中的播放控制与播放状态同步相关操作。
"""

import time

from PyQt5.QtCore import QTimer


class MainWindowPlaybackOpsMixin:
    """承载 MainWindow 的播放控制、音量和播放状态同步逻辑。"""

    def _set_preview_enabled(self, enabled: bool):
        """统一控制编辑器预览状态。"""
        self.unified_editor.set_preview_enabled(enabled)

    def _set_play_button_state(self, is_playing: bool):
        """统一更新播放按钮文本和提示。"""
        if not hasattr(self, "play_stop_button"):
            return
        self.play_stop_button.setText("⏸" if is_playing else "▶")
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

    def toggle_play_stop(self):
        """切换播放/停止状态（合并播放和暂停）。"""
        if self.sequencer.playback_state.is_playing:
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
        if self.sequencer.playback_state.is_playing:
            return

        current_time = self.sequence_widget.playhead_time
        self._set_preview_enabled(False)
        self.sequencer.play(start_time=current_time)
        self.statusBar().showMessage("播放中...")

        self.playback_start_time = time.time()
        self.playback_start_offset = current_time

        self._set_play_button_state(True)
        self._set_oscilloscope_playing(True)

    def pause(self):
        """暂停。"""
        if not self.sequencer.playback_state.is_playing:
            return

        self.sequencer.stop()
        self.statusBar().showMessage("已暂停")
        self._set_oscilloscope_playing(False)
        self._set_play_button_state(False)

    def stop(self):
        """停止。"""
        self.sequencer.stop()
        self.statusBar().showMessage("已停止")

        self.sequence_widget.set_playhead_time(0.0)
        self.playback_start_time = None

        self._set_preview_enabled(True)
        self._set_play_button_state(False)
        self._set_oscilloscope_playing(False)

    def on_playback_volume_ratios_changed(self, ratios: dict):
        """播放音量占比改变（实时生效，无需重新生成音频）。"""
        print(f"[DEBUG] on_playback_volume_ratios_changed called with ratios: {ratios}")
        self.sequencer.playback_volume_ratios = ratios
        print(f"[DEBUG] sequencer.playback_volume_ratios set to: {self.sequencer.playback_volume_ratios}")

        if self.sequencer.playback_state.is_playing:
            has_zero_volume = any(ratio <= 0.001 for ratio in ratios.values())
            if has_zero_volume:
                self._update_playback_volumes_realtime()
            else:
                self._retarget_playback_restart_timer(self._update_playback_volumes_realtime, 50)
        else:
            self.statusBar().showMessage("播放音量占比已更新")

    def _update_playback_volumes_realtime(self):
        """实时更新播放音量（通过 Channel，无需重新生成音频）。"""
        if not self.sequencer.playback_state.is_playing:
            return

        volume_scale = getattr(self.sequencer, "current_volume_scale", 1.0)
        playback_enabled = getattr(self.sequencer, "playback_enabled_tracks", {})

        for track in self.sequencer.project.tracks:
            track_id = id(track)
            is_enabled = playback_enabled.get(track_id, track.enabled) if playback_enabled else track.enabled

            if not is_enabled:
                self.sequencer.audio_engine.set_track_volume(track_id, 0.0, track.volume)
            else:
                volume_ratio = (
                    self.sequencer.playback_volume_ratios.get(track_id, 1.0)
                    if self.sequencer.playback_volume_ratios
                    else 1.0
                )
                self.sequencer.audio_engine.set_track_volume(
                    track_id,
                    volume_ratio * volume_scale,
                    track.volume,
                )

        self.statusBar().showMessage("播放音量已实时更新")

    def on_playback_track_selection_changed(self, enabled_tracks: dict):
        """播放设置面板音轨勾选状态改变。"""
        if not hasattr(self.sequencer, "playback_enabled_tracks"):
            self.sequencer.playback_enabled_tracks = {}
        self.sequencer.playback_enabled_tracks = enabled_tracks
        print(f"[DEBUG] on_playback_track_selection_changed - enabled_tracks: {enabled_tracks}")
        print(f"[DEBUG] sequencer.playback_enabled_tracks set to: {self.sequencer.playback_enabled_tracks}")

        if self.sequencer.playback_state.is_playing:
            for track in self.sequencer.project.tracks:
                track_id = id(track)
                is_enabled = enabled_tracks.get(track_id, track.enabled)
                self.sequencer.audio_engine.set_track_enabled(track_id, is_enabled)

            self._update_playback_volumes_realtime()
            self.statusBar().showMessage("播放音轨启用状态已实时更新")
        else:
            self.statusBar().showMessage("播放音轨启用状态已更新")

    def _restart_playback_from_current_position(self):
        """从当前位置重新开始播放（用于实时应用播放设置更改）。"""
        if not self.sequencer.playback_state.is_playing:
            return

        current_time = self.sequencer.playback_state.current_time
        if self.playback_start_time:
            elapsed = time.time() - self.playback_start_time
            current_time = self.playback_start_offset + elapsed

        QTimer.singleShot(0, lambda: self._do_restart_playback(current_time))

    def _do_restart_playback(self, current_time: float):
        """实际执行重新播放（在主线程中）。"""
        if not self.sequencer.playback_state.is_playing:
            return

        if hasattr(self.sequencer, "_current_sound") and self.sequencer._current_sound:
            self.sequencer._current_sound.stop()
            self.sequencer._current_sound = None

        self.sequencer.play(start_time=current_time)
        self.playback_start_time = time.time()
        self.playback_start_offset = current_time

        if hasattr(self, "sequence_widget"):
            self.sequence_widget.set_playhead_time(current_time)

        self.statusBar().showMessage("播放设置已实时应用")

    def on_bpm_changed(self, value: int):
        """BPM 改变。"""
        if self.sequencer.playback_state.is_playing:
            current_bpm = int(self.sequencer.get_bpm())
            self.bpm_spinbox.blockSignals(True)
            self.bpm_spinbox.setValue(current_bpm)
            self.bpm_spinbox.blockSignals(False)
            self.statusBar().showMessage("播放期间不能调整BPM，请先停止播放")
            return

        self._sync_project_bpm_to_ui(float(value))
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
            elapsed_time = time.time() - self.playback_start_time
            actual_playback_time = self.playback_start_offset + elapsed_time

            project = self.sequencer.project
            original_bpm = getattr(project, "original_bpm", None) or project.bpm
            current_bpm = project.bpm

            if original_bpm > 0 and current_bpm > 0 and original_bpm != current_bpm:
                bpm_ratio = original_bpm / current_bpm
                current_time = actual_playback_time / bpm_ratio
            else:
                current_time = actual_playback_time
                bpm_ratio = 1.0

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
                if original_bpm > 0 and current_bpm > 0 and original_bpm != current_bpm
                else total_duration_actual
            )
            if current_time >= total_duration:
                self.stop()
        elif not self.sequencer.playback_state.is_playing and not self.unified_editor.preview_enabled:
            self._set_preview_enabled(True)
