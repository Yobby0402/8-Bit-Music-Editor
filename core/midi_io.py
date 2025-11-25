"""
MIDI导入导出模块

负责MIDI文件的读取和写入。
"""

from typing import List, Optional, Dict, Any
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from .models import Project, Track, Note, WaveformType, ADSRParams, TrackType


class MidiIO:
    """MIDI导入导出处理器"""
    
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
        
        # 获取BPM（从第一个tempo消息）
        bpm = 120.0
        ticks_per_beat = mid.ticks_per_beat
        
        # 从所有轨道中查找第一个tempo消息
        for midi_track in mid.tracks:
            for msg in midi_track:
                if msg.type == 'set_tempo':
                    bpm = mido.tempo2bpm(msg.tempo)
                    break
            if bpm != 120.0:
                break
        
        # 创建项目
        project = Project(
            name=file_path.split('/')[-1].split('\\')[-1].replace('.mid', '').replace('.midi', ''),
            bpm=bpm,
            original_bpm=bpm,
            time_signature=(4, 4),
            sample_rate=44100
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
            bpm: BPM值
            default_waveform: 默认波形类型
        
        Returns:
            Note列表
        """
        notes = []
        active_notes: Dict[int, Dict[str, Any]] = {}  # {note_number: {start_tick, velocity}}
        current_tempo = bpm
        current_time = 0.0  # 当前时间（秒）
        tick_time = 0  # 当前tick数
        
        # 计算tick到秒的转换
        def ticks_to_seconds(ticks: int) -> float:
            return ticks * 60.0 / (current_tempo * ticks_per_beat)
        
        for msg in midi_track:
            # 更新当前时间
            tick_time += msg.time
            current_time += ticks_to_seconds(msg.time)
            
            # 处理tempo消息
            if msg.type == 'set_tempo':
                current_tempo = mido.tempo2bpm(msg.tempo)
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
                        if snap_to_beat:
                            beats_per_second = bpm / 60.0
                            start_beats = start_time * beats_per_second
                            # 对齐到1/4拍
                            start_beats = round(start_beats * 4) / 4
                            start_time = start_beats / beats_per_second
                        
                        # 检查重叠（如果不允许重叠）
                        if not allow_overlap:
                            # 检查是否与已有音符重叠
                            overlaps = False
                            for existing_note in notes:
                                if (start_time < existing_note.end_time and 
                                    start_time + duration > existing_note.start_time):
                                    overlaps = True
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
        
        # 设置BPM
        tempo = mido.bpm2tempo(project.bpm)
        
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
            
            # 设置tempo（只在第一个轨道设置）
            if mid.tracks.index(midi_track) == 0:
                midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
            
            # 转换音符为MIDI消息
            MidiIO._convert_notes_to_midi(track.notes, midi_track, project.bpm, mid.ticks_per_beat)
        
        # 如果没有轨道，创建一个空轨道
        if len(mid.tracks) == 0:
            midi_track = MidiTrack()
            mid.tracks.append(midi_track)
            midi_track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
        
        # 保存文件
        mid.save(file_path)
    
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

