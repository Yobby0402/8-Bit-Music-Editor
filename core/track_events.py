"""Track event models shared by the sequencer and UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .models import ADSRParams, WaveformType


class DrumType(Enum):
    """Supported drum event kinds."""

    KICK = "kick"
    SNARE = "snare"
    HIHAT = "hihat"
    CRASH = "crash"


@dataclass
class BassEvent:
    """Bass event stored on the musical timeline."""

    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int = 127
    waveform: WaveformType = WaveformType.TRIANGLE
    adsr: Optional[ADSRParams] = None

    def __post_init__(self):
        if self.adsr is None:
            self.adsr = ADSRParams()

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    def get_start_tick(self, project) -> int:
        """Return the event start tick in the project's standard timebase."""
        return project.beats_to_ticks(self.start_beat)

    def get_duration_ticks(self, project) -> int:
        """Return the event duration in ticks."""
        return max(0, project.beats_to_ticks(self.duration_beats))

    def apply_tick_timing(self, project, start_tick: int, duration_ticks: int) -> None:
        """Update beat timing from standard tick timing."""
        self.start_beat = project.ticks_to_beats(start_tick)
        self.duration_beats = project.ticks_to_beats(max(0, duration_ticks))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pitch": self.pitch,
            "start_beat": self.start_beat,
            "duration_beats": self.duration_beats,
            "velocity": self.velocity,
            "waveform": self.waveform.value,
            "adsr": self.adsr.to_dict() if self.adsr else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BassEvent":
        adsr = ADSRParams.from_dict(data["adsr"]) if data.get("adsr") else None
        return cls(
            pitch=data["pitch"],
            start_beat=data["start_beat"],
            duration_beats=data["duration_beats"],
            velocity=data.get("velocity", 127),
            waveform=WaveformType(data.get("waveform", "triangle")),
            adsr=adsr,
        )


@dataclass
class DrumEvent:
    """Drum event stored on the musical timeline."""

    drum_type: DrumType
    start_beat: float
    duration_beats: float
    velocity: int = 127

    @property
    def end_beat(self) -> float:
        return self.start_beat + self.duration_beats

    def get_start_tick(self, project) -> int:
        """Return the drum event start tick in the project's standard timebase."""
        return project.beats_to_ticks(self.start_beat)

    def get_duration_ticks(self, project) -> int:
        """Return the drum event duration in ticks."""
        return max(0, project.beats_to_ticks(self.duration_beats))

    def apply_tick_timing(self, project, start_tick: int, duration_ticks: int) -> None:
        """Update beat timing from standard tick timing."""
        self.start_beat = project.ticks_to_beats(start_tick)
        self.duration_beats = project.ticks_to_beats(max(0, duration_ticks))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drum_type": self.drum_type.value,
            "start_beat": self.start_beat,
            "duration_beats": self.duration_beats,
            "velocity": self.velocity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrumEvent":
        return cls(
            drum_type=DrumType(data["drum_type"]),
            start_beat=data["start_beat"],
            duration_beats=data["duration_beats"],
            velocity=data.get("velocity", 127),
        )
