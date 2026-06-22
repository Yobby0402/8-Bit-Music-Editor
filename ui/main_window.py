"""
Main window module.
"""

from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QMainWindow

from core.score_library import ScoreLibrary
from core.sequencer import Sequencer
from ui.main_window_app_ops import MainWindowAppOpsMixin
from ui.app_control_service import AppControlService
from ui.main_window_editor_ops import MainWindowEditorOpsMixin
from ui.main_window_note_entry_ops import MainWindowNoteEntryOpsMixin
from ui.main_window_playback_ops import MainWindowPlaybackOpsMixin
from ui.main_window_project_ops import MainWindowProjectOpsMixin
from ui.main_window_refresh_ops import MainWindowRefreshOpsMixin
from ui.main_window_score_ops import MainWindowScoreOpsMixin
from ui.main_window_seed_ops import MainWindowSeedOpsMixin
from ui.main_window_shell_ops import MainWindowShellOpsMixin
from ui.main_window_sfx_ops import MainWindowSfxOpsMixin
from ui.main_window_theme_ops import MainWindowThemeOpsMixin
from ui.main_window_view_ops import MainWindowViewOpsMixin
from ui.settings_manager import get_settings_manager
from ui.shortcut_manager import get_shortcut_manager


class MainWindow(
    MainWindowProjectOpsMixin,
    MainWindowPlaybackOpsMixin,
    MainWindowViewOpsMixin,
    MainWindowScoreOpsMixin,
    MainWindowEditorOpsMixin,
    MainWindowNoteEntryOpsMixin,
    MainWindowAppOpsMixin,
    MainWindowSeedOpsMixin,
    MainWindowSfxOpsMixin,
    MainWindowThemeOpsMixin,
    MainWindowRefreshOpsMixin,
    MainWindowShellOpsMixin,
    QMainWindow,
):
    """Application main window."""

    def __init__(self):
        super().__init__()

        self.sequencer = Sequencer()
        self.current_file_path = None
        self.current_midi_file_path = None
        self.current_seed_style = None
        self.current_seed_variant = None
        self._midi_import_thread = None
        self._midi_import_worker = None
        self._midi_import_request_id = 0
        self._midi_import_progress = None
        self._playback_prepare_thread = None
        self._playback_prepare_worker = None
        self._playback_prepare_request_id = 0
        self._app_control_service = None

        self.settings = QSettings("8bit", "MusicMaker")
        self.shortcut_manager = get_shortcut_manager()
        self.settings_manager = get_settings_manager()
        self.score_library = ScoreLibrary()

        self._right_dock_width = None

        self.init_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_shortcuts()

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_playback_status)
        self.update_timer.start(self.settings_manager.get_playhead_refresh_interval())

        self.playback_start_time = None
        self.playback_start_offset = 0.0

        self._playback_settings_restart_timer = QTimer()
        self._playback_settings_restart_timer.setSingleShot(True)
        self._playback_settings_restart_timer.timeout.connect(
            self._restart_playback_from_current_position
        )
        self._playback_settings_restart_delay = 800

        self._start_app_control_service()

    def init_default_tracks(self):
        """Legacy hook kept for compatibility."""
        pass

    def _start_app_control_service(self):
        """Start the localhost control service used by MCP/app integrations."""
        try:
            self._app_control_service = AppControlService(self)
            self._app_control_service.start()
        except Exception as exc:
            self._app_control_service = None
            self.statusBar().showMessage(f"App control service unavailable: {exc}")
