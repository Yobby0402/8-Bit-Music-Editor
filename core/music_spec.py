"""Structured music specs for MCP/app-control generation and insertion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from core.command import AddTrackCommand, BatchCommand, Command
from core.effect_processor import (
    DelayParams,
    FilterParams,
    FilterType,
    TremoloParams,
    VibratoParams,
)
from core.models import ADSRParams, Note, Project, Track, TrackRole, TrackType, WaveformType
from core.musical_time import TempoEvent
from core.track_events import DrumEvent, DrumType

MusicTrackKind = Literal["note", "drum"]
BEATS_PER_BAR = 4.0
SUPPORTED_PHRASE_BARS = 4
MAX_GENERATED_BARS = 32
EPIC_MELODY_NOTES_PER_BAR = 5
PLAYFUL_MELODY_NOTES_PER_BAR = 6


@dataclass(frozen=True)
class MusicNoteSpec:
    pitch: int
    start_beat: float
    duration_beats: float
    velocity: int = 110
    waveform: WaveformType = WaveformType.SQUARE
    duty_cycle: float = 0.5
    adsr: ADSRParams = field(default_factory=ADSRParams)
    vibrato: VibratoParams | None = None


@dataclass(frozen=True)
class MusicDrumEventSpec:
    drum_type: DrumType
    start_beat: float
    duration_beats: float = 0.25
    velocity: int = 110


@dataclass(frozen=True)
class MusicSectionSpec:
    name: str
    start_beat: float
    duration_beats: float


@dataclass(frozen=True)
class MusicTrackSpec:
    name: str
    track_type: TrackType = TrackType.NOTE_TRACK
    role: TrackRole | None = TrackRole.MELODY
    volume: float = 1.0
    pan: float = 0.0
    notes: tuple[MusicNoteSpec, ...] = ()
    drum_events: tuple[MusicDrumEventSpec, ...] = ()
    filter_params: FilterParams | None = None
    delay_params: DelayParams | None = None
    tremolo_params: TremoloParams | None = None
    vibrato_params: VibratoParams | None = None


@dataclass(frozen=True)
class MusicSpec:
    kind: str
    label: str
    bpm: float
    tracks: tuple[MusicTrackSpec, ...]
    time_signature: tuple[int, int] = (4, 4)
    structure: tuple[MusicSectionSpec, ...] = ()
    style_params: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_beats(self) -> float:
        section_end = max(
            (section.start_beat + section.duration_beats for section in self.structure),
            default=0.0,
        )
        track_end = max((_track_duration(track) for track in self.tracks), default=0.0)
        return max(section_end, track_end)


class SetProjectTempoCommand(Command):
    """Undoable project tempo replacement for app-control music insertion."""

    def __init__(self, project: Project, bpm: float, time_signature: tuple[int, int]):
        self.project = project
        self.next_bpm = float(bpm)
        self.next_time_signature = tuple(time_signature)
        self.previous_bpm = float(project.bpm)
        self.previous_original_bpm = project.original_bpm
        self.previous_time_signature = tuple(project.time_signature)
        self.previous_tempo_events = list(project.tempo_events)

    def execute(self) -> None:
        self.project.bpm = self.next_bpm
        self.project.original_bpm = self.next_bpm
        self.project.time_signature = self.next_time_signature
        self.project.replace_tempo_events([TempoEvent(0, self.next_bpm)])

    def undo(self) -> None:
        self.project.bpm = self.previous_bpm
        self.project.original_bpm = self.previous_original_bpm
        self.project.time_signature = self.previous_time_signature
        self.project.replace_tempo_events(self.previous_tempo_events)

    def get_description(self) -> str:
        return f"Set BPM: {self.next_bpm:g}"


def music_spec_from_dict(data: dict[str, Any]) -> MusicSpec:
    """Build a validated MusicSpec from an AI/MCP payload."""
    tracks_payload = data.get("tracks")
    if not isinstance(tracks_payload, list) or not tracks_payload:
        raise ValueError("Music spec requires a non-empty tracks list")
    if len(tracks_payload) > 16:
        raise ValueError("Music spec supports at most 16 tracks")

    tracks = tuple(_parse_track(track_data) for track_data in tracks_payload)
    if not any(track.track_type == TrackType.NOTE_TRACK and track.notes for track in tracks):
        raise ValueError("Music spec requires at least one note track with notes")

    kind = str(data.get("kind", "custom_music")).strip() or "custom_music"
    label = str(data.get("label", "Custom music")).strip() or "Custom music"
    return MusicSpec(
        kind=kind,
        label=label,
        bpm=_parse_bpm(data.get("bpm", 120.0)),
        time_signature=_parse_time_signature(data.get("time_signature", (4, 4))),
        structure=_parse_structure(data.get("structure")),
        style_params=_parse_style_params(data.get("style_params")),
        tracks=tracks,
    )


def music_spec_to_dict(spec: MusicSpec) -> dict[str, Any]:
    """Convert a MusicSpec to the JSON-ready AI/MCP payload shape."""
    return {
        "kind": spec.kind,
        "label": spec.label,
        "bpm": spec.bpm,
        "time_signature": list(spec.time_signature),
        "duration_beats": spec.duration_beats,
        "structure": [
            {
                "name": section.name,
                "start_beat": section.start_beat,
                "duration_beats": section.duration_beats,
            }
            for section in spec.structure
        ],
        "style_params": dict(spec.style_params),
        "tracks": [_track_to_dict(track) for track in spec.tracks],
    }


def generate_music_spec(
    *,
    style: str = "epic",
    length_bars: int = 8,
    bpm: float | None = None,
    key: str = "C",
    intensity: float = 0.85,
) -> MusicSpec:
    """Generate a deterministic multi-track music spec for AI/app-control tools."""
    normalized_style = _normalize_style(style)
    if normalized_style not in {"epic", "playful"}:
        normalized_style = "epic"
    bars = _normalize_phrase_bars(length_bars)
    default_bpm = 120.0 if normalized_style == "playful" else 132.0
    resolved_bpm = _parse_bpm(bpm if bpm is not None else default_bpm)
    root = _parse_key_root(key)
    intensity = max(0.0, min(1.0, float(intensity)))

    structure = _build_structure(bars)
    if normalized_style == "playful":
        tracks = (
            _build_playful_melody_track(root, bars, intensity),
            _build_playful_bass_track(root, bars, intensity),
            _build_playful_harmony_track(root, bars, intensity),
            _build_playful_drum_track(bars, intensity),
        )
        kind = "playful_music"
        label = "Playful 8bit Theme"
        palette = "bright comic bounce"
        drum_template = "playful_backbeat"
        melody_notes_per_bar = PLAYFUL_MELODY_NOTES_PER_BAR
    else:
        tracks = (
            _build_epic_melody_track(root, bars, intensity),
            _build_epic_bass_track(root, bars, intensity),
            _build_epic_harmony_track(root, bars, intensity),
            _build_epic_drum_track(bars, intensity),
        )
        kind = "epic_music"
        label = "Epic 8bit Theme"
        palette = "heroic minor fanfare"
        drum_template = "epic_backbeat"
        melody_notes_per_bar = EPIC_MELODY_NOTES_PER_BAR

    return MusicSpec(
        kind=kind,
        label=label,
        bpm=resolved_bpm,
        time_signature=(4, 4),
        structure=structure,
        style_params={
            "style": normalized_style,
            "key": key,
            "length_bars": bars,
            "intensity": intensity,
            "phrase_bars": SUPPORTED_PHRASE_BARS,
            "strong_beats": [0.0, 2.0],
            "melody_notes_per_bar_max": melody_notes_per_bar,
            "drum_template": drum_template,
            "palette": palette,
        },
        tracks=tracks,
    )


def build_insert_music_command(
    sequencer,
    spec: MusicSpec,
    start_beat: float = 0.0,
) -> tuple[BatchCommand, dict[str, Any]]:
    """Build an undoable command that inserts a full multi-track music spec."""
    start = max(0.0, float(start_beat))
    timing_project = Project(
        bpm=spec.bpm,
        original_bpm=spec.bpm,
        resolution=sequencer.project.resolution,
        time_signature=spec.time_signature,
        sample_rate=sequencer.project.sample_rate,
    )
    commands: list[Command] = [
        SetProjectTempoCommand(sequencer.project, spec.bpm, spec.time_signature)
    ]
    tracks = [music_track_to_track(timing_project, track_spec, start) for track_spec in spec.tracks]
    commands.extend(AddTrackCommand(sequencer, track) for track in tracks)
    summary = summarize_music_spec(spec, start_beat=start, track_start_index=len(sequencer.project.tracks))
    return BatchCommand(commands, f"Insert music: {spec.label}"), summary


def music_track_to_track(project: Project, spec: MusicTrackSpec, start_beat: float = 0.0) -> Track:
    """Convert a MusicTrackSpec into a project Track."""
    if spec.track_type == TrackType.DRUM_TRACK:
        return Track(
            name=spec.name,
            track_type=TrackType.DRUM_TRACK,
            volume=spec.volume,
            pan=spec.pan,
            drum_events=[
                DrumEvent(
                    drum_type=event.drum_type,
                    start_beat=max(0.0, float(start_beat) + event.start_beat),
                    duration_beats=event.duration_beats,
                    velocity=event.velocity,
                )
                for event in spec.drum_events
            ],
            filter_params=spec.filter_params,
            delay_params=spec.delay_params,
            tremolo_params=spec.tremolo_params,
            vibrato_params=spec.vibrato_params,
        )

    return Track(
        name=spec.name,
        track_type=TrackType.NOTE_TRACK,
        role=spec.role,
        volume=spec.volume,
        pan=spec.pan,
        notes=[music_note_to_note(project, note_spec, start_beat) for note_spec in spec.notes],
        filter_params=spec.filter_params,
        delay_params=spec.delay_params,
        tremolo_params=spec.tremolo_params,
        vibrato_params=spec.vibrato_params,
    )


def music_note_to_note(project: Project, spec: MusicNoteSpec, start_beat: float = 0.0) -> Note:
    """Convert a beat-based MusicNoteSpec to a project Note."""
    absolute_start_beat = max(0.0, float(start_beat) + spec.start_beat)
    start_tick = project.beats_to_ticks(absolute_start_beat)
    duration_ticks = max(1, project.beats_to_ticks(spec.duration_beats))
    note = Note(
        pitch=spec.pitch,
        start_time=0.0,
        duration=0.0,
        velocity=spec.velocity,
        waveform=spec.waveform,
        duty_cycle=spec.duty_cycle,
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


def summarize_music_spec(
    spec: MusicSpec,
    *,
    start_beat: float = 0.0,
    track_start_index: int = 0,
) -> dict[str, Any]:
    """Return a compact summary for dry-run and insertion results."""
    tracks = []
    note_count = 0
    drum_event_count = 0
    for offset, track in enumerate(spec.tracks):
        track_notes = len(track.notes)
        track_drums = len(track.drum_events)
        note_count += track_notes
        drum_event_count += track_drums
        effect_keys = [
            key
            for key, value in {
                "filter_params": track.filter_params,
                "delay_params": track.delay_params,
                "tremolo_params": track.tremolo_params,
                "vibrato_params": track.vibrato_params,
            }.items()
            if value is not None
        ]
        tracks.append(
            {
                "index": track_start_index + offset,
                "name": track.name,
                "track_type": track.track_type.value,
                "role": track.role.value if track.role else None,
                "note_count": track_notes,
                "drum_event_count": track_drums,
                "volume": track.volume,
                "pan": track.pan,
                "track_effects": effect_keys,
            }
        )

    return {
        "kind": spec.kind,
        "label": spec.label,
        "bpm": spec.bpm,
        "time_signature": list(spec.time_signature),
        "start_beat": max(0.0, float(start_beat)),
        "duration_beats": spec.duration_beats,
        "track_count": len(spec.tracks),
        "note_count": note_count,
        "drum_event_count": drum_event_count,
        "style_params": dict(spec.style_params),
        "structure": [
            {
                "name": section.name,
                "start_beat": section.start_beat,
                "duration_beats": section.duration_beats,
            }
            for section in spec.structure
        ],
        "tracks": tracks,
    }


def _parse_track(data: Any) -> MusicTrackSpec:
    if not isinstance(data, dict):
        raise ValueError("Each music track must be an object")
    track_type = _parse_track_type(data.get("track_type", data.get("type", "note")))
    notes_payload = data.get("notes", [])
    drums_payload = data.get("drum_events", data.get("drums", []))
    if notes_payload is None:
        notes_payload = []
    if drums_payload is None:
        drums_payload = []
    if not isinstance(notes_payload, list):
        raise ValueError("Music track notes must be a list")
    if not isinstance(drums_payload, list):
        raise ValueError("Music drum events must be a list")
    if len(notes_payload) > 512:
        raise ValueError("Each music track supports at most 512 notes")
    if len(drums_payload) > 512:
        raise ValueError("Each music track supports at most 512 drum events")

    name = str(data.get("name", "Music Track")).strip() or "Music Track"
    role = None if track_type == TrackType.DRUM_TRACK else _parse_track_role(data.get("role"))
    return MusicTrackSpec(
        name=name,
        track_type=track_type,
        role=role,
        volume=_clamp_float(data.get("volume", 1.0), 0.0, 2.0),
        pan=_clamp_float(data.get("pan", 0.0), -1.0, 1.0),
        notes=tuple(_parse_note(note) for note in notes_payload),
        drum_events=tuple(_parse_drum_event(event) for event in drums_payload),
        filter_params=_parse_filter_params(data.get("filter_params")),
        delay_params=_parse_delay_params(data.get("delay_params")),
        tremolo_params=_parse_tremolo_params(data.get("tremolo_params")),
        vibrato_params=_parse_vibrato_params(data.get("vibrato_params")),
    )


def _parse_note(data: Any) -> MusicNoteSpec:
    if not isinstance(data, dict):
        raise ValueError("Each music note must be an object")
    return MusicNoteSpec(
        pitch=_clamp_int(data.get("pitch", 72), 0, 127),
        start_beat=_clamp_float(data.get("start_beat", 0.0), 0.0, 1024.0),
        duration_beats=_clamp_float(data.get("duration_beats", 1.0), 0.01, 64.0),
        velocity=_clamp_int(data.get("velocity", 110), 0, 127),
        waveform=_parse_waveform(data.get("waveform")),
        duty_cycle=_clamp_float(data.get("duty_cycle", 0.5), 0.05, 0.95),
        adsr=_parse_adsr(data.get("adsr")),
        vibrato=_parse_vibrato_params(data.get("vibrato") or data.get("vibrato_params")),
    )


def _parse_drum_event(data: Any) -> MusicDrumEventSpec:
    if not isinstance(data, dict):
        raise ValueError("Each drum event must be an object")
    return MusicDrumEventSpec(
        drum_type=_parse_drum_type(data.get("drum_type", "kick")),
        start_beat=_clamp_float(data.get("start_beat", 0.0), 0.0, 1024.0),
        duration_beats=_clamp_float(data.get("duration_beats", 0.25), 0.01, 16.0),
        velocity=_clamp_int(data.get("velocity", 110), 0, 127),
    )


def _parse_structure(data: Any) -> tuple[MusicSectionSpec, ...]:
    if data is None:
        return ()
    if not isinstance(data, list):
        raise ValueError("Music structure must be a list")
    if len(data) > 64:
        raise ValueError("Music structure supports at most 64 sections")
    sections = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each music structure section must be an object")
        sections.append(
            MusicSectionSpec(
                name=str(item.get("name", "section")).strip() or "section",
                start_beat=_clamp_float(item.get("start_beat", 0.0), 0.0, 1024.0),
                duration_beats=_clamp_float(item.get("duration_beats", 4.0), 0.01, 256.0),
            )
        )
    return tuple(sections)


def _parse_style_params(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()}


def _parse_bpm(value: Any) -> float:
    return _clamp_float(value, 30.0, 260.0)


def _parse_time_signature(value: Any) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return (4, 4)
    numerator = _clamp_int(value[0], 1, 32)
    denominator = _clamp_int(value[1], 1, 32)
    return numerator, denominator


def _parse_track_type(value: Any) -> TrackType:
    try:
        return TrackType(str(value or TrackType.NOTE_TRACK.value).strip().lower())
    except ValueError:
        return TrackType.NOTE_TRACK


def _parse_track_role(value: Any) -> TrackRole | None:
    if value is None:
        return TrackRole.MELODY
    normalized = str(value).strip().lower()
    if not normalized:
        return TrackRole.MELODY
    try:
        return TrackRole(normalized)
    except ValueError:
        return TrackRole.MELODY


def _parse_waveform(value: Any) -> WaveformType:
    try:
        return WaveformType(str(value or WaveformType.SQUARE.value).strip().lower())
    except ValueError:
        return WaveformType.SQUARE


def _parse_drum_type(value: Any) -> DrumType:
    try:
        return DrumType(str(value or DrumType.KICK.value).strip().lower())
    except ValueError:
        return DrumType.KICK


def _parse_adsr(value: Any) -> ADSRParams:
    if not isinstance(value, dict):
        return ADSRParams(attack=0.003, decay=0.08, sustain=0.65, release=0.12)
    return ADSRParams(
        attack=_clamp_float(value.get("attack", 0.003), 0.0, 10.0),
        decay=_clamp_float(value.get("decay", 0.08), 0.0, 10.0),
        sustain=_clamp_float(value.get("sustain", 0.65), 0.0, 1.0),
        release=_clamp_float(value.get("release", 0.12), 0.0, 10.0),
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


def _parse_vibrato_params(value: Any) -> VibratoParams | None:
    if not isinstance(value, dict):
        return None
    params = VibratoParams.from_dict(value)
    params.rate = max(0.0, min(40.0, params.rate))
    params.depth = max(0.0, min(24.0, params.depth))
    return params


def _track_to_dict(track: MusicTrackSpec) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": track.name,
        "track_type": track.track_type.value,
        "role": track.role.value if track.role else None,
        "volume": track.volume,
        "pan": track.pan,
        "notes": [_note_to_dict(note) for note in track.notes],
        "drum_events": [_drum_event_to_dict(event) for event in track.drum_events],
    }
    _add_effect_dicts(track, result)
    return result


def _note_to_dict(note: MusicNoteSpec) -> dict[str, Any]:
    return {
        "pitch": note.pitch,
        "start_beat": note.start_beat,
        "duration_beats": note.duration_beats,
        "velocity": note.velocity,
        "waveform": note.waveform.value,
        "duty_cycle": note.duty_cycle,
        "adsr": note.adsr.to_dict(),
        "vibrato": note.vibrato.to_dict() if note.vibrato else None,
    }


def _drum_event_to_dict(event: MusicDrumEventSpec) -> dict[str, Any]:
    return {
        "drum_type": event.drum_type.value,
        "start_beat": event.start_beat,
        "duration_beats": event.duration_beats,
        "velocity": event.velocity,
    }


def _add_effect_dicts(track: MusicTrackSpec, result: dict[str, Any]) -> None:
    if track.filter_params is not None:
        result["filter_params"] = track.filter_params.to_dict()
    if track.delay_params is not None:
        result["delay_params"] = track.delay_params.to_dict()
    if track.tremolo_params is not None:
        result["tremolo_params"] = track.tremolo_params.to_dict()
    if track.vibrato_params is not None:
        result["vibrato_params"] = track.vibrato_params.to_dict()


def _track_duration(track: MusicTrackSpec) -> float:
    note_end = max((note.start_beat + note.duration_beats for note in track.notes), default=0.0)
    drum_end = max(
        (event.start_beat + event.duration_beats for event in track.drum_events),
        default=0.0,
    )
    return max(note_end, drum_end)


def _normalize_style(style: str) -> str:
    lowered = str(style or "epic").strip().lower()
    if lowered in {"epic", "cinematic", "orchestral", "heroic"} or any(
        keyword in lowered for keyword in ("史诗", "恢宏")
    ):
        return "epic"
    if lowered in {"playful", "funny", "comic", "humorous", "light"} or any(
        keyword in lowered for keyword in ("轻松", "幽默", "诙谐", "活泼")
    ):
        return "playful"
    return lowered


def _normalize_phrase_bars(length_bars: int) -> int:
    bars = max(SUPPORTED_PHRASE_BARS, min(MAX_GENERATED_BARS, int(length_bars)))
    remainder = bars % SUPPORTED_PHRASE_BARS
    if remainder:
        bars += SUPPORTED_PHRASE_BARS - remainder
    return min(MAX_GENERATED_BARS, bars)


def _parse_key_root(key: str) -> int:
    roots = {
        "c": 60,
        "c#": 61,
        "db": 61,
        "d": 62,
        "d#": 63,
        "eb": 63,
        "e": 64,
        "f": 65,
        "f#": 66,
        "gb": 66,
        "g": 67,
        "g#": 68,
        "ab": 68,
        "a": 69,
        "a#": 70,
        "bb": 70,
        "b": 71,
    }
    return roots.get(str(key or "C").strip().lower(), 60)


def _build_structure(length_bars: int) -> tuple[MusicSectionSpec, ...]:
    if length_bars <= 4:
        return (MusicSectionSpec("theme", 0.0, length_bars * 4.0),)
    if length_bars <= 8:
        return (
            MusicSectionSpec("intro", 0.0, 8.0),
            MusicSectionSpec("theme", 8.0, length_bars * 4.0 - 8.0),
        )
    return (
        MusicSectionSpec("intro", 0.0, 8.0),
        MusicSectionSpec("theme_a", 8.0, 16.0),
        MusicSectionSpec("theme_b", 24.0, max(0.0, length_bars * 4.0 - 24.0)),
    )


def _major_chord_for_bar(root: int, bar: int, octave: int = 0) -> tuple[int, int, int]:
    progression = (0, 5, 7, 0)
    chord_root = root + progression[bar % len(progression)] + octave
    return chord_root, chord_root + 4, chord_root + 7


def _minor_chord_for_bar(root: int, bar: int, octave: int = 0) -> tuple[int, int, int]:
    progression = (0, -3, -5, -7)
    chord_root = root + progression[bar % len(progression)] + octave
    return chord_root, chord_root + 3, chord_root + 7


def _clamp_pitch(pitch: int, minimum: int = 0, maximum: int = 127) -> int:
    return max(minimum, min(maximum, pitch))


def _build_epic_melody_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _minor_chord_for_bar(root, bar, octave=12)
        bar_start = bar * BEATS_PER_BAR
        motif = (
            (chord[0], chord[1], chord[2], chord[1], chord[2]),
            (chord[2], chord[1], chord[0], chord[1], chord[2]),
        )[bar % 2]
        starts = (0.0, 1.0, 2.0, 3.0, 3.5)
        durations = (0.75, 0.75, 0.75, 0.45, 0.45)
        for step, (beat, duration) in enumerate(zip(starts, durations)):
            octave_lift = 12 if bar >= bars * 0.75 and step in {0, 2} else 0
            notes.append(
                MusicNoteSpec(
                    pitch=_clamp_pitch(motif[step] + octave_lift),
                    start_beat=bar_start + beat,
                    duration_beats=duration,
                    velocity=int(92 + intensity * 30),
                    waveform=WaveformType.SQUARE,
                    duty_cycle=0.25,
                    adsr=ADSRParams(0.002, 0.06, 0.55, 0.10),
                    vibrato=VibratoParams(rate=7.5, depth=0.35, enabled=True)
                    if step % 4 == 2
                    else None,
                )
            )
    return MusicTrackSpec(
        name="AI Epic Melody",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.MELODY,
        volume=0.95,
        pan=0.05,
        notes=tuple(notes),
        delay_params=DelayParams(delay_time=0.11, feedback=0.24, mix=0.18, enabled=True),
    )


def _build_epic_bass_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _minor_chord_for_bar(root, bar, octave=-24)
        for beat in (0.0, 2.0):
            notes.append(
                MusicNoteSpec(
                    pitch=_clamp_pitch(chord[0], 24, 72),
                    start_beat=bar * BEATS_PER_BAR + beat,
                    duration_beats=1.5,
                    velocity=int(86 + intensity * 28),
                    waveform=WaveformType.TRIANGLE,
                    duty_cycle=0.5,
                    adsr=ADSRParams(0.003, 0.08, 0.75, 0.08),
                )
            )
    return MusicTrackSpec(
        name="AI Epic Bass",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.BASS,
        volume=0.88,
        pan=-0.08,
        notes=tuple(notes),
        filter_params=FilterParams(FilterType.LOWPASS, 1800.0, 1.0, True),
    )


def _build_epic_harmony_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _minor_chord_for_bar(root, bar, octave=-12)
        duration = 4.0 if bar % 4 != 3 else 3.5
        for pitch in chord:
            notes.append(
                MusicNoteSpec(
                    pitch=_clamp_pitch(pitch, 36, 96),
                    start_beat=bar * BEATS_PER_BAR,
                    duration_beats=duration,
                    velocity=int(62 + intensity * 24),
                    waveform=WaveformType.SAWTOOTH,
                    duty_cycle=0.45,
                    adsr=ADSRParams(0.015, 0.18, 0.68, 0.35),
                )
            )
    return MusicTrackSpec(
        name="AI Epic Harmony",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.HARMONY,
        volume=0.68,
        pan=0.12,
        notes=tuple(notes),
        tremolo_params=TremoloParams(rate=5.5, depth=0.12, enabled=True),
    )


def _build_epic_drum_track(bars: int, intensity: float) -> MusicTrackSpec:
    events = []
    for bar in range(bars):
        bar_start = bar * BEATS_PER_BAR
        events.append(MusicDrumEventSpec(DrumType.KICK, bar_start, 0.25, int(108 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.KICK, bar_start + 2.0, 0.25, int(100 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.SNARE, bar_start + 1.0, 0.25, int(96 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.SNARE, bar_start + 3.0, 0.25, int(102 + intensity * 18)))
        for beat in (0.5, 1.5, 2.5, 3.5):
            events.append(MusicDrumEventSpec(DrumType.HIHAT, bar_start + beat, 0.12, int(54 + intensity * 18)))
        if bar % 4 == 0:
            events.append(MusicDrumEventSpec(DrumType.CRASH, bar_start, 0.75, int(94 + intensity * 22)))
    return MusicTrackSpec(
        name="AI Epic Drums",
        track_type=TrackType.DRUM_TRACK,
        role=None,
        volume=1.0,
        drum_events=tuple(events),
    )


def _build_playful_melody_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _major_chord_for_bar(root, bar, octave=12)
        bar_start = bar * BEATS_PER_BAR
        motif = (
            (chord[0], chord[2], chord[1], chord[2], chord[0] + 12, chord[2]),
            (chord[2], chord[1], chord[0], chord[1], chord[2], chord[0] + 12),
        )[bar % 2]
        starts = (0.0, 0.75, 1.5, 2.0, 2.75, 3.5)
        durations = (0.5, 0.35, 0.35, 0.5, 0.35, 0.35)
        for step, (beat, duration) in enumerate(zip(starts, durations)):
            notes.append(
                MusicNoteSpec(
                    pitch=_clamp_pitch(motif[step]),
                    start_beat=bar_start + beat,
                    duration_beats=duration,
                    velocity=int(84 + intensity * 26),
                    waveform=WaveformType.SQUARE,
                    duty_cycle=0.20,
                    adsr=ADSRParams(0.002, 0.045, 0.45, 0.06),
                    vibrato=VibratoParams(rate=6.5, depth=0.18, enabled=True)
                    if step == 4
                    else None,
                )
            )
    return MusicTrackSpec(
        name="AI Playful Melody",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.MELODY,
        volume=0.86,
        pan=0.08,
        notes=tuple(notes),
        delay_params=DelayParams(delay_time=0.08, feedback=0.14, mix=0.11, enabled=True),
    )


def _build_playful_bass_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _major_chord_for_bar(root, bar, octave=-24)
        bar_start = bar * BEATS_PER_BAR
        for beat, pitch in ((0.0, chord[0]), (2.0, chord[2])):
            notes.append(
                MusicNoteSpec(
                    pitch=_clamp_pitch(pitch, 24, 72),
                    start_beat=bar_start + beat,
                    duration_beats=0.9,
                    velocity=int(74 + intensity * 20),
                    waveform=WaveformType.TRIANGLE,
                    duty_cycle=0.5,
                    adsr=ADSRParams(0.002, 0.06, 0.58, 0.07),
                )
            )
    return MusicTrackSpec(
        name="AI Playful Bass",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.BASS,
        volume=0.72,
        pan=-0.08,
        notes=tuple(notes),
        filter_params=FilterParams(FilterType.LOWPASS, 2200.0, 0.9, True),
    )


def _build_playful_harmony_track(root: int, bars: int, intensity: float) -> MusicTrackSpec:
    notes = []
    for bar in range(bars):
        chord = _major_chord_for_bar(root, bar, octave=-12)
        bar_start = bar * BEATS_PER_BAR
        for beat in (0.0, 2.0):
            for pitch in chord[:2]:
                notes.append(
                    MusicNoteSpec(
                        pitch=_clamp_pitch(pitch, 36, 96),
                        start_beat=bar_start + beat,
                        duration_beats=1.5,
                        velocity=int(48 + intensity * 20),
                        waveform=WaveformType.SAWTOOTH,
                        duty_cycle=0.35,
                        adsr=ADSRParams(0.006, 0.10, 0.46, 0.16),
                    )
                )
    return MusicTrackSpec(
        name="AI Playful Harmony",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.HARMONY,
        volume=0.46,
        pan=0.14,
        notes=tuple(notes),
        tremolo_params=TremoloParams(rate=4.0, depth=0.10, enabled=True),
    )


def _build_playful_drum_track(bars: int, intensity: float) -> MusicTrackSpec:
    events = []
    for bar in range(bars):
        bar_start = bar * BEATS_PER_BAR
        events.append(MusicDrumEventSpec(DrumType.KICK, bar_start, 0.18, int(84 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.KICK, bar_start + 2.0, 0.18, int(70 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.SNARE, bar_start + 1.0, 0.16, int(72 + intensity * 18)))
        events.append(MusicDrumEventSpec(DrumType.SNARE, bar_start + 3.0, 0.16, int(78 + intensity * 18)))
        for beat in (0.5, 1.5, 2.5, 3.5):
            events.append(MusicDrumEventSpec(DrumType.HIHAT, bar_start + beat, 0.08, int(42 + intensity * 14)))
        if bar % 4 == 3:
            events.append(MusicDrumEventSpec(DrumType.SNARE, bar_start + 3.5, 0.14, int(66 + intensity * 16)))
    return MusicTrackSpec(
        name="AI Playful Drums",
        track_type=TrackType.DRUM_TRACK,
        role=None,
        volume=0.76,
        drum_events=tuple(events),
    )


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


__all__ = [
    "MusicDrumEventSpec",
    "MusicNoteSpec",
    "MusicSectionSpec",
    "MusicSpec",
    "MusicTrackSpec",
    "SetProjectTempoCommand",
    "build_insert_music_command",
    "generate_music_spec",
    "music_note_to_note",
    "music_spec_from_dict",
    "music_spec_to_dict",
    "music_track_to_track",
    "summarize_music_spec",
]
