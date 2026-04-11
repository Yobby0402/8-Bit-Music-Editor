"""Standard musical time helpers based on ticks and tempo events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

DEFAULT_PPQN = 960
TempoRegion = tuple[int, int | None, float, float]


@dataclass(frozen=True, order=True)
class TempoEvent:
    """A tempo change anchored on the musical timeline."""

    tick: int
    bpm: float

    def to_dict(self) -> dict[str, float | int]:
        return {"tick": int(self.tick), "bpm": float(self.bpm)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TempoEvent":
        return cls(
            tick=int(data.get("tick", 0)),
            bpm=float(data.get("bpm", 120.0)),
        )


def normalize_resolution(resolution: int) -> int:
    """Return a safe PPQN resolution."""
    return int(resolution) if int(resolution) > 0 else DEFAULT_PPQN


def beats_to_ticks(beats: float, resolution: int = DEFAULT_PPQN) -> int:
    """Convert beats to integer ticks."""
    safe_resolution = normalize_resolution(resolution)
    return max(0, int(round(float(beats) * safe_resolution)))


def ticks_to_beats(ticks: int, resolution: int = DEFAULT_PPQN) -> float:
    """Convert ticks to beats."""
    safe_resolution = normalize_resolution(resolution)
    if ticks <= 0:
        return 0.0
    return float(ticks) / safe_resolution


def ticks_to_seconds(
    ticks: int,
    tempo_events: Iterable[Any] | None,
    resolution: int = DEFAULT_PPQN,
    fallback_bpm: float = 120.0,
) -> float:
    """Convert ticks to seconds using tempo events."""
    if ticks <= 0:
        return 0.0

    safe_resolution = normalize_resolution(resolution)
    regions = build_tempo_regions(tempo_events, safe_resolution, fallback_bpm)
    return ticks_to_seconds_with_regions(ticks, regions, safe_resolution)


def seconds_to_ticks(
    seconds: float,
    tempo_events: Iterable[Any] | None,
    resolution: int = DEFAULT_PPQN,
    fallback_bpm: float = 120.0,
) -> int:
    """Convert seconds to integer ticks using tempo events."""
    if seconds <= 0:
        return 0

    safe_resolution = normalize_resolution(resolution)
    regions = build_tempo_regions(tempo_events, safe_resolution, fallback_bpm)
    return seconds_to_ticks_with_regions(seconds, regions, safe_resolution)


def build_tempo_regions(
    tempo_events: Iterable[Any] | None,
    resolution: int = DEFAULT_PPQN,
    fallback_bpm: float = 120.0,
) -> list[TempoRegion]:
    """Build reusable tempo regions for repeated tick/second conversions."""
    safe_resolution = normalize_resolution(resolution)
    return _build_tempo_regions(tempo_events, safe_resolution, fallback_bpm)


def ticks_to_seconds_with_regions(
    ticks: int,
    regions: list[TempoRegion],
    resolution: int = DEFAULT_PPQN,
) -> float:
    """Convert ticks to seconds using prebuilt tempo regions."""
    if ticks <= 0:
        return 0.0

    safe_resolution = normalize_resolution(resolution)
    target_ticks = int(ticks)

    for index, (start_tick, end_tick, start_seconds, bpm_value) in enumerate(regions):
        if end_tick is None:
            return start_seconds + _ticks_delta_to_seconds(
                target_ticks - start_tick,
                bpm_value,
                safe_resolution,
            )

        is_last_region = index == len(regions) - 1
        if target_ticks <= end_tick or is_last_region:
            delta_ticks = max(0, target_ticks - start_tick)
            return start_seconds + _ticks_delta_to_seconds(
                delta_ticks,
                bpm_value,
                safe_resolution,
            )

    last_start_tick, _, last_start_seconds, last_bpm = regions[-1]
    return last_start_seconds + _ticks_delta_to_seconds(
        max(0, target_ticks - last_start_tick),
        last_bpm,
        safe_resolution,
    )


def seconds_to_ticks_with_regions(
    seconds: float,
    regions: list[TempoRegion],
    resolution: int = DEFAULT_PPQN,
) -> int:
    """Convert seconds to ticks using prebuilt tempo regions."""
    if seconds <= 0:
        return 0

    safe_resolution = normalize_resolution(resolution)
    target_seconds = float(seconds)

    for start_tick, end_tick, start_seconds, bpm_value in regions:
        if target_seconds <= start_seconds:
            return max(0, start_tick)

        if end_tick is None:
            delta_seconds = target_seconds - start_seconds
            delta_ticks = _seconds_delta_to_ticks(delta_seconds, bpm_value, safe_resolution)
            return max(0, start_tick + delta_ticks)

        end_seconds = start_seconds + _ticks_delta_to_seconds(
            end_tick - start_tick,
            bpm_value,
            safe_resolution,
        )
        if target_seconds < end_seconds:
            delta_seconds = target_seconds - start_seconds
            delta_ticks = _seconds_delta_to_ticks(delta_seconds, bpm_value, safe_resolution)
            return max(0, start_tick + delta_ticks)

    last_start_tick, _, last_start_seconds, last_bpm = regions[-1]
    delta_seconds = target_seconds - last_start_seconds
    delta_ticks = _seconds_delta_to_ticks(delta_seconds, last_bpm, safe_resolution)
    return max(0, last_start_tick + delta_ticks)


def tempo_events_from_bpm_segments(
    bpm_segments: Iterable[Any] | None,
    resolution: int = DEFAULT_PPQN,
    fallback_bpm: float = 120.0,
) -> list[TempoEvent]:
    """Convert legacy second-based BPM segments into standard tempo events."""
    safe_resolution = normalize_resolution(resolution)
    safe_bpm = fallback_bpm if fallback_bpm > 0 else 120.0
    source_segments = sorted(
        list(bpm_segments or []),
        key=lambda segment: float(getattr(segment, "start_time", 0.0)),
    )

    if not source_segments:
        return [TempoEvent(0, safe_bpm)]

    tempo_events: list[TempoEvent] = []
    for segment in source_segments:
        start_seconds = max(0.0, float(getattr(segment, "start_time", 0.0)))
        bpm_value = float(getattr(segment, "bpm", safe_bpm) or safe_bpm)
        if bpm_value <= 0:
            bpm_value = safe_bpm
        tick = seconds_to_ticks(start_seconds, tempo_events, safe_resolution, safe_bpm)
        event = TempoEvent(tick=tick, bpm=bpm_value)
        if tempo_events and event.tick == tempo_events[-1].tick:
            tempo_events[-1] = event
        else:
            tempo_events.append(event)

    if not tempo_events or tempo_events[0].tick != 0:
        first_bpm = tempo_events[0].bpm if tempo_events else safe_bpm
        tempo_events.insert(0, TempoEvent(0, first_bpm))

    return tempo_events


def tempo_event_rows_to_segments(
    tempo_events: Iterable[Any] | None,
    resolution: int = DEFAULT_PPQN,
    fallback_bpm: float = 120.0,
) -> list[tuple[float, float, float | None]]:
    """Return second-based segment rows derived from tempo events."""
    safe_resolution = normalize_resolution(resolution)
    normalized_events = _normalize_tempo_events(tempo_events, fallback_bpm)

    rows: list[tuple[float, float, float | None]] = []
    for index, event in enumerate(normalized_events):
        start_seconds = ticks_to_seconds(event.tick, normalized_events, safe_resolution, fallback_bpm)
        if index + 1 < len(normalized_events):
            end_seconds = ticks_to_seconds(
                normalized_events[index + 1].tick,
                normalized_events,
                safe_resolution,
                fallback_bpm,
            )
        else:
            end_seconds = None
        rows.append((start_seconds, event.bpm, end_seconds))
    return rows


def _normalize_tempo_events(
    tempo_events: Iterable[Any] | None,
    fallback_bpm: float,
) -> list[TempoEvent]:
    safe_bpm = fallback_bpm if fallback_bpm > 0 else 120.0
    source_events = sorted(
        [
            TempoEvent(
                tick=max(0, int(getattr(event, "tick", 0))),
                bpm=float(getattr(event, "bpm", safe_bpm) or safe_bpm),
            )
            for event in list(tempo_events or [])
        ],
        key=lambda event: event.tick,
    )

    if not source_events:
        return [TempoEvent(0, safe_bpm)]

    normalized: list[TempoEvent] = []
    for event in source_events:
        bpm_value = event.bpm if event.bpm > 0 else safe_bpm
        normalized_event = TempoEvent(event.tick, bpm_value)
        if normalized and normalized[-1].tick == normalized_event.tick:
            normalized[-1] = normalized_event
        else:
            normalized.append(normalized_event)

    if normalized[0].tick != 0:
        normalized.insert(0, TempoEvent(0, normalized[0].bpm))

    return normalized


def _build_tempo_regions(
    tempo_events: Iterable[Any] | None,
    resolution: int,
    fallback_bpm: float,
) -> list[tuple[int, int | None, float, float]]:
    normalized_events = _normalize_tempo_events(tempo_events, fallback_bpm)
    regions: list[tuple[int, int | None, float, float]] = []
    current_seconds = 0.0

    for index, event in enumerate(normalized_events):
        if index + 1 < len(normalized_events):
            end_tick: int | None = normalized_events[index + 1].tick
        else:
            end_tick = None
        regions.append((event.tick, end_tick, current_seconds, event.bpm))
        if end_tick is not None:
            current_seconds += _ticks_delta_to_seconds(
                end_tick - event.tick,
                event.bpm,
                resolution,
            )

    return regions


def _ticks_delta_to_seconds(ticks: int, bpm: float, resolution: int) -> float:
    if ticks <= 0:
        return 0.0
    safe_bpm = bpm if bpm > 0 else 120.0
    return float(ticks) * 60.0 / (safe_bpm * resolution)


def _seconds_delta_to_ticks(seconds: float, bpm: float, resolution: int) -> int:
    if seconds <= 0:
        return 0
    safe_bpm = bpm if bpm > 0 else 120.0
    return int(round(float(seconds) * safe_bpm * resolution / 60.0))
