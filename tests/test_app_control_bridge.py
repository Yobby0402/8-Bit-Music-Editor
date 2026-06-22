from pathlib import Path
from threading import Event, Thread

from core.app_control_bridge import (
    AppControlBridge,
    sfx_spec_to_dict,
    summarize_playback_context,
    summarize_project,
)
from core.models import TrackRole, TrackType
from core.sequencer import Sequencer


class RecordingSequencer(Sequencer):
    def __init__(self):
        super().__init__(initialize_audio=False)
        self.play_calls = []

    def play(self, start_time: float = 0.0, loop: bool = False, end_time: float | None = None) -> bool:
        self.play_calls.append((start_time, loop, end_time))
        return True


def test_summarize_project_includes_track_counts():
    sequencer = Sequencer(initialize_audio=False)
    bridge = AppControlBridge(sequencer)

    bridge.insert_sfx("coin", start_beat=0.0)
    summary = summarize_project(sequencer.project)

    assert summary["track_count"] == 1
    assert summary["tracks"][0]["role"] == TrackRole.EFFECT.value
    assert summary["tracks"][0]["note_count"] == 3


def test_list_sfx_presets_result_is_json_ready():
    result = AppControlBridge(Sequencer(initialize_audio=False)).list_sfx_presets()

    assert result.ok is True
    assert "coin" in result.data["presets"]
    assert result.changed is False


def test_get_ui_context_returns_playback_context():
    sequencer = Sequencer(initialize_audio=False)
    sequencer.playback_state.current_time = 1.25

    result = AppControlBridge(sequencer).get_ui_context()
    summary = summarize_playback_context(sequencer)

    assert result.ok is True
    assert result.command == "get_ui_context"
    assert result.data == summary
    assert result.data["playhead_time"] == 1.25


def test_generate_sfx_spec_result_is_json_ready():
    data = sfx_spec_to_dict("jump")

    assert data["kind"] == "jump"
    assert data["notes"][0]["waveform"] == "square"
    assert data["notes"][0]["adsr"]["attack"] >= 0.0
    assert data["filter_params"]["enabled"] is True


def test_generate_music_spec_result_is_json_ready_multi_track():
    result = AppControlBridge(Sequencer(initialize_audio=False)).generate_music_spec(
        style="epic",
        length_bars=8,
        bpm=136,
        key="C",
    )

    assert result.ok is True
    assert result.command == "generate_music_spec"
    assert result.data["kind"] == "epic_music"
    assert result.data["bpm"] == 136
    assert len(result.data["tracks"]) == 4
    assert result.data["tracks"][0]["role"] == "melody"
    assert result.data["tracks"][3]["track_type"] == "drum"


def test_insert_sfx_dry_run_does_not_mutate_project():
    sequencer = Sequencer(initialize_audio=False)

    result = AppControlBridge(sequencer).insert_sfx("coin", start_beat=1.0, dry_run=True)

    assert result.ok is True
    assert result.dry_run is True
    assert result.changed is False
    assert result.data["created_track"] is True
    assert result.data["track_index"] == 0
    assert sequencer.project.tracks == []


def test_insert_sfx_mutates_project_and_can_undo():
    sequencer = Sequencer(initialize_audio=False)
    bridge = AppControlBridge(sequencer)

    result = bridge.insert_sfx("coin", start_beat=1.0)

    assert result.changed is True
    assert len(sequencer.project.tracks) == 1
    track = sequencer.project.tracks[0]
    assert track.role == TrackRole.EFFECT
    assert len(track.notes) == 3
    assert track.notes[0].start_tick == sequencer.project.beats_to_ticks(1.0)
    assert track.delay_params is not None
    assert track.delay_params.enabled is True

    undo_result = bridge.undo()

    assert undo_result.ok is True
    assert undo_result.changed is True
    assert sequencer.project.tracks == []


def test_insert_sfx_updates_existing_sfx_track_effects_and_undoes():
    sequencer = Sequencer(initialize_audio=False)
    bridge = AppControlBridge(sequencer)
    bridge.insert_sfx("coin", start_beat=0.0)
    track = sequencer.project.tracks[0]

    result = bridge.insert_sfx("laser", start_beat=1.0)

    assert result.ok is True
    assert result.data["track_effects"] == ["filter_params", "vibrato_params"]
    assert track.filter_params is not None
    assert track.filter_params.enabled is True
    assert track.vibrato_params is not None
    assert track.vibrato_params.enabled is True

    undo_result = bridge.undo()

    assert undo_result.ok is True
    assert track.filter_params is None
    assert track.vibrato_params is None


def test_insert_sfx_spec_supports_ai_payload_dry_run_and_mutation():
    sequencer = Sequencer(initialize_audio=False)
    bridge = AppControlBridge(sequencer)
    spec = {
        "kind": "custom_coin",
        "label": "Custom coin",
        "notes": [
            {"pitch": 84, "start_beat": 0.0, "duration_beats": 0.1, "waveform": "square"},
            {"pitch": 96, "start_beat": 0.1, "duration_beats": 0.12, "waveform": "triangle"},
        ],
    }

    dry_run = bridge.insert_sfx_spec(spec, start_beat=4.0, dry_run=True)
    inserted = bridge.insert_sfx_spec(spec, start_beat=4.0)

    assert dry_run.ok is True
    assert dry_run.dry_run is True
    assert dry_run.changed is False
    assert inserted.ok is True
    assert inserted.changed is True
    assert inserted.data["kind"] == "custom_coin"
    assert inserted.data["note_count"] == 2
    assert sequencer.project.tracks[0].notes[0].start_tick == sequencer.project.beats_to_ticks(4.0)


def test_insert_sfx_spec_can_request_auto_preview():
    sequencer = RecordingSequencer()
    bridge = AppControlBridge(sequencer)
    spec = {
        "kind": "custom_coin",
        "label": "Custom coin",
        "notes": [{"pitch": 84, "start_beat": 0.0, "duration_beats": 0.5}],
    }

    result = bridge.insert_sfx_spec(spec, start_beat=2.0, auto_preview=True)

    assert result.ok is True
    assert sequencer.play_calls == [(1.0, False, 1.25)]
    assert result.data["preview_result"]["start_beat"] == 2.0


def test_insert_music_spec_supports_dry_run_mutation_and_undo():
    sequencer = Sequencer(initialize_audio=False)
    sequencer.project.bpm = 120
    bridge = AppControlBridge(sequencer)
    spec = bridge.generate_music_spec(style="epic", length_bars=4, bpm=132).data

    dry_run = bridge.insert_music_spec(spec, start_beat=8.0, dry_run=True)

    assert dry_run.ok is True
    assert dry_run.dry_run is True
    assert dry_run.changed is False
    assert sequencer.project.tracks == []

    inserted = bridge.insert_music_spec(spec, start_beat=8.0)

    assert inserted.ok is True
    assert inserted.changed is True
    assert inserted.data["track_count"] == 4
    assert inserted.data["note_count"] > 0
    assert inserted.data["drum_event_count"] > 0
    assert sequencer.project.bpm == 132
    assert [track.role for track in sequencer.project.tracks[:3]] == [
        TrackRole.MELODY,
        TrackRole.BASS,
        TrackRole.HARMONY,
    ]
    assert sequencer.project.tracks[3].track_type == TrackType.DRUM_TRACK
    assert sequencer.project.tracks[0].notes[0].start_tick == sequencer.project.beats_to_ticks(8.0)

    undo = bridge.undo()

    assert undo.ok is True
    assert sequencer.project.tracks == []
    assert sequencer.project.bpm == 120


def test_insert_music_spec_can_request_auto_preview():
    sequencer = RecordingSequencer()
    bridge = AppControlBridge(sequencer)
    spec = bridge.generate_music_spec(style="epic", length_bars=4, bpm=120).data

    result = bridge.insert_music_spec(spec, start_beat=4.0, auto_preview=True)

    assert result.ok is True
    assert sequencer.play_calls == [(2.0, False, 10.0)]
    assert result.data["preview_result"]["end_beat"] == 20.0


def test_operation_log_records_recent_commands():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))

    bridge.list_sfx_presets()
    bridge.insert_sfx("coin", dry_run=True)
    result = bridge.get_operation_log(limit=2)

    assert result.ok is True
    assert [entry["command"] for entry in result.data["entries"]] == [
        "list_sfx_presets",
        "insert_sfx",
    ]


def test_busy_lock_rejects_concurrent_mutation():
    sequencer = Sequencer(initialize_audio=False)
    bridge = AppControlBridge(sequencer)
    lock = sequencer._app_control_lock
    acquired = Event()
    release = Event()

    def hold_lock():
        lock.acquire()
        acquired.set()
        release.wait(timeout=5.0)
        lock.release()

    thread = Thread(target=hold_lock)
    thread.start()
    acquired.wait(timeout=2.0)
    try:
        result = bridge.insert_sfx("coin")
    finally:
        release.set()
        thread.join(timeout=2.0)

    assert result.ok is False
    assert "already running" in result.message
    assert sequencer.project.tracks == []


def test_insert_sfx_spec_rejects_invalid_payload():
    result = AppControlBridge(Sequencer(initialize_audio=False)).insert_sfx_spec({})

    assert result.ok is False
    assert result.command == "insert_sfx_spec"
    assert "Invalid SFX spec" in result.message


def test_undo_reports_noop_when_history_is_empty():
    result = AppControlBridge(Sequencer(initialize_audio=False)).undo()

    assert result.ok is False
    assert result.changed is False


def test_stop_playback_reports_success():
    result = AppControlBridge(Sequencer(initialize_audio=False)).stop_playback()

    assert result.ok is True
    assert result.command == "stop_playback"


def test_preview_playback_converts_beats_to_seconds():
    sequencer = RecordingSequencer()
    result = AppControlBridge(sequencer).preview_playback(
        start_beat=2.0,
        end_beat=3.0,
        loop=True,
    )

    assert result.ok is True
    assert sequencer.play_calls == [(1.0, True, 1.5)]
    assert result.data["start_time"] == 1.0
    assert result.data["end_time"] == 1.5


def test_preview_playback_rejects_invalid_range():
    result = AppControlBridge(Sequencer(initialize_audio=False)).preview_playback(
        start_beat=2.0,
        end_beat=1.0,
    )

    assert result.ok is False
    assert "after start" in result.message


def test_export_audio_rejects_relative_path():
    result = AppControlBridge(Sequencer(initialize_audio=False)).export_audio("relative.wav")

    assert result.ok is False
    assert "absolute" in result.message


def test_export_audio_dry_run_does_not_create_file(tmp_path: Path):
    target = tmp_path / "coin.wav"
    result = AppControlBridge(Sequencer(initialize_audio=False)).export_audio(
        str(target),
        dry_run=True,
    )

    assert result.ok is True
    assert result.dry_run is True
    assert not target.exists()


def test_export_audio_range_dry_run_converts_beats_to_seconds(tmp_path: Path):
    target = tmp_path / "coin-range.wav"
    result = AppControlBridge(Sequencer(initialize_audio=False)).export_audio_range(
        str(target),
        start_beat=2.0,
        end_beat=3.0,
        sfx_only=True,
        dry_run=True,
    )

    assert result.ok is True
    assert result.command == "export_audio_range"
    assert result.dry_run is True
    assert result.data["start_time"] == 1.0
    assert result.data["end_time"] == 1.5
    assert result.data["sfx_only"] is True
    assert not target.exists()


def test_export_audio_range_rejects_invalid_range(tmp_path: Path):
    result = AppControlBridge(Sequencer(initialize_audio=False)).export_audio_range(
        str(tmp_path / "bad.wav"),
        start_beat=2.0,
        end_beat=2.0,
    )

    assert result.ok is False
    assert result.command == "export_audio_range"
    assert "after start" in result.message
