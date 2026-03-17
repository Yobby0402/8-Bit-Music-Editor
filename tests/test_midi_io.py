from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from core.midi_io import MidiIO


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
    assert len(project.bpm_segments) == 2
    assert round(project.bpm_segments[1].bpm, 2) == 90.0
    assert len(project.tracks) == 1
    assert project.tracks[0].name == "Lead"
    assert [note.pitch for note in project.tracks[0].notes] == [60, 64]

