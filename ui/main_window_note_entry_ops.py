"""
主窗口中的音符/鼓点编辑入口与可测试 helper。
"""

from __future__ import annotations

from core.models import Note, Track, TrackType, WaveformType
from core.track_events import DrumType
from ui.main_window_editor_ops import DRUM_NAMES, format_pitch_name


def resolve_entry_track(
    tracks: list[Track],
    track_type: TrackType,
    preferred_track: Track | None = None,
    *,
    require_items: bool = False,
) -> Track | None:
    """解析当前编辑入口应使用的音轨。"""

    def is_valid(track: Track | None) -> bool:
        if track is None or track.track_type != track_type:
            return False
        if not require_items:
            return True
        if track_type == TrackType.DRUM_TRACK:
            return bool(track.drum_events)
        return bool(track.notes)

    if is_valid(preferred_track):
        return preferred_track

    for track in tracks:
        if is_valid(track):
            return track
    return None


def compute_note_insert_time(
    track: Track,
    duration: float,
    insert_mode: str,
    playhead_time: float,
) -> float:
    """计算音符插入时间，并尽量避免与现有音符重叠。"""
    if insert_mode == "playhead":
        start_time = float(playhead_time)
    else:
        start_time = max((note.end_time for note in track.notes), default=0.0)

    for existing_note in track.notes:
        if start_time < existing_note.end_time and start_time + duration > existing_note.start_time:
            start_time = existing_note.end_time
            break
    return start_time


def compute_drum_insert_beat(
    track: Track,
    duration_beats: float,
    insert_mode: str,
    playhead_time: float,
    bpm: float,
) -> float:
    """计算打击乐事件插入拍点，并尽量避免与现有事件重叠。"""
    if insert_mode == "playhead":
        start_beat = float(playhead_time) * bpm / 60.0
    else:
        start_beat = max((event.end_beat for event in track.drum_events), default=0.0)

    for existing_event in track.drum_events:
        if start_beat < existing_event.end_beat and (
            start_beat + duration_beats > existing_event.start_beat
        ):
            start_beat = existing_event.end_beat
            break
    return start_beat


def find_last_note(track: Track) -> Note | None:
    """找到音轨中最后一个音符。"""
    return max(
        track.notes,
        key=lambda note: (note.end_time, note.start_time),
        default=None,
    )


class MainWindowNoteEntryOpsMixin:
    """承载 MainWindow 中的音符/鼓点编辑入口。"""

    def _can_add_editor_item(self) -> bool:
        """播放期间禁止通过编辑器继续插入对象。"""
        return not self.sequencer.playback_state.is_playing

    def _get_or_create_entry_track(
        self,
        track_type: TrackType,
        preferred_track: Track | None = None,
    ) -> Track:
        """获取编辑目标音轨，不存在时自动创建。"""
        track = resolve_entry_track(
            self.sequencer.project.tracks,
            track_type,
            preferred_track,
        )
        if track is not None:
            return track

        if track_type == TrackType.DRUM_TRACK:
            return self.sequencer.add_track(name="打击乐", track_type=TrackType.DRUM_TRACK)
        return self.sequencer.add_track(name="音轨 1", track_type=TrackType.NOTE_TRACK)

    def _finalize_entry_refresh(self, track: Track):
        """插入后统一刷新并高亮目标音轨。"""
        self.sequence_widget.set_highlighted_track(track)
        self.refresh_ui()

    def _add_note_like_item(
        self,
        pitch: int,
        duration_beats: float,
        waveform: WaveformType,
        target_track: Track | None = None,
        insert_mode: str = "sequential",
    ):
        """为主旋律和低音统一处理音符插入逻辑。"""
        if not self._can_add_editor_item():
            return

        track = self._get_or_create_entry_track(TrackType.NOTE_TRACK, target_track)
        duration = duration_beats * 60.0 / self.sequencer.get_bpm()
        start_time = compute_note_insert_time(
            track,
            duration,
            insert_mode,
            float(self.sequence_widget.playhead_time),
        )

        note = self.sequencer.add_note(track, pitch, start_time, duration)
        note.waveform = waveform
        self._finalize_entry_refresh(track)
        self.statusBar().showMessage(
            f"已添加音符: {format_pitch_name(pitch)} ({duration_beats}拍)"
        )

    def on_add_melody_note(
        self,
        pitch: int,
        duration_beats: float,
        waveform,
        target_track=None,
        insert_mode="sequential",
    ):
        """添加主旋律音符。"""
        self._add_note_like_item(pitch, duration_beats, waveform, target_track, insert_mode)

    def on_add_bass_event(
        self,
        pitch: int,
        duration_beats: float,
        waveform,
        target_track=None,
        insert_mode="sequential",
    ):
        """添加低音事件。"""
        self._add_note_like_item(pitch, duration_beats, waveform, target_track, insert_mode)

    def on_add_drum_event(
        self,
        drum_type: DrumType,
        duration_beats: float,
        target_track=None,
        insert_mode="sequential",
    ):
        """添加打击乐事件。"""
        if not self._can_add_editor_item():
            return

        track = self._get_or_create_entry_track(TrackType.DRUM_TRACK, target_track)
        start_beat = compute_drum_insert_beat(
            track,
            duration_beats,
            insert_mode,
            float(self.sequence_widget.playhead_time),
            self.sequencer.get_bpm(),
        )
        self.sequencer.add_drum_event(track, drum_type, start_beat, duration_beats)
        self._finalize_entry_refresh(track)
        self.statusBar().showMessage(
            f"已添加打击乐: {DRUM_NAMES.get(drum_type, '打击')} ({duration_beats}拍)"
        )

    def delete_last_note(self):
        """删除当前音轨上的最后一个音符。"""
        preferred_track = getattr(getattr(self, "unified_editor", None), "selected_track", None)
        target_track = resolve_entry_track(
            self.sequencer.project.tracks,
            TrackType.NOTE_TRACK,
            preferred_track,
            require_items=True,
        )
        if target_track is None:
            self.statusBar().showMessage("没有可删除的音符")
            return

        last_note = find_last_note(target_track)
        if last_note is None:
            self.statusBar().showMessage("没有找到可删除的音符")
            return

        self.sequencer.remove_note(target_track, last_note, use_command=True)
        self.refresh_ui()
        self.statusBar().showMessage(
            f"已删除最后一个音符: {format_pitch_name(last_note.pitch)} (音轨: {target_track.name})"
        )
