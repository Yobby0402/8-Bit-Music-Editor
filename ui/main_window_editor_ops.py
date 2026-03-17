"""
主窗口中的编辑动作、选择联动与属性同步逻辑。
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QMessageBox

from core.command import BatchCommand, DeleteNoteCommand, DeleteTrackCommand, ModifyNoteCommand
from core.models import Note, Track, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DRUM_NAMES = {
    DrumType.KICK: "底鼓",
    DrumType.SNARE: "军鼓",
    DrumType.HIHAT: "踩镲",
    DrumType.CRASH: "吊镲",
}
WAVEFORM_INDEX_MAP = {
    0: WaveformType.SQUARE,
    1: WaveformType.TRIANGLE,
    2: WaveformType.SAWTOOTH,
    3: WaveformType.SINE,
    4: WaveformType.NOISE,
}


def format_pitch_name(pitch: int) -> str:
    """将 MIDI 音高格式化为音名。"""
    octave = pitch // 12 - 1
    note_name = NOTE_NAMES[pitch % 12]
    return f"{note_name}{octave}"


def format_sequence_item_label(item: object) -> str:
    """格式化音符或打击乐事件的显示名称。"""
    if isinstance(item, DrumEvent):
        return DRUM_NAMES.get(item.drum_type, "打击")
    return format_pitch_name(item.pitch)


def format_sequence_item_message(action: str, item: object) -> str:
    """格式化针对音符或打击乐事件的状态栏消息。"""
    if isinstance(item, DrumEvent):
        return f"{action}打击乐: {format_sequence_item_label(item)}"
    return f"{action}音符: {format_sequence_item_label(item)}"


def count_track_items(track: Track) -> int:
    """统计音轨内当前可编辑对象数量。"""
    if track.track_type == TrackType.DRUM_TRACK:
        return len(track.drum_events)
    return len(track.notes)


def build_track_multi_select_message(track: Track, selected_count: int) -> str:
    """生成音轨编辑模式下的多选提示文案。"""
    if track.track_type == TrackType.DRUM_TRACK:
        return (
            f"音轨: {track.name}\n"
            f"已选中 {selected_count} 个打击乐事件\n"
            "（打击乐事件暂不支持批量编辑）"
        )
    return f"音轨: {track.name}\n已选中 {selected_count} 个音符\n可以统一编辑共有属性"


def build_single_note_property_updates(property_panel, note: Note, bpm: float) -> dict:
    """从属性面板提取单音符更新参数。"""
    kwargs = {}

    if hasattr(property_panel, "pitch_spinbox"):
        new_pitch = property_panel.pitch_spinbox.value()
        if new_pitch != note.pitch:
            kwargs["pitch"] = new_pitch

    if hasattr(property_panel, "duration_spinbox"):
        duration_beats = property_panel.duration_spinbox.value()
        duration_seconds = duration_beats * 60.0 / bpm
        if abs(duration_seconds - note.duration) > 0.001:
            kwargs["duration"] = duration_seconds

    if hasattr(property_panel, "velocity_slider"):
        new_velocity = property_panel.velocity_slider.value()
        if new_velocity != note.velocity:
            kwargs["velocity"] = new_velocity

    if hasattr(property_panel, "waveform_combo"):
        waveform = WAVEFORM_INDEX_MAP.get(
            property_panel.waveform_combo.currentIndex(),
            WaveformType.SQUARE,
        )
        if waveform != note.waveform:
            kwargs["waveform"] = waveform

    if hasattr(property_panel, "attack_spinbox") and note.adsr:
        adsr_updates = {}
        if abs(property_panel.attack_spinbox.value() - note.adsr.attack) > 0.001:
            adsr_updates["attack"] = property_panel.attack_spinbox.value()
        if abs(property_panel.decay_spinbox.value() - note.adsr.decay) > 0.001:
            adsr_updates["decay"] = property_panel.decay_spinbox.value()
        if abs(property_panel.sustain_spinbox.value() - note.adsr.sustain) > 0.001:
            adsr_updates["sustain"] = property_panel.sustain_spinbox.value()
        if abs(property_panel.release_spinbox.value() - note.adsr.release) > 0.001:
            adsr_updates["release"] = property_panel.release_spinbox.value()
        if adsr_updates:
            kwargs["adsr"] = adsr_updates

    return kwargs


def build_batch_note_property_updates(property_panel) -> tuple[dict, int | None]:
    """从批量编辑区提取批量修改参数和力度偏移。"""
    kwargs = {}
    velocity_offset = None

    if hasattr(property_panel, "batch_waveform_combo") and getattr(
        property_panel,
        "_batch_waveform_dirty",
        False,
    ):
        waveform = WAVEFORM_INDEX_MAP.get(property_panel.batch_waveform_combo.currentIndex())
        if waveform is not None:
            kwargs["waveform"] = waveform

    if hasattr(property_panel, "batch_velocity_slider") and getattr(
        property_panel,
        "_batch_velocity_dirty",
        False,
    ):
        kwargs["velocity"] = property_panel.batch_velocity_slider.value()

    if "velocity" not in kwargs and hasattr(property_panel, "batch_velocity_offset_spinbox"):
        if getattr(property_panel, "_batch_velocity_offset_dirty", False):
            offset = property_panel.batch_velocity_offset_spinbox.value()
            if offset != 0:
                velocity_offset = offset

    if hasattr(property_panel, "batch_duty_spinbox") and getattr(
        property_panel,
        "_batch_duty_dirty",
        False,
    ):
        kwargs["duty_cycle"] = property_panel.batch_duty_spinbox.value()

    return kwargs, velocity_offset


class MainWindowEditorOpsMixin:
    """承载 MainWindow 中的编辑动作与属性同步流程。"""

    def _restore_block_selection(self, notes_and_tracks: list):
        """刷新后恢复多选状态。"""
        try:
            selected_blocks = []
            for note, track in notes_and_tracks:
                block = self.sequence_widget.note_blocks.get((id(note), id(track)))
                if block:
                    block.setSelected(True)
                    selected_blocks.append(block)
            if selected_blocks and hasattr(self.sequence_widget, "_update_selection_from_blocks"):
                self.sequence_widget._update_selection_from_blocks(selected_blocks)
        except Exception:
            pass

    def _clear_selected_editor_state(self):
        """清空当前选中项与编辑器中的选中音轨。"""
        self.selected_note = None
        self.selected_track = None
        if hasattr(self, "unified_editor"):
            self.unified_editor.set_selected_track(None)

    def on_note_selected(self, note, track):
        """音符或打击乐事件被选中。"""
        self.selected_note = note
        self.selected_track = track
        self.property_panel.set_note(note, track)

        message = format_sequence_item_message("已选中", note)
        if isinstance(note, DrumEvent):
            self.statusBar().showMessage(f"{message} (按Delete键删除)")
        else:
            self.statusBar().showMessage(f"{message} (按Delete键删除)")
        self._focus_property_panel()

    def on_note_deleted(self, note, track):
        """单个音符被删除。"""
        if note in track.notes:
            self.sequencer.remove_note(track, note, use_command=True)

        self.refresh_ui()
        self.statusBar().showMessage(format_sequence_item_message("已删除", note))

    def on_notes_deleted(self, notes_and_tracks):
        """批量删除音符。"""
        if not notes_and_tracks:
            return

        commands = []
        for note, track in notes_and_tracks:
            if note in track.notes:
                commands.append(DeleteNoteCommand(self.sequencer, track, note))

        if commands:
            batch_command = BatchCommand(commands, f"批量删除 {len(commands)} 个音符")
            self.sequencer.command_history.execute_command(batch_command)
            QTimer.singleShot(50, lambda: self.refresh_ui())
            self.statusBar().showMessage(f"已删除 {len(commands)} 个音符")

    def on_note_position_changed(self, note, track, old_start_time, new_start_time):
        """音符位置改变。"""
        if abs(old_start_time - new_start_time) > 0.001:
            note.start_time = old_start_time
            self.sequencer.move_note(track, note, new_start_time)

        self.statusBar().showMessage(f"音符已移动到: {new_start_time:.2f}s")
        self.refresh_ui()

    def on_property_changed(self, note: Note, track: Track):
        """属性面板中的单音符属性改变。"""
        kwargs = build_single_note_property_updates(
            self.property_panel,
            note,
            self.sequencer.get_bpm(),
        )

        if kwargs:
            if "duration" in kwargs:
                old_duration = note.duration
                new_duration = kwargs["duration"]
                duration_delta = new_duration - old_duration
                self.sequencer.modify_note(track, note, **kwargs)
                if abs(duration_delta) > 0.001:
                    self.property_panel.adjust_following_notes(duration_delta)
            else:
                self.sequencer.modify_note(track, note, **kwargs)

        self.refresh_ui(preserve_selection=True)
        if self.property_panel.current_note == note:
            self.property_panel.update_ui()

    def on_property_update_requested(self, note: Note, track: Track):
        """属性面板请求刷新 UI。"""
        self.refresh_ui()

    def on_selection_changed(self):
        """序列编辑器选择变化。"""
        selected_blocks = [
            item
            for item in self.sequence_widget.scene.selectedItems()
            if hasattr(item, "item") and hasattr(item, "track")
        ]

        if self.property_panel.current_track_for_edit is not None:
            current_track = self.property_panel.current_track_for_edit
            all_in_current_track = all(
                id(block.track) == id(current_track) for block in selected_blocks
            )

            if all_in_current_track:
                if selected_blocks:
                    notes_and_tracks = [(block.item, block.track) for block in selected_blocks]
                    self.property_panel.current_notes = notes_and_tracks
                    if self.property_panel.multi_select_label.isVisible():
                        self.property_panel.multi_select_label.setText(
                            build_track_multi_select_message(current_track, len(notes_and_tracks))
                        )
                return

            self.property_panel.current_track_for_edit = None

        if len(selected_blocks) == 0:
            self.property_panel.set_note(None, None)
        elif len(selected_blocks) == 1:
            block = selected_blocks[0]
            self.property_panel.set_note(block.item, block.track)
        else:
            notes_and_tracks = [(block.item, block.track) for block in selected_blocks]
            self.property_panel.set_notes(notes_and_tracks)
            self._focus_property_panel()

    def on_batch_property_changed(self, notes_and_tracks: list):
        """批量属性改变。"""
        if not notes_and_tracks:
            return

        kwargs, velocity_offset = build_batch_note_property_updates(self.property_panel)
        velocity_offset_applied = False

        if velocity_offset is not None:
            velocity_commands = []
            for note, track in notes_and_tracks:
                new_velocity = max(0, min(127, note.velocity + velocity_offset))
                if new_velocity != note.velocity:
                    velocity_commands.append(
                        ModifyNoteCommand(
                            self.sequencer,
                            track,
                            note,
                            velocity=new_velocity,
                        )
                    )

            if velocity_commands:
                batch_cmd = BatchCommand(
                    velocity_commands,
                    f"批量调整力度偏移 ({velocity_offset:+d})",
                )
                self.sequencer.command_history.execute_command(batch_cmd)
                velocity_offset_applied = True

        if kwargs:
            self.sequencer.batch_modify_notes(notes_and_tracks, **kwargs)

        if kwargs or velocity_offset_applied:
            self.refresh_ui(preserve_selection=True)
            self._restore_block_selection(notes_and_tracks)

            if velocity_offset_applied:
                offset_value = self.property_panel.batch_velocity_offset_spinbox.value()
                self.statusBar().showMessage(
                    f"已批量调整 {len(notes_and_tracks)} 个音符的力度偏移 ({offset_value:+d})"
                )
            elif kwargs:
                self.statusBar().showMessage(f"已批量修改 {len(notes_and_tracks)} 个音符的属性")

    def on_track_clicked(self, track: Track):
        """音轨被点击。"""
        self.property_panel.set_track(track)
        self.sequence_widget.select_track_notes(track)
        self.statusBar().showMessage(
            f"已选中音轨: {track.name} ({count_track_items(track)} 个音符/事件)"
        )

    def on_track_property_changed(self, track: Track):
        """音轨属性改变。"""
        self.refresh_ui(preserve_selection=True)
        self.statusBar().showMessage(f"已更新音轨: {track.name}")

    def on_track_deleted(self, track: Track):
        """删除指定音轨。"""
        if track not in self.sequencer.project.tracks:
            self.refresh_ui()
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除音轨 "{track.name}" 吗？\n此操作将删除该音轨上的所有音符。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            command = DeleteTrackCommand(self.sequencer, track)
            self.sequencer.command_history.execute_command(command)
            self.refresh_ui(force_full_refresh=True)
            self._clear_selected_editor_state()
            self.statusBar().showMessage(f"已删除音轨: {track.name}")

    def clear_all_tracks(self):
        """清空所有音轨。"""
        if not self.sequencer.project.tracks:
            self.statusBar().showMessage("没有可清空的音轨")
            return

        reply = QMessageBox.question(
            self,
            "确认清空",
            (
                f"确定要清空所有 {len(self.sequencer.project.tracks)} 个音轨吗？\n"
                "此操作将删除所有音轨及其上的所有音符，且无法撤销。"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            tracks_to_delete = list(self.sequencer.project.tracks)
            commands = [DeleteTrackCommand(self.sequencer, track) for track in tracks_to_delete]

            if commands:
                batch_command = BatchCommand(commands, f"清空所有音轨 ({len(commands)} 个)")
                self.sequencer.command_history.execute_command(batch_command)
                self.refresh_ui()
                self._clear_selected_editor_state()
                self.statusBar().showMessage(f"已清空所有音轨 ({len(commands)} 个)")

    def on_track_enabled_changed(self, track: Track, enabled: bool):
        """音轨启用状态改变。"""
        if not hasattr(self.sequencer, "project") or not self.sequencer.project:
            return

        track.enabled = enabled
        QTimer.singleShot(50, self.sequence_widget.refresh)
        status = "启用" if enabled else "禁用"
        self.statusBar().showMessage(f"已{status}音轨: {track.name}")

    def select_all_notes(self):
        """全选当前序列编辑器中的音符。"""
        if hasattr(self.sequence_widget, "view"):
            fake_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.ControlModifier)
            self.sequence_widget.on_key_press(fake_event)

    def on_note_added(self, note, track):
        """音符添加。"""
        self.statusBar().showMessage(f"已添加音符: MIDI {note.pitch}")

    def on_note_removed(self, note, track):
        """音符删除。"""
        self.statusBar().showMessage("已删除音符")
