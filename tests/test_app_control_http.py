import json
import urllib.request

from core.app_control_bridge import AppControlBridge
from core.app_control_http import AppControlHttpServer, dispatch_bridge_request
from core.sequencer import Sequencer


def test_dispatch_bridge_request_supports_dry_run_insert():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))

    result = dispatch_bridge_request(
        bridge,
        "/insert-sfx",
        {"kind": "coin", "start_beat": 1.0, "dry_run": True},
    )

    assert result.ok is True
    assert result.dry_run is True
    assert bridge.sequencer.project.tracks == []


def test_dispatch_bridge_request_supports_ui_context():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    bridge.sequencer.playback_state.current_time = 0.5

    result = dispatch_bridge_request(bridge, "/ui-context")

    assert result.ok is True
    assert result.command == "get_ui_context"
    assert result.data["playhead_time"] == 0.5


def test_dispatch_bridge_request_supports_operation_log():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    dispatch_bridge_request(bridge, "/sfx-presets")

    result = dispatch_bridge_request(bridge, "/operation-log", {"limit": 1})

    assert result.ok is True
    assert result.command == "get_operation_log"
    assert result.data["entries"][0]["command"] == "list_sfx_presets"


def test_dispatch_bridge_request_supports_custom_sfx_spec_dry_run():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))

    result = dispatch_bridge_request(
        bridge,
        "/insert-sfx-spec",
        {
            "start_beat": 1.0,
            "dry_run": True,
            "spec": {
                "label": "Zap",
                "notes": [{"pitch": 88, "start_beat": 0.0, "duration_beats": 0.1}],
            },
        },
    )

    assert result.ok is True
    assert result.command == "insert_sfx_spec"
    assert result.dry_run is True
    assert bridge.sequencer.project.tracks == []


def test_dispatch_bridge_request_rejects_unknown_path():
    result = dispatch_bridge_request(AppControlBridge(Sequencer(initialize_audio=False)), "/nope")

    assert result.ok is False
    assert result.data["path"] == "/nope"


def test_http_server_handles_project_and_insert_requests():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    server = AppControlHttpServer(lambda: bridge, port=0)
    server.start()
    try:
        base = f"http://127.0.0.1:{server.bound_port}"
        with urllib.request.urlopen(f"{base}/project", timeout=5) as response:
            project = json.loads(response.read().decode("utf-8"))
        assert project["ok"] is True
        assert project["data"]["track_count"] == 0

        request = urllib.request.Request(
            f"{base}/insert-sfx",
            data=json.dumps({"kind": "coin", "start_beat": 2.0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            inserted = json.loads(response.read().decode("utf-8"))

        assert inserted["ok"] is True
        assert inserted["changed"] is True
        assert len(bridge.sequencer.project.tracks) == 1
    finally:
        server.stop()


def test_dispatch_bridge_request_supports_stop_and_export_dry_run(tmp_path):
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    export_path = tmp_path / "out.wav"

    preview_result = dispatch_bridge_request(
        bridge,
        "/preview",
        {"start_beat": 2.0, "end_beat": 1.0},
    )
    stop_result = dispatch_bridge_request(bridge, "/stop-playback", {})
    export_result = dispatch_bridge_request(
        bridge,
        "/export-audio",
        {"file_path": str(export_path), "format": "wav", "dry_run": True},
    )
    range_export_result = dispatch_bridge_request(
        bridge,
        "/export-audio-range",
        {
            "file_path": str(export_path),
            "start_beat": 1.0,
            "end_beat": 1.5,
            "format": "wav",
            "sfx_only": True,
            "dry_run": True,
        },
    )

    assert preview_result.ok is False
    assert preview_result.command == "preview_playback"
    assert stop_result.ok is True
    assert stop_result.command == "stop_playback"
    assert export_result.ok is True
    assert export_result.dry_run is True
    assert range_export_result.ok is True
    assert range_export_result.command == "export_audio_range"
    assert range_export_result.dry_run is True
    assert range_export_result.data["sfx_only"] is True
    assert not export_path.exists()
