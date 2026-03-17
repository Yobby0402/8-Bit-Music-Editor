from core.models import ADSRParams, BPMSegment, Note, Project, Track, TrackType, WaveformType
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
    assert len(restored.bpm_segments) == 2
    assert restored.bpm_segments[0].end_time == 1.0
    assert [track.track_type for track in restored.tracks] == [
        TrackType.NOTE_TRACK,
        TrackType.DRUM_TRACK,
    ]
    assert restored.tracks[0].notes[0].waveform == WaveformType.SQUARE
    assert restored.tracks[1].drum_events[0].drum_type == DrumType.KICK


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

