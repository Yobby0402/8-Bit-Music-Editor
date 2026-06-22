"""Localhost HTTP transport for AppControlBridge commands."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from core.app_control_bridge import AppCommandResult, AppControlBridge

JsonDict = dict[str, object]


def result_to_json_dict(result: AppCommandResult) -> JsonDict:
    """Convert a bridge result to a JSON-ready dictionary."""
    return asdict(result)


def dispatch_bridge_request(
    bridge: AppControlBridge,
    path: str,
    payload: JsonDict | None = None,
) -> AppCommandResult:
    """Dispatch a local HTTP request to an AppControlBridge command."""
    payload = dict(payload or {})

    if path == "/project":
        return bridge.get_project_state()
    if path == "/ui-context":
        return bridge.get_ui_context()
    if path == "/operation-log":
        return bridge.get_operation_log(int(payload.get("limit", 20)))
    if path == "/sfx-presets":
        return bridge.list_sfx_presets()
    if path == "/sfx-spec":
        return bridge.generate_sfx_spec(str(payload.get("kind", "coin")))
    if path == "/music-spec":
        bpm_payload = payload.get("bpm")
        return bridge.generate_music_spec(
            style=str(payload.get("style", "epic")),
            length_bars=int(payload.get("length_bars", 8)),
            bpm=None if bpm_payload is None else float(bpm_payload),
            key=str(payload.get("key", "C")),
            intensity=float(payload.get("intensity", 0.85)),
        )
    if path == "/insert-sfx":
        return bridge.insert_sfx(
            str(payload.get("kind", "coin")),
            start_beat=float(payload.get("start_beat", 0.0)),
            dry_run=bool(payload.get("dry_run", False)),
            auto_preview=bool(payload.get("auto_preview", False)),
        )
    if path == "/insert-sfx-spec":
        spec_payload = payload.get("spec", {})
        if not isinstance(spec_payload, dict):
            spec_payload = {}
        return bridge.insert_sfx_spec(
            spec_payload,
            start_beat=float(payload.get("start_beat", 0.0)),
            dry_run=bool(payload.get("dry_run", False)),
            auto_preview=bool(payload.get("auto_preview", False)),
        )
    if path == "/insert-music-spec":
        spec_payload = payload.get("spec", {})
        if not isinstance(spec_payload, dict):
            spec_payload = {}
        return bridge.insert_music_spec(
            spec_payload,
            start_beat=float(payload.get("start_beat", 0.0)),
            dry_run=bool(payload.get("dry_run", False)),
            auto_preview=bool(payload.get("auto_preview", False)),
        )
    if path == "/preview":
        end_beat = payload.get("end_beat")
        return bridge.preview_playback(
            start_beat=float(payload.get("start_beat", 0.0)),
            end_beat=None if end_beat is None else float(end_beat),
            loop=bool(payload.get("loop", False)),
        )
    if path == "/stop-playback":
        return bridge.stop_playback()
    if path == "/export-audio":
        return bridge.export_audio(
            str(payload.get("file_path", "")),
            format=str(payload.get("format", "wav")),
            overwrite=bool(payload.get("overwrite", False)),
            dry_run=bool(payload.get("dry_run", False)),
        )
    if path == "/export-audio-range":
        return bridge.export_audio_range(
            str(payload.get("file_path", "")),
            start_beat=float(payload.get("start_beat", 0.0)),
            end_beat=float(payload.get("end_beat", 0.0)),
            format=str(payload.get("format", "wav")),
            sfx_only=bool(payload.get("sfx_only", False)),
            overwrite=bool(payload.get("overwrite", False)),
            dry_run=bool(payload.get("dry_run", False)),
        )
    if path == "/undo":
        return bridge.undo()

    return AppCommandResult(
        command="get_project_state",
        ok=False,
        message=f"Unknown control path: {path}",
        data={"path": path},
    )


class AppControlHttpServer:
    """Small localhost-only HTTP server for controlling the running app."""

    def __init__(
        self,
        bridge_factory: Callable[[], AppControlBridge],
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.bridge_factory = bridge_factory
        self.host = host
        self.port = int(port)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    @property
    def bound_port(self) -> int:
        if self._server is None:
            return self.port
        return int(self._server.server_address[1])

    def start(self) -> None:
        if self.is_running:
            return

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._handle_json(None)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0") or 0)
                body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    payload = json.loads(body.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    self._send_json(400, {"ok": False, "message": "Invalid JSON"})
                    return
                if not isinstance(payload, dict):
                    self._send_json(400, {"ok": False, "message": "JSON body must be an object"})
                    return
                self._handle_json(payload)

            def log_message(self, _format: str, *_args) -> None:
                return

            def _handle_json(self, payload: JsonDict | None) -> None:
                try:
                    result = dispatch_bridge_request(owner.bridge_factory(), self.path, payload)
                    status = 200 if result.ok else 404
                except Exception as exc:
                    result = AppCommandResult(
                        command="app_control_error",
                        ok=False,
                        message=f"App-control request failed: {exc}",
                        data={"path": self.path},
                    )
                    status = 500
                self._send_json(status, result_to_json_dict(result))

            def _send_json(self, status: int, payload: JsonDict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="8bit-app-control-http",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
