from core.models import BPMSegment
from core.tempo_map import beat_span_to_seconds, beats_to_seconds, seconds_to_beats


def test_tempo_map_converts_between_beats_and_seconds():
    bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]

    assert beats_to_seconds(2.5, bpm_segments, 120.0) == 1.5
    assert seconds_to_beats(1.5, bpm_segments, 120.0) == 2.5


def test_tempo_map_computes_beat_spans_across_tempo_changes():
    bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]

    assert beat_span_to_seconds(1.5, 2.5, bpm_segments, 120.0) == 0.75
