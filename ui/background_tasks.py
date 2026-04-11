"""Background worker objects for long-running UI tasks."""

from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

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
