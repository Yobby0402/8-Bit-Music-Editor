from core.models import Note, Project, Track, TrackRole, TrackType
from core.track_events import DrumEvent, DrumType
from ui.property_panel_widget import (
    can_change_track_type_on_existing_track,
    get_track_role_editor_index,
    get_track_type_editor_index,
    resolve_track_role_from_editor_index,
    resolve_track_type_from_editor_index,
    resolve_note_timing_for_duration_beats,
    resolve_note_timing_for_end_time,
    resolve_note_timing_for_start_time,
    shift_contiguous_following_notes_by_ticks,
    snap_tick_to_grid,
)


def test_snap_tick_to_grid_rounds_to_nearest_grid():
    assert snap_tick_to_grid(970, 240) == 960
    assert snap_tick_to_grid(1080, 240) == 960
    assert snap_tick_to_grid(1090, 240) == 1200


def test_resolve_note_timing_for_start_time_keeps_note_end_fixed():
    project = Project(name="Start Edit", bpm=120.0, original_bpm=120.0)
    note = Note(pitch=60, start_time=0.5, duration=0.5)
    note.sync_tick_timing(project, prefer_existing=False)

    new_start_tick, new_duration_ticks = resolve_note_timing_for_start_time(
        note,
        project,
        0.25,
        snap_to_beat=True,
    )

    assert new_start_tick == 480
    assert new_duration_ticks == 1440


def test_resolve_note_timing_for_end_time_keeps_note_start_fixed():
    project = Project(name="End Edit", bpm=120.0, original_bpm=120.0)
    note = Note(pitch=60, start_time=0.5, duration=0.5)
    note.sync_tick_timing(project, prefer_existing=False)

    start_tick, duration_ticks = resolve_note_timing_for_end_time(
        note,
        project,
        1.25,
        snap_to_beat=True,
    )

    assert start_tick == 960
    assert duration_ticks == 1440


def test_resolve_note_timing_for_duration_beats_uses_project_resolution():
    project = Project(name="Duration Edit", bpm=120.0, original_bpm=120.0)
    note = Note(pitch=60, start_time=0.5, duration=0.5)
    note.sync_tick_timing(project, prefer_existing=False)

    start_tick, duration_ticks = resolve_note_timing_for_duration_beats(
        note,
        project,
        1.5,
        snap_to_beat=True,
    )

    assert start_tick == 960
    assert duration_ticks == 1440


def test_shift_contiguous_following_notes_by_ticks_preserves_original_chain():
    project = Project(name="Chain Shift", bpm=120.0, original_bpm=120.0)
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    current = Note(pitch=60, start_time=0.0, duration=0.5)
    next_note = Note(pitch=62, start_time=0.5, duration=0.5)
    third_note = Note(pitch=64, start_time=1.0, duration=0.5)
    gap_note = Note(pitch=65, start_time=2.0, duration=0.5)
    for note in (current, next_note, third_note, gap_note):
        note.sync_tick_timing(project, prefer_existing=False)
        lead.add_note(note)

    current.apply_tick_timing(project, current.get_start_tick(project), project.beats_to_ticks(1.0))
    adjusted = shift_contiguous_following_notes_by_ticks(
        current,
        [next_note, third_note, gap_note],
        project,
        old_end_tick=project.beats_to_ticks(1.0),
        new_end_tick=project.beats_to_ticks(2.0),
    )

    assert adjusted == [next_note, third_note]
    assert next_note.start_tick == project.beats_to_ticks(2.0)
    assert third_note.start_tick == project.beats_to_ticks(3.0)
    assert gap_note.start_tick == project.beats_to_ticks(4.0)


def test_track_type_editor_index_matches_canonical_track_type():
    note_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    drum_track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)

    assert get_track_type_editor_index(note_track) == 0
    assert get_track_type_editor_index(drum_track) == 1
    assert resolve_track_type_from_editor_index(0) == TrackType.NOTE_TRACK
    assert resolve_track_type_from_editor_index(1) == TrackType.DRUM_TRACK


def test_track_role_editor_index_matches_canonical_track_role():
    melody_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    bass_track = Track(name="Bass", track_type=TrackType.NOTE_TRACK, role=TrackRole.BASS)
    harmony_track = Track(name="Pad", track_type=TrackType.NOTE_TRACK, role=TrackRole.HARMONY)
    effect_track = Track(name="FX", track_type=TrackType.NOTE_TRACK, role=TrackRole.EFFECT)

    assert get_track_role_editor_index(melody_track) == 0
    assert get_track_role_editor_index(bass_track) == 1
    assert get_track_role_editor_index(harmony_track) == 2
    assert get_track_role_editor_index(effect_track) == 3
    assert resolve_track_role_from_editor_index(0) == TrackRole.MELODY
    assert resolve_track_role_from_editor_index(1) == TrackRole.BASS
    assert resolve_track_role_from_editor_index(2) == TrackRole.HARMONY
    assert resolve_track_role_from_editor_index(3) == TrackRole.EFFECT


def test_non_empty_note_track_cannot_switch_to_drum_track():
    track = Track(
        name="Lead",
        track_type=TrackType.NOTE_TRACK,
        notes=[Note(pitch=60, start_time=0.0, duration=0.5)],
    )

    assert can_change_track_type_on_existing_track(track, TrackType.DRUM_TRACK) is False


def test_non_empty_drum_track_cannot_switch_to_note_track():
    track = Track(
        name="Drums",
        track_type=TrackType.DRUM_TRACK,
        drum_events=[DrumEvent(drum_type=DrumType.KICK, start_beat=0.0, duration_beats=1.0)],
    )

    assert can_change_track_type_on_existing_track(track, TrackType.NOTE_TRACK) is False


def test_empty_track_can_switch_between_track_types():
    track = Track(name="Empty", track_type=TrackType.NOTE_TRACK)

    assert can_change_track_type_on_existing_track(track, TrackType.DRUM_TRACK) is True
