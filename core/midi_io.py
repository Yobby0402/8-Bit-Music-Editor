"""
MIDI导入导出模块

负责MIDI文件的读取和写入。
"""

from time import perf_counter
from typing import Dict, List, Optional

import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack

from .models import ADSRParams, BPMSegment, Note, Project, Track, TrackType, WaveformType
from .musical_time import TempoEvent, TempoRegion, build_tempo_regions, ticks_to_seconds_with_regions

MIDI_IMPORT_PROFILE_THRESHOLD_MS = 200.0


class MidiIO:
    @staticmethod
    def _log_import_profile(
        *,
        file_path: str,
        load_ms: float,
        tempo_ms: float,
        tracks_ms: float,
        track_count: int,
        note_count: int,
    ) -> None:
        """Print a compact stage breakdown for slow MIDI imports."""
        total_ms = load_ms + tempo_ms + tracks_ms
        if total_ms < MIDI_IMPORT_PROFILE_THRESHOLD_MS:
            return

        print(
            "[PROFILE] midi.import_stages "
            f"total={total_ms:.1f}ms "
            f"load={load_ms:.1f}ms "
            f"tempo={tempo_ms:.1f}ms "
            f"tracks={tracks_ms:.1f}ms "
            f"track_count={track_count} "
            f"note_count={note_count} "
            f"source={file_path!r}"
        )

    @staticmethod
    def _extract_track_name(midi_track: MidiTrack, track_index: int) -> str:
        """Extract a displayable track name from a MIDI track."""
        track_name = f"轨道 {track_index + 1}"
        for msg in midi_track:
            if msg.type != "track_name":
                continue
            try:
                if isinstance(msg.name, bytes):
                    try:
                        track_name = msg.name.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            track_name = msg.name.decode("latin-1")
                        except UnicodeDecodeError:
                            try:
                                track_name = msg.name.decode("gbk")
                            except UnicodeDecodeError:
                                track_name = msg.name.decode("utf-8", errors="replace")
                else:
                    track_name = msg.name
            except Exception:
                track_name = f"轨道 {track_index + 1}"
            break
        return track_name

    @staticmethod
    def _apply_note_tick_timing_fast(
        note: Note,
        start_tick: int,
        duration_ticks: int,
        tempo_regions: list[TempoRegion],
        resolution: int,
    ) -> None:
        """Populate note tick/second timing using prebuilt tempo regions."""
        safe_start_tick = max(0, int(start_tick))
        safe_duration_ticks = max(0, int(duration_ticks))
        start_time = ticks_to_seconds_with_regions(safe_start_tick, tempo_regions, resolution)
        end_time = ticks_to_seconds_with_regions(
            safe_start_tick + safe_duration_ticks,
            tempo_regions,
            resolution,
        )
        note.start_tick = safe_start_tick
        note.duration_ticks = safe_duration_ticks
        note.start_time = start_time
        note.duration = max(0.0, end_time - start_time)
    """MIDI导入导出处理器"""

    @staticmethod
    def _extract_tempo_events(mid: MidiFile) -> List[TempoEvent]:
        """从MIDI文件中提取标准 tick 锚定的 tempo events。"""
        raw_events = []
        for midi_track in mid.tracks:
            current_tick = 0
            for msg in midi_track:
                current_tick += msg.time
                if msg.type == "set_tempo":
                    raw_events.append((current_tick, float(mido.tempo2bpm(msg.tempo))))

        if not raw_events:
            return [TempoEvent(0, 120.0)]

        raw_events.sort(key=lambda item: item[0])
        tempo_events: List[TempoEvent] = []
        for tick, bpm in raw_events:
            event = TempoEvent(max(0, int(tick)), bpm)
            if tempo_events and tempo_events[-1].tick == event.tick:
                tempo_events[-1] = event
            else:
                tempo_events.append(event)

        if tempo_events[0].tick != 0:
            tempo_events.insert(0, TempoEvent(0, 120.0))

        return tempo_events

    @staticmethod
    def _extract_bpm_segments(mid: MidiFile, ticks_per_beat: int) -> List[BPMSegment]:
        """
        从MIDI文件中提取BPM段信息
        
        分析所有轨道中的tempo变化，创建BPM段列表。
        需要正确计算每个tempo消息的时间位置。
        
        Args:
            mid: MIDI文件对象
            ticks_per_beat: 每拍的tick数
        
        Returns:
            BPM段列表
        """
        # 收集所有tempo消息及其时间位置（以秒为单位）
        tempo_events = []  # [(time_seconds, tempo_microseconds), ...]
        
        # 使用默认120 BPM作为初始tempo
        default_tempo = mido.bpm2tempo(120.0)
        current_tempo = default_tempo
        current_time = 0.0
        current_tick = 0
        
        # 遍历所有轨道，收集tempo消息
        # 需要按时间顺序处理所有消息
        all_messages = []  # [(tick, msg), ...]
        for midi_track in mid.tracks:
            track_tick = 0
            for msg in midi_track:
                track_tick += msg.time
                all_messages.append((track_tick, msg))
        
        # 按tick时间排序
        all_messages.sort(key=lambda x: x[0])
        
        # 处理所有消息，找到tempo变化
        for tick, msg in all_messages:
            # 计算从上次tempo变化到现在的delta time
            delta_tick = tick - current_tick
            if delta_tick > 0:
                try:
                    delta_time = mido.tick2second(delta_tick, ticks_per_beat, current_tempo)
                except Exception:
                    delta_time = delta_tick * (current_tempo / 1_000_000.0) / ticks_per_beat
                current_time += delta_time
            
            current_tick = tick
            
            # 如果是tempo消息，记录它
            if msg.type == 'set_tempo':
                # 如果这是第一个tempo消息，记录在时间0处
                if not tempo_events:
                    tempo_events.append((0.0, msg.tempo))
                else:
                    # 记录当前时间的tempo变化
                    tempo_events.append((current_time, msg.tempo))
                current_tempo = msg.tempo
        
        # 如果没有找到任何tempo消息，返回空列表（将使用默认BPM）
        if not tempo_events:
            return []
        
        # 去重（相同时间的tempo只保留最后一个）
        unique_tempo_events = []
        seen_times = set()
        for time_seconds, tempo_microseconds in reversed(tempo_events):
            if time_seconds not in seen_times:
                unique_tempo_events.append((time_seconds, tempo_microseconds))
                seen_times.add(time_seconds)
        unique_tempo_events.reverse()
        
        # 创建BPM段列表
        bpm_segments = []
        for i, (time_seconds, tempo_microseconds) in enumerate(unique_tempo_events):
            bpm = mido.tempo2bpm(tempo_microseconds)
            # 结束时间由下一个段决定（最后一个段的结束时间为None）
            end_time = None
            if i + 1 < len(unique_tempo_events):
                end_time = unique_tempo_events[i + 1][0]
            bpm_segments.append(BPMSegment(start_time=time_seconds, bpm=bpm, end_time=end_time))
        
        return bpm_segments
    
    @staticmethod
    def _calculate_average_bpm(mid: MidiFile, ticks_per_beat: int) -> Optional[float]:
        """
        计算MIDI文件的加权平均BPM
        
        分析所有轨道中的tempo变化，根据每个tempo持续的时间计算加权平均BPM。
        这样可以更好地处理有tempo变化的MIDI文件。
        
        Args:
            mid: MIDI文件对象
            ticks_per_beat: 每拍的tick数
        
        Returns:
            加权平均BPM，如果没有找到tempo消息则返回None
        """
        # 收集所有tempo消息及其时间位置
        tempo_events = []  # [(tick_time, tempo_microseconds), ...]
        
        # 遍历所有轨道，收集tempo消息
        for midi_track in mid.tracks:
            current_tick = 0
            current_tempo = None  # 初始tempo（如果没有tempo消息，使用默认120 BPM）
            
            for msg in midi_track:
                current_tick += msg.time
                
                if msg.type == 'set_tempo':
                    # 如果这是第一个tempo消息，记录初始tempo
                    if current_tempo is None:
                        current_tempo = msg.tempo
                        tempo_events.append((0, msg.tempo))  # 在时间0处设置初始tempo
                    else:
                        # 记录tempo变化
                        tempo_events.append((current_tick, msg.tempo))
                    current_tempo = msg.tempo
        
        # 如果没有找到任何tempo消息，返回None（使用默认120 BPM）
        if not tempo_events:
            return None
        
        # 如果没有tempo变化，直接返回第一个tempo的BPM
        if len(tempo_events) == 1:
            return mido.tempo2bpm(tempo_events[0][1])
        
        # 计算每个tempo持续的时间（以秒为单位）
        # 需要找到MIDI文件的总时长
        total_ticks = 0
        for midi_track in mid.tracks:
            track_ticks = sum(msg.time for msg in midi_track)
            total_ticks = max(total_ticks, track_ticks)
        
        # 按tick时间排序tempo事件
        tempo_events.sort(key=lambda x: x[0])
        
        # 计算加权平均BPM
        # 对于每个tempo段，计算其持续时间和对应的BPM
        total_weighted_bpm = 0.0
        total_duration = 0.0
        
        # 使用第一个tempo作为初始tempo
        initial_tempo = tempo_events[0][1]
        current_tempo = initial_tempo
        
        # 计算每个tempo段的持续时间
        for i in range(len(tempo_events)):
            start_tick = tempo_events[i][0]
            current_tempo = tempo_events[i][1]
            
            # 计算这个tempo段的结束tick
            if i + 1 < len(tempo_events):
                end_tick = tempo_events[i + 1][0]
            else:
                end_tick = total_ticks
            
            # 计算这个tempo段的持续时间（秒）
            duration_ticks = end_tick - start_tick
            if duration_ticks > 0:
                # 使用mido的tick2second方法计算时间
                try:
                    duration_seconds = mido.tick2second(duration_ticks, ticks_per_beat, current_tempo)
                except Exception:
                    # 如果mido方法失败，使用标准公式
                    duration_seconds = duration_ticks * (current_tempo / 1_000_000.0) / ticks_per_beat
                
                # 计算这个tempo段的BPM
                segment_bpm = mido.tempo2bpm(current_tempo)
                
                # 累加加权BPM
                total_weighted_bpm += segment_bpm * duration_seconds
                total_duration += duration_seconds
        
        # 计算加权平均BPM
        if total_duration > 0:
            average_bpm = total_weighted_bpm / total_duration
            return average_bpm
        else:
            # 如果总时长为0，返回第一个tempo的BPM
            return mido.tempo2bpm(initial_tempo)
    
    @staticmethod
    def import_midi(file_path: str, default_waveform: WaveformType = WaveformType.SQUARE, 
                    snap_to_beat: bool = True, allow_overlap: bool = False) -> Project:
        """
        导入MIDI文件
        
        Args:
            file_path: MIDI文件路径
            default_waveform: 默认波形类型，用于导入的音符
        
        Returns:
            Project对象
        """
        load_started_at = perf_counter()
        mid = MidiFile(file_path)
        load_ms = (perf_counter() - load_started_at) * 1000.0
        
        ticks_per_beat = mid.ticks_per_beat

        tempo_started_at = perf_counter()
        tempo_events = MidiIO._extract_tempo_events(mid)
        tempo_ms = (perf_counter() - tempo_started_at) * 1000.0
        bpm = tempo_events[0].bpm if tempo_events else 120.0
        
        # 创建项目
        project = Project(
            name=file_path.split('/')[-1].split('\\')[-1].replace('.mid', '').replace('.midi', ''),
            bpm=bpm,
            original_bpm=bpm,
            resolution=ticks_per_beat,
            time_signature=(4, 4),
            sample_rate=44100,
            tempo_events=tempo_events,
        )
        tempo_regions = build_tempo_regions(
            project.tempo_events,
            project.resolution,
            project.get_reference_bpm(),
        )
        
        # 处理每个MIDI轨道
        track_parse_started_at = perf_counter()
        total_notes = 0
        for track_index, midi_track in enumerate(mid.tracks):
            # 跳过空轨道
            if len(midi_track) == 0:
                continue
            
            # 创建轨道
            track_name = MidiIO._extract_track_name(midi_track, track_index)
            
            track = Track(
                name=track_name,
                track_type=TrackType.NOTE_TRACK,
                volume=1.0,
                pan=0.0,
                enabled=True
            )
            
            # 解析MIDI消息，转换为音符
            notes = MidiIO._parse_midi_track(
                midi_track,
                project,
                default_waveform,
                snap_to_beat,
                allow_overlap,
                tempo_regions=tempo_regions,
            )
            track.notes = notes
            total_notes += len(notes)
            
            if notes:  # 只添加有音符的轨道
                project.add_track(track)
        
        # 如果没有轨道，创建一个默认轨道
        if not project.tracks:
            default_track = Track(
                name="主旋律",
                track_type=TrackType.NOTE_TRACK
            )
            project.add_track(default_track)
        
        tracks_ms = (perf_counter() - track_parse_started_at) * 1000.0
        MidiIO._log_import_profile(
            file_path=file_path,
            load_ms=load_ms,
            tempo_ms=tempo_ms,
            tracks_ms=tracks_ms,
            track_count=len(project.tracks),
            note_count=total_notes,
        )
        return project
    
    @staticmethod
    def _parse_midi_track(
        midi_track: MidiTrack,
        project: Project,
        default_waveform: WaveformType = WaveformType.SQUARE,
        snap_to_beat: bool = True,
        allow_overlap: bool = False,
        tempo_regions: list[TempoRegion] | None = None,
    ) -> List[Note]:
        """
        解析MIDI轨道，转换为Note列表
        
        Args:
            midi_track: MIDI轨道
            ticks_per_beat: 每拍的tick数
            bpm: BPM值（用于初始化，如果轨道中没有tempo消息）
            default_waveform: 默认波形类型
        
        Returns:
            Note列表
        """
        notes = []
        active_notes: Dict[int, Dict[str, int]] = {}  # {note_number: {start_tick, velocity}}
        tick_time = 0
        snap_tick = max(1, project.beats_to_ticks(0.25))

        for msg in midi_track:
            tick_time += msg.time
            if msg.type == 'set_tempo':
                continue

            if msg.type == 'note_on' and msg.velocity > 0:
                note_number = msg.note
                active_notes[note_number] = {
                    'start_tick': tick_time,
                    'velocity': msg.velocity,
                }
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                note_number = msg.note
                if note_number in active_notes:
                    note_info = active_notes[note_number]
                    start_tick = note_info['start_tick']
                    duration_ticks = max(0, tick_time - start_tick)

                    if duration_ticks > 0:
                        if snap_to_beat:
                            start_tick = int(round(start_tick / snap_tick) * snap_tick)

                        if not allow_overlap:
                            for existing_note in notes:
                                existing_start_tick = existing_note.get_start_tick(project)
                                existing_end_tick = (
                                    existing_start_tick + existing_note.get_duration_ticks(project)
                                )
                                if (
                                    start_tick < existing_end_tick
                                    and start_tick + duration_ticks > existing_start_tick
                                ):
                                    start_tick = existing_end_tick
                                    break

                        note = Note(
                            pitch=note_number,
                            start_time=0.0,
                            duration=0.0,
                            velocity=note_info['velocity'],
                            waveform=default_waveform,
                            adsr=ADSRParams(),
                        )
                        if tempo_regions is None:
                            note.apply_tick_timing(project, start_tick, duration_ticks)
                        else:
                            MidiIO._apply_note_tick_timing_fast(
                                note,
                                start_tick,
                                duration_ticks,
                                tempo_regions,
                                project.resolution,
                            )
                        notes.append(note)

                    del active_notes[note_number]

        for note_number, note_info in active_notes.items():
            duration_ticks = project.beats_to_ticks(1.0)
            note = Note(
                pitch=note_number,
                start_time=0.0,
                duration=0.0,
                velocity=note_info['velocity'],
                waveform=default_waveform,
                adsr=ADSRParams(),
            )
            if tempo_regions is None:
                note.apply_tick_timing(project, note_info['start_tick'], duration_ticks)
            else:
                MidiIO._apply_note_tick_timing_fast(
                    note,
                    note_info['start_tick'],
                    duration_ticks,
                    tempo_regions,
                    project.resolution,
                )
            notes.append(note)

        notes.sort(
            key=lambda note: (
                note.start_tick if note.start_tick is not None else float("inf"),
                note.start_time,
            )
        )
        return notes
    
    @staticmethod
    def export_midi(project: Project, file_path: str) -> None:
        """
        导出项目为MIDI文件
        
        Args:
            project: 项目对象
            file_path: 输出文件路径
        """
        project.sync_note_ticks_from_seconds()
        mid = MidiFile()
        mid.ticks_per_beat = int(project.resolution or 480)
        
        # 为每个轨道创建MIDI轨道
        for track in project.tracks:
            if not track.enabled or not track.notes:
                continue
            
            midi_track = MidiTrack()
            mid.tracks.append(midi_track)
            
            # 设置轨道名称（处理中文字符编码问题）
            # mido库使用latin-1编码，需要将非ASCII字符转换为ASCII兼容字符串
            safe_track_name = MidiIO._encode_track_name(track.name)
            midi_track.append(MetaMessage('track_name', name=safe_track_name, time=0))

            events = []
            if mid.tracks.index(midi_track) == 0:
                events.extend(MidiIO._build_tempo_meta_events(project.tempo_events))
            events.extend(MidiIO._build_note_events(track.notes, project))
            MidiIO._append_sorted_events_to_track(midi_track, events)
        
        # 如果没有轨道，创建一个空轨道
        if len(mid.tracks) == 0:
            midi_track = MidiTrack()
            mid.tracks.append(midi_track)
            MidiIO._append_sorted_events_to_track(
                midi_track,
                MidiIO._build_tempo_meta_events(project.tempo_events),
            )
        
        # 保存文件
        mid.save(file_path)
    
    @staticmethod
    def _add_bpm_segments_to_track(midi_track: MidiTrack, bpm_segments: List[BPMSegment], ticks_per_beat: int) -> None:
        """将BPM段添加到MIDI轨道"""
        if not bpm_segments:
            return
        
        # 添加第一个BPM段（在时间0处）
        first_segment = bpm_segments[0]
        tempo = mido.bpm2tempo(first_segment.bpm)
        midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
        
        # 添加后续BPM段
        for i in range(1, len(bpm_segments)):
            segment = bpm_segments[i]
            prev_segment = bpm_segments[i - 1]
            
            # 计算从上一个段结束到这个段开始的时间（以tick为单位）
            # 需要使用上一个段的BPM来计算
            prev_bpm = prev_segment.bpm
            time_delta = segment.start_time - prev_segment.start_time
            
            # 将秒转换为tick
            try:
                delta_ticks = int(mido.second2tick(time_delta, ticks_per_beat, mido.bpm2tempo(prev_bpm)))
            except Exception:
                # 如果mido方法失败，使用标准公式
                tempo_microseconds = mido.bpm2tempo(prev_bpm)
                delta_ticks = int(time_delta * ticks_per_beat / (tempo_microseconds / 1_000_000.0))
            
            tempo = mido.bpm2tempo(segment.bpm)
            midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=delta_ticks))

    @staticmethod
    def _add_tempo_events_to_track(
        midi_track: MidiTrack,
        tempo_events: List[TempoEvent],
    ) -> None:
        """将标准 tempo events 写入MIDI轨道。"""
        if not tempo_events:
            midi_track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(120.0), time=0))
            return

        last_tick = 0
        for event in tempo_events:
            current_tick = max(0, int(event.tick))
            delta_tick = current_tick - last_tick
            last_tick = current_tick
            midi_track.append(
                MetaMessage('set_tempo', tempo=mido.bpm2tempo(float(event.bpm)), time=delta_tick)
            )

    @staticmethod
    def _build_tempo_meta_events(tempo_events: List[TempoEvent]) -> List[Dict[str, int | float | str]]:
        """Build absolute-tick tempo meta events for export."""
        if not tempo_events:
            return [{'tick': 0, 'type': 'set_tempo', 'tempo': mido.bpm2tempo(120.0)}]
        return [
            {
                'tick': max(0, int(event.tick)),
                'type': 'set_tempo',
                'tempo': mido.bpm2tempo(float(event.bpm)),
            }
            for event in tempo_events
        ]
    
    @staticmethod
    def _convert_notes_to_midi_with_bpm_segments(
        notes: List[Note], 
        midi_track: MidiTrack, 
        bpm_segments: List[BPMSegment],
        ticks_per_beat: int
    ) -> None:
        """将Note列表转换为MIDI消息（支持可变BPM）"""
        # 按开始时间排序
        sorted_notes = sorted(notes, key=lambda n: n.start_time)
        
        # 创建事件列表（note_on和note_off）
        events = []
        for note in sorted_notes:
            if note.pitch <= 0:  # 跳过休止符
                continue
            
            # 使用BPM段计算tick
            start_tick = MidiIO._time_to_ticks_with_bpm_segments(note.start_time, bpm_segments, ticks_per_beat)
            end_tick = MidiIO._time_to_ticks_with_bpm_segments(note.start_time + note.duration, bpm_segments, ticks_per_beat)
            
            events.append({
                'tick': start_tick,
                'type': 'note_on',
                'note': note.pitch,
                'velocity': note.velocity
            })
            events.append({
                'tick': end_tick,
                'type': 'note_off',
                'note': note.pitch,
                'velocity': 0
            })
        
        # 按tick时间排序
        events.sort(key=lambda e: e['tick'])
        
        # 转换为MIDI消息（计算delta time）
        last_tick = 0
        for event in events:
            delta_tick = event['tick'] - last_tick
            last_tick = event['tick']
            
            if event['type'] == 'note_on':
                msg = Message('note_on', note=event['note'], velocity=event['velocity'], time=delta_tick)
            else:  # note_off
                msg = Message('note_off', note=event['note'], velocity=0, time=delta_tick)
            
            midi_track.append(msg)

    @staticmethod
    def _convert_notes_to_midi_with_project_tempo(
        notes: List[Note],
        midi_track: MidiTrack,
        project: Project,
    ) -> None:
        """将Note列表转换为MIDI消息，优先使用项目标准 tick 时间模型。"""
        MidiIO._append_sorted_events_to_track(
            midi_track,
            MidiIO._build_note_events(notes, project),
        )

    @staticmethod
    def _build_note_events(
        notes: List[Note],
        project: Project,
    ) -> List[Dict[str, int | str]]:
        """Build absolute-tick note events for export."""
        sorted_notes = sorted(
            notes,
            key=lambda note: (
                note.start_tick if note.start_tick is not None else project.seconds_to_ticks(note.start_time),
                note.start_time,
            ),
        )

        events: List[Dict[str, int | str]] = []
        for note in sorted_notes:
            if note.pitch <= 0:
                continue

            start_tick = note.get_start_tick(project)
            end_tick = start_tick + note.get_duration_ticks(project)
            events.append({
                'tick': start_tick,
                'type': 'note_on',
                'note': note.pitch,
                'velocity': note.velocity,
            })
            events.append({
                'tick': end_tick,
                'type': 'note_off',
                'note': note.pitch,
                'velocity': 0,
            })
        return events

    @staticmethod
    def _append_sorted_events_to_track(
        midi_track: MidiTrack,
        events: List[Dict[str, int | float | str]],
    ) -> None:
        """Append absolute-tick events to a MIDI track using proper delta times."""
        event_priority = {
            'set_tempo': 0,
            'note_off': 1,
            'note_on': 2,
        }
        sorted_events = sorted(
            events,
            key=lambda event: (
                int(event['tick']),
                event_priority.get(str(event['type']), 99),
            ),
        )

        last_tick = 0
        for event in sorted_events:
            current_tick = int(event['tick'])
            delta_tick = current_tick - last_tick
            last_tick = current_tick

            if event['type'] == 'set_tempo':
                midi_track.append(
                    MetaMessage('set_tempo', tempo=int(event['tempo']), time=delta_tick)
                )
            elif event['type'] == 'note_on':
                midi_track.append(
                    Message(
                        'note_on',
                        note=int(event['note']),
                        velocity=int(event['velocity']),
                        time=delta_tick,
                    )
                )
            else:
                midi_track.append(
                    Message(
                        'note_off',
                        note=int(event['note']),
                        velocity=0,
                        time=delta_tick,
                    )
                )
    
    @staticmethod
    def _time_to_ticks_with_bpm_segments(time: float, bpm_segments: List[BPMSegment], ticks_per_beat: int) -> int:
        """将时间（秒）转换为tick（支持可变BPM）"""
        if not bpm_segments:
            # 如果没有BPM段，使用默认120 BPM
            default_bpm = 120.0
            return int(time * default_bpm * ticks_per_beat / 60.0)
        
        # 找到包含该时间的BPM段
        current_time = 0.0
        current_tick = 0
        
        for segment in bpm_segments:
            segment_start_time = segment.start_time
            segment_end_time = segment.end_time if segment.end_time is not None else float('inf')
            
            if time < segment_start_time:
                break
            
            # 计算从current_time到segment_start_time的tick
            if current_time < segment_start_time:
                # 使用前一个段的BPM（如果有）
                if bpm_segments.index(segment) > 0:
                    prev_segment = bpm_segments[bpm_segments.index(segment) - 1]
                    prev_bpm = prev_segment.bpm
                else:
                    prev_bpm = segment.bpm
                
                delta_time = segment_start_time - current_time
                try:
                    delta_ticks = int(mido.second2tick(delta_time, ticks_per_beat, mido.bpm2tempo(prev_bpm)))
                except Exception:
                    tempo_microseconds = mido.bpm2tempo(prev_bpm)
                    delta_ticks = int(delta_time * ticks_per_beat / (tempo_microseconds / 1_000_000.0))
                current_tick += delta_ticks
                current_time = segment_start_time
            
            # 如果时间在这个段内
            if segment_start_time <= time < segment_end_time:
                delta_time = time - segment_start_time
                try:
                    delta_ticks = int(mido.second2tick(delta_time, ticks_per_beat, mido.bpm2tempo(segment.bpm)))
                except Exception:
                    tempo_microseconds = mido.bpm2tempo(segment.bpm)
                    delta_ticks = int(delta_time * ticks_per_beat / (tempo_microseconds / 1_000_000.0))
                return current_tick + delta_ticks
        
        # 如果时间超出所有段，使用最后一个段的BPM
        last_segment = bpm_segments[-1]
        delta_time = time - last_segment.start_time
        try:
            delta_ticks = int(mido.second2tick(delta_time, ticks_per_beat, mido.bpm2tempo(last_segment.bpm)))
        except Exception:
            tempo_microseconds = mido.bpm2tempo(last_segment.bpm)
            delta_ticks = int(delta_time * ticks_per_beat / (tempo_microseconds / 1_000_000.0))
        return current_tick + delta_ticks
    
    @staticmethod
    def _convert_notes_to_midi(notes: List[Note], midi_track: MidiTrack, bpm: float, ticks_per_beat: int) -> None:
        """
        将Note列表转换为MIDI消息
        
        Args:
            notes: Note列表
            midi_track: MIDI轨道
            bpm: BPM值
            ticks_per_beat: 每拍的tick数
        """
        # 按开始时间排序
        sorted_notes = sorted(notes, key=lambda n: n.start_time)
        
        # 计算tick到秒的转换
        def seconds_to_ticks(seconds: float) -> int:
            return int(seconds * bpm * ticks_per_beat / 60.0)
        
        # 创建事件列表（note_on和note_off）
        events = []
        for note in sorted_notes:
            if note.pitch <= 0:  # 跳过休止符
                continue
            
            start_tick = seconds_to_ticks(note.start_time)
            end_tick = seconds_to_ticks(note.start_time + note.duration)
            
            events.append({
                'tick': start_tick,
                'type': 'note_on',
                'note': note.pitch,
                'velocity': note.velocity
            })
            events.append({
                'tick': end_tick,
                'type': 'note_off',
                'note': note.pitch,
                'velocity': 0
            })
        
        # 按tick时间排序
        events.sort(key=lambda e: e['tick'])
        
        # 转换为MIDI消息（计算delta time）
        last_tick = 0
        for event in events:
            delta_tick = event['tick'] - last_tick
            last_tick = event['tick']
            
            if event['type'] == 'note_on':
                msg = Message('note_on', note=event['note'], velocity=event['velocity'], time=delta_tick)
            else:  # note_off
                msg = Message('note_off', note=event['note'], velocity=0, time=delta_tick)
            
            midi_track.append(msg)
    
    @staticmethod
    def _encode_track_name(name: str) -> str:
        """
        将轨道名称编码为MIDI兼容的字符串
        
        MIDI规范使用latin-1编码（ISO-8859-1），只能表示0-255的字符。
        对于无法编码的字符（如中文），使用ASCII替代方案。
        
        Args:
            name: 原始轨道名称
            
        Returns:
            编码后的轨道名称（ASCII兼容）
        """
        try:
            # 尝试使用latin-1编码
            name.encode('latin-1')
            return name
        except UnicodeEncodeError:
            # 如果包含非latin-1字符，使用ASCII替代
            # 方案1：使用拼音映射（简单实现）
            # 方案2：使用Unicode转义（不推荐，不兼容）
            # 方案3：使用ASCII替代字符（推荐）
            
            # 简单映射常见中文字符到ASCII
            chinese_to_ascii = {
                '主旋律': 'Melody',
                '低音': 'Bass',
                '打击乐': 'Drums',
                '轨道': 'Track',
                '音轨': 'Track',
            }
            
            # 检查是否是完全匹配的中文名称
            if name in chinese_to_ascii:
                return chinese_to_ascii[name]
            
            # 否则，尝试将中文字符替换为拼音或使用Unicode转义
            # 为了兼容性，我们使用简单的ASCII替代
            # 将非ASCII字符替换为下划线或移除
            ascii_name = ''
            for char in name:
                try:
                    char.encode('latin-1')
                    ascii_name += char
                except UnicodeEncodeError:
                    # 非ASCII字符替换为下划线
                    ascii_name += '_'
            
            # 如果结果为空，使用默认名称
            if not ascii_name or ascii_name == '_' * len(name):
                return f"Track_{hash(name) % 10000}"
            
            return ascii_name
