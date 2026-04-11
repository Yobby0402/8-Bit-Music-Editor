import pytest
from types import SimpleNamespace

import ui.main_window_editor_ops as editor_ops
from core.models import Note, Track, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType
from ui.main_window_editor_ops import (
    MainWindowEditorOpsMixin,
    build_batch_note_property_updates,
    build_single_note_property_updates,
    build_track_multi_select_message,
    count_track_items,
    dedupe_note_track_pairs,
    format_sequence_item_message,
)


class ValueControl:
    def __init__(self, value):
        self._value = value

    def value(self):
        return self._value


class IndexControl:
    def __init__(self, index):
        self._index = index

    def currentIndex(self):
        return self._index


def test_format_sequence_item_message_supports_note_and_drum_event():
    note = Note(pitch=60, start_time=0.0, duration=0.5)
    drum = DrumEvent(DrumType.SNARE, start_beat=1.0, duration_beats=0.25)

    assert format_sequence_item_message("已选中", note) == "已选中音符: C4"
    assert format_sequence_item_message("已删除", drum) == "已删除打击乐: 军鼓"


def test_build_single_note_property_updates_extracts_changed_values():
    note = Note(
        pitch=60,
        start_time=0.0,
        duration=0.5,
        velocity=90,
        waveform=WaveformType.SQUARE,
    )
    panel = SimpleNamespace(
        pitch_spinbox=ValueControl(62),
        duration_spinbox=ValueControl(2.0),
        velocity_slider=ValueControl(100),
        waveform_combo=IndexControl(1),
        attack_spinbox=ValueControl(0.05),
        decay_spinbox=ValueControl(note.adsr.decay),
        sustain_spinbox=ValueControl(0.8),
        release_spinbox=ValueControl(note.adsr.release),
    )

    kwargs = build_single_note_property_updates(panel, note, bpm=120.0)

    assert kwargs == {
        "pitch": 62,
        "duration": 1.0,
        "velocity": 100,
        "waveform": WaveformType.TRIANGLE,
        "adsr": {
            "attack": 0.05,
            "sustain": 0.8,
        },
    }


def test_build_batch_note_property_updates_respects_dirty_flags():
    panel = SimpleNamespace(
        batch_waveform_combo=IndexControl(2),
        _batch_waveform_dirty=True,
        batch_velocity_slider=ValueControl(96),
        _batch_velocity_dirty=False,
        batch_velocity_offset_spinbox=ValueControl(-12),
        _batch_velocity_offset_dirty=True,
        batch_duty_spinbox=ValueControl(0.25),
        _batch_duty_dirty=True,
    )

    kwargs, velocity_offset = build_batch_note_property_updates(panel)

    assert kwargs == {
        "waveform": WaveformType.SAWTOOTH,
        "duty_cycle": 0.25,
    }
    assert velocity_offset == -12


def test_build_track_multi_select_message_distinguishes_track_types():
    note_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    drum_track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)

    assert "3 个音符" in build_track_multi_select_message(note_track, 3)
    assert "2 个打击乐事件" in build_track_multi_select_message(drum_track, 2)


def test_count_track_items_uses_track_type():
    note_track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note_track.add_note(Note(pitch=60, start_time=0.0, duration=0.25))
    drum_track = Track(name="Drums", track_type=TrackType.DRUM_TRACK)
    drum_track.add_drum_event(DrumEvent(DrumType.KICK, start_beat=0.0, duration_beats=0.25))

    assert count_track_items(note_track) == 1
    assert count_track_items(drum_track) == 1


def test_dedupe_note_track_pairs_preserves_first_seen_order():
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    first = Note(pitch=60, start_time=0.0, duration=0.25)
    second = Note(pitch=64, start_time=0.5, duration=0.25)

    assert dedupe_note_track_pairs(
        [(first, track), (first, track), (second, track)]
    ) == [(first, track), (second, track)]


class FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message):
        self.messages.append(message)


class FakeUnifiedEditor:
    def __init__(self):
        self.selected_track = None
        self.selected_track_calls = []

    def set_selected_track(self, track):
        self.selected_track = track
        self.selected_track_calls.append(track)


class FakeSequenceWidget:
    def __init__(self):
        self.highlighted_tracks = []
        self.selected_track_notes_calls = []

    def set_highlighted_track(self, track):
        self.highlighted_tracks.append(track)

    def select_track_notes(self, track):
        self.selected_track_notes_calls.append(track)


class FakeEditorWindow(MainWindowEditorOpsMixin):
    def __init__(self):
        self.sync_note_block_calls = []
        self.sync_note_blocks_calls = []
        self.refresh_calls = []
        self.restore_block_selection_calls = []
        self.oscilloscope_refresh_calls = 0
        self.modified_note_calls = []
        self.batch_modify_note_calls = []
        self.move_note_calls = []
        self.executed_commands = []
        self.sync_note_block_result = True
        self.sync_note_blocks_result = True
        self.property_panel_update_calls = 0
        self._status_bar = FakeStatusBar()
        self.unified_editor = FakeUnifiedEditor()
        self.sequence_widget = FakeSequenceWidget()
        self.view_stack = SimpleNamespace(currentIndex=lambda: 0)
        self.property_panel = SimpleNamespace(
            current_note=None,
            current_track=None,
            current_notes=[],
            set_note=self._set_property_note,
            set_track=self._set_property_track,
            update_ui=self._update_property_panel_ui,
            adjust_following_notes=lambda duration_delta: [],
            batch_waveform_combo=IndexControl(0),
            _batch_waveform_dirty=False,
            batch_velocity_slider=ValueControl(100),
            _batch_velocity_dirty=False,
            batch_velocity_offset_spinbox=ValueControl(0),
            _batch_velocity_offset_dirty=False,
            batch_duty_spinbox=ValueControl(0.25),
            _batch_duty_dirty=False,
        )
        self.sequencer = SimpleNamespace(
            get_bpm=lambda: 120.0,
            modify_note=self._modify_note,
            batch_modify_notes=self._batch_modify_notes,
            move_note=self._move_note,
            command_history=SimpleNamespace(execute_command=self._execute_command),
        )

    def _update_property_panel_ui(self):
        self.property_panel_update_calls += 1

    def _set_property_note(self, note, track):
        self.property_panel.current_note = note
        self.property_panel.current_track = track

    def _set_property_track(self, track):
        self.property_panel.current_track = track

    def _modify_note(self, track, note, **kwargs):
        self.modified_note_calls.append((track, note, dict(kwargs)))
        for key, value in kwargs.items():
            setattr(note, key, value)

    def _batch_modify_notes(self, notes_and_tracks, **kwargs):
        self.batch_modify_note_calls.append((list(notes_and_tracks), dict(kwargs)))
        for note, track in notes_and_tracks:
            for key, value in kwargs.items():
                setattr(note, key, value)

    def _move_note(self, track, note, new_start_time):
        self.move_note_calls.append((track, note, new_start_time))
        note.start_time = new_start_time

    def _execute_command(self, command):
        self.executed_commands.append(command)

    def _sync_note_block_ui(self, note, track):
        self.sync_note_block_calls.append((note, track))
        return self.sync_note_block_result

    def _sync_note_blocks_ui(self, notes_and_tracks):
        self.sync_note_blocks_calls.append(list(notes_and_tracks))
        return self.sync_note_blocks_result

    def refresh_ui(self, preserve_selection=False):
        self.refresh_calls.append(preserve_selection)

    def _restore_block_selection(self, notes_and_tracks):
        self.restore_block_selection_calls.append(list(notes_and_tracks))

    def _refresh_oscilloscope_widget(self):
        self.oscilloscope_refresh_calls += 1

    def _refresh_note_related_views(self):
        self._refresh_oscilloscope_widget()

    def _focus_property_panel(self):
        return None

    def statusBar(self):
        return self._status_bar


def test_on_property_changed_batches_linked_note_refreshes(monkeypatch):
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    following_note = Note(pitch=64, start_time=0.5, duration=0.25)
    window.property_panel.current_note = note
    window.property_panel.current_track = track
    window.property_panel.adjust_following_notes = lambda duration_delta: [following_note]

    monkeypatch.setattr(
        editor_ops,
        "build_single_note_property_updates",
        lambda property_panel, current_note, bpm: {"duration": 0.5},
    )

    window.on_property_changed(note, track)

    assert window.modified_note_calls == [(track, note, {"duration": 0.5})]
    assert window.sync_note_block_calls == []
    assert window.sync_note_blocks_calls == [[(note, track), (following_note, track)]]
    assert window.refresh_calls == []
    assert window.property_panel_update_calls == 1


def test_on_note_position_changed_refreshes_oscilloscope_after_local_sync_in_waveform_view():
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)

    window.on_note_position_changed(note, track, 0.0, 0.5)

    assert window.move_note_calls == [(track, note, 0.5)]
    assert window.sync_note_block_calls == [(note, track)]
    assert window.oscilloscope_refresh_calls == 1
    assert window.refresh_calls == []


def test_on_batch_property_changed_falls_back_to_full_refresh_when_block_sync_unavailable():
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25, waveform=WaveformType.SQUARE)
    notes_and_tracks = [(note, track)]
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)
    window.sync_note_block_result = False
    window.sync_note_blocks_result = False
    window.property_panel.current_notes = notes_and_tracks
    window.property_panel.batch_waveform_combo = IndexControl(1)
    window.property_panel._batch_waveform_dirty = True

    window.on_batch_property_changed(notes_and_tracks)

    assert window.batch_modify_note_calls == [(notes_and_tracks, {"waveform": WaveformType.TRIANGLE})]
    assert window.oscilloscope_refresh_calls == 0
    assert window.refresh_calls == [True]
    assert window.restore_block_selection_calls == [notes_and_tracks]


def test_on_note_position_changed_falls_back_to_full_refresh_when_block_sync_unavailable():
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)
    window.view_stack = SimpleNamespace(currentIndex=lambda: 1)
    window.sync_note_block_result = False

    window.on_note_position_changed(note, track, 0.0, 0.5)

    assert window.move_note_calls == [(track, note, 0.5)]
    assert window.oscilloscope_refresh_calls == 0
    assert window.refresh_calls == [True]


def test_on_track_clicked_updates_entry_target_track_selection():
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)

    window.on_track_clicked(track)

    assert window.selected_track is track
    assert window.unified_editor.selected_track is track
    assert window.sequence_widget.highlighted_tracks == [track]
    assert window.sequence_widget.selected_track_notes_calls == [track]
    assert window.property_panel.current_track is track


def test_on_note_selected_updates_entry_target_track_selection():
    window = FakeEditorWindow()
    track = Track(name="Lead", track_type=TrackType.NOTE_TRACK)
    note = Note(pitch=60, start_time=0.0, duration=0.25)

    window.on_note_selected(note, track)

    assert window.selected_track is track
    assert window.unified_editor.selected_track is track
    assert window.sequence_widget.highlighted_tracks == [track]
    assert window.property_panel.current_note is note
    assert window.property_panel.current_track is track
