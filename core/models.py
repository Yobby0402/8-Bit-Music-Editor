"""
数据模型定义

定义Note、Track、Project等核心数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .musical_time import (
    DEFAULT_PPQN,
    TempoEvent,
    build_tempo_regions,
    seconds_to_ticks_with_regions,
    tempo_event_rows_to_segments,
    tempo_events_from_bpm_segments,
    ticks_to_seconds_with_regions,
)
from .musical_time import (
    beats_to_ticks as musical_beats_to_ticks,
)
from .musical_time import (
    ticks_to_beats as musical_ticks_to_beats,
)

if TYPE_CHECKING:
    from .effect_processor import DelayParams, FilterParams, TremoloParams, VibratoParams
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


class TrackRole(Enum):
    """音符音轨的语义角色枚举。"""
    MELODY = "melody"
    BASS = "bass"
    HARMONY = "harmony"
    EFFECT = "effect"


LEGACY_TRACK_ROLE_KEYWORDS: dict[TrackRole, tuple[str, ...]] = {
    TrackRole.MELODY: ("主旋律", "melody", "lead"),
    TrackRole.BASS: ("低音", "bass"),
    TrackRole.HARMONY: ("和声", "harmony", "pad", "chord"),
    TrackRole.EFFECT: ("效果", "effect", "fx", "sfx"),
}


def infer_track_role(name: str | None, track_type: TrackType | None) -> Optional[TrackRole]:
    """基于旧项目的音轨名称推断角色。"""
    if track_type == TrackType.DRUM_TRACK:
        return None

    normalized_name = (name or "").strip().lower()
    for role, keywords in LEGACY_TRACK_ROLE_KEYWORDS.items():
        if any(keyword in normalized_name for keyword in keywords):
            return role
    return TrackRole.MELODY


def normalize_track_role(
    role: TrackRole | str | None,
    name: str | None,
    track_type: TrackType | None,
) -> Optional[TrackRole]:
    """规范化 role 字段，并兼容旧项目未显式保存角色的情况。"""
    if track_type == TrackType.DRUM_TRACK:
        return None
    if isinstance(role, TrackRole):
        return role
    if isinstance(role, str):
        normalized_role = role.strip().lower()
        for candidate in TrackRole:
            if candidate.value == normalized_role:
                return candidate
    return infer_track_role(name, track_type)


@dataclass
class BPMSegment:
    """BPM段数据模型"""
    start_time: float  # 开始时间（秒）
    bpm: float         # 该段的BPM值
    end_time: Optional[float] = None  # 结束时间（秒），None表示到下一个段或项目结束
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "start_time": self.start_time,
            "bpm": self.bpm,
            "end_time": self.end_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BPMSegment':
        """从字典创建"""
        return cls(
            start_time=data.get("start_time", 0.0),
            bpm=data.get("bpm", 120.0),
            end_time=data.get("end_time")
        )
    
    def contains_time(self, time: float) -> bool:
        """检查时间是否在此段内"""
        if self.end_time is None:
            return time >= self.start_time
        return self.start_time <= time < self.end_time


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
    start_tick: Optional[int] = None  # 标准时间模型中的开始tick
    duration_ticks: Optional[int] = None  # 标准时间模型中的持续tick
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
            result["vibrato_params"] = {
                "rate": self.vibrato_params.rate,
                "depth": self.vibrato_params.depth,
                "enabled": self.vibrato_params.enabled
            }
        if self.start_tick is not None:
            result["start_tick"] = self.start_tick
        if self.duration_ticks is not None:
            result["duration_ticks"] = self.duration_ticks
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
            start_tick=data.get("start_tick"),
            duration_ticks=data.get("duration_ticks"),
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
            start_tick=data.get("start_tick"),
            duration_ticks=data.get("duration_ticks"),
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
            start_tick=data.get("start_tick"),
            duration_ticks=data.get("duration_ticks"),
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

    def get_start_tick(self, project: "Project") -> int:
        """Return the note start tick in the project's standard timebase."""
        if self.start_tick is not None:
            return max(0, int(self.start_tick))
        return project.seconds_to_ticks(self.start_time)

    def get_duration_ticks(self, project: "Project") -> int:
        """Return the note duration in ticks."""
        if self.duration_ticks is not None:
            return max(0, int(self.duration_ticks))
        end_tick = project.seconds_to_ticks(self.end_time)
        start_tick = self.get_start_tick(project)
        return max(0, end_tick - start_tick)

    def sync_tick_timing(self, project: "Project", prefer_existing: bool = True) -> None:
        """Populate tick fields from either stored tick timing or current second timing."""
        if prefer_existing:
            start_tick = self.get_start_tick(project)
            duration_ticks = self.get_duration_ticks(project)
        else:
            start_tick = max(0, project.seconds_to_ticks(self.start_time))
            end_tick = max(start_tick, project.seconds_to_ticks(self.end_time))
            duration_ticks = max(0, end_tick - start_tick)
        self.start_tick = start_tick
        self.duration_ticks = duration_ticks

    def sync_second_timing(self, project: "Project") -> None:
        """Populate second timing from the current tick timing."""
        self.apply_tick_timing(
            project,
            self.get_start_tick(project),
            self.get_duration_ticks(project),
        )

    def apply_tick_timing(
        self,
        project: "Project",
        start_tick: int,
        duration_ticks: int,
    ) -> None:
        """Update both tick and second timing from standard musical timing."""
        safe_start_tick = max(0, int(start_tick))
        safe_duration_ticks = max(0, int(duration_ticks))
        self.start_tick = safe_start_tick
        self.duration_ticks = safe_duration_ticks
        self.start_time = project.ticks_to_seconds(safe_start_tick)
        end_time = project.ticks_to_seconds(safe_start_tick + safe_duration_ticks)
        self.duration = max(0.0, end_time - self.start_time)


@dataclass
class Track:
    """轨道数据模型"""
    name: str = "Track 1"
    track_type: 'TrackType' = None  # 音轨类型（NOTE_TRACK 或 DRUM_TRACK）
    role: Optional['TrackRole'] = None  # 音符音轨角色（主旋律/低音/和声/效果）
    volume: float = 1.0      # 音量（0-1）
    pan: float = 0.0         # 声相（-1到1，0为居中）
    enabled: bool = True    # 是否启用
    display_height: Optional[int] = None  # UI 中该音轨的显示高度（像素）
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
        self.role = normalize_track_role(self.role, self.name, self.track_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（完整格式）"""
        result = {
            "name": self.name,
            "track_type": self.track_type.value if self.track_type else TrackType.NOTE_TRACK.value,
            "volume": self.volume,
            "pan": self.pan,
            "enabled": self.enabled,
        }
        if self.role is not None:
            result["role"] = self.role.value
        if self.display_height is not None:
            result["display_height"] = int(self.display_height)
        if self.track_type == TrackType.DRUM_TRACK:
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
        if self.role is not None:
            result["role"] = self.role.value
        if self.display_height is not None:
            result["display_height"] = int(self.display_height)
        if self.track_type == TrackType.DRUM_TRACK:
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
        if self.role is not None:
            result["role"] = self.role.value
        if self.display_height is not None:
            result["display_height"] = int(self.display_height)
        if self.track_type == TrackType.DRUM_TRACK:
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
        track_role = normalize_track_role(
            data.get("role"),
            data.get("name", "Track 1"),
            track_type,
        )

        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                role=track_role,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                display_height=data.get("display_height"),
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
            role=track_role,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            display_height=data.get("display_height"),
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
        track_role = normalize_track_role(
            data.get("role"),
            data.get("name", "Track 1"),
            track_type,
        )

        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                role=track_role,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                display_height=data.get("display_height"),
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
            role=track_role,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            display_height=data.get("display_height"),
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
        track_role = normalize_track_role(
            data.get("role"),
            data.get("name", "Track 1"),
            track_type,
        )

        # 如果是打击乐音轨，处理 drum_events
        if track_type == TrackType.DRUM_TRACK:
            from .track_events import DrumEvent
            drum_events_data = data.get("drum_events", [])
            drum_events = [DrumEvent.from_dict(event_data) for event_data in drum_events_data]
            return cls(
                name=data.get("name", "Track 1"),
                track_type=track_type,
                role=track_role,
                volume=data.get("volume", 1.0),
                pan=data.get("pan", 0.0),
                enabled=data.get("enabled", True),
                display_height=data.get("display_height"),
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
            role=track_role,
            volume=data.get("volume", 1.0),
            pan=data.get("pan", 0.0),
            enabled=data.get("enabled", True),
            display_height=data.get("display_height"),
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
    bpm: float = 120.0              # 节拍速度（当前BPM，用于兼容性，实际使用bpm_segments）
    original_bpm: Optional[float] = None  # 原始BPM（JSON生成时的BPM，用于BPM缩放）
    resolution: int = DEFAULT_PPQN  # 标准时间模型中的每拍tick数（PPQN）
    time_signature: tuple = (4, 4)  # 拍号（分子，分母）
    sample_rate: int = 44100        # 采样率
    tracks: List[Track] = field(default_factory=list)  # 轨道列表
    bpm_segments: List[BPMSegment] = field(default_factory=list)  # BPM段列表（支持可变BPM）
    tempo_events: List[TempoEvent] = field(default_factory=list)  # 标准tick时间轴上的速度事件
    _tempo_region_cache: List[tuple[int, Optional[int], float, float]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _tempo_region_cache_signature: Optional[tuple[Any, ...]] = field(
        default=None,
        init=False,
        repr=False,
    )
    
    def __post_init__(self):
        """初始化后处理"""
        self.resolution = int(self.resolution) if int(self.resolution) > 0 else DEFAULT_PPQN
        if self.tempo_events:
            self.replace_tempo_events(self.tempo_events)
        elif self.bpm_segments:
            self.replace_bpm_segments(self.bpm_segments)
        else:
            self.replace_tempo_events([TempoEvent(0, self.bpm)])
        self.sync_note_seconds_from_ticks()
    
    def get_bpm_at_time(self, time: float) -> float:
        """获取指定时间的BPM值"""
        # 如果没有BPM段，使用默认BPM
        if not self.bpm_segments:
            return self.bpm
        
        # 查找包含该时间的BPM段
        for segment in self.bpm_segments:
            if segment.contains_time(time):
                return segment.bpm
        
        # 如果没有找到，返回最后一个段的BPM
        if self.bpm_segments:
            return self.bpm_segments[-1].bpm
        
        return self.bpm

    def uses_variable_bpm(self) -> bool:
        """Return whether the project uses a multi-segment tempo map."""
        return len(self.tempo_events) > 1

    def get_reference_bpm(self) -> float:
        """Return the legacy single-BPM reference used by note timing."""
        reference_bpm = self.original_bpm if self.original_bpm is not None else self.bpm
        return reference_bpm if reference_bpm > 0 else 120.0

    def beats_to_seconds(self, beats: float) -> float:
        """Convert beats to project timeline seconds."""
        return self.ticks_to_seconds(self.beats_to_ticks(beats))

    def seconds_to_beats(self, seconds: float) -> float:
        """Convert project timeline seconds to beats."""
        return self.ticks_to_beats(self.seconds_to_ticks(seconds))

    def beats_to_ticks(self, beats: float) -> int:
        """Convert beats to project ticks."""
        return musical_beats_to_ticks(beats, self.resolution)

    def ticks_to_beats(self, ticks: int) -> float:
        """Convert ticks to beats."""
        return musical_ticks_to_beats(ticks, self.resolution)

    def ticks_to_seconds(self, ticks: int) -> float:
        """Convert ticks to seconds using the standard tick tempo map."""
        return ticks_to_seconds_with_regions(
            ticks,
            self.get_tempo_regions(),
            self.resolution,
        )

    def seconds_to_ticks(self, seconds: float) -> int:
        """Convert seconds to ticks using the standard tick tempo map."""
        return seconds_to_ticks_with_regions(
            seconds,
            self.get_tempo_regions(),
            self.resolution,
        )

    def _invalidate_tempo_region_cache(self) -> None:
        self._tempo_region_cache = []
        self._tempo_region_cache_signature = None

    def _tempo_region_signature(self) -> tuple[Any, ...]:
        return (
            int(self.resolution),
            float(self.get_reference_bpm()),
            tuple((int(event.tick), float(event.bpm)) for event in self.tempo_events),
        )

    def get_tempo_regions(self) -> List[tuple[int, Optional[int], float, float]]:
        """Return cached tempo regions for repeated timeline conversions."""
        signature = self._tempo_region_signature()
        if self._tempo_region_cache_signature != signature:
            self._tempo_region_cache = build_tempo_regions(
                self.tempo_events,
                self.resolution,
                self.get_reference_bpm(),
            )
            self._tempo_region_cache_signature = signature
        return self._tempo_region_cache

    def replace_bpm_segments(self, bpm_segments: List[BPMSegment]) -> None:
        """Replace legacy second-based BPM segments and sync standard tempo events."""
        self.sync_note_ticks_from_seconds()
        normalized_segments = [
            BPMSegment(
                start_time=max(0.0, float(segment.start_time)),
                bpm=float(segment.bpm),
                end_time=segment.end_time,
            )
            for segment in list(bpm_segments or [])
        ]
        if not normalized_segments:
            normalized_segments = [BPMSegment(start_time=0.0, bpm=self.get_reference_bpm())]
        normalized_segments.sort(key=lambda segment: segment.start_time)
        normalized_segments[0].start_time = 0.0
        self.bpm_segments = normalized_segments
        self.bpm = self.bpm_segments[0].bpm
        self._update_segment_end_times()
        self.sync_note_seconds_from_ticks()

    def replace_tempo_events(self, tempo_events: List[TempoEvent]) -> None:
        """Replace standard tick-based tempo events and sync legacy BPM segments."""
        self.sync_note_ticks_from_seconds()
        safe_bpm = self.get_reference_bpm()
        normalized_events = sorted(
            [
                TempoEvent(
                    tick=max(0, int(event.tick)),
                    bpm=float(event.bpm if float(event.bpm) > 0 else safe_bpm),
                )
                for event in list(tempo_events or [])
            ],
            key=lambda event: event.tick,
        )
        if not normalized_events:
            normalized_events = [TempoEvent(0, safe_bpm)]

        deduped_events: List[TempoEvent] = []
        for event in normalized_events:
            if deduped_events and deduped_events[-1].tick == event.tick:
                deduped_events[-1] = event
            else:
                deduped_events.append(event)

        if deduped_events[0].tick != 0:
            deduped_events.insert(0, TempoEvent(0, deduped_events[0].bpm))
        else:
            deduped_events[0] = TempoEvent(0, deduped_events[0].bpm)

        self.tempo_events = deduped_events
        self._invalidate_tempo_region_cache()
        self.bpm = self.tempo_events[0].bpm
        self._sync_segments_from_tempo_events()
        self.sync_note_seconds_from_ticks()

    def add_tempo_event(self, tick: int, bpm: float) -> TempoEvent:
        """Add a tempo event on the standard musical timeline."""
        new_event = TempoEvent(tick=max(0, int(tick)), bpm=float(bpm))
        self.replace_tempo_events([*self.tempo_events, new_event])
        for event in self.tempo_events:
            if event.tick == new_event.tick:
                return event
        return self.tempo_events[-1]

    def remove_tempo_event(self, tempo_event: TempoEvent) -> None:
        """Remove a tempo event and keep the tempo map normalized."""
        remaining_events = [
            event for event in self.tempo_events if event != tempo_event
        ]
        self.replace_tempo_events(remaining_events)

    def sync_note_ticks_from_seconds(self) -> None:
        """Capture current UI-facing second timing into the note tick bridge."""
        for track in self.tracks:
            if track.track_type != TrackType.NOTE_TRACK:
                continue
            for note in track.notes:
                note.sync_tick_timing(self, prefer_existing=False)

    def sync_note_seconds_from_ticks(self) -> None:
        """Refresh note second timing from the standard tick timeline."""
        for track in self.tracks:
            if track.track_type != TrackType.NOTE_TRACK:
                continue
            for note in track.notes:
                if note.start_tick is None or note.duration_ticks is None:
                    note.sync_tick_timing(self, prefer_existing=False)
                note.sync_second_timing(self)
            track.notes.sort(key=lambda note: note.start_time)

    def add_bpm_segment(self, start_time: float, bpm: float, end_time: Optional[float] = None) -> BPMSegment:
        """添加BPM段"""
        segment = BPMSegment(start_time=start_time, bpm=bpm, end_time=end_time)
        self.replace_bpm_segments([*self.bpm_segments, segment])
        return max(
            self.bpm_segments,
            key=lambda current: (current.start_time == max(0.0, float(start_time)), current.start_time),
        )
    
    def remove_bpm_segment(self, segment: BPMSegment) -> None:
        """删除BPM段"""
        if segment in self.bpm_segments:
            remaining_segments = [
                current_segment
                for current_segment in self.bpm_segments
                if current_segment != segment
            ]
            self.replace_bpm_segments(remaining_segments)
    
    def _update_segment_end_times(self) -> None:
        """更新BPM段的结束时间"""
        # 按开始时间排序
        self.bpm_segments.sort(key=lambda s: s.start_time)
        if self.bpm_segments:
            self.bpm_segments[0].start_time = 0.0
        # 更新每个段的结束时间（除了最后一个）
        for i in range(len(self.bpm_segments) - 1):
            self.bpm_segments[i].end_time = self.bpm_segments[i + 1].start_time
        # 最后一个段的结束时间为None（表示到项目结束）
        if self.bpm_segments:
            self.bpm_segments[-1].end_time = None
        self._sync_tempo_events_from_segments()

    def _sync_tempo_events_from_segments(self) -> None:
        """Derive tick-based tempo events from legacy second-based segments."""
        self.tempo_events = tempo_events_from_bpm_segments(
            self.bpm_segments,
            self.resolution,
            self.get_reference_bpm(),
        )
        self._invalidate_tempo_region_cache()
        if self.tempo_events:
            self.bpm = self.tempo_events[0].bpm

    def _sync_segments_from_tempo_events(self) -> None:
        """Derive second-based BPM segments for legacy UI paths."""
        rows = tempo_event_rows_to_segments(
            self.tempo_events,
            self.resolution,
            self.get_reference_bpm(),
        )
        self.bpm_segments = [
            BPMSegment(start_time=start_time, bpm=bpm, end_time=end_time)
            for start_time, bpm, end_time in rows
        ]
        if self.bpm_segments:
            self.bpm = self.bpm_segments[0].bpm
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        self.sync_note_ticks_from_seconds()
        result = {
            "name": self.name,
            "bpm": self.bpm,
            "original_bpm": self.original_bpm if self.original_bpm is not None else self.bpm,
            "resolution": self.resolution,
            "time_signature": list(self.time_signature),
            "sample_rate": self.sample_rate,
            "tracks": [track.to_dict() for track in self.tracks]
        }
        # 如果有BPM段，添加BPM段信息
        if self.bpm_segments and len(self.bpm_segments) > 1:
            result["bpm_segments"] = [segment.to_dict() for segment in self.bpm_segments]
        if self.tempo_events:
            result["tempo_events"] = [event.to_dict() for event in self.tempo_events]
        return result
    
    def to_dict_sequence(self) -> Dict[str, Any]:
        """转换为字典（序列格式，不包含start_time）"""
        bpm = self.original_bpm if self.original_bpm is not None else self.bpm
        return {
            "name": self.name,
            "bpm": self.bpm,
            "original_bpm": self.original_bpm if self.original_bpm is not None else self.bpm,
            "resolution": self.resolution,
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
            "resolution": self.resolution,
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
        resolution = int(data.get("resolution", DEFAULT_PPQN) or DEFAULT_PPQN)
        
        # 创建轨道（使用当前BPM用于序列格式的导入）
        tracks = []
        for track_data in data.get("tracks", []):
            track = Track.from_dict(track_data, bpm=current_bpm)
            tracks.append(track)
        
        # 加载BPM段（如果存在）
        bpm_segments = []
        if "bpm_segments" in data and data["bpm_segments"]:
            bpm_segments = [BPMSegment.from_dict(seg_data) for seg_data in data["bpm_segments"]]
        tempo_events = []
        if "tempo_events" in data and data["tempo_events"]:
            tempo_events = [TempoEvent.from_dict(event_data) for event_data in data["tempo_events"]]
        
        project = cls(
            name=data.get("name", "Untitled Project"),
            bpm=current_bpm,
            original_bpm=original_bpm,
            resolution=resolution,
            time_signature=tuple(data.get("time_signature", [4, 4])),
            sample_rate=data.get("sample_rate", 44100),
            tracks=tracks,
            bpm_segments=bpm_segments,
            tempo_events=tempo_events,
        )
        return project
    
    def add_track(self, track: Track) -> None:
        """添加轨道"""
        self.tracks.append(track)
    
    def remove_track(self, track: Track) -> None:
        """删除轨道"""
        if track in self.tracks:
            self.tracks.remove(track)
    
    def _legacy_get_total_duration(self) -> float:
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

    def get_total_duration(self) -> float:
        """鑾峰彇椤圭洰鎬绘椂闀?"""
        max_duration = 0.0
        for track in self.tracks:
            if track.track_type == TrackType.DRUM_TRACK:
                for event in track.drum_events:
                    event_end_time = self.beats_to_seconds(event.end_beat)
                    max_duration = max(max_duration, event_end_time)
            else:
                for note in track.notes:
                    max_duration = max(max_duration, note.end_time)
        return max_duration
