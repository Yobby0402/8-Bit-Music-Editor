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


def test_prepare_playback_plan_mixes_tracks_and_applies_track_ratios():
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
    assert plan.track_count == 2
    assert plan.volume_scale == 1.0
    assert plan.end_time > plan.start_time
    assert plan.audio_buffer.dtype == np.int16
    assert plan.audio_buffer.ndim == 2
    assert plan.audio_buffer.shape[1] == 2
    assert np.max(np.abs(plan.audio_buffer)) > 0


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
    assert plan.track_count == 1
    assert plan.volume_scale == 1.0


def test_sequencer_play_uses_prepared_playback_pipeline(monkeypatch):
    project, _, _ = _build_project_with_two_tracks()
    sequencer = Sequencer(project=project, sample_rate=1000, initialize_audio=False)
    fake_plan = PreparedPlaybackPlan(
        start_time=0.5,
        end_time=1.0,
        loop=True,
        volume_scale=1.0,
        audio_buffer=np.zeros((100, 2), dtype=np.int16),
        track_count=1,
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


def test_start_prepared_playback_uses_single_mixed_channel(monkeypatch):
    sequencer = Sequencer(project=Project(), sample_rate=1000, initialize_audio=False)
    calls = {}

    class FakeChannel:
        def play(self, sound, loops=0):
            calls["play"] = (sound, loops)

    def fake_prepare_packed_track_audio(audio_buffer, volume=None, track_id=None):
        calls["prepare"] = (audio_buffer, volume, track_id)
        return ("sound", FakeChannel())

    monkeypatch.setattr(
        sequencer.audio_engine,
        "prepare_packed_track_audio",
        fake_prepare_packed_track_audio,
    )
    plan = PreparedPlaybackPlan(
        start_time=1.0,
        end_time=2.0,
        loop=True,
        volume_scale=1.0,
        audio_buffer=np.ones((100, 2), dtype=np.int16),
        track_count=2,
    )

    assert sequencer.start_prepared_playback(plan) is True
    assert calls["prepare"] == (plan.audio_buffer, 1.0, None)
    assert calls["play"] == ("sound", -1)
    assert sequencer.playback_state.is_playing is True
    assert sequencer.playback_state.end_time == 2.0


def test_start_prepared_playback_resets_state_when_channel_play_fails(monkeypatch):
    sequencer = Sequencer(project=Project(), sample_rate=1000, initialize_audio=False)

    class FailingChannel:
        def play(self, sound, loops=0):
            raise RuntimeError("play failed")

    monkeypatch.setattr(
        sequencer.audio_engine,
        "prepare_packed_track_audio",
        lambda *_args, **_kwargs: ("sound", FailingChannel()),
    )
    plan = PreparedPlaybackPlan(
        start_time=1.0,
        end_time=2.0,
        loop=False,
        volume_scale=1.0,
        audio_buffer=np.ones((100, 2), dtype=np.int16),
        track_count=1,
    )

    assert sequencer.start_prepared_playback(plan) is False
    assert sequencer.playback_state.is_playing is False
    assert sequencer.playback_state.current_time == 0.0
    assert sequencer.playback_state.end_time == 0.0
    assert sequencer._current_sounds == []


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
