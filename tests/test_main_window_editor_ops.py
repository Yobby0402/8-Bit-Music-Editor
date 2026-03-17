from types import SimpleNamespace

from core.models import Note, Track, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType
from ui.main_window_editor_ops import (
    build_batch_note_property_updates,
    build_single_note_property_updates,
    build_track_multi_select_message,
    count_track_items,
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
