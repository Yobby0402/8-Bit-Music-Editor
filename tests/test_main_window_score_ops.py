import pytest

from core.models import Note, Track, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType
from ui.main_window_score_ops import (
    build_preview_track,
    build_score_snippet_from_selection,
    resolve_snippet_insert_position,
)


def test_build_score_snippet_from_note_selection_normalizes_offsets():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    first_note = Note(
        pitch=60,
        start_time=1.5,
        duration=0.25,
        velocity=90,
        waveform=WaveformType.TRIANGLE,
        duty_cycle=0.25,
    )
    second_note = Note(
        pitch=64,
        start_time=2.0,
        duration=0.5,
        velocity=80,
        waveform=WaveformType.SQUARE,
        duty_cycle=0.5,
    )

    selected_track, snippet_type, data = build_score_snippet_from_selection(
        [(first_note, track), (second_note, track)]
    )

    assert selected_track is track
    assert snippet_type == "note"
    assert data == {
        "notes": [
            {
                "offset": 0.0,
                "duration": 0.25,
                "pitch": 60,
                "velocity": 90,
                "waveform": "TRIANGLE",
                "duty_cycle": 0.25,
            },
            {
                "offset": 0.5,
                "duration": 0.5,
                "pitch": 64,
                "velocity": 80,
                "waveform": "SQUARE",
                "duty_cycle": 0.5,
            },
        ]
    }


def test_build_score_snippet_from_drum_selection_uses_relative_beats():
    track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    kick = DrumEvent(DrumType.KICK, start_beat=2.0, duration_beats=0.25, velocity=110)
    snare = DrumEvent(DrumType.SNARE, start_beat=2.5, duration_beats=0.25, velocity=100)

    selected_track, snippet_type, data = build_score_snippet_from_selection(
        [(kick, track), (snare, track)]
    )

    assert selected_track is track
    assert snippet_type == "drum"
    assert data == {
        "drums": [
            {
                "offset_beats": 0.0,
                "duration_beats": 0.25,
                "drum_type": "KICK",
                "velocity": 110,
            },
            {
                "offset_beats": 0.5,
                "duration_beats": 0.25,
                "drum_type": "SNARE",
                "velocity": 100,
            },
        ]
    }


def test_build_score_snippet_from_selection_rejects_cross_track_selection():
    first_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    second_track = Track(name="Pad", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)

    with pytest.raises(ValueError, match="cross_track_selection"):
        build_score_snippet_from_selection([(note, first_track), (note, second_track)])


def test_resolve_snippet_insert_position_supports_note_and_drum_modes():
    note_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note_track.add_note(Note(pitch=60, start_time=0.0, duration=0.5))
    note_track.add_note(Note(pitch=62, start_time=1.0, duration=0.25))

    drum_track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    drum_track.add_drum_event(DrumEvent(DrumType.KICK, start_beat=0.0, duration_beats=0.5))
    drum_track.add_drum_event(DrumEvent(DrumType.SNARE, start_beat=1.0, duration_beats=0.25))

    note_base_time, note_base_beat = resolve_snippet_insert_position(
        "note",
        note_track,
        "sequential",
        playhead_time=9.0,
        bpm=120.0,
    )
    drum_base_time, drum_base_beat = resolve_snippet_insert_position(
        "drum",
        drum_track,
        "sequential",
        playhead_time=9.0,
        bpm=120.0,
    )
    playhead_time, playhead_beat = resolve_snippet_insert_position(
        "note",
        note_track,
        "playhead",
        playhead_time=3.5,
        bpm=120.0,
    )

    assert (note_base_time, note_base_beat) == (1.25, 2.5)
    assert (drum_base_time, drum_base_beat) == (0.625, 1.25)
    assert (playhead_time, playhead_beat) == (3.5, 7.0)


def test_build_preview_track_handles_note_and_drum_snippets():
    note_preview = build_preview_track(
        "note",
        {
            "notes": [
                {
                    "offset": 0.25,
                    "duration": 0.5,
                    "pitch": 67,
                    "velocity": 88,
                    "waveform": "TRIANGLE",
                    "duty_cycle": 0.125,
                }
            ]
        },
    )
    drum_preview = build_preview_track(
        "drum",
        {
            "drums": [
                {
                    "offset_beats": 1.0,
                    "duration_beats": 0.25,
                    "drum_type": "SNARE",
                    "velocity": 99,
                }
            ]
        },
    )

    assert note_preview.track_type == TrackType.NOTE_TRACK
    assert note_preview.notes[0].start_time == 0.25
    assert note_preview.notes[0].waveform == WaveformType.TRIANGLE
    assert drum_preview.track_type == TrackType.DRUM_TRACK
    assert drum_preview.drum_events[0].start_beat == 1.0
    assert drum_preview.drum_events[0].drum_type == DrumType.SNARE
