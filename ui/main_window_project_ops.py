"""
主窗口中的项目文件打开、保存、导入、导出相关操作。
"""

import os
import sys
from time import perf_counter

from PyQt5.QtCore import Qt, QThread
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog

from app_info import APP_NAME
from core.project_service import (
    AudioExportDependencyError,
    EmptyAudioExportError,
    export_audio_document,
    export_midi_document,
    load_project_document,
    save_project_document,
)
from core.sequencer import Sequencer
from ui.background_tasks import MidiImportWorker
from ui.error_utils import show_error_with_console
from ui.main_window_file_ops import (
    EXPORT_FILE_FILTER,
    MIDI_OPEN_FILE_FILTER,
    OPEN_IMPORT_FILE_FILTER,
    PROJECT_OPEN_FILE_FILTER,
    detect_open_file_kind,
    resolve_export_target,
)
from ui.performance_utils import begin_profile_span, finish_profile_span

MIDI_IMPORT_UI_PROFILE_THRESHOLD_MS = 100.0


class MainWindowProjectOpsMixin:
    """承载 MainWindow 的文件打开、保存、导入、导出流程。"""

    def _begin_midi_import_profile(self, request_id: int, file_path: str) -> None:
        """Start tracking a background MIDI import request."""
        tokens = getattr(self, "_midi_import_profile_tokens", None)
        if tokens is None:
            tokens = {}
            self._midi_import_profile_tokens = tokens
        tokens[request_id] = begin_profile_span(
            self,
            "project.import_midi",
            source=os.path.basename(file_path),
        )

    def _finish_midi_import_profile(self, request_id: int, *, outcome: str) -> None:
        """Finish tracking a background MIDI import request."""
        tokens = getattr(self, "_midi_import_profile_tokens", None)
        if not tokens:
            return
        token = tokens.pop(request_id, None)
        finish_profile_span(self, token, outcome=outcome)

    def _log_midi_import_ui_profile(self, file_path: str, **stage_timings_ms: float) -> None:
        """Print a stage breakdown for slow UI-side MIDI import work."""
        total_ms = sum(stage_timings_ms.values())
        if total_ms < MIDI_IMPORT_UI_PROFILE_THRESHOLD_MS:
            return

        stage_parts = " ".join(
            f"{name}={elapsed_ms:.1f}ms"
            for name, elapsed_ms in stage_timings_ms.items()
        )
        project = getattr(self.sequencer, "project", None)
        tracks = getattr(project, "tracks", []) or []
        note_count = sum(len(getattr(track, "notes", [])) for track in tracks)
        print(
            "[PROFILE] project.import_midi_ui_apply "
            f"total={total_ms:.1f}ms "
            f"{stage_parts} "
            f"track_count={len(tracks)} "
            f"note_count={note_count} "
            f"source={os.path.basename(file_path)!r}"
        )

    def _update_file_name_display(self):
        """更新当前文件标签显示。"""
        if not hasattr(self, "file_name_label"):
            return

        if self.current_midi_file_path:
            file_name = os.path.basename(self.current_midi_file_path)
            self.file_name_label.setText(f"文件: {file_name}")
        elif self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
            self.file_name_label.setText(f"文件: {file_name}")
        else:
            self.file_name_label.setText("")

    def _sync_project_bpm_to_ui(self, bpm: float, *, refresh_sequence_widget: bool = True):
        """将项目 BPM 同步到主界面相关控件。"""
        project = getattr(self.sequencer, "project", None)
        if hasattr(self, "sequence_widget") and hasattr(self.sequence_widget, "set_project"):
            self.sequence_widget.set_project(project)
        if hasattr(self, "property_panel") and hasattr(self.property_panel, "set_project"):
            self.property_panel.set_project(project)
        self.sequencer.set_bpm(bpm)
        self.bpm_spinbox.blockSignals(True)
        self.bpm_spinbox.setValue(int(bpm))
        self.bpm_spinbox.blockSignals(False)
        self.sequence_widget.set_bpm(bpm, refresh=refresh_sequence_widget)
        self.unified_editor.set_bpm(bpm)
        self.property_panel.set_bpm(bpm)
        if hasattr(self, "oscilloscope_widget"):
            self.oscilloscope_widget.set_bpm(bpm)

    def _clear_project_panel_state(self):
        """清理属性面板中的项目相关状态。"""
        self.property_panel.set_track(None)
        self.property_panel.set_note(None, None)
        self.property_panel.set_notes([])

    def _reset_project_selection(self):
        """重置当前选中音符和音轨状态。"""
        self.selected_note = None
        self.selected_track = None
        if hasattr(self, "unified_editor"):
            self.unified_editor.set_selected_track(None)

    def _refresh_project_after_open(self):
        """项目打开后刷新主界面。"""
        self._sync_project_bpm_to_ui(
            float(self.sequencer.get_bpm()),
            refresh_sequence_widget=False,
        )
        self.refresh_ui(force_full_refresh=True)

    def _refresh_project_after_midi_import(self, project):
        """MIDI 导入后刷新主界面和关联面板。"""
        self._sync_project_bpm_to_ui(float(project.bpm), refresh_sequence_widget=False)
        self.refresh_ui(force_full_refresh=True)

    def new_project(self):
        """新建项目。"""
        if not self.check_unsaved_changes():
            return

        self.stop()
        self.sequencer = Sequencer()
        self.sequencer.playback_volume_ratios = {}
        self.current_file_path = None
        self.current_midi_file_path = None
        self.setWindowTitle(f"{APP_NAME} - 新建项目")
        self._update_file_name_display()
        self._clear_project_panel_state()
        self._reset_project_selection()
        self._sync_project_bpm_to_ui(
            float(self.sequencer.get_bpm()),
            refresh_sequence_widget=False,
        )
        self.refresh_ui()
        self.statusBar().showMessage("已创建新项目")

    def open_or_import_file(self):
        """打开或导入文件（根据文件类型自动判断）。"""
        if not self.check_unsaved_changes():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开/导入文件",
            "",
            OPEN_IMPORT_FILE_FILTER,
        )

        if not file_path:
            return

        file_kind = detect_open_file_kind(file_path)
        if file_kind == "project":
            self.open_project_file(file_path)
        elif file_kind == "midi":
            self.import_midi_file(file_path)
        else:
            QMessageBox.warning(self, "警告", f"不支持的文件类型: {file_path}")

    def open_project_file(self, file_path: str):
        """打开项目文件。"""
        try:
            progress = QProgressDialog("正在加载项目...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            QApplication.processEvents()

            progress.setLabelText("正在读取文件...")
            progress.setValue(10)
            QApplication.processEvents()

            progress.setLabelText("正在解析项目数据...")
            progress.setValue(30)
            QApplication.processEvents()

            self._clear_project_panel_state()

            progress.setLabelText("正在加载项目...")
            progress.setValue(50)
            QApplication.processEvents()

            load_result = load_project_document(file_path)
            project = load_result.project
            self.sequencer.set_project(project)
            self.current_file_path = load_result.current_file_path
            self.current_midi_file_path = load_result.current_midi_file_path
            self.setWindowTitle(f"{APP_NAME} - {project.name}")

            progress.setLabelText("正在更新界面...")
            progress.setValue(70)
            QApplication.processEvents()

            self._reset_project_selection()

            progress.setLabelText("正在刷新显示...")
            progress.setValue(90)
            QApplication.processEvents()

            self._refresh_project_after_open()

            progress.setValue(100)
            progress.close()

            self._update_file_name_display()
            self.statusBar().showMessage(f"已打开项目: {file_path}")
        except Exception as exc:
            error_msg = f"打开项目失败:\n{exc}"
            show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def open_project(self):
        """打开项目（保留以兼容旧代码）。"""
        if not self.check_unsaved_changes():
            return

        last_dir = self.settings.value("last_open_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开项目",
            last_dir,
            PROJECT_OPEN_FILE_FILTER,
        )

        if file_path:
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_open_directory", directory)
            self.open_project_file(file_path)

    def save_project(self):
        """保存项目。"""
        if self.current_file_path:
            self.save_project_to_file(self.current_file_path)
        else:
            self.export_file()

    def export_file(self):
        """导出文件（统一处理项目保存和音频导出）。"""
        last_dir = self.settings.value("last_save_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出文件",
            last_dir,
            EXPORT_FILE_FILTER,
        )

        if not file_path:
            return

        directory = os.path.dirname(file_path)
        self.settings.setValue("last_save_directory", directory)

        export_target = resolve_export_target(file_path, selected_filter)
        if export_target.kind == "project":
            self.save_project_to_file(export_target.file_path)
        elif export_target.kind == "midi":
            self.export_midi_to_file(export_target.file_path)
        else:
            self.export_audio_to_file(export_target.file_path, format=export_target.audio_format)

    def save_project_to_file(self, file_path: str):
        """保存项目到文件。"""
        try:
            save_result = save_project_document(self.sequencer.project, file_path)
            self.current_file_path = save_result.file_path
            self.current_midi_file_path = None
            self.setWindowTitle(f"{APP_NAME} - {self.sequencer.project.name}")
            self._update_file_name_display()
            self.statusBar().showMessage(f"项目已保存: {save_result.file_path}")
        except Exception as exc:
            error_msg = f"保存项目失败:\n{exc}"
            show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def export_midi_to_file(self, file_path: str):
        """导出 MIDI 文件。"""
        try:
            export_result = export_midi_document(self.sequencer.project, file_path)
            self.statusBar().showMessage(f"已导出MIDI: {export_result.file_path}")
            QMessageBox.information(self, "成功", f"MIDI文件已导出:\n{export_result.file_path}")
        except Exception as exc:
            error_msg = f"导出MIDI失败:\n{exc}"
            show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def export_audio_to_file(self, file_path: str, format: str = "wav"):
        """导出音频文件。"""
        try:
            export_result = export_audio_document(
                self.sequencer.project,
                self.sequencer.audio_engine,
                file_path,
                format=format,
            )
            format_label = export_result.format.upper()
            self.statusBar().showMessage(f"已导出{format_label}: {export_result.file_path}")
            QMessageBox.information(
                self,
                "成功",
                f"{format_label}文件已导出:\n{export_result.file_path}",
            )
        except EmptyAudioExportError:
            QMessageBox.warning(self, "警告", "项目中没有音频数据")
        except AudioExportDependencyError as exc:
            QMessageBox.warning(self, exc.title, exc.user_message)
        except ImportError as exc:
            QMessageBox.critical(self, "错误", f"导出失败:\n{exc}")
        except Exception as exc:
            error_msg = f"导出{format.upper()}失败:\n{exc}"
            show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def _close_midi_import_progress(self):
        """Close the active MIDI import progress dialog if one exists."""
        progress = getattr(self, "_midi_import_progress", None)
        if progress is None:
            return

        previous_signal_state = None
        if hasattr(progress, "blockSignals"):
            previous_signal_state = progress.blockSignals(True)
        try:
            progress.close()
            progress.deleteLater()
        finally:
            if previous_signal_state is not None:
                progress.blockSignals(previous_signal_state)
            self._midi_import_progress = None

    def _cleanup_midi_import_task(self, thread: QThread):
        """Release references after the background MIDI import completes."""
        if getattr(self, "_midi_import_thread", None) is not thread:
            return

        self._midi_import_thread = None
        self._midi_import_worker = None
        self._close_midi_import_progress()

    def _cancel_pending_midi_import(self, request_id: int):
        """Cancel the current MIDI import request result without killing the thread."""
        if request_id != getattr(self, "_midi_import_request_id", 0):
            return

        self._finish_midi_import_profile(request_id, outcome="cancelled")
        self._midi_import_request_id += 1
        self._close_midi_import_progress()
        self.statusBar().showMessage("已取消 MIDI 导入，正在等待后台任务收尾...")

    def _on_midi_import_finished(self, request_id: int, load_result, file_path: str):
        """Apply an asynchronously imported MIDI project to the UI."""
        if request_id != getattr(self, "_midi_import_request_id", 0):
            return

        stage_started_at = perf_counter()
        project = load_result.project
        self.sequencer.set_project(project)
        self.current_file_path = load_result.current_file_path
        self.current_midi_file_path = load_result.current_midi_file_path
        self.setWindowTitle(f"{APP_NAME} - {project.name}")
        apply_project_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self._reset_project_selection()
        reset_selection_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self._refresh_project_after_midi_import(project)
        refresh_project_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self._update_file_name_display()
        update_file_label_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.statusBar().showMessage(f"已导入MIDI: {file_path}")
        show_status_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        directory = os.path.dirname(file_path)
        self.settings.setValue("last_midi_directory", directory)
        persist_directory_ms = (perf_counter() - stage_started_at) * 1000.0

        self._finish_midi_import_profile(request_id, outcome="ok")
        self._log_midi_import_ui_profile(
            file_path,
            apply_project_ms=apply_project_ms,
            reset_selection_ms=reset_selection_ms,
            refresh_project_ms=refresh_project_ms,
            update_file_label_ms=update_file_label_ms,
            show_status_ms=show_status_ms,
            persist_directory_ms=persist_directory_ms,
        )

    def _on_midi_import_failed(self, request_id: int, exc: Exception):
        """Handle a failed asynchronous MIDI import."""
        if request_id != getattr(self, "_midi_import_request_id", 0):
            return

        self._finish_midi_import_profile(request_id, outcome="failed")
        error_msg = f"导入MIDI失败:\n{exc}"
        show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def import_midi_file(self, file_path: str):
        """导入 MIDI 文件。"""
        try:
            if not self.check_unsaved_changes():
                return
            if getattr(self, "_midi_import_thread", None) is not None:
                self.statusBar().showMessage("正在导入 MIDI，请稍候...")
                return

            self._clear_project_panel_state()
            default_waveform = self.unified_editor.selected_waveform
            request_id = getattr(self, "_midi_import_request_id", 0) + 1
            self._midi_import_request_id = request_id
            self._begin_midi_import_profile(request_id, file_path)

            progress = QProgressDialog("正在导入MIDI文件...", "取消", 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.setLabelText("正在解析 MIDI 数据，这可能需要一些时间...")
            progress.canceled.connect(
                lambda rid=request_id: self._cancel_pending_midi_import(rid)
            )
            self._midi_import_progress = progress

            thread = QThread(self)
            worker = MidiImportWorker(file_path, default_waveform)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(
                lambda load_result, rid=request_id, source=file_path: (
                    self._on_midi_import_finished(rid, load_result, source)
                )
            )
            worker.failed.connect(
                lambda exc, rid=request_id: self._on_midi_import_failed(rid, exc)
            )
            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(
                lambda current_thread=thread: self._cleanup_midi_import_task(current_thread)
            )

            self._midi_import_thread = thread
            self._midi_import_worker = worker
            progress.show()
            self.statusBar().showMessage("正在导入 MIDI...")
            thread.start()
        except Exception as exc:
            error_msg = f"导入MIDI失败:\n{exc}"
            show_error_with_console(self, "错误", error_msg, "critical", exc_info=sys.exc_info())

    def import_midi(self):
        """导入 MIDI 文件（保留以兼容旧代码）。"""
        last_dir = self.settings.value("last_midi_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = self.settings.value("last_open_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入MIDI",
            last_dir,
            MIDI_OPEN_FILE_FILTER,
        )

        if file_path:
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_open_directory", directory)
            self.settings.setValue("last_midi_directory", directory)
            self.import_midi_file(file_path)
