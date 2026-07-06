from core.app_control_bridge import AppControlBridge
from core.sequencer import Sequencer
from mcp_server.eightbit_mcp_server import (
    LocalhostAppClient,
    McpCommandRouter,
    register_mcp_handlers,
)


class FakeMCP:
    def __init__(self):
        self.tools = {}
        self.resources = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def resource(self, uri):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator


class FailingAppClient:
    def request(self, _path, _payload=None):
        raise OSError("app offline")


class RecordingAppClient:
    def __init__(self):
        self.calls = []

    def request(self, path, payload=None):
        self.calls.append((path, payload))
        return {
            "command": "get_project_state",
            "ok": True,
            "message": "from app",
            "data": {"path": path, "payload": payload},
            "changed": False,
            "dry_run": False,
        }


def test_register_mcp_handlers_exposes_expected_tools_and_resources():
    fake = register_mcp_handlers(FakeMCP(), AppControlBridge(Sequencer(initialize_audio=False)))

    assert "eightbit_get_project" in fake.tools
    assert "eightbit_get_ui_context" in fake.tools
    assert "eightbit_get_operation_log" in fake.tools
    assert "eightbit_generate_music" in fake.tools
    assert "eightbit_insert_sfx" in fake.tools
    assert "eightbit_insert_sfx_spec" in fake.tools
    assert "eightbit_insert_music_spec" in fake.tools
    assert "eightbit_preview_playback" in fake.tools
    assert "eightbit_stop_playback" in fake.tools
    assert "eightbit_export_audio" in fake.tools
    assert "eightbit_export_audio_range" in fake.tools
    assert "eightbit_undo" in fake.tools
    assert "eightbit://project" in fake.resources
    assert "eightbit://sfx-presets" in fake.resources


def test_mcp_insert_sfx_tool_supports_dry_run_and_mutation():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    fake = register_mcp_handlers(FakeMCP(), bridge, app_client=FailingAppClient())

    dry_run = fake.tools["eightbit_insert_sfx"]("coin", 1.0, True)
    inserted = fake.tools["eightbit_insert_sfx"]("coin", 1.0, False)

    assert dry_run["dry_run"] is True
    assert dry_run["changed"] is False
    assert inserted["ok"] is True
    assert inserted["changed"] is True
    assert bridge.sequencer.project.tracks[0].notes[0].start_tick == bridge.sequencer.project.beats_to_ticks(1.0)


def test_mcp_insert_sfx_spec_tool_supports_dry_run_and_mutation():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    fake = register_mcp_handlers(FakeMCP(), bridge, app_client=FailingAppClient())
    spec = {
        "label": "Zap",
        "notes": [{"pitch": 88, "start_beat": 0.0, "duration_beats": 0.1}],
    }

    dry_run = fake.tools["eightbit_insert_sfx_spec"](spec, 1.0, True)
    inserted = fake.tools["eightbit_insert_sfx_spec"](spec, 1.0, False)

    assert dry_run["dry_run"] is True
    assert dry_run["changed"] is False
    assert inserted["ok"] is True
    assert inserted["changed"] is True
    assert len(bridge.sequencer.project.tracks[0].notes) == 1


def test_mcp_music_tools_support_generation_dry_run_and_mutation():
    bridge = AppControlBridge(Sequencer(initialize_audio=False))
    fake = register_mcp_handlers(FakeMCP(), bridge, app_client=FailingAppClient())

    generated = fake.tools["eightbit_generate_music"]("epic", 4, 132, "C", 0.9)
    dry_run = fake.tools["eightbit_insert_music_spec"](generated["data"], 2.0, True)
    inserted = fake.tools["eightbit_insert_music_spec"](generated["data"], 2.0, False)

    assert generated["ok"] is True
    assert len(generated["data"]["tracks"]) == 4
    assert dry_run["dry_run"] is True
    assert dry_run["changed"] is False
    assert inserted["ok"] is True
    assert inserted["changed"] is True
    assert len(bridge.sequencer.project.tracks) == 4
    assert bridge.sequencer.project.bpm == 132


def test_mcp_resources_return_json_strings():
    fake = register_mcp_handlers(
        FakeMCP(),
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client=FailingAppClient(),
    )

    project_json = fake.resources["eightbit://project"]()
    presets_json = fake.resources["eightbit://sfx-presets"]()

    assert '"command": "get_project_state"' in project_json
    assert '"coin"' in presets_json


def test_mcp_router_prefers_running_app_client_when_available():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )

    result = router.insert_sfx("coin", start_beat=2.0, dry_run=True)

    assert result["message"] == "from app"
    assert result["mcp_target"] == "running_app"
    assert app_client.calls == [
        (
            "/insert-sfx",
            {"kind": "coin", "start_beat": 2.0, "dry_run": True, "auto_preview": False},
        )
    ]


def test_mcp_router_routes_ui_context_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )

    result = router.get_ui_context()

    assert result["message"] == "from app"
    assert app_client.calls == [("/ui-context", None)]


def test_mcp_router_routes_operation_log_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )

    result = router.get_operation_log(limit=5)

    assert result["message"] == "from app"
    assert app_client.calls == [("/operation-log", {"limit": 5})]


def test_mcp_router_routes_preview_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )

    result = router.preview_playback(start_beat=1.0, end_beat=1.5, loop=True)

    assert result["message"] == "from app"
    assert app_client.calls == [
        (
            "/preview",
            {"start_beat": 1.0, "end_beat": 1.5, "loop": True},
        )
    ]


def test_mcp_router_routes_custom_sfx_spec_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )
    spec = {"label": "Zap", "notes": [{"pitch": 88, "start_beat": 0.0, "duration_beats": 0.1}]}

    result = router.insert_sfx_spec(spec, start_beat=1.0, dry_run=True, auto_preview=True)

    assert result["message"] == "from app"
    assert app_client.calls == [
        (
            "/insert-sfx-spec",
            {"spec": spec, "start_beat": 1.0, "dry_run": True, "auto_preview": True},
        )
    ]


def test_mcp_router_routes_music_generation_and_insert_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )
    spec = {"label": "Theme", "tracks": [{"name": "Lead", "notes": [{"pitch": 72}]}]}

    generated = router.generate_music_spec(style="epic", length_bars=4, bpm=132, key="D")
    inserted = router.insert_music_spec(spec, start_beat=1.0, dry_run=True, auto_preview=True)

    assert generated["message"] == "from app"
    assert inserted["message"] == "from app"
    assert app_client.calls == [
        (
            "/music-spec",
            {
                "style": "epic",
                "length_bars": 4,
                "bpm": 132,
                "key": "D",
                "intensity": 0.85,
            },
        ),
        (
            "/insert-music-spec",
            {"spec": spec, "start_beat": 1.0, "dry_run": True, "auto_preview": True},
        ),
    ]


def test_mcp_router_routes_range_export_to_running_app_client():
    app_client = RecordingAppClient()
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        app_client,
    )

    result = router.export_audio_range(
        "C:/tmp/coin.wav",
        start_beat=1.0,
        end_beat=1.5,
        sfx_only=True,
        dry_run=True,
    )

    assert result["message"] == "from app"
    assert app_client.calls == [
        (
            "/export-audio-range",
            {
                "file_path": "C:/tmp/coin.wav",
                "start_beat": 1.0,
                "end_beat": 1.5,
                "format": "wav",
                "sfx_only": True,
                "overwrite": False,
                "dry_run": True,
            },
        )
    ]


def test_mcp_router_falls_back_when_app_client_is_unavailable():
    router = McpCommandRouter(
        AppControlBridge(Sequencer(initialize_audio=False)),
        FailingAppClient(),
    )

    result = router.stop_playback()

    assert result["ok"] is True
    assert result["command"] == "stop_playback"
    assert result["mcp_target"] == "fallback_memory"


def test_localhost_app_client_returns_json_error_without_fallback():
    class BrokenBridge:
        def get_project_state(self):
            raise RuntimeError("preview failed")

    from core.app_control_http import AppControlHttpServer

    fallback_bridge = AppControlBridge(Sequencer(initialize_audio=False))
    server = AppControlHttpServer(lambda: BrokenBridge(), port=0)
    server.start()
    try:
        router = McpCommandRouter(
            fallback_bridge,
            LocalhostAppClient(f"http://127.0.0.1:{server.bound_port}", timeout=2),
        )
        result = router.get_project_state()

        assert result["ok"] is False
        assert result["command"] == "app_control_error"
        assert result["mcp_target"] == "running_app"
        assert result["data"]["path"] == "/project"
        assert fallback_bridge.sequencer.project.tracks == []
    finally:
        server.stop()
