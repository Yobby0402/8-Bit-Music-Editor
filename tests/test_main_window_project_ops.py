from types import SimpleNamespace

from core.models import Project, Track, TrackType
from ui.main_window_project_ops import MainWindowProjectOpsMixin


class FakeProgress:
    def __init__(self):
        self.signal_state = False
        self.events = []

    def blockSignals(self, value):
        self.events.append(("blockSignals", value))
        previous = self.signal_state
        self.signal_state = value
        return previous

    def close(self):
        self.events.append(("close", None))

    def deleteLater(self):
        self.events.append(("deleteLater", None))


class FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message):
        self.messages.append(message)


class FakeSettings:
    def __init__(self):
        self.values = {}

    def setValue(self, key, value):
        self.values[key] = value


class FakeSequencer:
    def __init__(self):
        self.project = None

    def set_project(self, project):
        self.project = project


class FakeWindow(MainWindowProjectOpsMixin):
    def __init__(self):
        self._midi_import_request_id = 1
        self._midi_import_progress = None
        self._status_bar = FakeStatusBar()
        self.settings = FakeSettings()
        self.sequencer = FakeSequencer()
        self.current_file_path = None
        self.current_midi_file_path = None
        self.window_title = None
        self.reset_calls = 0
        self.refresh_calls = []
        self.update_file_name_calls = 0
        self.profile_outcomes = []
        self.ui_profile_logs = []

    def statusBar(self):
        return self._status_bar

    def setWindowTitle(self, title):
        self.window_title = title

    def _reset_project_selection(self):
        self.reset_calls += 1

    def _refresh_project_after_midi_import(self, project):
        self.refresh_calls.append(project)

    def _update_file_name_display(self):
        self.update_file_name_calls += 1

    def _finish_midi_import_profile(self, request_id: int, *, outcome: str) -> None:
        self.profile_outcomes.append((request_id, outcome))

    def _log_midi_import_ui_profile(self, file_path: str, **stage_timings_ms: float) -> None:
        self.ui_profile_logs.append((file_path, stage_timings_ms))


def test_close_midi_import_progress_blocks_signals_before_closing():
    window = FakeWindow()
    progress = FakeProgress()
    window._midi_import_progress = progress

    window._close_midi_import_progress()

    assert progress.events == [
        ("blockSignals", True),
        ("close", None),
        ("deleteLater", None),
        ("blockSignals", False),
    ]
    assert window._midi_import_progress is None


def test_on_midi_import_finished_marks_request_ok_and_updates_state():
    window = FakeWindow()
    project = Project(name="Imported", bpm=120.0, original_bpm=120.0)
    project.add_track(Track(name="Lead", track_type=TrackType.NOTE_TRACK))
    load_result = SimpleNamespace(
        project=project,
        current_file_path=None,
        current_midi_file_path="D:/music/demo.mid",
    )

    window._on_midi_import_finished(1, load_result, "D:/music/demo.mid")

    assert window.sequencer.project is project
    assert window.current_file_path is None
    assert window.current_midi_file_path == "D:/music/demo.mid"
    assert window.window_title == "8bit音乐制作器 - Imported"
    assert window.reset_calls == 1
    assert window.refresh_calls == [project]
    assert window.update_file_name_calls == 1
    assert window._status_bar.messages == ["已导入MIDI: D:/music/demo.mid"]
    assert window.settings.values["last_midi_directory"] == "D:/music"
    assert window.profile_outcomes == [(1, "ok")]
    assert len(window.ui_profile_logs) == 1
    _, stage_timings = window.ui_profile_logs[0]
    assert set(stage_timings) == {
        "apply_project_ms",
        "reset_selection_ms",
        "refresh_project_ms",
        "update_file_label_ms",
        "show_status_ms",
        "persist_directory_ms",
    }
