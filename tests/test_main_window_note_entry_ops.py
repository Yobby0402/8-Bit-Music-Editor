from core.models import Note, Track, TrackType
from core.track_events import DrumEvent, DrumType
from ui.main_window_note_entry_ops import (
    compute_drum_insert_beat,
    compute_note_insert_time,
    find_last_note,
    resolve_entry_track,
)


def test_resolve_entry_track_prefers_matching_track_and_can_require_items():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)
    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    bass.add_note(Note(pitch=48, start_time=0.0, duration=0.5))

    assert resolve_entry_track([lead, bass, drums], TrackType.NOTE_TRACK, lead) is lead
    assert (
        resolve_entry_track(
            [lead, bass, drums],
            TrackType.NOTE_TRACK,
            lead,
            require_items=True,
        )
        is bass
    )
    assert resolve_entry_track([lead, bass, drums], TrackType.DRUM_TRACK) is drums


def test_compute_note_insert_time_supports_sequential_and_playhead_modes():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    track.add_note(Note(pitch=60, start_time=0.0, duration=0.5))
    track.add_note(Note(pitch=62, start_time=1.0, duration=0.25))

    sequential_time = compute_note_insert_time(track, duration=0.5, insert_mode="sequential", playhead_time=9)
    playhead_time = compute_note_insert_time(track, duration=0.5, insert_mode="playhead", playhead_time=0.25)

    assert sequential_time == 1.25
    assert playhead_time == 0.5


def test_compute_drum_insert_beat_supports_sequential_and_playhead_modes():
    track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    track.add_drum_event(DrumEvent(DrumType.KICK, start_beat=0.0, duration_beats=0.5))
    track.add_drum_event(DrumEvent(DrumType.SNARE, start_beat=1.0, duration_beats=0.25))

    sequential_beat = compute_drum_insert_beat(
        track,
        duration_beats=0.25,
        insert_mode="sequential",
        playhead_time=9.0,
        bpm=120.0,
    )
    playhead_beat = compute_drum_insert_beat(
        track,
        duration_beats=0.5,
        insert_mode="playhead",
        playhead_time=0.25,
        bpm=120.0,
    )

    assert sequential_beat == 1.25
    assert playhead_beat == 0.5


def test_find_last_note_prefers_latest_end_then_latest_start():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    early = Note(pitch=60, start_time=0.0, duration=1.0)
    later_same_end = Note(pitch=64, start_time=0.5, duration=0.5)
    latest = Note(pitch=67, start_time=1.5, duration=0.5)

    track.add_note(early)
    track.add_note(later_same_end)
    track.add_note(latest)

    assert find_last_note(track) is latest
