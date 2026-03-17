"""
MIDI导入导出模块

负责MIDI文件的读取和写入。
"""

from typing import Any, Dict, List, Optional

import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack

from .models import ADSRParams, BPMSegment, Note, Project, Track, TrackType, WaveformType


class MidiIO:
    """MIDI导入导出处理器"""
    
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
        mid = MidiFile(file_path)
        
        ticks_per_beat = mid.ticks_per_beat
        
        # 分析所有tempo变化，提取BPM段信息
        bpm_segments = MidiIO._extract_bpm_segments(mid, ticks_per_beat)
        
        # 如果没有找到任何tempo消息，使用默认120 BPM
        if not bpm_segments:
            bpm = 120.0
            bpm_segments = [BPMSegment(start_time=0.0, bpm=bpm)]
        else:
            # 使用第一个BPM段的BPM作为默认BPM（用于兼容性）
            bpm = bpm_segments[0].bpm
        
        # 创建项目
        project = Project(
            name=file_path.split('/')[-1].split('\\')[-1].replace('.mid', '').replace('.midi', ''),
            bpm=bpm,
            original_bpm=bpm,
            time_signature=(4, 4),
            sample_rate=44100,
            bpm_segments=bpm_segments
        )
        
        # 处理每个MIDI轨道
        for track_index, midi_track in enumerate(mid.tracks):
            # 跳过空轨道
            if len(midi_track) == 0:
                continue
            
            # 创建轨道
            track_name = f"轨道 {track_index + 1}"
            # 尝试从轨道名称消息中获取名称
            for msg in midi_track:
                if msg.type == 'track_name':
                    # 尝试多种编码方式处理轨道名称，避免乱码
                    try:
                        # mido库返回的name可能是bytes或str
                        if isinstance(msg.name, bytes):
                            # 尝试UTF-8解码
                            try:
                                track_name = msg.name.decode('utf-8')
                            except UnicodeDecodeError:
                                # 如果UTF-8失败，尝试latin-1（MIDI标准编码）
                                try:
                                    track_name = msg.name.decode('latin-1')
                                except UnicodeDecodeError:
                                    # 如果都失败，尝试GBK（中文Windows常用编码）
                                    try:
                                        track_name = msg.name.decode('gbk')
                                    except UnicodeDecodeError:
                                        # 最后尝试使用错误处理
                                        track_name = msg.name.decode('utf-8', errors='replace')
                        else:
                            # 已经是字符串，直接使用
                            track_name = msg.name
                    except Exception:
                        # 如果处理失败，使用默认名称
                        track_name = f"轨道 {track_index + 1}"
                    break
            
            track = Track(
                name=track_name,
                track_type=TrackType.NOTE_TRACK,
                volume=1.0,
                pan=0.0,
                enabled=True
            )
            
            # 解析MIDI消息，转换为音符
            notes = MidiIO._parse_midi_track(midi_track, ticks_per_beat, bpm, default_waveform, snap_to_beat, allow_overlap)
            track.notes = notes
            
            if notes:  # 只添加有音符的轨道
                project.add_track(track)
        
        # 如果没有轨道，创建一个默认轨道
        if not project.tracks:
            default_track = Track(
                name="主旋律",
                track_type=TrackType.NOTE_TRACK
            )
            project.add_track(default_track)
        
        return project
    
    @staticmethod
    def _parse_midi_track(midi_track: MidiTrack, ticks_per_beat: int, bpm: float, 
                          default_waveform: WaveformType = WaveformType.SQUARE,
                          snap_to_beat: bool = True, allow_overlap: bool = False) -> List[Note]:
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
        active_notes: Dict[int, Dict[str, Any]] = {}  # {note_number: {start_tick, start_time, velocity}}
        
        # 跟踪当前的tempo（以微秒/四分音符为单位，而不是BPM）
        # 重要：MIDI标准规定，如果没有tempo消息，默认使用120 BPM（500000微秒/四分音符）
        # 但是，如果轨道中有tempo消息，应该使用第一个tempo消息的值
        # 为了正确处理，我们使用传入的bpm参数来初始化，然后在解析过程中更新
        # 如果轨道中有tempo消息，它会在解析过程中被处理并更新current_tempo_microseconds
        current_tempo_microseconds = mido.bpm2tempo(bpm)
        current_time = 0.0  # 当前时间（秒）
        tick_time = 0       # 当前tick数
        tempo_initialized = False  # 标记是否已经遇到第一个tempo消息
        
        # 根据当前tempo计算tick到秒的转换
        # 使用mido库的内置方法确保准确性
        def ticks_to_seconds(ticks: int, tempo_microseconds: int) -> float:
            if tempo_microseconds <= 0 or ticks_per_beat <= 0:
                return 0.0
            # 使用mido库的tick2second方法，确保时间转换的准确性
            # tick2second(ticks, ticks_per_beat, tempo_microseconds)
            try:
                return mido.tick2second(ticks, ticks_per_beat, tempo_microseconds)
            except Exception:
                # 如果mido方法失败，使用标准公式作为后备
                # tempo_microseconds 是每四分音符的微秒数
                # 每个tick的秒数 = (tempo_microseconds / 1,000,000) / ticks_per_beat
                result = ticks * (tempo_microseconds / 1_000_000.0) / ticks_per_beat
                return result
        
        for msg in midi_track:
            # 更新当前时间（在tempo变化之前计算，使用旧的tempo）
            # 重要：MIDI标准规定，tempo消息在它出现之后才生效
            # 所以，在计算当前消息的delta time时，应该使用消息出现之前的tempo
            tick_time += msg.time
            time_delta = ticks_to_seconds(msg.time, current_tempo_microseconds)
            current_time += time_delta
            
            # 处理tempo消息（允许MIDI内部改变速度）
            # 注意：tempo变化在当前消息的时间计算之后生效，影响后续消息
            if msg.type == 'set_tempo':
                # 如果这是第一个tempo消息，记录它用于后续参考
                if not tempo_initialized:
                    tempo_initialized = True
                current_tempo_microseconds = msg.tempo
                continue
            
            # 处理note_on消息
            if msg.type == 'note_on' and msg.velocity > 0:
                note_number = msg.note
                velocity = msg.velocity
                active_notes[note_number] = {
                    'start_tick': tick_time,
                    'start_time': current_time,
                    'velocity': velocity
                }
            
            # 处理note_off消息（或velocity=0的note_on）
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                note_number = msg.note
                if note_number in active_notes:
                    note_info = active_notes[note_number]
                    duration = current_time - note_info['start_time']
                    
                    # 创建Note对象
                    if duration > 0.001:  # 只添加有效时长的音符
                        start_time = note_info['start_time']
                        
                        # 如果启用吸附对齐，对齐到1/4拍网格
                        # 注意：使用当前tempo（current_tempo_microseconds）而不是初始bpm，以正确处理tempo变化
                        if snap_to_beat:
                            # 使用当前tempo计算节拍，而不是初始bpm
                            # 这样可以正确处理MIDI文件中的tempo变化
                            current_tempo_bpm = mido.tempo2bpm(current_tempo_microseconds)
                            beats_per_second = current_tempo_bpm / 60.0
                            start_beats = start_time * beats_per_second
                            # 对齐到1/4拍
                            start_beats = round(start_beats * 4) / 4
                            start_time = start_beats / beats_per_second
                        
                        # 检查重叠（如果不允许重叠）
                        if not allow_overlap:
                            for existing_note in notes:
                                if (start_time < existing_note.end_time and 
                                    start_time + duration > existing_note.start_time):
                                    # 移动到下一个可用位置
                                    start_time = existing_note.end_time
                                    break
                        
                        note = Note(
                            pitch=note_number,
                            start_time=start_time,
                            duration=duration,
                            velocity=note_info['velocity'],
                            waveform=default_waveform,  # 使用传入的默认波形
                            adsr=ADSRParams()
                        )
                        notes.append(note)
                    
                    del active_notes[note_number]
        
        # 处理未关闭的音符（在轨道结束时）
        for note_number, note_info in active_notes.items():
            # 假设最后一个音符持续到轨道结束
            duration = 0.5  # 默认0.5秒
            note = Note(
                pitch=note_number,
                start_time=note_info['start_time'],
                duration=duration,
                velocity=note_info['velocity'],
                waveform=default_waveform,  # 使用传入的默认波形
                adsr=ADSRParams()
            )
            notes.append(note)
        
        # 按开始时间排序
        notes.sort(key=lambda n: n.start_time)
        
        return notes
    
    @staticmethod
    def export_midi(project: Project, file_path: str) -> None:
        """
        导出项目为MIDI文件
        
        Args:
            project: 项目对象
            file_path: 输出文件路径
        """
        mid = MidiFile()
        mid.ticks_per_beat = 480  # 标准MIDI分辨率
        
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
            
            # 设置tempo（只在第一个轨道设置，并且需要设置所有BPM段）
            if mid.tracks.index(midi_track) == 0:
                # 如果有BPM段，导出所有BPM段
                if project.bpm_segments and len(project.bpm_segments) > 1:
                    MidiIO._add_bpm_segments_to_track(midi_track, project.bpm_segments, mid.ticks_per_beat)
                else:
                    # 否则使用默认BPM
                    tempo = mido.bpm2tempo(project.bpm)
                    midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
            
            # 转换音符为MIDI消息（使用可变BPM）
            MidiIO._convert_notes_to_midi_with_bpm_segments(
                track.notes, midi_track, project.bpm_segments, mid.ticks_per_beat
            )
        
        # 如果没有轨道，创建一个空轨道
        if len(mid.tracks) == 0:
            midi_track = MidiTrack()
            mid.tracks.append(midi_track)
            if project.bpm_segments and len(project.bpm_segments) > 1:
                MidiIO._add_bpm_segments_to_track(midi_track, project.bpm_segments, mid.ticks_per_beat)
            else:
                tempo = mido.bpm2tempo(project.bpm)
                midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
        
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
