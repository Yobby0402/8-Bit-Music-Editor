"""
数据模型定义

定义Note、Track、Project等核心数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union
from enum import Enum

if TYPE_CHECKING:
    from .effect_processor import FilterParams, DelayParams, TremoloParams, VibratoParams
    from .track_events import DrumEvent


class WaveformType(Enum):
    """波形类型枚举"""
    SQUARE = "square"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    SINE = "sine"
    NOISE = "noise"


class TrackType(Enum):
    """音轨类型枚举"""
    NOTE_TRACK = "note"    # 音符音轨（主旋律/低音）
    DRUM_TRACK = "drum"    # 打击乐音轨


@dataclass
class ADSRParams:
    """ADSR包络参数"""
    attack: float = 0.01   # 起音时间（秒）
    decay: float = 0.1     # 衰减时间（秒）
    sustain: float = 0.7   # 延音级别（0-1）
    release: float = 0.2   # 释音时间（秒）
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "attack": self.attack,
            "decay": self.decay,
            "sustain": self.sustain,
            "release": self.release
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'ADSRParams':
        """从字典创建"""
        return cls(
            attack=data.get("attack", 0.01),
            decay=data.get("decay", 0.1),
            sustain=data.get("sustain", 0.7),
            release=data.get("release", 0.2)
        )


# 音符类型（几分音符）
NOTE_VALUE_WHOLE = 1      # 全音符（4拍）
NOTE_VALUE_HALF = 2       # 二分音符（2拍）
NOTE_VALUE_QUARTER = 4    # 四分音符（1拍）
NOTE_VALUE_EIGHTH = 8     # 八分音符（0.5拍）
NOTE_VALUE_SIXTEENTH = 16 # 十六分音符（0.25拍）

@dataclass
class Note:
    """音符数据模型"""
    pitch: int              # MIDI音高（0-127），0表示休止符（空白音符）
    start_time: float       # 开始时间（秒）- 仅用于运行时，不存储到JSON
    duration: float         # 持续时间（秒）- 仅用于运行时，不存储到JSON
    velocity: int = 127     # 力度/音量（0-127）
    waveform: WaveformType = WaveformType.SQUARE  # 波形类型
    duty_cycle: float = 0.5  # 占空比（仅用于方波，0-1）
    adsr: Optional[ADSRParams] = None  # 包络参数
    vibrato_params: Optional['VibratoParams'] = None  # 单个音符的颤音效果参数
    # 网格格式（存储到JSON）
    note_value: Optional[int] = None  # 音符类型（1=全音符, 2=二分音符, 4=四分音符, 8=八分音符, 16=十六分音符）
    grid_index: Optional[int] = None  # 格子索引（从0开始）
    
    def __post_init__(self):
        """初始化后处理"""
        if self.adsr is None:
            self.adsr = ADSRParams()
        # vibrato_params在需要时创建，不在这里初始化
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（完整格式，包含start_time）"""
        result = {
            "pitch": self.pitch,
            "start_time": self.start_time,
            "duration": self.duration,
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "duty_cycle": self.duty_cycle,
            "adsr": self.adsr.to_dict() if self.adsr else None
        }
        # 添加vibrato_params（如果存在）
        if self.vibrato_params:
            from .effect_processor import VibratoParams
            result["vibrato_params"] = {
                "rate": self.vibrato_params.rate,
                "depth": self.vibrato_params.depth,
                "enabled": self.vibrato_params.enabled
            }
        return result
    
    def to_dict_sequence(self) -> Dict[str, Any]:
        """转换为字典（序列格式，不包含start_time，duration用节拍数）"""
        # 计算节拍数（需要BPM，但这里只存储相对值，导入时用当前BPM）
        return {
            "pitch": self.pitch,
            "duration_beats": None,  # 需要BPM计算，这里不存储
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "duty_cycle": self.duty_cycle,
            "adsr": self.adsr.to_dict() if self.adsr else None
        }
    
    def to_dict_sequence_with_bpm(self, bpm: float) -> Dict[str, Any]:
        """转换为字典（序列格式，根据BPM计算duration_beats）"""
        duration_beats = self.duration * bpm / 60.0
        return {
            "pitch": self.pitch,
            "duration_beats": duration_beats,
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "duty_cycle": self.duty_cycle,
            "adsr": self.adsr.to_dict() if self.adsr else None
        }
    
    def to_dict_grid(self) -> Dict[str, Any]:
        """转换为字典（网格格式，只存储note_value和grid_index）"""
        return {
            "pitch": self.pitch,
            "note_value": self.note_value if self.note_value is not None else NOTE_VALUE_QUARTER,
            "grid_index": self.grid_index if self.grid_index is not None else 0,
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "duty_cycle": self.duty_cycle,
            "adsr": self.adsr.to_dict() if self.adsr else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Note':
        """从字典创建（完整格式）"""
        adsr = None
        if data.get("adsr"):
            adsr = ADSRParams.from_dict(data["adsr"])
        
        vibrato_params = None
        if data.get("vibrato_params"):
            from .effect_processor import VibratoParams
            vp_data = data["vibrato_params"]
            vibrato_params = VibratoParams(
                rate=vp_data.get("rate", 6.0),
                depth=vp_data.get("depth", 2.0),
                enabled=vp_data.get("enabled", False)
            )
        
        return cls(
            pitch=data["pitch"],
            start_time=data["start_time"],
            duration=data["duration"],
            velocity=data.get("velocity", 127),
            waveform=WaveformType(data.get("waveform", "square")),
            duty_cycle=data.get("duty_cycle", 0.5),
            adsr=adsr,
            vibrato_params=vibrato_params
        )
    
    @classmethod
    def from_dict_sequence(cls, data: Dict[str, Any], start_time: float, bpm: float) -> 'Note':
        """从字典创建（序列格式，根据BPM计算duration和start_time）"""
        adsr = None
        if data.get("adsr"):
            adsr = ADSRParams.from_dict(data["adsr"])
        
        # 从节拍数转换为秒
        duration_beats = data.get("duration_beats", 0.25)  # 默认1/4拍
        duration = duration_beats * 60.0 / bpm
        
        return cls(
            pitch=data["pitch"],
            start_time=start_time,
            duration=duration,
            velocity=data.get("velocity", 127),
            waveform=WaveformType(data.get("waveform", "square")),
            duty_cycle=data.get("duty_cycle", 0.5),
            adsr=adsr
        )
    
    @classmethod
    def from_dict_grid(cls, data: Dict[str, Any], grid_size: int, bpm: float) -> 'Note':
        """从字典创建（网格格式，根据grid_index和note_value计算start_time和duration）"""
        adsr = None
        if data.get("adsr"):
            adsr = ADSRParams.from_dict(data["adsr"])
        
        # 从格子索引和音符类型计算时间
        grid_index = data.get("grid_index", 0)
        note_value = data.get("note_value", NOTE_VALUE_QUARTER)
        
        # 格子大小（每格多少拍）：由grid_size决定（如grid_size=16表示每格1/16拍）
        # 例如：grid_size=16（十六分音符网格），每格=1/16拍 = 0.25拍
        beats_per_grid = 4.0 / grid_size  # 每格多少拍（假设四分音符=1拍）
        start_beats = grid_index * beats_per_grid
        
        # 音符持续时间（拍）：根据note_value计算
        # note_value=1(全音符)=4拍, note_value=2(二分音符)=2拍, note_value=4(四分音符)=1拍, etc.
        duration_beats = 4.0 / note_value
        
        # 转换为秒
        start_time = start_beats * 60.0 / bpm
        duration = duration_beats * 60.0 / bpm
        
        return cls(
            pitch=data["pitch"],
            start_time=start_time,
            duration=duration,
            velocity=data.get("velocity", 127),
            waveform=WaveformType(data.get("waveform", "square")),
            duty_cycle=data.get("duty_cycle", 0.5),
            adsr=adsr,
            note_value=note_value,
            grid_index=grid_index
        )
    
    @property
    def end_time(self) -> float:
        """结束时间"""
        return self.start_time + self.duration
    
    def overlaps(self, other: 'Note') -> bool:
        """检查是否与另一个音符重叠"""
        return not (self.end_time <= other.start_time or 
                   other.end_time <= self.start_time)


@dataclass
class Track:
    """轨道数据模型"""
    name: str = "Track 1"
    track_type: 'TrackType' = None  # 音轨类型（NOTE_TRACK 或 DRUM_TRACK）
    volume: float = 1.0      # 音量（0-1）
    pan: float = 0.0         # 声相（-1到1，0为居中）
    enabled: bool = True    # 是否启用
    notes: List[Note] = field(default_factory=list)  # 音符列表（用于音符音轨）
    drum_events: List['DrumEvent'] = field(default_factory=list)  # 打击乐事件列表（用于打击乐音轨）
    # 效果参数（可选）
    filter_params: Optional['FilterParams'] = None
    delay_params: Optional['DelayParams'] = None
    tremolo_params: Optional['TremoloParams'] = None
    vibrato_params: Optional['VibratoParams'] = None
    
    def __post_init__(self):
        """初始化后处理"""
        # 如果没有指定 track_type，根据是否有 drum_events 推断
        if self.track_type is None:
            if self.drum_events:
                self.track_type = TrackType.DRUM_TRACK
            else:
                self.track_type = TrackType.NOTE_TRACK
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（完整格式）"""
        result = {
            "name": self.name,
            "track_type": self.track_type.value if self.track_type else TrackType.NOTE_TRACK.value,
            "volume": self.volume,
            "pan": self.pan,
            "enabled": self.enabled,
        }
        if self.track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            result["drum_events"] = [event.to_dict() for event in self.drum_events]
        else:
            result["notes"] = [note.to_dict() for note in self.notes]
        return result
    
    def to_dict_sequence(self, bpm: float) -> Dict[str, Any]:
        """转换为字典（序列格式）"""
        result = {
            "name": self.name,
            "track_type": self.track_type.value if self.track_type else TrackType.NOTE_TRACK.value,
            "volume": self.volume,
            "pan": self.pan,
            "enabled": self.enabled,
        }
        if self.track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            result["drum_events"] = [event.to_dict() for event in self.drum_events]
        else:
            result["notes"] = [note.to_dict_sequence_with_bpm(bpm) for note in self.notes]
        return result
    
    def to_dict_grid(self) -> Dict[str, Any]:
        """转换为字典（网格格式）"""
        result = {
            "name": self.name,
            "track_type": self.track_type.value if self.track_type else TrackType.NOTE_TRACK.value,
            "volume": self.volume,
            "pan": self.pan,
            "enabled": self.enabled,
        }
        if self.track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            result["drum_events"] = [event.to_dict() for event in self.drum_events]
        else:
            result["notes"] = [note.to_dict_grid() for note in self.notes]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], bpm: Optional[float] = None) -> 'Track':
        """从字典创建（完整格式或序列格式）"""
        # 过滤掉已移除的字段（向后兼容）
        data = {k: v for k, v in data.items() if k != "waveform"}
        
        # 检查音轨类型
        track_type_str = data.get("track_type", "note")
        track_type = TrackType(track_type_str) if track_type_str else TrackType.NOTE_TRACK
        
        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                drum_events=drum_events
            )
        
        # 音符音轨：处理 notes
        notes_data = data.get("notes", [])
        
        # 检查格式类型
        if notes_data:
            first_note = notes_data[0]
            if "grid_index" in first_note and "note_value" in first_note:
                # 网格格式：需要grid_size参数
                # 从最短音符计算grid_size
                grid_size = 16  # 默认十六分音符网格
                min_note_value = min((n.get("note_value", 4) for n in notes_data), default=4)
                if min_note_value >= 16:
                    grid_size = 16
                elif min_note_value >= 8:
                    grid_size = 8
                elif min_note_value >= 4:
                    grid_size = 4
                elif min_note_value >= 2:
                    grid_size = 2
                else:
                    grid_size = 1
                return cls.from_dict_grid(data, grid_size, bpm or 120.0)
            elif "start_time" not in first_note and "duration_beats" in first_note:
                # 序列格式：按顺序计算start_time并合并相同音符
                return cls.from_dict_sequence(data, bpm)
        
        # 完整格式：直接读取
        return cls(
            name=data.get("name", "Track 1"),
            track_type=track_type,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            notes=[Note.from_dict(note_data) for note_data in notes_data]
        )
    
    @classmethod
    def from_dict_sequence(cls, data: Dict[str, Any], bpm: Optional[float] = None) -> 'Track':
        """从字典创建（序列格式，按顺序计算start_time并合并相同音符）"""
        # 过滤掉已移除的字段（向后兼容）
        data = {k: v for k, v in data.items() if k != "waveform"}
        
        if bpm is None:
            # 如果没有提供BPM，使用默认值（稍后需要从Project获取）
            bpm = 120.0
        
        # 检查音轨类型
        track_type_str = data.get("track_type", "note")
        track_type = TrackType(track_type_str) if track_type_str else TrackType.NOTE_TRACK
        
        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                drum_events=drum_events
            )
        
        # 音符音轨：处理 notes
        notes_data = data.get("notes", [])
        notes = []
        current_time = 0.0
        
        for note_data in notes_data:
            # 计算持续时间（秒）
            duration_beats = note_data.get("duration_beats", 0.25)
            duration = duration_beats * 60.0 / bpm
            
            pitch = note_data.get("pitch", 0)
            
            # 跳过休止符（pitch=0），但保留时间
            if pitch == 0:
                current_time += duration
                continue
            
            # 检查是否可以与上一个音符合并（相同音高且连续）
            if notes:
                last_note = notes[-1]
                if (last_note.pitch == pitch and 
                    abs(current_time - (last_note.start_time + last_note.duration)) < 0.01):
                    # 合并：延长上一个音符的持续时间
                    last_note.duration = (current_time + duration) - last_note.start_time
                    current_time = last_note.start_time + last_note.duration
                    continue
            
            # 创建新音符
            note = Note.from_dict_sequence(note_data, current_time, bpm)
            notes.append(note)
            current_time += duration
        
        return cls(
            name=data.get("name", "Track 1"),
            track_type=track_type,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            notes=notes
        )
    
    @classmethod
    def from_dict_grid(cls, data: Dict[str, Any], grid_size: int, bpm: float) -> 'Track':
        """从字典创建（网格格式，根据grid_index和note_value计算start_time和duration）"""
        # 过滤掉已移除的字段（向后兼容）
        data = {k: v for k, v in data.items() if k != "waveform"}
        
        # 检查音轨类型
        track_type_str = data.get("track_type", "note")
        track_type = TrackType(track_type_str) if track_type_str else TrackType.NOTE_TRACK
        
        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                drum_events=drum_events
            )
        
        # 音符音轨：处理 notes
        notes_data = data.get("notes", [])
        notes = []
        
        for note_data in notes_data:
            pitch = note_data.get("pitch", 0)
            
            # 跳过休止符（pitch=0）
            if pitch == 0:
                continue
            
            # 创建音符
            note = Note.from_dict_grid(note_data, grid_size, bpm)
            notes.append(note)
        
        return cls(
            name=data.get("name", "Track 1"),
            track_type=track_type,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            notes=notes
        )
    
    def add_note(self, note: Note) -> None:
        """添加音符"""
        if self.track_type == TrackType.DRUM_TRACK:
            raise ValueError("Cannot add note to drum track. Use add_drum_event instead.")
        self.notes.append(note)
        self.notes.sort(key=lambda n: n.start_time)
    
    def remove_note(self, note: Note) -> None:
        """删除音符"""
        if note in self.notes:
            self.notes.remove(note)
    
    def add_drum_event(self, drum_event: 'DrumEvent') -> None:
        """添加打击乐事件"""
        if self.track_type != TrackType.DRUM_TRACK:
            raise ValueError("Cannot add drum event to note track. Use add_note instead.")
        self.drum_events.append(drum_event)
        self.drum_events.sort(key=lambda e: e.start_beat)
    
    def remove_drum_event(self, drum_event: 'DrumEvent') -> None:
        """删除打击乐事件"""
        if drum_event in self.drum_events:
            self.drum_events.remove(drum_event)
    
    def get_notes_at_time(self, time: float) -> List[Note]:
        """获取指定时间点的音符"""
        return [note for note in self.notes 
                if note.start_time <= time < note.end_time]
    
    def get_notes_in_range(self, start_time: float, end_time: float) -> List[Note]:
        """获取时间范围内的音符"""
        return [note for note in self.notes 
                if not (note.end_time <= start_time or note.start_time >= end_time)]


@dataclass
class Project:
    """项目数据模型"""
    name: str = "Untitled Project"
    bpm: float = 120.0              # 节拍速度（当前BPM）
    original_bpm: Optional[float] = None  # 原始BPM（JSON生成时的BPM，用于BPM缩放）
    time_signature: tuple = (4, 4)  # 拍号（分子，分母）
    sample_rate: int = 44100        # 采样率
    tracks: List[Track] = field(default_factory=list)  # 轨道列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "bpm": self.bpm,
            "original_bpm": self.original_bpm if self.original_bpm is not None else self.bpm,
            "time_signature": list(self.time_signature),
            "sample_rate": self.sample_rate,
            "tracks": [track.to_dict() for track in self.tracks]
        }
    
    def to_dict_sequence(self) -> Dict[str, Any]:
        """转换为字典（序列格式，不包含start_time）"""
        bpm = self.original_bpm if self.original_bpm is not None else self.bpm
        return {
            "name": self.name,
            "bpm": self.bpm,
            "original_bpm": self.original_bpm if self.original_bpm is not None else self.bpm,
            "time_signature": list(self.time_signature),
            "sample_rate": self.sample_rate,
            "tracks": [track.to_dict_sequence(bpm) for track in self.tracks]
        }
    
    def to_dict_grid(self) -> Dict[str, Any]:
        """转换为字典（网格格式，只存储note_value和grid_index）"""
        return {
            "name": self.name,
            "bpm": self.bpm,
            "original_bpm": self.original_bpm if self.original_bpm is not None else self.bpm,
            "time_signature": list(self.time_signature),
            "sample_rate": self.sample_rate,
            "tracks": [track.to_dict_grid() for track in self.tracks]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """从字典创建（支持完整格式和序列格式）"""
        original_bpm = data.get("original_bpm")
        if original_bpm is None:
            # 如果没有original_bpm，使用bpm作为原始BPM
            original_bpm = data.get("bpm", 120.0)
        
        current_bpm = data.get("bpm", 120.0)
        
        # 创建轨道（使用当前BPM用于序列格式的导入）
        tracks = []
        for track_data in data.get("tracks", []):
            track = Track.from_dict(track_data, bpm=current_bpm)
            tracks.append(track)
        
        return cls(
            name=data.get("name", "Untitled Project"),
            bpm=current_bpm,
            original_bpm=original_bpm,
            time_signature=tuple(data.get("time_signature", [4, 4])),
            sample_rate=data.get("sample_rate", 44100),
            tracks=tracks
        )
    
    def add_track(self, track: Track) -> None:
        """添加轨道"""
        self.tracks.append(track)
    
    def remove_track(self, track: Track) -> None:
        """删除轨道"""
        if track in self.tracks:
            self.tracks.remove(track)
    
    def get_total_duration(self) -> float:
        """获取项目总时长"""
        max_duration = 0.0
        for track in self.tracks:
            if track.track_type == TrackType.DRUM_TRACK:
                # 打击乐音轨：使用 drum_events
                for event in track.drum_events:
                    # 将节拍转换为秒（使用项目BPM）
                    event_end_time = event.end_beat * 60.0 / self.bpm
                    max_duration = max(max_duration, event_end_time)
            else:
                # 音符音轨：使用 notes
                for note in track.notes:
                    max_duration = max(max_duration, note.end_time)
        return max_duration

