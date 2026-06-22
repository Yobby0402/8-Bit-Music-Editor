"""8bit sound effect presets and conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from core.effect_processor import (
    DelayParams,
    FilterParams,
    FilterType,
    TremoloParams,
    VibratoParams,
)
from core.models import ADSRParams, Note, Project, Track, TrackRole, TrackType, WaveformType

SfxKind = Literal[
    "coin",
    "jump",
    "hit",
    "power_up",
    "laser",
    "explosion",
    "select",
    "error",
    "door",
    "heal",
]


@dataclass(frozen=True)
class SfxNoteSpec:
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int = 110
    waveform: WaveformType = WaveformType.SQUARE
    duty_cycle: float = 0.5
    adsr: ADSRParams = field(default_factory=lambda: ADSRParams(0.002, 0.04, 0.35, 0.03))
    vibrato: VibratoParams | None = None


@dataclass(frozen=True)
class SfxSpec:
    kind: str
    label: str
    notes: tuple[SfxNoteSpec, ...]
    filter_params: FilterParams | None = None
    delay_params: DelayParams | None = None
    tremolo_params: TremoloParams | None = None
    vibrato_params: VibratoParams | None = None

    @property
    def duration_beats(self) -> float:
        return max(
            (note.start_beat + note.duration_beats for note in self.notes),
            default=0.0,
        )


SFX_PRESET_LABELS: dict[SfxKind, str] = {
    "coin": "Coin pickup",
    "jump": "Jump",
    "hit": "Hit",
    "power_up": "Power up",
    "laser": "Laser",
    "explosion": "Explosion",
    "select": "Menu select",
    "error": "Error beep",
    "door": "Door open",
    "heal": "Heal",
}


def list_sfx_presets() -> list[str]:
    """Return supported SFX preset ids."""
    return list(SFX_PRESET_LABELS.keys())


def _short_adsr(decay: float = 0.04, release: float = 0.03) -> ADSRParams:
    return ADSRParams(attack=0.002, decay=decay, sustain=0.25, release=release)


def build_sfx_spec(kind: SfxKind = "coin") -> SfxSpec:
    """Build a deterministic 8bit SFX note specification."""
    filter_params = None
    delay_params = None
    tremolo_params = None
    vibrato_params = None
    if kind == "coin":
        notes = (
            SfxNoteSpec(84, 0.00, 0.10, 112, WaveformType.SQUARE, 0.25, _short_adsr()),
            SfxNoteSpec(91, 0.10, 0.09, 118, WaveformType.SQUARE, 0.25, _short_adsr()),
            SfxNoteSpec(96, 0.19, 0.14, 105, WaveformType.TRIANGLE, 0.5, _short_adsr(0.05, 0.05)),
        )
        delay_params = DelayParams(delay_time=0.055, feedback=0.18, mix=0.18, enabled=True)
    elif kind == "jump":
        notes = (
            SfxNoteSpec(
                67,
                0.00,
                0.12,
                104,
                WaveformType.SQUARE,
                0.25,
                _short_adsr(0.03, 0.025),
                VibratoParams(rate=18.0, depth=1.2, enabled=True),
            ),
            SfxNoteSpec(76, 0.12, 0.12, 96, WaveformType.SQUARE, 0.25, _short_adsr(0.03, 0.03)),
        )
        filter_params = FilterParams(FilterType.HIGHPASS, 450.0, 1.0, True)
    elif kind == "hit":
        notes = (
            SfxNoteSpec(43, 0.00, 0.08, 126, WaveformType.NOISE, 0.5, _short_adsr(0.02, 0.04)),
            SfxNoteSpec(36, 0.05, 0.13, 96, WaveformType.SQUARE, 0.5, _short_adsr(0.05, 0.08)),
        )
        filter_params = FilterParams(FilterType.LOWPASS, 1200.0, 1.2, True)
    elif kind == "power_up":
        notes = (
            SfxNoteSpec(72, 0.00, 0.09, 94, WaveformType.SQUARE, 0.25, _short_adsr()),
            SfxNoteSpec(76, 0.09, 0.09, 100, WaveformType.SQUARE, 0.25, _short_adsr()),
            SfxNoteSpec(79, 0.18, 0.09, 106, WaveformType.SQUARE, 0.25, _short_adsr()),
            SfxNoteSpec(84, 0.27, 0.18, 114, WaveformType.TRIANGLE, 0.5, _short_adsr(0.08, 0.08)),
        )
        delay_params = DelayParams(delay_time=0.08, feedback=0.28, mix=0.22, enabled=True)
        tremolo_params = TremoloParams(rate=10.0, depth=0.18, enabled=True)
    elif kind == "laser":
        notes = (
            SfxNoteSpec(96, 0.00, 0.08, 122, WaveformType.SAWTOOTH, 0.5, _short_adsr(0.015, 0.035)),
            SfxNoteSpec(88, 0.06, 0.10, 112, WaveformType.SQUARE, 0.25, _short_adsr(0.02, 0.04)),
            SfxNoteSpec(79, 0.14, 0.08, 92, WaveformType.SQUARE, 0.25, _short_adsr(0.02, 0.04)),
        )
        filter_params = FilterParams(FilterType.HIGHPASS, 700.0, 1.3, True)
        vibrato_params = VibratoParams(rate=24.0, depth=0.8, enabled=True)
    elif kind == "explosion":
        notes = (
            SfxNoteSpec(38, 0.00, 0.16, 126, WaveformType.NOISE, 0.5, _short_adsr(0.08, 0.12)),
            SfxNoteSpec(31, 0.08, 0.18, 108, WaveformType.SQUARE, 0.5, _short_adsr(0.08, 0.14)),
            SfxNoteSpec(26, 0.20, 0.20, 84, WaveformType.NOISE, 0.5, _short_adsr(0.10, 0.18)),
        )
        filter_params = FilterParams(FilterType.LOWPASS, 900.0, 1.1, True)
        tremolo_params = TremoloParams(rate=18.0, depth=0.35, enabled=True)
    elif kind == "select":
        notes = (
            SfxNoteSpec(79, 0.00, 0.06, 92, WaveformType.SQUARE, 0.25, _short_adsr(0.015, 0.02)),
            SfxNoteSpec(84, 0.06, 0.07, 98, WaveformType.SQUARE, 0.25, _short_adsr(0.015, 0.025)),
        )
    elif kind == "error":
        notes = (
            SfxNoteSpec(48, 0.00, 0.11, 110, WaveformType.SQUARE, 0.5, _short_adsr(0.04, 0.05)),
            SfxNoteSpec(45, 0.13, 0.13, 104, WaveformType.SQUARE, 0.5, _short_adsr(0.05, 0.06)),
        )
        tremolo_params = TremoloParams(rate=12.0, depth=0.28, enabled=True)
    elif kind == "door":
        notes = (
            SfxNoteSpec(52, 0.00, 0.12, 92, WaveformType.TRIANGLE, 0.5, _short_adsr(0.04, 0.08)),
            SfxNoteSpec(55, 0.12, 0.14, 102, WaveformType.SQUARE, 0.25, _short_adsr(0.05, 0.08)),
            SfxNoteSpec(59, 0.26, 0.12, 88, WaveformType.TRIANGLE, 0.5, _short_adsr(0.04, 0.08)),
        )
        filter_params = FilterParams(FilterType.LOWPASS, 1600.0, 1.0, True)
    elif kind == "heal":
        notes = (
            SfxNoteSpec(72, 0.00, 0.10, 92, WaveformType.TRIANGLE, 0.5, _short_adsr(0.04, 0.08)),
            SfxNoteSpec(76, 0.10, 0.10, 100, WaveformType.TRIANGLE, 0.5, _short_adsr(0.04, 0.08)),
            SfxNoteSpec(84, 0.20, 0.18, 108, WaveformType.SINE, 0.5, _short_adsr(0.08, 0.12)),
        )
        delay_params = DelayParams(delay_time=0.09, feedback=0.22, mix=0.20, enabled=True)
    else:
        raise ValueError(f"Unsupported SFX preset: {kind}")

    return SfxSpec(
        kind=kind,
        label=SFX_PRESET_LABELS[kind],
        notes=notes,
        filter_params=filter_params,
        delay_params=delay_params,
        tremolo_params=tremolo_params,
        vibrato_params=vibrato_params,
    )


def _parse_waveform(value: Any) -> WaveformType:
    try:
        return WaveformType(str(value or WaveformType.SQUARE.value))
    except ValueError:
        return WaveformType.SQUARE


def _parse_adsr(value: Any) -> ADSRParams:
    if not isinstance(value, dict):
        return _short_adsr()
    return ADSRParams(
        attack=max(0.0, float(value.get("attack", 0.002))),
        decay=max(0.0, float(value.get("decay", 0.04))),
        sustain=max(0.0, min(1.0, float(value.get("sustain", 0.25)))),
        release=max(0.0, float(value.get("release", 0.03))),
    )


def _parse_vibrato(value: Any) -> VibratoParams | None:
    if not isinstance(value, dict):
        return None
    return VibratoParams(
        rate=max(0.0, float(value.get("rate", 6.0))),
        depth=max(0.0, float(value.get("depth", 2.0))),
        enabled=bool(value.get("enabled", True)),
    )


def _parse_filter_params(value: Any) -> FilterParams | None:
    if not isinstance(value, dict):
        return None
    params = FilterParams.from_dict(value)
    params.cutoff_frequency = max(20.0, min(20000.0, params.cutoff_frequency))
    params.resonance = max(0.1, min(10.0, params.resonance))
    return params


def _parse_delay_params(value: Any) -> DelayParams | None:
    if not isinstance(value, dict):
        return None
    params = DelayParams.from_dict(value)
    params.delay_time = max(0.0, min(2.0, params.delay_time))
    params.feedback = max(0.0, min(0.95, params.feedback))
    params.mix = max(0.0, min(1.0, params.mix))
    return params


def _parse_tremolo_params(value: Any) -> TremoloParams | None:
    if not isinstance(value, dict):
        return None
    params = TremoloParams.from_dict(value)
    params.rate = max(0.0, min(40.0, params.rate))
    params.depth = max(0.0, min(1.0, params.depth))
    return params


def sfx_spec_from_dict(data: dict[str, Any]) -> SfxSpec:
    """Build a validated SFX spec from an AI/MCP payload."""
    notes_payload = data.get("notes")
    if not isinstance(notes_payload, list) or not notes_payload:
        raise ValueError("SFX spec requires a non-empty notes list")
    if len(notes_payload) > 32:
        raise ValueError("SFX spec supports at most 32 notes")

    notes = []
    for note_data in notes_payload:
        if not isinstance(note_data, dict):
            raise ValueError("Each SFX note must be an object")
        notes.append(
            SfxNoteSpec(
                pitch=max(0, min(127, int(note_data.get("pitch", 84)))),
                start_beat=max(0.0, float(note_data.get("start_beat", 0.0))),
                duration_beats=max(0.01, min(16.0, float(note_data.get("duration_beats", 0.1)))),
                velocity=max(0, min(127, int(note_data.get("velocity", 110)))),
                waveform=_parse_waveform(note_data.get("waveform")),
                duty_cycle=max(0.05, min(0.95, float(note_data.get("duty_cycle", 0.5)))),
                adsr=_parse_adsr(note_data.get("adsr")),
                vibrato=_parse_vibrato(note_data.get("vibrato") or note_data.get("vibrato_params")),
            )
        )

    kind = str(data.get("kind", "custom")).strip() or "custom"
    label = str(data.get("label", "Custom SFX")).strip() or "Custom SFX"
    return SfxSpec(
        kind=kind,
        label=label,
        notes=tuple(notes),
        filter_params=_parse_filter_params(data.get("filter_params")),
        delay_params=_parse_delay_params(data.get("delay_params")),
        tremolo_params=_parse_tremolo_params(data.get("tremolo_params")),
        vibrato_params=_parse_vibrato(data.get("vibrato_params")),
    )


def find_sfx_track(tracks: Iterable[Track]) -> Track | None:
    """Find the first existing note track dedicated to sound effects."""
    for track in tracks:
        if track.track_type == TrackType.NOTE_TRACK and track.role == TrackRole.EFFECT:
            return track
    return None


def make_sfx_track(name: str = "SFX") -> Track:
    """Create a note track intended for short sound effects."""
    return Track(name=name, track_type=TrackType.NOTE_TRACK, role=TrackRole.EFFECT, volume=0.9)


def sfx_note_to_note(project: Project, spec: SfxNoteSpec, start_beat: float) -> Note:
    """Convert a beat-based SFX note spec to a project note."""
    absolute_start_beat = max(0.0, float(start_beat) + spec.start_beat)
    start_tick = project.beats_to_ticks(absolute_start_beat)
    duration_ticks = max(1, project.beats_to_ticks(spec.duration_beats))
    note = Note(
        pitch=max(0, min(127, int(spec.pitch))),
        start_time=0.0,
        duration=0.0,
        velocity=max(0, min(127, int(spec.velocity))),
        waveform=spec.waveform,
        duty_cycle=max(0.05, min(0.95, float(spec.duty_cycle))),
        adsr=ADSRParams(
            attack=spec.adsr.attack,
            decay=spec.adsr.decay,
            sustain=spec.adsr.sustain,
            release=spec.adsr.release,
        ),
        vibrato_params=VibratoParams(
            rate=spec.vibrato.rate,
            depth=spec.vibrato.depth,
            enabled=spec.vibrato.enabled,
        )
        if spec.vibrato
        else None,
    )
    note.apply_tick_timing(project, start_tick, duration_ticks)
    return note


def build_sfx_notes(project: Project, spec: SfxSpec, start_beat: float = 0.0) -> list[Note]:
    """Convert an SFX spec to project notes."""
    return [sfx_note_to_note(project, note_spec, start_beat) for note_spec in spec.notes]


__all__ = [
    "SFX_PRESET_LABELS",
    "SfxKind",
    "SfxNoteSpec",
    "SfxSpec",
    "build_sfx_notes",
    "build_sfx_spec",
    "find_sfx_track",
    "list_sfx_presets",
    "make_sfx_track",
    "sfx_spec_from_dict",
    "sfx_note_to_note",
]
