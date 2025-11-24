"""
轨道事件模型

定义不同类型的轨道事件：音符（主旋律）、低音事件、打击乐事件。
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

from .models import WaveformType, ADSRParams


class DrumType(Enum):
    """打击乐类型"""
    KICK = "kick"      # 底鼓
    SNARE = "snare"    # 军鼓
    HIHAT = "hihat"    # 踩镲
    CRASH = "crash"    # 吊镲


@dataclass
class BassEvent:
    """低音事件（不是音符，是低音线）"""
    pitch: int              # MIDI音高（0-127）
    start_beat: float       # 开始节拍位置（节拍数，不是秒）
    duration_beats: float    # 持续节拍数
    velocity: int = 127     # 力度
    waveform: WaveformType = WaveformType.TRIANGLE
    adsr: Optional[ADSRParams] = None
    
    def __post_init__(self):
        if self.adsr is None:
            from .models import ADSRParams
            self.adsr = ADSRParams()
    
    @property
    def end_beat(self) -> float:
        """结束节拍位置"""
        return self.start_beat + self.duration_beats
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pitch": self.pitch,
            "start_beat": self.start_beat,
            "duration_beats": self.duration_beats,
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "adsr": self.adsr.to_dict() if self.adsr else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BassEvent':
        """从字典创建"""
        adsr = None
        if data.get("adsr"):
            adsr = ADSRParams.from_dict(data["adsr"])
        
        return cls(
            pitch=data["pitch"],
            start_beat=data["start_beat"],
            duration_beats=data["duration_beats"],
            velocity=data.get("velocity", 127),
            waveform=WaveformType(data.get("waveform", "triangle")),
            adsr=adsr
        )


@dataclass
class DrumEvent:
    """打击乐事件"""
    drum_type: DrumType      # 打击乐类型
    start_beat: float        # 开始节拍位置
    duration_beats: float    # 持续节拍数（通常很短）
    velocity: int = 127      # 力度
    
    @property
    def end_beat(self) -> float:
        """结束节拍位置"""
        return self.start_beat + self.duration_beats
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "drum_type": self.drum_type.value,
            "start_beat": self.start_beat,
            "duration_beats": self.duration_beats,
            "velocity": self.velocity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DrumEvent':
        """从字典创建"""
        return cls(
            drum_type=DrumType(data["drum_type"]),
            start_beat=data["start_beat"],
            duration_beats=data["duration_beats"],
            velocity=data.get("velocity", 127)
        )

