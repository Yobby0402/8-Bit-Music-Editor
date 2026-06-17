"""Background worker objects for long-running UI tasks."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from core.llm_client import chat_completion
from core.models import Project, WaveformType
from core.project_service import import_midi_document
from core.sequencer import prepare_playback_plan


class MidiImportWorker(QObject):
    """Import a MIDI file off the UI thread."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(
        self,
        file_path: str,
        default_waveform: WaveformType,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self.default_waveform = default_waveform

    @pyqtSlot()
    def run(self) -> None:
        """Run the blocking MIDI import workflow."""
        try:
            result = import_midi_document(
                self.file_path,
                default_waveform=self.default_waveform,
                snap_to_beat=False,
                allow_overlap=True,
            )
        except Exception as exc:  # pragma: no cover - exercised via signal flow
            self.failed.emit(exc)
            return

        self.finished.emit(result)


class PlaybackPrepareWorker(QObject):
    """Render playback audio off the UI thread before starting pygame."""

    finished = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(
        self,
        project: Project,
        sample_rate: int,
        *,
        start_time: float = 0.0,
        loop: bool = False,
        loop_end: float | None = None,
        playback_enabled_tracks: dict | None = None,
        playback_volume_ratios: dict | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.sample_rate = sample_rate
        self.start_time = start_time
        self.loop = loop
        self.loop_end = loop_end
        self.playback_enabled_tracks = dict(playback_enabled_tracks or {})
        self.playback_volume_ratios = dict(playback_volume_ratios or {})

    @pyqtSlot()
    def run(self) -> None:
        """Render the playback plan."""
        try:
            result = prepare_playback_plan(
                self.project,
                self.sample_rate,
                start_time=self.start_time,
                loop=self.loop,
                loop_end=self.loop_end,
                playback_enabled_tracks=self.playback_enabled_tracks,
                playback_volume_ratios=self.playback_volume_ratios,
            )
        except Exception as exc:  # pragma: no cover - exercised via signal flow
            self.failed.emit(exc)
            return

        self.finished.emit(result)


class LlmHttpThread(QThread):
    """
    在独立线程中同步调用 OpenAI 兼容 API（如 LM Studio）。

    必须 **重写 run()** 并在其中阻塞，而不能用「默认 QThread.exec + worker.run」：
    否则 httpx 会占满子线程事件循环，`quit()` 无法处理，主线程 `wait()` 会死锁，
    进而出现 ``QThread: Destroyed while thread is still running`` 与闪退。
    """

    success = pyqtSignal(str)
    failed = pyqtSignal(object)

    def __init__(
        self,
        base_url: str,
        model: str,
        messages: List[Dict[str, Any]],
        *,
        api_key: str = "",
        timeout_sec: float = 120.0,
        temperature: float = 0.7,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._model = model
        self._messages = messages
        self._api_key = api_key
        self._timeout_sec = timeout_sec
        self._temperature = temperature

    def run(self) -> None:
        """在线程中执行 HTTP 请求（阻塞直至完成或超时）。"""
        try:
            text = chat_completion(
                self._base_url,
                self._model,
                self._messages,
                api_key=self._api_key,
                timeout_sec=self._timeout_sec,
                temperature=self._temperature,
            )
        except Exception as exc:  # pragma: no cover - exercised via signal flow
            self.failed.emit(exc)
            return

        self.success.emit(text)
