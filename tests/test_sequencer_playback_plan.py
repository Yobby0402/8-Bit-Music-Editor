import numpy as np

from core.models import Note, Project, Track, TrackRole, TrackType
from core.sequencer import PreparedPlaybackPlan, Sequencer, prepare_playback_plan


def _build_project_with_two_tracks():
    project = Project(name="Playback Plan", bpm=120.0, original_bpm=120.0)

    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    lead.add_note(Note(pitch=60, start_time=0.0, duration=0.25, velocity=100))
    project.add_track(lead)

    bass = Track(name="Bass", track_type=TrackType.NOTE_TRACK)
    bass.add_note(Note(pitch=48, start_time=0.0, duration=0.25, velocity=100))
    project.add_track(bass)

    return project, lead, bass


def test_prepare_playback_plan_applies_volume_scale_and_track_ratios():
    project, lead, bass = _build_project_with_two_tracks()

    plan = prepare_playback_plan(
        project,
        sample_rate=1000,
        playback_volume_ratios={
            id(lead): 0.5,
            id(bass): 1.0,
        },
    )

    assert plan is not None
    assert len(plan.tracks) == 2
    assert plan.volume_scale == 0.5
    assert plan.end_time > plan.start_time

    volumes = {prepared.track_id: prepared.initial_volume for prepared in plan.tracks}
    assert volumes[id(lead)] == 0.25
    assert volumes[id(bass)] == 0.5
    assert all(prepared.audio_buffer.dtype == np.int16 for prepared in plan.tracks)
    assert all(prepared.audio_buffer.ndim == 2 for prepared in plan.tracks)
    assert all(prepared.audio_buffer.shape[1] == 2 for prepared in plan.tracks)


def test_prepare_playback_plan_respects_enabled_track_filter():
    project, lead, bass = _build_project_with_two_tracks()

    plan = prepare_playback_plan(
        project,
        sample_rate=1000,
        playback_enabled_tracks={
            id(lead): False,
            id(bass): True,
        },
    )

    assert plan is not None
    assert len(plan.tracks) == 1
    assert plan.tracks[0].track is bass
    assert plan.volume_scale == 1.0


def test_sequencer_play_uses_prepared_playback_pipeline(monkeypatch):
    project, _, _ = _build_project_with_two_tracks()
    sequencer = Sequencer(project=project, sample_rate=1000, initialize_audio=False)
    fake_plan = PreparedPlaybackPlan(
        start_time=0.5,
        end_time=1.0,
        loop=True,
        volume_scale=1.0,
        tracks=[],
    )
    calls = {}

    def fake_prepare_playback(*, start_time=0.0, loop=False, end_time=None):
        calls["prepare"] = (start_time, loop, end_time)
        return fake_plan

    def fake_start_prepared_playback(plan):
        calls["start"] = plan
        return True

    monkeypatch.setattr(sequencer, "prepare_playback", fake_prepare_playback)
    monkeypatch.setattr(sequencer, "start_prepared_playback", fake_start_prepared_playback)

    result = sequencer.play(start_time=0.5, loop=True, end_time=0.9)

    assert result is True
    assert calls["prepare"] == (0.5, True, 0.9)
    assert calls["start"] is fake_plan


def test_sequencer_add_track_preserves_note_role_and_clears_drum_role():
    sequencer = Sequencer(project=Project(), initialize_audio=False)

    bass_track = sequencer.add_track(
        name="低音",
        track_type=TrackType.NOTE_TRACK,
        role=TrackRole.BASS,
    )
    drum_track = sequencer.add_track(
        name="打击乐",
        track_type=TrackType.DRUM_TRACK,
        role=TrackRole.BASS,
    )

    assert bass_track.role == TrackRole.BASS
    assert drum_track.role is None
