from types import SimpleNamespace

from core.models import Note, Project, Track, TrackRole, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType
from ui.main_window_note_entry_ops import (
    MainWindowNoteEntryOpsMixin,
    compute_drum_insert_beat,
    compute_note_insert_time,
    find_last_note,
    resolve_entry_track,
    resolve_insert_track,
)


def test_resolve_entry_track_prefers_matching_track_and_can_require_items():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
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


def test_resolve_entry_track_prefers_matching_role_when_no_explicit_target():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
    bass.add_note(Note(pitch=48, start_time=0.0, duration=0.5))

    resolved = resolve_entry_track(
        [lead, bass],
        TrackType.NOTE_TRACK,
        preferred_role=TrackRole.BASS,
    )

    assert resolved is bass


def test_resolve_insert_track_prefers_selected_track_then_first_compatible_track():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)

    assert (
        resolve_insert_track(
            [lead, bass, drums],
            TrackType.NOTE_TRACK,
            selected_track=bass,
        )
        is bass
    )
    assert (
        resolve_insert_track(
            [lead, bass, drums],
            TrackType.NOTE_TRACK,
            selected_track=drums,
        )
        is lead
    )
    assert resolve_insert_track([lead, bass, drums], TrackType.DRUM_TRACK) is drums


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


class FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message):
        self.messages.append(message)


class FakeEntrySequencer:
    def __init__(self, tracks):
        self.project = Project(tracks=list(tracks))
        self.playback_state = SimpleNamespace(is_playing=False)

    def get_bpm(self):
        return 120.0

    def add_track(self, name=None, track_type=TrackType.NOTE_TRACK):
        track = Track(name=name or "New Track", track_type=track_type)
        self.project.add_track(track)
        return track

    def add_note(self, track, pitch, start_time, duration):
        note = Note(pitch=pitch, start_time=start_time, duration=duration)
        track.add_note(note)
        return note

    def add_drum_event(self, track, drum_type, start_beat, duration_beats):
        event = DrumEvent(drum_type, start_beat=start_beat, duration_beats=duration_beats)
        track.add_drum_event(event)
        return event


class FakeEntryWindow(MainWindowNoteEntryOpsMixin):
    def __init__(self, tracks):
        self.sequencer = FakeEntrySequencer(tracks)
        self.sequence_widget = SimpleNamespace(
            playhead_time=0.0,
            highlighted_track=None,
            selected_tracks=[],
        )
        self.unified_editor = SimpleNamespace(selected_track=None)
        self.selected_track = None
        self.finalized_pairs = []
        self._status_bar = FakeStatusBar()

    def _finalize_entry_refresh(self, track, item=None):
        self.finalized_pairs.append((track, item))

    def statusBar(self):
        return self._status_bar


def test_add_melody_note_prefers_current_selected_note_track():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    harmony = Track(name="Harmony", track_type=TrackType.NOTE_TRACK, role=TrackRole.HARMONY)
    window = FakeEntryWindow([lead, harmony])
    window.selected_track = harmony

    window.on_add_melody_note(64, 1.0, WaveformType.SQUARE)

    assert window.finalized_pairs[-1][0] is harmony


def test_add_bass_event_without_selection_uses_first_note_track():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
    window = FakeEntryWindow([lead, bass])

    window.on_add_bass_event(48, 1.0, WaveformType.TRIANGLE)

    assert window.finalized_pairs[-1][0] is lead


def test_add_drum_event_defaults_to_first_drum_track_when_note_track_selected():
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    extra_drums = Track(name="Perc", track_type=TrackType.DRUM_TRACK)
    window = FakeEntryWindow([lead, drums, extra_drums])
    window.selected_track = lead

    window.on_add_drum_event(DrumType.KICK, 1.0)

    assert window.finalized_pairs[-1][0] is drums
