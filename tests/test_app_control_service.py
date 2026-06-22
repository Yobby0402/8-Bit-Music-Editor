import json
import threading
import urllib.request

from PyQt5.QtCore import QCoreApplication, QObject, QTimer

from core.app_control_bridge import AppControlBridge
from core.app_control_http import AppControlHttpServer
from core.sequencer import Sequencer
from ui.app_control_service import MainWindowAppControlBridge, QtAppBridgeProxy


class Owner(QObject):
    def __init__(self):
        super().__init__()
        self.sequencer = Sequencer(initialize_audio=False)
        self.refresh_calls = []
        self.messages = []
        self.prepare_calls = []
        self.playback_start_offset = 0.0
        self.sequence_widget = type(
            "FakeSequenceWidget",
            (),
            {
                "playhead_time": 1.0,
                "selected_track": None,
                "selected_tracks": [],
                "selected_items": [],
            },
        )()

    def refresh_ui(self, preserve_selection=False, force_full_refresh=False):
        self.refresh_calls.append((preserve_selection, force_full_refresh))

    def statusBar(self):
        return self

    def showMessage(self, message):
        self.messages.append(message)

    def _has_pending_playback_prepare(self):
        return False

    def _request_playback_prepare(self, start_time, *, loop=False, completion_message=""):
        self.prepare_calls.append(
            {
                "start_time": start_time,
                "loop": loop,
                "completion_message": completion_message,
                "loop_end": self.sequencer.playback_state.loop_end,
            }
        )


def _app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_qt_app_bridge_proxy_runs_command_through_qt_event_loop():
    app = _app()
    owner = Owner()
    proxy = QtAppBridgeProxy(lambda: AppControlBridge(owner.sequencer), owner)
    result_holder = {}

    def worker():
        result_holder["result"] = proxy.insert_sfx("coin", start_beat=1.0)

    thread = threading.Thread(target=worker)
    thread.start()

    def poll():
        if thread.is_alive():
            QTimer.singleShot(10, poll)
        else:
            app.quit()

    QTimer.singleShot(10, poll)
    app.exec_()
    thread.join(timeout=2)

    assert result_holder["result"].ok is True
    assert len(owner.sequencer.project.tracks) == 1
    assert owner.refresh_calls == [(True, True)]
    assert owner.messages == ["Inserted SFX: Coin pickup"]


def test_qt_app_bridge_proxy_inserts_music_spec_and_refreshes_ui():
    app = _app()
    owner = Owner()
    proxy = QtAppBridgeProxy(lambda: AppControlBridge(owner.sequencer), owner)
    spec = AppControlBridge(owner.sequencer).generate_music_spec(length_bars=4, bpm=132).data
    result_holder = {}

    def worker():
        result_holder["result"] = proxy.insert_music_spec(spec, start_beat=0.0)

    thread = threading.Thread(target=worker)
    thread.start()

    def poll():
        if thread.is_alive():
            QTimer.singleShot(10, poll)
        else:
            app.quit()

    QTimer.singleShot(10, poll)
    app.exec_()
    thread.join(timeout=2)

    assert result_holder["result"].ok is True
    assert len(owner.sequencer.project.tracks) == 4
    assert owner.refresh_calls == [(True, True)]
    assert owner.messages == ["Inserted music spec: Epic 8bit Theme"]


def test_qt_app_bridge_proxy_can_cancel_file_export_without_bridge_call(tmp_path):
    owner = Owner()
    calls = []

    class RecordingBridge(AppControlBridge):
        def export_audio(self, *args, **kwargs):
            calls.append((args, kwargs))
            return super().export_audio(*args, **kwargs)

    proxy = QtAppBridgeProxy(lambda: RecordingBridge(owner.sequencer), owner)
    proxy._confirm_file_write = lambda *_args: False

    result = proxy.export_audio(str(tmp_path / "out.wav"))

    assert result.ok is False
    assert result.command == "export_audio"
    assert calls == []


def test_qt_app_bridge_proxy_updates_running_app_over_http():
    app = _app()
    owner = Owner()
    proxy = QtAppBridgeProxy(lambda: AppControlBridge(owner.sequencer), owner)
    server = AppControlHttpServer(lambda: proxy, port=0)
    result_holder = {}

    def worker():
        base = f"http://127.0.0.1:{server.bound_port}"
        request = urllib.request.Request(
            f"{base}/insert-sfx",
            data=json.dumps({"kind": "coin", "start_beat": 2.0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            result_holder["result"] = json.loads(response.read().decode("utf-8"))

    server.start()
    thread = threading.Thread(target=worker)
    thread.start()

    def poll():
        if thread.is_alive():
            QTimer.singleShot(10, poll)
        else:
            app.quit()

    try:
        QTimer.singleShot(10, poll)
        app.exec_()
        thread.join(timeout=2)
    finally:
        server.stop()

    assert result_holder["result"]["ok"] is True
    assert len(owner.sequencer.project.tracks) == 1
    assert owner.refresh_calls == [(True, True)]


def test_main_window_app_control_bridge_reports_ui_context():
    owner = Owner()
    bridge = MainWindowAppControlBridge(owner)

    result = bridge.get_ui_context()

    assert result.ok is True
    assert result.data["playhead_time"] == 1.0
    assert result.data["playhead_beat"] == 2.0
    assert result.data["selected_item_count"] == 0


def test_main_window_app_control_bridge_previews_range_through_window_prepare():
    owner = Owner()
    owner.sequencer.playback_state.loop_end = 99.0
    bridge = MainWindowAppControlBridge(owner)

    result = bridge.preview_playback(start_beat=2.0, end_beat=3.0, loop=True)

    assert result.ok is True
    assert owner.prepare_calls == [
        {
            "start_time": 1.0,
            "loop": True,
            "completion_message": "AI preview playback",
            "loop_end": 1.5,
        }
    ]
    assert owner.playback_start_offset == 1.0
    assert owner.sequencer.playback_state.loop_end == 99.0
