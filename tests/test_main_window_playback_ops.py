from types import SimpleNamespace

from ui.main_window_playback_ops import MainWindowPlaybackOpsMixin


class FakeStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message):
        self.messages.append(message)


class FakeProgressBar:
    def __init__(self):
        self.is_dragging = False
        self.current_time = None

    def set_current_time(self, current_time):
        self.current_time = current_time


class FakeSequenceWidget:
    def __init__(self):
        self.playhead_time = 0.0
        self.progress_bar = FakeProgressBar()

    def set_playhead_time(self, current_time):
        self.playhead_time = current_time


class FakeUnifiedEditor:
    def __init__(self, values):
        self.preview_enabled = False
        self.values = values

    def set_preview_enabled(self, enabled):
        self.preview_enabled = enabled
        self.values.append(enabled)


class FakeSequencer:
    def __init__(self):
        self.project = SimpleNamespace(bpm=120, original_bpm=120, bpm_segments=[])
        self.playback_state = SimpleNamespace(
            is_playing=False,
            current_time=0.0,
            end_time=10.0,
        )
        self.pause_calls = 0
        self.stop_calls = 0

    def pause(self):
        self.pause_calls += 1
        self.playback_state.is_playing = False

    def stop(self):
        self.stop_calls += 1
        self.playback_state.is_playing = False
        self.playback_state.current_time = 0.0


class FakePlaybackWindow(MainWindowPlaybackOpsMixin):
    def __init__(self):
        self.sequencer = FakeSequencer()
        self.sequence_widget = FakeSequenceWidget()
        self.play_stop_button = SimpleNamespace(
            icon=None,
            tooltip=None,
            setIcon=lambda icon: setattr(self.play_stop_button, "icon", icon),
            setToolTip=lambda text: setattr(self.play_stop_button, "tooltip", text),
        )
        self.playback_start_time = None
        self.playback_start_offset = 0.0
        self.preview_enabled_values = []
        self.unified_editor = FakeUnifiedEditor(self.preview_enabled_values)
        self.hover_preview_enabled = True
        self.oscilloscope_values = []
        self.status_bar = FakeStatusBar()

    def _has_pending_playback_prepare(self):
        return False

    def _set_oscilloscope_playing(self, is_playing):
        self.oscilloscope_values.append(is_playing)

    def statusBar(self):
        return self.status_bar

    def style(self):
        return SimpleNamespace(standardIcon=lambda icon_name: icon_name)


def test_pause_preserves_current_playhead(monkeypatch):
    window = FakePlaybackWindow()
    window.sequencer.playback_state.is_playing = True
    window.playback_start_time = 10.0
    window.playback_start_offset = 2.0
    monkeypatch.setattr("ui.main_window_playback_ops.time.time", lambda: 13.25)

    window.pause()

    assert window.sequencer.pause_calls == 1
    assert window.sequencer.stop_calls == 0
    assert window.sequence_widget.playhead_time == 5.25
    assert window.sequence_widget.progress_bar.current_time == 5.25
    assert window.sequencer.playback_state.current_time == 5.25
    assert window.playback_start_offset == 5.25
    assert window.playback_start_time is None
    assert window.preview_enabled_values[-1] is True
    assert window.status_bar.messages[-1] == "已暂停"


def test_stop_resets_playhead_to_start():
    window = FakePlaybackWindow()
    window.sequencer.playback_state.is_playing = True
    window.sequence_widget.playhead_time = 5.25

    window.stop()

    assert window.sequencer.stop_calls == 1
    assert window.sequence_widget.playhead_time == 0.0
    assert window.playback_start_time is None
    assert window.preview_enabled_values[-1] is True
    assert window.status_bar.messages[-1] == "已停止"


def test_hover_preview_toggle_disables_editor_preview():
    window = FakePlaybackWindow()

    window.set_hover_preview_enabled(False)

    assert window.hover_preview_enabled is False
    assert window.unified_editor.preview_enabled is False
    assert window.preview_enabled_values[-1] is False
    assert window.status_bar.messages[-1] == "悬停试听已关闭"


def test_pause_keeps_hover_preview_disabled(monkeypatch):
    window = FakePlaybackWindow()
    window.set_hover_preview_enabled(False)
    window.sequencer.playback_state.is_playing = True
    window.playback_start_time = 10.0
    window.playback_start_offset = 2.0
    monkeypatch.setattr("ui.main_window_playback_ops.time.time", lambda: 13.25)

    window.pause()

    assert window.preview_enabled_values[-1] is False
    assert window.unified_editor.preview_enabled is False
    assert window.status_bar.messages[-1] == "已暂停"


def test_stop_keeps_hover_preview_disabled():
    window = FakePlaybackWindow()
    window.set_hover_preview_enabled(False)
    window.sequencer.playback_state.is_playing = True

    window.stop()

    assert window.preview_enabled_values[-1] is False
    assert window.unified_editor.preview_enabled is False
    assert window.status_bar.messages[-1] == "已停止"
