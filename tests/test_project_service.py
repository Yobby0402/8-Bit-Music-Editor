from types import SimpleNamespace

import pytest

from core.models import Project, Track, TrackRole, WaveformType
from core.project_service import (
    AudioExportDependencyError,
    EmptyAudioExportError,
    build_audio_export_dependency_guidance,
    export_audio_document,
    export_audio_range_document,
    export_midi_document,
    import_midi_document,
    load_project_document,
    save_project_document,
)


def test_load_project_document_returns_project_source_paths(monkeypatch):
    project = Project(name="demo")

    monkeypatch.setattr("core.project_service.load_project_from_file", lambda path: project)

    result = load_project_document("demo.json")

    assert result.project is project
    assert result.current_file_path == "demo.json"
    assert result.current_midi_file_path is None


def test_import_midi_document_delegates_to_midi_import(monkeypatch):
    project = Project(name="midi-demo")
    captured = {}

    def fake_import_midi(file_path, default_waveform, snap_to_beat, allow_overlap):
        captured["file_path"] = file_path
        captured["default_waveform"] = default_waveform
        captured["snap_to_beat"] = snap_to_beat
        captured["allow_overlap"] = allow_overlap
        return project

    monkeypatch.setattr("core.project_service.MidiIO.import_midi", fake_import_midi)

    result = import_midi_document(
        "theme.mid",
        WaveformType.TRIANGLE,
        snap_to_beat=True,
        allow_overlap=False,
    )

    assert result.project is project
    assert result.current_file_path is None
    assert result.current_midi_file_path == "theme.mid"
    assert captured == {
        "file_path": "theme.mid",
        "default_waveform": WaveformType.TRIANGLE,
        "snap_to_beat": True,
        "allow_overlap": False,
    }


def test_save_project_document_delegates_to_project_io(monkeypatch):
    project = Project(name="save-demo")
    captured = {}

    def fake_save_project(project_arg, file_path):
        captured["project"] = project_arg
        captured["file_path"] = file_path

    monkeypatch.setattr("core.project_service.save_project_to_file", fake_save_project)

    result = save_project_document(project, "save.json")

    assert result.file_path == "save.json"
    assert captured == {"project": project, "file_path": "save.json"}


def test_export_midi_document_delegates_to_midi_export(monkeypatch):
    project = Project(name="export-demo")
    captured = {}

    def fake_export_midi(project_arg, file_path):
        captured["project"] = project_arg
        captured["file_path"] = file_path

    monkeypatch.setattr("core.project_service.MidiIO.export_midi", fake_export_midi)

    result = export_midi_document(project, "theme.mid")

    assert result.file_path == "theme.mid"
    assert captured == {"project": project, "file_path": "theme.mid"}


def test_build_audio_export_dependency_guidance_supports_mp3_and_ogg():
    mp3_guidance = build_audio_export_dependency_guidance("mp3", "missing moviepy")
    ogg_guidance = build_audio_export_dependency_guidance("ogg", "soundfile not found")

    assert mp3_guidance is not None
    assert "moviepy" in mp3_guidance.message
    assert ogg_guidance is not None
    assert "soundfile" in ogg_guidance.message


def test_export_audio_document_rejects_empty_audio():
    project = Project(name="empty-demo")
    engine = SimpleNamespace(sample_rate=44100, generate_project_audio=lambda _project: [])

    with pytest.raises(EmptyAudioExportError, match="没有音频"):
        export_audio_document(project, engine, "empty.wav")


def test_export_audio_document_wraps_dependency_errors(monkeypatch):
    project = Project(name="ogg-demo")
    engine = SimpleNamespace(sample_rate=44100, generate_project_audio=lambda _project: [0.1, 0.2])

    def fake_export_audio(audio, file_path, sample_rate, format):
        raise ImportError("soundfile is required")

    monkeypatch.setattr("core.audio_export.AudioExporter.export_audio", fake_export_audio)

    with pytest.raises(AudioExportDependencyError) as exc_info:
        export_audio_document(project, engine, "theme.ogg", format="ogg")

    assert exc_info.value.title == "缺少依赖"
    assert "soundfile" in exc_info.value.user_message


def test_export_audio_document_returns_export_result(monkeypatch):
    project = Project(name="audio-demo")
    engine = SimpleNamespace(sample_rate=32000, generate_project_audio=lambda _project: [0.1, 0.2])
    captured = {}

    def fake_export_audio(audio, file_path, sample_rate, format):
        captured["audio"] = audio
        captured["file_path"] = file_path
        captured["sample_rate"] = sample_rate
        captured["format"] = format

    monkeypatch.setattr("core.audio_export.AudioExporter.export_audio", fake_export_audio)

    result = export_audio_document(project, engine, "theme.wav", format="wav")

    assert result.file_path == "theme.wav"
    assert result.format == "wav"
    assert captured == {
        "audio": [0.1, 0.2],
        "file_path": "theme.wav",
        "sample_rate": 32000,
        "format": "wav",
    }


def test_export_audio_range_document_uses_time_range(monkeypatch):
    project = Project(name="range-demo")
    captured = {}

    def fake_generate_project_audio(project_arg, *, start_time, end_time, playback_enabled_tracks=None):
        captured["project"] = project_arg
        captured["start_time"] = start_time
        captured["end_time"] = end_time
        captured["playback_enabled_tracks"] = playback_enabled_tracks
        return [0.1, 0.2]

    engine = SimpleNamespace(sample_rate=32000, generate_project_audio=fake_generate_project_audio)

    def fake_export_audio(audio, file_path, sample_rate, format):
        captured["audio"] = audio
        captured["file_path"] = file_path
        captured["sample_rate"] = sample_rate
        captured["format"] = format

    monkeypatch.setattr("core.audio_export.AudioExporter.export_audio", fake_export_audio)

    result = export_audio_range_document(
        project,
        engine,
        "range.wav",
        start_time=0.5,
        end_time=1.25,
        format="wav",
    )

    assert result.file_path == "range.wav"
    assert captured == {
        "project": project,
        "start_time": 0.5,
        "end_time": 1.25,
        "playback_enabled_tracks": None,
        "audio": [0.1, 0.2],
        "file_path": "range.wav",
        "sample_rate": 32000,
        "format": "wav",
    }


def test_export_audio_range_document_can_render_sfx_only(monkeypatch):
    project = Project(name="sfx-only")
    melody = Track(name="Lead")
    sfx = Track(name="SFX", role=TrackRole.EFFECT)
    project.add_track(melody)
    project.add_track(sfx)
    captured = {}

    def fake_generate_project_audio(project_arg, *, start_time, end_time, playback_enabled_tracks=None):
        captured["project"] = project_arg
        captured["start_time"] = start_time
        captured["end_time"] = end_time
        captured["playback_enabled_tracks"] = playback_enabled_tracks
        return [0.1, 0.2]

    engine = SimpleNamespace(sample_rate=32000, generate_project_audio=fake_generate_project_audio)

    def fake_export_audio(audio, file_path, sample_rate, format):
        captured["audio"] = audio
        captured["file_path"] = file_path
        captured["sample_rate"] = sample_rate
        captured["format"] = format

    monkeypatch.setattr("core.audio_export.AudioExporter.export_audio", fake_export_audio)

    export_audio_range_document(
        project,
        engine,
        "sfx.wav",
        start_time=0.5,
        end_time=1.25,
        sfx_only=True,
    )

    assert captured["playback_enabled_tracks"] == {
        id(melody): False,
        id(sfx): True,
    }
