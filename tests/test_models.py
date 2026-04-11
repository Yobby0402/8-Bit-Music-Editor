import core.models as models_module
from core.models import (
    ADSRParams,
    BPMSegment,
    Note,
    Project,
    Track,
    TrackRole,
    TrackType,
    WaveformType,
)
from core.musical_time import TempoEvent
from core.track_events import DrumEvent, DrumType


def test_project_round_trip_preserves_note_and_drum_tracks():
    project = Project(name="Round Trip", bpm=120.0, original_bpm=96.0)
    project.bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=90.0),
    ]
    project._update_segment_end_times()

    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    lead.add_note(
        Note(
            pitch=64,
            start_time=0.0,
            duration=0.5,
            velocity=100,
            waveform=WaveformType.SQUARE,
            duty_cycle=0.25,
            adsr=ADSRParams(attack=0.01, decay=0.2, sustain=0.6, release=0.1),
        )
    )

    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    drums.add_drum_event(
        DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=0.0,
            duration_beats=0.5,
            velocity=110,
        )
    )

    project.add_track(lead)
    project.add_track(drums)

    restored = Project.from_dict(project.to_dict())

    assert restored.name == "Round Trip"
    assert restored.original_bpm == 96.0
    assert restored.resolution == 960
    assert len(restored.bpm_segments) == 2
    assert len(restored.tempo_events) == 2
    assert restored.bpm_segments[0].end_time == 1.0
    assert [track.track_type for track in restored.tracks] == [
        TrackType.NOTE_TRACK,
        TrackType.DRUM_TRACK,
    ]
    assert restored.tracks[0].notes[0].waveform == WaveformType.SQUARE
    assert restored.tracks[1].drum_events[0].drum_type == DrumType.KICK


def test_track_display_height_round_trip_is_preserved():
    track = Track(
        name="Lead",
        track_type=TrackType.NOTE_TRACK,
        display_height=96,
        notes=[Note(pitch=60, start_time=0.0, duration=0.5)],
    )

    restored = Track.from_dict(track.to_dict())

    assert restored.display_height == 96


def test_track_role_round_trip_is_preserved():
    track = Track(
        name="Bass",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.BASS,
        notes=[Note(pitch=48, start_time=0.0, duration=0.5)],
    )

    restored = Track.from_dict(track.to_dict())

    assert restored.role == TrackRole.BASS


def test_track_role_falls_back_to_legacy_name_inference_when_missing():
    restored = Track.from_dict(
        {
            "name": "Bass",
            "track_type": "note",
            "notes": [],
        }
    )

    assert restored.role == TrackRole.BASS


def test_drum_tracks_do_not_keep_note_roles():
    restored = Track.from_dict(
        {
            "name": "Drums",
            "track_type": "drum",
            "role": "bass",
            "drum_events": [],
        }
    )

    assert restored.role is None


def test_project_total_duration_accounts_for_drum_tracks():
    project = Project(name="Duration", bpm=120.0)

    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    lead.add_note(Note(pitch=60, start_time=0.0, duration=1.0))

    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    drums.add_drum_event(
        DrumEvent(
            drum_type=DrumType.CRASH,
            start_beat=4.0,
            duration_beats=2.0,
            velocity=100,
        )
    )

    project.add_track(lead)
    project.add_track(drums)

    assert project.get_total_duration() == 3.0


def test_project_total_duration_uses_tempo_map_for_drum_tracks():
    project = Project(name="Variable Duration", bpm=120.0, original_bpm=120.0)
    project.bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]
    project._update_segment_end_times()

    drums = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    drums.add_drum_event(
        DrumEvent(
            drum_type=DrumType.CRASH,
            start_beat=1.5,
            duration_beats=1.0,
            velocity=100,
        )
    )

    project.add_track(drums)

    assert project.get_total_duration() == 1.5


def test_project_exposes_standard_tick_time_helpers():
    project = Project(name="Tick Helpers", bpm=120.0, original_bpm=120.0)
    project.bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]
    project._update_segment_end_times()

    assert project.beats_to_ticks(2.5) == 2400
    assert project.ticks_to_beats(2400) == 2.5
    assert project.ticks_to_seconds(2400) == 1.5
    assert project.seconds_to_ticks(1.5) == 2400


def test_note_can_bridge_between_tick_and_second_timing():
    project = Project(name="Note Bridge", bpm=120.0, original_bpm=120.0)
    project.bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]
    project._update_segment_end_times()

    note = Note(pitch=60, start_time=0.0, duration=0.0)
    note.apply_tick_timing(project, start_tick=1920, duration_ticks=480)

    assert note.start_tick == 1920
    assert note.duration_ticks == 480
    assert note.start_time == 1.0
    assert note.duration == 0.5


def test_project_can_replace_tempo_events_and_sync_legacy_segments():
    project = Project(name="Tempo Replace", bpm=120.0, original_bpm=120.0)

    project.replace_tempo_events(
        [
            TempoEvent(960, 120.0),
            TempoEvent(1920, 60.0),
        ]
    )

    assert project.tempo_events[0] == TempoEvent(0, 120.0)
    assert project.tempo_events[1] == TempoEvent(960, 120.0)
    assert project.tempo_events[2] == TempoEvent(1920, 60.0)
    assert project.bpm_segments[0].start_time == 0.0
    assert project.bpm_segments[1].start_time == 0.5
    assert project.bpm_segments[2].start_time == 1.0
    assert project.beats_to_seconds(2.5) == 1.5
    assert project.seconds_to_beats(1.5) == 2.5


def test_replacing_tempo_events_retimes_existing_notes_by_tick_position():
    note = Note(pitch=60, start_time=0.5, duration=0.5)
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK, notes=[note])
    project = Project(
        name="Tempo Retiming",
        bpm=120.0,
        original_bpm=120.0,
        tracks=[track],
    )

    assert note.start_tick == 960
    assert note.duration_ticks == 960

    project.replace_tempo_events([TempoEvent(0, 60.0)])

    assert note.start_tick == 960
    assert note.duration_ticks == 960
    assert note.start_time == 1.0
    assert note.duration == 1.0


def test_project_caches_tempo_regions_between_repeated_conversions(monkeypatch):
    build_calls = []
    real_build_tempo_regions = models_module.build_tempo_regions

    def counting_build_tempo_regions(*args, **kwargs):
        build_calls.append(1)
        return real_build_tempo_regions(*args, **kwargs)

    monkeypatch.setattr(
        models_module,
        "build_tempo_regions",
        counting_build_tempo_regions,
    )

    project = Project(name="Tempo Cache", bpm=120.0, original_bpm=120.0)
    project.replace_tempo_events(
        [
            TempoEvent(0, 120.0),
            TempoEvent(1920, 60.0),
        ]
    )

    assert project.seconds_to_ticks(1.5) == 2400
    assert project.seconds_to_beats(1.5) == 2.5
    assert project.ticks_to_seconds(2400) == 1.5
    assert len(build_calls) == 1

    project.replace_tempo_events(
        [
            TempoEvent(0, 120.0),
            TempoEvent(960, 90.0),
        ]
    )

    assert project.seconds_to_ticks(1.0) == 1680
    assert len(build_calls) == 2
