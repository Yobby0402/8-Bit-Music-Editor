from core.models import Note, Project, Track, TrackRole, TrackType
from core.project_io import load_project_from_file, save_project_to_file


def test_project_file_io_round_trip_preserves_project_data(tmp_path):
    project = Project(name="测试项目", bpm=128.0, original_bpm=96.0)
    lead = Track(name="Lead", track_type=TrackType.NOTE_TRACK, role=TrackRole.MELODY)
    lead.add_note(Note(pitch=64, start_time=0.0, duration=0.5, velocity=100))
    project.add_track(lead)

    file_path = tmp_path / "project.json"
    save_project_to_file(project, str(file_path))

    saved_text = file_path.read_text(encoding="utf-8")
    restored = load_project_from_file(str(file_path))

    assert "测试项目" in saved_text
    assert restored.name == "测试项目"
    assert restored.original_bpm == 96.0
    assert restored.tracks[0].role == TrackRole.MELODY
    assert restored.tracks[0].notes[0].pitch == 64
