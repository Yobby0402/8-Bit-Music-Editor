from types import SimpleNamespace

import ui.main_window_app_ops as app_ops_module
from core.command import (
    AddNoteCommand,
    BatchCommand,
    CommandHistoryResult,
    DeleteNoteCommand,
)
from core.models import Note, Track, TrackRole, TrackType
from ui.main_window_dialogs import NewTrackSelection
from ui.main_window_app_ops import (
    MainWindowAppOpsMixin,
    build_history_refresh_plan,
    build_about_text,
    find_category_index,
    get_first_segment_bpm,
)


def test_build_about_text_contains_app_identity():
    text = build_about_text("8bit", "9.9.9")

    assert "8bit 9.9.9" in text
    assert "PyQt5" in text


def test_get_first_segment_bpm_returns_none_for_empty_segments():
    assert get_first_segment_bpm([]) is None


def test_get_first_segment_bpm_uses_first_segment():
    bpm = get_first_segment_bpm(
        [
            SimpleNamespace(bpm=144.0),
            SimpleNamespace(bpm=120.0),
        ]
    )

    assert bpm == 144.0


def test_find_category_index_returns_matching_position():
    category_names = ["显示设置", "编辑设置", "快捷键", "其他设置"]

    assert find_category_index(category_names, "快捷键") == 2
    assert find_category_index(category_names, "不存在") is None


class FakeAppWindow(MainWindowAppOpsMixin):
    def __init__(self):
        self.setup_shortcuts_calls = 0
        self.sequencer = SimpleNamespace(project=SimpleNamespace(tracks=[]))

    def setup_shortcuts(self):
        self.setup_shortcuts_calls += 1


def test_refresh_after_settings_dialog_only_rebinds_shortcuts():
    window = FakeAppWindow()

    window._refresh_after_settings_dialog()

    assert window.setup_shortcuts_calls == 1


def test_on_add_track_clicked_passes_role_to_sequencer(monkeypatch):
    class FakeTrackAddWindow(MainWindowAppOpsMixin):
        def __init__(self):
            self.sequencer = SimpleNamespace(
                project=SimpleNamespace(tracks=[]),
                add_track=self._add_track,
            )
            self.refresh_calls = 0
            self._status_bar = FakeStatusBar()
            self.add_track_calls = []

        def _add_track(self, *, name, track_type, role):
            self.add_track_calls.append((name, track_type, role))
            return Track(name=name, track_type=track_type, role=role)

        def refresh_ui(self):
            self.refresh_calls += 1

        def statusBar(self):
            return self._status_bar

    monkeypatch.setattr(
        app_ops_module,
        "prompt_new_track",
        lambda parent, track_count: NewTrackSelection(
            name="低音",
            track_type=TrackType.NOTE_TRACK,
            role=TrackRole.BASS,
        ),
    )
    window = FakeTrackAddWindow()

    window.on_add_track_clicked()

    assert window.add_track_calls == [("低音", TrackType.NOTE_TRACK, TrackRole.BASS)]
    assert window.refresh_calls == 1
    assert window.statusBar().messages[-1] == "已添加音轨: 低音"


def test_build_history_refresh_plan_flattens_batch_note_commands():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note_to_add = Note(pitch=60, start_time=0.0, duration=0.25)
    note_to_delete = Note(pitch=64, start_time=0.5, duration=0.25)
    command = BatchCommand(
        [
            AddNoteCommand(SimpleNamespace(project=None), track, note_to_add),
            DeleteNoteCommand(SimpleNamespace(project=None), track, note_to_delete),
        ]
    )
    history_result = CommandHistoryResult(
        command=command,
        description="batch",
        operation="undo",
    )

    plan = build_history_refresh_plan(history_result)

    assert plan.requires_full_refresh is False
    assert plan.note_items_to_remove == [(note_to_add, track)]
    assert plan.note_items_to_sync == [(note_to_delete, track)]


class FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message):
        self.messages.append(message)


class FakePropertyPanel:
    def __init__(self):
        self.current_note = None
        self.current_track = None
        self.current_notes = []
        self.current_track_for_edit = None
        self.set_note_calls = []
        self.set_notes_calls = []
        self.set_track_calls = []
        self.update_ui_calls = 0

    def set_note(self, note, track):
        self.current_note = note
        self.current_track = track
        self.current_notes = []
        self.set_note_calls.append((note, track))

    def set_notes(self, notes):
        self.current_notes = list(notes)
        self.current_note = None
        self.current_track = None
        self.set_notes_calls.append(list(notes))

    def set_track(self, track):
        self.current_track_for_edit = track
        self.set_track_calls.append(track)

    def update_ui(self):
        self.update_ui_calls += 1


class FakeUndoRedoWindow(MainWindowAppOpsMixin):
    def __init__(self, history_result):
        self.history_result = history_result
        self.sequencer = SimpleNamespace(
            undo=lambda: self.history_result,
            redo=lambda: self.history_result,
            can_undo=lambda: True,
            can_redo=lambda: True,
        )
        self.property_panel = FakePropertyPanel()
        self.sync_note_blocks_calls = []
        self.remove_note_blocks_calls = []
        self.sync_track_calls = []
        self.refresh_calls = 0
        self.oscilloscope_refresh_calls = 0
        self.undo_state_updates = 0
        self._status_bar = FakeStatusBar()
        self.selected_note = None
        self.selected_track = None
        self.view_stack = SimpleNamespace(currentIndex=lambda: 0)

    def _sync_note_blocks_ui(self, items):
        self.sync_note_blocks_calls.append(list(items))
        return True

    def _remove_note_blocks_ui(self, items):
        self.remove_note_blocks_calls.append(list(items))
        return True

    def _sync_track_ui(self, track):
        self.sync_track_calls.append(track)
        return True

    def refresh_ui(self):
        self.refresh_calls += 1

    def _refresh_note_related_views(self):
        self.oscilloscope_refresh_calls += 1

    def update_undo_redo_state(self):
        self.undo_state_updates += 1

    def statusBar(self):
        return self._status_bar


def test_undo_prefers_lightweight_refresh_for_note_commands():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    history_result = CommandHistoryResult(
        command=AddNoteCommand(SimpleNamespace(project=None), track, note),
        description="添加音符",
        operation="undo",
    )
    window = FakeUndoRedoWindow(history_result)

    window.undo()

    assert window.undo_state_updates == 1
    assert window.remove_note_blocks_calls == [[(note, track)]]
    assert window.sync_note_blocks_calls == []
    assert window.refresh_calls == 0
    assert window.statusBar().messages[-1] == "已撤销: 添加音符"


def test_redo_updates_property_panel_for_modified_note():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    command = DeleteNoteCommand(SimpleNamespace(project=None), track, note)
    command.undo()
    history_result = CommandHistoryResult(
        command=command,
        description="删除音符",
        operation="undo",
    )
    window = FakeUndoRedoWindow(history_result)
    window.property_panel.current_note = command.note
    window.property_panel.current_track = track
    window.selected_note = command.note
    window.selected_track = track

    window.undo()

    assert window.sync_note_blocks_calls == [[(command.note, track)]]
    assert window.property_panel.update_ui_calls == 1
    assert window.selected_note is command.note
    assert window.refresh_calls == 0


def test_undo_refreshes_oscilloscope_after_lightweight_note_sync_in_waveform_view():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    history_result = CommandHistoryResult(
        command=DeleteNoteCommand(SimpleNamespace(project=None), track, note),
        description="鍒犻櫎闊崇",
        operation="undo",
    )
    window = FakeUndoRedoWindow(history_result)
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)

    window.undo()

    assert window.sync_note_blocks_calls == [[(note, track)]]
    assert window.sync_track_calls == []
    assert window.oscilloscope_refresh_calls == 1
    assert window.refresh_calls == 0
