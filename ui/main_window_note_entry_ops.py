"""
主窗口中的音符/鼓点编辑入口与可测试 helper。
"""

from __future__ import annotations

from core.models import Note, Track, TrackRole, TrackType, WaveformType
from core.track_events import DrumType
from ui.main_window_editor_ops import DRUM_NAMES, format_pitch_name


def resolve_entry_track(
    tracks: list[Track],
    track_type: TrackType,
    preferred_track: Track | None = None,
    *,
    require_items: bool = False,
    preferred_role: TrackRole | None = None,
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

    def role_matches(track: Track) -> bool:
        if preferred_role is None or track_type == TrackType.DRUM_TRACK:
            return True
        return track.role == preferred_role

    if is_valid(preferred_track):
        return preferred_track

    for track in tracks:
        if is_valid(track) and role_matches(track):
            return track
    return None


def resolve_insert_track(
    tracks: list[Track],
    track_type: TrackType,
    explicit_track: Track | None = None,
    selected_track: Track | None = None,
) -> Track | None:
    """Resolve the track used for note/drum insertion.

    Priority:
    1. Explicit target track if it matches the required type.
    2. Currently selected track if it matches the required type.
    3. The first compatible track in project order.
    """

    def is_valid(track: Track | None) -> bool:
        return track is not None and track in tracks and track.track_type == track_type

    if is_valid(explicit_track):
        return explicit_track
    if is_valid(selected_track):
        return selected_track

    for track in tracks:
        if track.track_type == track_type:
            return track
    return None


def get_default_track_name_for_role(track_type: TrackType, role: TrackRole | None = None) -> str:
    """Return a localized default name for newly created entry tracks."""
    if track_type == TrackType.DRUM_TRACK:
        return "打击乐"

    role_name_map = {
        TrackRole.MELODY: "主旋律",
        TrackRole.BASS: "低音",
        TrackRole.HARMONY: "和声",
        TrackRole.EFFECT: "效果",
    }
    return role_name_map.get(role, "音轨 1")


def compute_note_insert_time(
    track: Track,
    duration: float,
    insert_mode: str,
    playhead_time: float,
    *,
    duration_resolver=None,
) -> float:
    """计算音符插入时间，并尽量避免与现有音符重叠。"""
    if insert_mode == "playhead":
        start_time = float(playhead_time)
    else:
        start_time = max((note.end_time for note in track.notes), default=0.0)

    while True:
        resolved_duration = duration_resolver(start_time) if duration_resolver else duration
        overlap_found = False
        for existing_note in track.notes:
            if (
                start_time < existing_note.end_time
                and start_time + resolved_duration > existing_note.start_time
            ):
                next_start_time = existing_note.end_time
                if next_start_time <= start_time:
                    return start_time
                start_time = next_start_time
                overlap_found = True
                break
        if not overlap_found:
            break
    return start_time


def compute_note_duration_seconds(
    start_time: float,
    duration_beats: float,
    bpm: float,
    project=None,
) -> float:
    """Convert note duration beats to seconds using the project tempo map when available."""
    if project is not None:
        start_beat = project.seconds_to_beats(start_time)
        end_time = project.beats_to_seconds(start_beat + duration_beats)
        return max(0.0, end_time - start_time)
    return max(0.0, duration_beats) * 60.0 / bpm


def compute_playhead_beat(playhead_time: float, bpm: float, project=None) -> float:
    """Convert playhead seconds to beats using the project tempo map when available."""
    if project is not None:
        return project.seconds_to_beats(playhead_time)
    return max(0.0, float(playhead_time)) * bpm / 60.0


def compute_drum_insert_beat(
    track: Track,
    duration_beats: float,
    insert_mode: str,
    playhead_time: float,
    bpm: float,
    project=None,
) -> float:
    """计算打击乐事件插入拍点，并尽量避免与现有事件重叠。"""
    if insert_mode == "playhead":
        start_beat = compute_playhead_beat(playhead_time, bpm, project)
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
        preferred_role: TrackRole | None = None,
        *,
        match_existing_role: bool = True,
    ) -> Track:
        """获取编辑目标音轨，不存在时自动创建。"""
        track = resolve_entry_track(
            self.sequencer.project.tracks,
            track_type,
            preferred_track,
            preferred_role=preferred_role if match_existing_role else None,
        )
        if track is not None:
            return track

        if track_type == TrackType.DRUM_TRACK:
            return self.sequencer.add_track(
                name=get_default_track_name_for_role(track_type),
                track_type=TrackType.DRUM_TRACK,
            )

        track = self.sequencer.add_track(
            name=get_default_track_name_for_role(track_type, preferred_role),
            track_type=TrackType.NOTE_TRACK,
        )
        if preferred_role is not None:
            track.role = preferred_role
        return track

    def _get_current_entry_selected_track(self) -> Track | None:
        """Return the track the UI currently treats as selected for insertion."""
        project_tracks = list(getattr(self.sequencer.project, "tracks", []) or [])
        sequence_widget = getattr(self, "sequence_widget", None)
        unified_editor = getattr(self, "unified_editor", None)

        candidates: list[Track | None] = [
            getattr(self, "selected_track", None),
            getattr(unified_editor, "selected_track", None),
            getattr(sequence_widget, "highlighted_track", None),
        ]

        selected_tracks = list(getattr(sequence_widget, "selected_tracks", []) or [])
        if selected_tracks:
            candidates.append(selected_tracks[-1])

        if hasattr(self, "_get_selected_track"):
            try:
                candidates.append(self._get_selected_track())
            except Exception:
                pass

        for candidate in candidates:
            if candidate in project_tracks:
                return candidate
        return None

    def _resolve_insert_target_track(
        self,
        track_type: TrackType,
        explicit_track: Track | None = None,
    ) -> Track | None:
        """Resolve insertion target using explicit target, current selection, then defaults."""
        return resolve_insert_track(
            self.sequencer.project.tracks,
            track_type,
            explicit_track,
            self._get_current_entry_selected_track(),
        )

    def _finalize_entry_refresh(self, track: Track, item=None):
        """插入后优先执行局部刷新，必要时再回退到整页刷新。"""
        if item is not None and self._sync_note_block_ui(item, track, highlight_track=True):
            if hasattr(self, "_refresh_note_related_views"):
                self._refresh_note_related_views()
            return

        self.sequence_widget.set_highlighted_track(track)
        self.refresh_ui()

    def _add_note_like_item(
        self,
        pitch: int,
        duration_beats: float,
        waveform: WaveformType,
        target_track: Track | None = None,
        insert_mode: str = "sequential",
        preferred_role: TrackRole | None = None,
    ):
        """为主旋律和低音统一处理音符插入逻辑。"""
        if not self._can_add_editor_item():
            return

        resolved_target_track = self._resolve_insert_target_track(
            TrackType.NOTE_TRACK,
            target_track,
        )
        track = self._get_or_create_entry_track(
            TrackType.NOTE_TRACK,
            resolved_target_track,
            preferred_role=preferred_role,
            match_existing_role=False,
        )
        project = getattr(self.sequencer, "project", None)
        bpm = self.sequencer.get_bpm()
        playhead_time = float(self.sequence_widget.playhead_time)
        initial_start_time = (
            playhead_time
            if insert_mode == "playhead"
            else max((note.end_time for note in track.notes), default=0.0)
        )

        def duration_resolver(start_time: float) -> float:
            return compute_note_duration_seconds(
                start_time,
                duration_beats,
                bpm,
                project,
            )

        duration = duration_resolver(initial_start_time)
        start_time = compute_note_insert_time(
            track,
            duration,
            insert_mode,
            playhead_time,
            duration_resolver=duration_resolver,
        )
        duration = duration_resolver(start_time)

        note = self.sequencer.add_note(track, pitch, start_time, duration)
        note.waveform = waveform
        self._finalize_entry_refresh(track, note)
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
        self._add_note_like_item(
            pitch,
            duration_beats,
            waveform,
            target_track,
            insert_mode,
            preferred_role=TrackRole.MELODY,
        )

    def on_add_bass_event(
        self,
        pitch: int,
        duration_beats: float,
        waveform,
        target_track=None,
        insert_mode="sequential",
    ):
        """添加低音事件。"""
        self._add_note_like_item(
            pitch,
            duration_beats,
            waveform,
            target_track,
            insert_mode,
            preferred_role=TrackRole.BASS,
        )

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

        resolved_target_track = self._resolve_insert_target_track(
            TrackType.DRUM_TRACK,
            target_track,
        )
        track = self._get_or_create_entry_track(
            TrackType.DRUM_TRACK,
            resolved_target_track,
        )
        start_beat = compute_drum_insert_beat(
            track,
            duration_beats,
            insert_mode,
            float(self.sequence_widget.playhead_time),
            self.sequencer.get_bpm(),
            getattr(self.sequencer, "project", None),
        )
        event = self.sequencer.add_drum_event(track, drum_type, start_beat, duration_beats)
        self._finalize_entry_refresh(track, event)
        self.statusBar().showMessage(
            f"已添加打击乐: {DRUM_NAMES.get(drum_type, '打击')} ({duration_beats}拍)"
        )

    def delete_last_note(self):
        """删除当前音轨上的最后一个音符。"""
        unified_editor = getattr(self, "unified_editor", None)
        preferred_track = getattr(unified_editor, "selected_track", None)
        preferred_role = (
            TrackRole.BASS
            if getattr(unified_editor, "current_entry_role", "melody") == "bass"
            else TrackRole.MELODY
        )
        target_track = resolve_entry_track(
            self.sequencer.project.tracks,
            TrackType.NOTE_TRACK,
            preferred_track,
            require_items=True,
            preferred_role=preferred_role,
        )
        if target_track is None:
            self.statusBar().showMessage("没有可删除的音符")
            return

        last_note = find_last_note(target_track)
        if last_note is None:
            self.statusBar().showMessage("没有找到可删除的音符")
            return

        self.sequencer.remove_note(target_track, last_note, use_command=True)
        if hasattr(self, "property_panel") and self.property_panel.current_note == last_note:
            self.property_panel.set_note(None, None)
        if not self._remove_note_block_ui(last_note, target_track):
            self.refresh_ui()
        elif hasattr(self, "_refresh_note_related_views"):
            self._refresh_note_related_views()
        self.statusBar().showMessage(
            f"已删除最后一个音符: {format_pitch_name(last_note.pitch)} (音轨: {target_track.name})"
        )
