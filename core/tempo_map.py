"""Helpers for converting between beats and seconds across tempo maps."""

from __future__ import annotations

from typing import Any, Iterable


def has_variable_tempo(bpm_segments: Iterable[Any] | None) -> bool:
    """Return whether the project uses more than one tempo segment."""
    if not bpm_segments:
        return False
    return len(list(bpm_segments)) > 1


def beats_to_seconds(
    beats: float,
    bpm_segments: Iterable[Any] | None,
    fallback_bpm: float = 120.0,
) -> float:
    """Convert a beat position to seconds using the provided tempo map."""
    if beats <= 0:
        return 0.0

    segments = _normalize_segments(bpm_segments, fallback_bpm)
    remaining_beats = beats

    for index, (start_time, end_time, bpm_value) in enumerate(segments):
        if end_time is None:
            return start_time + remaining_beats * 60.0 / bpm_value

        segment_duration = max(0.0, end_time - start_time)
        segment_beats = segment_duration * bpm_value / 60.0
        is_last_segment = index == len(segments) - 1
        if remaining_beats <= segment_beats or is_last_segment:
            return start_time + remaining_beats * 60.0 / bpm_value

        remaining_beats -= segment_beats

    last_start_time, _, last_bpm = segments[-1]
    return last_start_time + remaining_beats * 60.0 / last_bpm


def seconds_to_beats(
    seconds: float,
    bpm_segments: Iterable[Any] | None,
    fallback_bpm: float = 120.0,
) -> float:
    """Convert a time position to beats using the provided tempo map."""
    if seconds <= 0:
        return 0.0

    segments = _normalize_segments(bpm_segments, fallback_bpm)
    total_beats = 0.0

    for start_time, end_time, bpm_value in segments:
        if seconds <= start_time:
            return total_beats

        if end_time is None or seconds < end_time:
            return total_beats + (seconds - start_time) * bpm_value / 60.0

        segment_duration = max(0.0, end_time - start_time)
        total_beats += segment_duration * bpm_value / 60.0

    return total_beats


def beat_span_to_seconds(
    start_beat: float,
    end_beat: float,
    bpm_segments: Iterable[Any] | None,
    fallback_bpm: float = 120.0,
) -> float:
    """Convert a beat span to seconds using the provided tempo map."""
    if end_beat <= start_beat:
        return 0.0
    return beats_to_seconds(end_beat, bpm_segments, fallback_bpm) - beats_to_seconds(
        start_beat,
        bpm_segments,
        fallback_bpm,
    )


def _normalize_segments(
    bpm_segments: Iterable[Any] | None,
    fallback_bpm: float,
) -> list[tuple[float, float | None, float]]:
    safe_bpm = fallback_bpm if fallback_bpm > 0 else 120.0
    source_segments = sorted(
        list(bpm_segments or []),
        key=lambda segment: getattr(segment, "start_time", 0.0),
    )

    if not source_segments:
        return [(0.0, None, safe_bpm)]

    normalized: list[tuple[float, float | None, float]] = []
    first_start_time = max(0.0, float(getattr(source_segments[0], "start_time", 0.0)))
    if first_start_time > 0.0:
        normalized.append((0.0, first_start_time, safe_bpm))

    for index, segment in enumerate(source_segments):
        start_time = max(0.0, float(getattr(segment, "start_time", 0.0)))
        bpm_value = float(getattr(segment, "bpm", safe_bpm) or safe_bpm)
        if bpm_value <= 0:
            bpm_value = safe_bpm

        if index + 1 < len(source_segments):
            next_start_time = float(getattr(source_segments[index + 1], "start_time", start_time))
            end_time: float | None = max(start_time, next_start_time)
        else:
            end_time = None

        normalized.append((start_time, end_time, bpm_value))

    return normalized
