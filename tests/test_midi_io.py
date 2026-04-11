from pathlib import Path

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from core.midi_io import MidiIO
from core.models import Note, Project, Track, TrackType
from core.musical_time import TempoEvent


def _write_test_midi(file_path: Path) -> None:
    midi = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    midi.tracks.append(track)

    track.append(MetaMessage("track_name", name="Lead", time=0))
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(120), time=0))
    track.append(Message("note_on", note=60, velocity=100, time=0))
    track.append(Message("note_off", note=60, velocity=0, time=480))
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(90), time=0))
    track.append(Message("note_on", note=64, velocity=100, time=480))
    track.append(Message("note_off", note=64, velocity=0, time=480))

    midi.save(file_path)


def test_import_midi_extracts_tempo_segments_and_notes(tmp_path):
    midi_path = tmp_path / "tempo_change.mid"
    _write_test_midi(midi_path)

    project = MidiIO.import_midi(
        str(midi_path),
        snap_to_beat=False,
        allow_overlap=True,
    )

    assert project.name == "tempo_change"
    assert round(project.bpm, 2) == 120.0
    assert project.resolution == 480
    assert len(project.tempo_events) == 2
    assert len(project.bpm_segments) == 2
    assert round(project.bpm_segments[1].bpm, 2) == 90.0
    assert len(project.tracks) == 1
    assert project.tracks[0].name == "Lead"
    assert [note.pitch for note in project.tracks[0].notes] == [60, 64]
    assert project.tracks[0].notes[0].start_tick == 0
    assert project.tracks[0].notes[0].duration_ticks == 480
    assert project.tracks[0].notes[1].start_tick == 960
    assert project.tracks[0].notes[1].duration_ticks == 480
    assert project.tracks[0].notes[0].start_time == 0.0
    assert project.tracks[0].notes[0].duration == 0.5
    assert project.tracks[0].notes[1].start_time == pytest.approx(1.1666666666666665)
    assert project.tracks[0].notes[1].duration == pytest.approx(0.6666666666666667)


def test_export_midi_uses_project_resolution_and_tempo_events(tmp_path):
    project = Project(
        name="Export Tick Project",
        bpm=120.0,
        original_bpm=120.0,
        resolution=960,
        tempo_events=[TempoEvent(0, 120.0), TempoEvent(1920, 60.0)],
    )
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=67, start_time=0.0, duration=0.0)
    note.apply_tick_timing(project, 1920, 960)
    track.add_note(note)
    project.add_track(track)

    midi_path = tmp_path / "export_tick.mid"
    MidiIO.export_midi(project, str(midi_path))

    exported = MidiFile(midi_path)

    assert exported.ticks_per_beat == 960
    assert exported.tracks[0][1].type == "set_tempo"
    assert exported.tracks[0][1].time == 0
    assert exported.tracks[0][2].type == "set_tempo"
    assert exported.tracks[0][2].time == 1920
    assert exported.tracks[0][3].type == "note_on"
    assert exported.tracks[0][3].time == 0
    assert exported.tracks[0][4].type == "note_off"
    assert exported.tracks[0][4].time == 960
