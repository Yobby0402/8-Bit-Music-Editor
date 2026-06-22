import numpy as np

from core.audio_engine import MIXER_BUFFER_SIZE, AudioEngine
from core.models import BPMSegment, Project, Track, TrackType
from core.track_events import DrumEvent, DrumType


def _build_audio_engine(monkeypatch, sample_rate: int = 1000) -> AudioEngine:
    monkeypatch.setattr("core.audio_engine.pygame.mixer.init", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "core.audio_engine.pygame.mixer.set_num_channels",
        lambda *args, **kwargs: None,
    )
    return AudioEngine(sample_rate=sample_rate)


def test_generate_track_audio_uses_tempo_map_for_variable_bpm_drums(monkeypatch):
    engine = _build_audio_engine(monkeypatch)

    project = Project(name="Tempo Map", bpm=120.0, original_bpm=120.0)
    project.bpm_segments = [
        BPMSegment(start_time=0.0, bpm=120.0),
        BPMSegment(start_time=1.0, bpm=60.0),
    ]
    project._update_segment_end_times()

    track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    track.add_drum_event(
        DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=1.5,
            duration_beats=1.0,
            velocity=127,
        )
    )

    audio = engine.generate_track_audio(
        track,
        start_time=0.0,
        end_time=None,
        bpm=project.bpm,
        original_bpm=project.original_bpm,
        project=project,
    )

    assert len(audio) == 1500
    assert np.max(np.abs(audio[:750])) == 0.0
    assert np.max(np.abs(audio[750:900])) > 0.0


def test_audio_engine_uses_stable_mixer_buffer(monkeypatch):
    init_calls = []
    monkeypatch.setattr("core.audio_engine.pygame.mixer.init", lambda **kwargs: init_calls.append(kwargs))
    monkeypatch.setattr(
        "core.audio_engine.pygame.mixer.set_num_channels",
        lambda *args, **kwargs: None,
    )

    AudioEngine(sample_rate=44100, initialize_mixer=True)

    assert init_calls[0]["buffer"] == MIXER_BUFFER_SIZE
    assert MIXER_BUFFER_SIZE >= 2048


def test_generate_track_audio_keeps_legacy_single_bpm_drum_offsets_aligned(monkeypatch):
    engine = _build_audio_engine(monkeypatch)

    track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    track.add_drum_event(
        DrumEvent(
            drum_type=DrumType.SNARE,
            start_beat=2.0,
            duration_beats=0.5,
            velocity=127,
        )
    )

    audio = engine.generate_track_audio(
        track,
        start_time=1.0,
        end_time=2.0,
        bpm=60.0,
        original_bpm=120.0,
    )

    assert len(audio) == 2000
    assert np.max(np.abs(audio[:50])) > 0.0
    assert np.max(np.abs(audio[600:])) == 0.0
