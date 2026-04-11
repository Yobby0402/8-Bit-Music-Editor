"""
乐谱片段相关操作与可测试 helper。
"""

from __future__ import annotations

from typing import Sequence

from PyQt5.QtWidgets import QInputDialog, QMessageBox

from core.models import ADSRParams, Note, Track, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType

SNIPPET_NO_SELECTION = "no_selection"
SNIPPET_CROSS_TRACK_SELECTION = "cross_track_selection"
SNIPPET_INVALID_DRUM_SELECTION = "invalid_drum_selection"


def build_score_snippet_from_selection(
    selected_items: Sequence[tuple[object, Track]],
) -> tuple[Track, str, dict]:
    """将当前选区标准化为可持久化的乐谱片段数据。"""
    if not selected_items:
        raise ValueError(SNIPPET_NO_SELECTION)

    first_track = selected_items[0][1]
    is_drum_track = first_track.track_type == TrackType.DRUM_TRACK

    for item, track in selected_items:
        if track is not first_track:
            raise ValueError(SNIPPET_CROSS_TRACK_SELECTION)
        if is_drum_track and not isinstance(item, DrumEvent):
            raise TypeError(SNIPPET_INVALID_DRUM_SELECTION)

    if is_drum_track:
        all_beats = [event.start_beat for event, _track in selected_items]
        base_beat = min(all_beats)
        drums = [
            {
                "offset_beats": event.start_beat - base_beat,
                "duration_beats": event.duration_beats,
                "drum_type": event.drum_type.name,
                "velocity": getattr(event, "velocity", 100),
            }
            for event, _track in selected_items
        ]
        return first_track, "drum", {"drums": drums}

    all_times = [note.start_time for note, _track in selected_items]
    base_time = min(all_times)
    notes = [
        {
            "offset": note.start_time - base_time,
            "duration": note.duration,
            "pitch": note.pitch,
            "velocity": getattr(note, "velocity", 100),
            "waveform": getattr(getattr(note, "waveform", None), "name", ""),
            "duty_cycle": getattr(note, "duty_cycle", 0.5),
        }
        for note, _track in selected_items
    ]
    return first_track, "note", {"notes": notes}


def resolve_snippet_insert_position(
    snippet_type: str,
    target_track: Track,
    insert_mode: str,
    playhead_time: float,
    bpm: float,
) -> tuple[float, float]:
    """根据插入模式计算乐谱片段的时间/拍点基准。"""
    if insert_mode == "sequential":
        if snippet_type == "drum":
            last_end_beat = max(
                (event.end_beat for event in target_track.drum_events),
                default=0.0,
            )
            return last_end_beat * 60.0 / bpm, last_end_beat

        last_end_time = max((note.end_time for note in target_track.notes), default=0.0)
        return last_end_time, last_end_time * bpm / 60.0

    base_time = float(playhead_time)
    return base_time, base_time * bpm / 60.0


def build_preview_track(snippet_type: str, data: dict) -> Track:
    """将乐谱片段转换成可直接试听的临时音轨。"""
    preview_track = Track(
        name="预览",
        track_type=TrackType.DRUM_TRACK if snippet_type == "drum" else TrackType.NOTE_TRACK,
    )

    if snippet_type == "drum":
        drums = data.get("drums") or []
        for info in drums:
            drum_name = info.get("drum_type", "KICK")
            try:
                drum_type = getattr(DrumType, drum_name)
            except AttributeError:
                drum_type = DrumType.KICK

            preview_track.drum_events.append(
                DrumEvent(
                    drum_type=drum_type,
                    start_beat=float(info.get("offset_beats", 0.0)),
                    duration_beats=float(info.get("duration_beats", 1.0)),
                    velocity=int(info.get("velocity", 100)),
                )
            )
        return preview_track

    notes = data.get("notes") or []
    for info in notes:
        waveform_name = info.get("waveform", "SQUARE")
        try:
            waveform = getattr(WaveformType, waveform_name)
        except AttributeError:
            waveform = WaveformType.SQUARE

        preview_track.notes.append(
            Note(
                start_time=float(info.get("offset", 0.0)),
                duration=float(info.get("duration", 0.5)),
                pitch=int(info.get("pitch", 60)),
                velocity=int(info.get("velocity", 100)),
                waveform=waveform,
                duty_cycle=float(info.get("duty_cycle", 0.5)),
                adsr=ADSRParams(),
            )
        )
    return preview_track


def apply_score_snippet_to_track(
    sequencer,
    target_track: Track,
    snippet_type: str,
    data: dict,
    *,
    base_time: float,
    base_beat: float,
    selected_waveform=None,
) -> list[tuple[object, Track]]:
    """Apply a score snippet to a track and return the added items."""
    added_items: list[tuple[object, Track]] = []

    if snippet_type == "drum":
        for info in data.get("drums") or []:
            drum_name = info.get("drum_type", "KICK")
            try:
                drum_type = getattr(DrumType, drum_name)
            except AttributeError:
                drum_type = DrumType.KICK

            event = sequencer.add_drum_event(
                target_track,
                drum_type,
                base_beat + float(info.get("offset_beats", 0.0)),
                float(info.get("duration_beats", 1.0)),
                velocity=int(info.get("velocity", 100)),
            )
            added_items.append((event, target_track))
        return added_items

    for info in data.get("notes") or []:
        waveform_name = info.get("waveform", "") or "SQUARE"
        duty_cycle = float(info.get("duty_cycle", 0.5))
        note = sequencer.add_note(
            target_track,
            int(info.get("pitch", 60)),
            base_time + float(info.get("offset", 0.0)),
            float(info.get("duration", 0.25)),
            velocity=int(info.get("velocity", 100)),
        )
        try:
            note.waveform = (
                selected_waveform
                if selected_waveform is not None
                else getattr(WaveformType, waveform_name)
            )
        except AttributeError:
            pass
        if hasattr(note, "duty_cycle"):
            note.duty_cycle = duty_cycle
        added_items.append((note, target_track))

    return added_items


class MainWindowScoreOpsMixin:
    """承载 MainWindow 中的乐谱片段相关流程。"""

    def _prompt_score_snippet_details(self):
        """询问用户输入乐谱片段名称和分组。"""
        name, ok = QInputDialog.getText(self, "乐谱片段名称", "请输入片段名称：")
        if not ok or not name.strip():
            return None

        group, ok = QInputDialog.getText(
            self,
            "乐谱片段分组",
            "可选：输入分组名称（例如：常用鼓点 / 和弦进行）：",
        )
        if not ok:
            group = ""

        return name.strip(), group.strip()

    def _refresh_score_panel(self):
        """刷新乐谱片段面板。"""
        if hasattr(self, "score_panel"):
            self.score_panel.refresh()

    def _refresh_after_score_apply(
        self,
        target_track: Track,
        added_items: list[tuple[object, Track]],
    ):
        """Prefer lightweight UI sync after applying a score snippet."""
        note_sync_ok = bool(
            added_items
            and hasattr(self, "_sync_note_blocks_ui")
            and self._sync_note_blocks_ui(added_items)
        )
        if note_sync_ok:
            if hasattr(self.sequence_widget, "set_highlighted_track"):
                self.sequence_widget.set_highlighted_track(target_track)
            track_refresh_ok = False
            if hasattr(self, "_sync_track_ui"):
                track_refresh_ok = self._sync_track_ui(target_track)
            if not track_refresh_ok and hasattr(self, "_refresh_note_related_views"):
                self._refresh_note_related_views()
            return

        if added_items:
            self.refresh_ui(preserve_selection=False)
            return

        if hasattr(self, "_sync_track_ui") and self._sync_track_ui(target_track):
            if hasattr(self.sequence_widget, "set_highlighted_track"):
                self.sequence_widget.set_highlighted_track(target_track)
            return

        self.refresh_ui(preserve_selection=False)

    def on_score_create_from_selection(self):
        """从当前选区创建乐谱片段。"""
        if not hasattr(self.sequence_widget, "selected_items"):
            return

        selected = list(self.sequence_widget.selected_items)
        try:
            first_track, snippet_type, data = build_score_snippet_from_selection(selected)
        except ValueError as exc:
            if str(exc) == SNIPPET_NO_SELECTION:
                QMessageBox.information(
                    self,
                    "提示",
                    "请先在音轨区域选择一个或多个音符/鼓点。",
                )
            else:
                QMessageBox.warning(
                    self,
                    "提示",
                    "当前仅支持从单个音轨的选择创建片段，请不要跨多个音轨选择。",
                )
            return
        except TypeError:
            QMessageBox.warning(
                self,
                "提示",
                "鼓点乐谱片段仅支持来自打击乐音轨的事件。",
            )
            return

        snippet_details = self._prompt_score_snippet_details()
        if snippet_details is None:
            return

        name, group = snippet_details
        snippet_id = self.score_library.add_snippet(
            name=name,
            group=group,
            snippet_type=snippet_type,
            track_name=first_track.name,
            data=data,
        )

        self._refresh_score_panel()
        self.statusBar().showMessage(f"已保存乐谱片段：{name}（{snippet_id[:8]}）")

    def on_score_apply_snippet(self, snippet_id: str):
        """将指定乐谱片段应用到当前音轨。"""
        snippet = self.score_library.get_snippet(snippet_id)
        if not snippet:
            return

        snippet_type = snippet.get("type")
        data = snippet.get("data") or {}

        target_track = self._get_selected_track()
        if target_track is None:
            QMessageBox.information(self, "提示", "请先在音轨区域选择一个目标音轨。")
            return

        if snippet_type == "drum" and target_track.track_type != TrackType.DRUM_TRACK:
            QMessageBox.warning(self, "提示", "鼓点乐谱片段只能应用到打击乐音轨。")
            return
        if snippet_type == "note" and target_track.track_type != TrackType.NOTE_TRACK:
            QMessageBox.warning(
                self,
                "提示",
                "音符乐谱片段只能应用到音符音轨（主旋律、低音等）。",
            )
            return

        insert_mode = getattr(self.unified_editor, "insert_mode", "playhead")
        selected_waveform = getattr(self.unified_editor, "selected_waveform", None)
        base_time, base_beat = resolve_snippet_insert_position(
            snippet_type,
            target_track,
            insert_mode,
            float(self.sequence_widget.playhead_time),
            self.sequencer.get_bpm(),
        )

        added_items = apply_score_snippet_to_track(
            self.sequencer,
            target_track,
            snippet_type,
            data,
            base_time=base_time,
            base_beat=base_beat,
            selected_waveform=selected_waveform,
        )
        self._refresh_after_score_apply(target_track, added_items)
        self.statusBar().showMessage(
            f"已将乐谱片段“{snippet.get('name', '')}”应用到音轨：{target_track.name}"
        )

    def on_score_preview_snippet(self, snippet_id: str):
        """试听指定乐谱片段，不修改当前工程。"""
        snippet = self.score_library.get_snippet(snippet_id)
        if not snippet:
            return

        if self.sequencer.playback_state.is_playing:
            self.stop()

        snippet_type = snippet.get("type")
        data = snippet.get("data") or {}
        preview_track = build_preview_track(snippet_type, data)
        bpm = self.sequencer.get_bpm()

        try:
            audio = self.sequencer.audio_engine.generate_track_audio(
                preview_track,
                start_time=0.0,
                end_time=None,
                bpm=bpm,
                original_bpm=bpm,
            )
            self.sequencer.audio_engine.play_audio(audio, loop=False)
            self.statusBar().showMessage("正在试听乐谱片段")
        except Exception:
            pass

    def on_score_delete_snippet(self, snippet_id: str):
        """删除指定乐谱片段。"""
        self.score_library.delete_snippet(snippet_id)
        self._refresh_score_panel()
        self.statusBar().showMessage("已删除乐谱片段")
