"""MCP stdio server for the 8bit music app command bridge.

This module keeps the `mcp` package optional: importing it is only required when
creating or running the server. Unit tests can exercise registration with a fake
FastMCP-compatible object.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any

from core.app_control_bridge import AppCommandResult, AppControlBridge
from core.sequencer import Sequencer
from core.sfx_generator import SfxKind

DEFAULT_APP_CONTROL_URL = "http://127.0.0.1:8765"
MCP_TARGET_RUNNING_APP = "running_app"
MCP_TARGET_FALLBACK_MEMORY = "fallback_memory"


def command_result_to_dict(result: AppCommandResult) -> dict[str, Any]:
    """Convert an app command result to a JSON-ready MCP tool payload."""
    return asdict(result)


def create_default_bridge() -> AppControlBridge:
    """Create an isolated in-memory bridge for stdio MCP sessions."""
    return AppControlBridge(Sequencer(initialize_audio=False))


def with_mcp_target(payload: dict[str, Any], target: str) -> dict[str, Any]:
    """Mark whether an MCP result came from the live app or fallback bridge."""
    result = dict(payload)
    result["mcp_target"] = target
    return result


class LocalhostAppClient:
    """HTTP client for a running PyQt app control service."""

    def __init__(self, base_url: str = DEFAULT_APP_CONTROL_URL, timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    def request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            if payload is None:
                with urllib.request.urlopen(url, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))

            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read().decode("utf-8"))


class McpCommandRouter:
    """Route MCP calls to the running app, falling back to an in-memory bridge."""

    def __init__(
        self,
        bridge: AppControlBridge | None = None,
        app_client: LocalhostAppClient | None = None,
    ):
        self.bridge = bridge or create_default_bridge()
        self.app_client = app_client or LocalhostAppClient()

    def _fallback(self, method_name: str, *args, **kwargs) -> dict[str, Any]:
        method = getattr(self.bridge, method_name)
        return with_mcp_target(
            command_result_to_dict(method(*args, **kwargs)),
            MCP_TARGET_FALLBACK_MEMORY,
        )

    def _app_or_fallback(
        self,
        path: str,
        payload: dict[str, Any] | None,
        method_name: str,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        try:
            return with_mcp_target(
                self.app_client.request(path, payload),
                MCP_TARGET_RUNNING_APP,
            )
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return self._fallback(method_name, *args, **kwargs)

    def get_project_state(self) -> dict[str, Any]:
        return self._app_or_fallback("/project", None, "get_project_state")

    def get_ui_context(self) -> dict[str, Any]:
        return self._app_or_fallback("/ui-context", None, "get_ui_context")

    def get_operation_log(self, limit: int = 20) -> dict[str, Any]:
        return self._app_or_fallback(
            "/operation-log",
            {"limit": limit},
            "get_operation_log",
            limit,
        )

    def list_sfx_presets(self) -> dict[str, Any]:
        return self._app_or_fallback("/sfx-presets", None, "list_sfx_presets")

    def generate_sfx_spec(self, kind: SfxKind = "coin") -> dict[str, Any]:
        return self._app_or_fallback("/sfx-spec", {"kind": kind}, "generate_sfx_spec", kind)

    def generate_music_spec(
        self,
        style: str = "epic",
        length_bars: int = 8,
        bpm: float | None = None,
        key: str = "C",
        intensity: float = 0.85,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/music-spec",
            {
                "style": style,
                "length_bars": length_bars,
                "bpm": bpm,
                "key": key,
                "intensity": intensity,
            },
            "generate_music_spec",
            style=style,
            length_bars=length_bars,
            bpm=bpm,
            key=key,
            intensity=intensity,
        )

    def insert_sfx(
        self,
        kind: SfxKind = "coin",
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/insert-sfx",
            {
                "kind": kind,
                "start_beat": start_beat,
                "dry_run": dry_run,
                "auto_preview": auto_preview,
            },
            "insert_sfx",
            kind,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def insert_sfx_spec(
        self,
        spec: dict[str, Any],
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/insert-sfx-spec",
            {
                "spec": spec,
                "start_beat": start_beat,
                "dry_run": dry_run,
                "auto_preview": auto_preview,
            },
            "insert_sfx_spec",
            spec,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def insert_music_spec(
        self,
        spec: dict[str, Any],
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/insert-music-spec",
            {
                "spec": spec,
                "start_beat": start_beat,
                "dry_run": dry_run,
                "auto_preview": auto_preview,
            },
            "insert_music_spec",
            spec,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    def preview_playback(
        self,
        start_beat: float = 0.0,
        end_beat: float | None = None,
        loop: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/preview",
            {"start_beat": start_beat, "end_beat": end_beat, "loop": loop},
            "preview_playback",
            start_beat=start_beat,
            end_beat=end_beat,
            loop=loop,
        )

    def stop_playback(self) -> dict[str, Any]:
        return self._app_or_fallback("/stop-playback", {}, "stop_playback")

    def export_audio(
        self,
        file_path: str,
        format: str = "wav",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/export-audio",
            {
                "file_path": file_path,
                "format": format,
                "overwrite": overwrite,
                "dry_run": dry_run,
            },
            "export_audio",
            file_path,
            format=format,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    def export_audio_range(
        self,
        file_path: str,
        start_beat: float,
        end_beat: float,
        format: str = "wav",
        sfx_only: bool = False,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return self._app_or_fallback(
            "/export-audio-range",
            {
                "file_path": file_path,
                "start_beat": start_beat,
                "end_beat": end_beat,
                "format": format,
                "sfx_only": sfx_only,
                "overwrite": overwrite,
                "dry_run": dry_run,
            },
            "export_audio_range",
            file_path,
            start_beat=start_beat,
            end_beat=end_beat,
            format=format,
            sfx_only=sfx_only,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    def undo(self) -> dict[str, Any]:
        return self._app_or_fallback("/undo", {}, "undo")


def register_mcp_handlers(
    mcp,
    bridge: AppControlBridge | None = None,
    *,
    router: McpCommandRouter | None = None,
    app_client: LocalhostAppClient | None = None,
):
    """Register MCP tools/resources on a FastMCP-like server object."""
    router = router or McpCommandRouter(bridge, app_client)

    @mcp.tool()
    def eightbit_get_project() -> dict[str, Any]:
        """Return the current 8bit project summary."""
        return router.get_project_state()

    @mcp.tool()
    def eightbit_get_ui_context() -> dict[str, Any]:
        """Return current app playhead, selection, and playback context."""
        return router.get_ui_context()

    @mcp.tool()
    def eightbit_get_operation_log(limit: int = 20) -> dict[str, Any]:
        """Return recent MCP/app-control operations."""
        return router.get_operation_log(limit)

    @mcp.tool()
    def eightbit_list_sfx_presets() -> dict[str, Any]:
        """List supported 8bit sound-effect presets."""
        return router.list_sfx_presets()

    @mcp.tool()
    def eightbit_generate_sfx(kind: SfxKind = "coin") -> dict[str, Any]:
        """Return a structured 8bit SFX spec without mutating the project."""
        return router.generate_sfx_spec(kind)

    @mcp.tool()
    def eightbit_generate_music(
        style: str = "epic",
        length_bars: int = 8,
        bpm: float | None = None,
        key: str = "C",
        intensity: float = 0.85,
    ) -> dict[str, Any]:
        """Return a structured multi-track 8bit music spec without mutating the project."""
        return router.generate_music_spec(
            style=style,
            length_bars=length_bars,
            bpm=bpm,
            key=key,
            intensity=intensity,
        )

    @mcp.tool()
    def eightbit_insert_sfx(
        kind: SfxKind = "coin",
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        """Insert an 8bit SFX preset into the current project."""
        return router.insert_sfx(
            kind,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    @mcp.tool()
    def eightbit_insert_sfx_spec(
        spec: dict[str, Any],
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        """Insert a validated custom 8bit SFX spec into the current project."""
        return router.insert_sfx_spec(
            spec,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    @mcp.tool()
    def eightbit_insert_music_spec(
        spec: dict[str, Any],
        start_beat: float = 0.0,
        dry_run: bool = False,
        auto_preview: bool = False,
    ) -> dict[str, Any]:
        """Insert a validated multi-track 8bit music spec into the current project."""
        return router.insert_music_spec(
            spec,
            start_beat=start_beat,
            dry_run=dry_run,
            auto_preview=auto_preview,
        )

    @mcp.tool()
    def eightbit_preview_playback(
        start_beat: float = 0.0,
        end_beat: float | None = None,
        loop: bool = False,
    ) -> dict[str, Any]:
        """Start preview playback in the running 8bit app."""
        return router.preview_playback(
            start_beat=start_beat,
            end_beat=end_beat,
            loop=loop,
        )

    @mcp.tool()
    def eightbit_stop_playback() -> dict[str, Any]:
        """Stop playback in the running 8bit app."""
        return router.stop_playback()

    @mcp.tool()
    def eightbit_export_audio(
        file_path: str,
        format: str = "wav",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Export the current project audio to an absolute local path."""
        return router.export_audio(
            file_path,
            format=format,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    @mcp.tool()
    def eightbit_export_audio_range(
        file_path: str,
        start_beat: float,
        end_beat: float,
        format: str = "wav",
        sfx_only: bool = False,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Export a beat range from the current project audio."""
        return router.export_audio_range(
            file_path,
            start_beat=start_beat,
            end_beat=end_beat,
            format=format,
            sfx_only=sfx_only,
            overwrite=overwrite,
            dry_run=dry_run,
        )

    @mcp.tool()
    def eightbit_undo() -> dict[str, Any]:
        """Undo the previous app command."""
        return router.undo()

    @mcp.resource("eightbit://project")
    def eightbit_project_resource() -> str:
        """Read the current project summary as JSON."""
        return json.dumps(
            router.get_project_state(),
            ensure_ascii=False,
        )

    @mcp.resource("eightbit://sfx-presets")
    def eightbit_sfx_presets_resource() -> str:
        """Read available SFX presets as JSON."""
        return json.dumps(
            router.list_sfx_presets(),
            ensure_ascii=False,
        )

    return mcp


def create_mcp_server(bridge: AppControlBridge | None = None):
    """Create the real FastMCP server, importing the optional MCP SDK lazily."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            'MCP support requires the optional package: pip install "mcp[cli]>=1.27,<2"'
        ) from exc

    mcp = FastMCP("8bit Music App")
    return register_mcp_handlers(mcp, bridge)


def main() -> None:
    """Run the MCP server over stdio."""
    create_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
