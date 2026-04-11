from types import SimpleNamespace

from core.musical_time import (
    TempoEvent,
    beats_to_ticks,
    build_tempo_regions,
    seconds_to_ticks,
    seconds_to_ticks_with_regions,
    tempo_event_rows_to_segments,
    tempo_events_from_bpm_segments,
    ticks_to_beats,
    ticks_to_seconds,
    ticks_to_seconds_with_regions,
)


def test_tick_time_round_trip_across_tempo_changes():
    tempo_events = [
        TempoEvent(tick=0, bpm=120.0),
        TempoEvent(tick=1920, bpm=60.0),
    ]

    assert ticks_to_seconds(2400, tempo_events, 960, 120.0) == 1.5
    assert seconds_to_ticks(1.5, tempo_events, 960, 120.0) == 2400


def test_tick_beat_helpers_use_project_resolution():
    assert beats_to_ticks(2.5, 960) == 2400
    assert ticks_to_beats(2400, 960) == 2.5


def test_legacy_second_segments_can_be_converted_to_tempo_events():
    bpm_segments = [
        SimpleNamespace(start_time=0.0, bpm=120.0),
        SimpleNamespace(start_time=1.0, bpm=60.0),
    ]

    tempo_events = tempo_events_from_bpm_segments(bpm_segments, 960, 120.0)

    assert tempo_events == [
        TempoEvent(tick=0, bpm=120.0),
        TempoEvent(tick=1920, bpm=60.0),
    ]


def test_tempo_events_can_be_projected_back_to_second_segments():
    rows = tempo_event_rows_to_segments(
        [TempoEvent(tick=0, bpm=120.0), TempoEvent(tick=1920, bpm=60.0)],
        960,
        120.0,
    )

    assert rows == [
        (0.0, 120.0, 1.0),
        (1.0, 60.0, None),
    ]


def test_prebuilt_tempo_regions_match_direct_tick_second_helpers():
    tempo_events = [
        TempoEvent(tick=0, bpm=120.0),
        TempoEvent(tick=1920, bpm=60.0),
    ]

    regions = build_tempo_regions(tempo_events, 960, 120.0)

    assert ticks_to_seconds_with_regions(2400, regions, 960) == ticks_to_seconds(
        2400,
        tempo_events,
        960,
        120.0,
    )
    assert seconds_to_ticks_with_regions(1.5, regions, 960) == seconds_to_ticks(
        1.5,
        tempo_events,
        960,
        120.0,
    )
