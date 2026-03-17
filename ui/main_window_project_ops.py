"""
主窗口中的项目文件打开、保存、导入、导出相关操作。
"""

import os
import sys
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QProgressDialog

from app_info import APP_NAME
from core.project_service import (
    AudioExportDependencyError,
    EmptyAudioExportError,
    export_audio_document,
    export_midi_document,
    import_midi_document,
    load_project_document,
    save_project_document,
)
from core.sequencer import Sequencer
from ui.error_utils import show_error_with_console
from ui.main_window_file_ops import (
    EXPORT_FILE_FILTER,
    MIDI_OPEN_FILE_FILTER,
    OPEN_IMPORT_FILE_FILTER,
    PROJECT_OPEN_FILE_FILTER,
    detect_open_file_kind,
    resolve_export_target,
)


class MainWindowProjectOpsMixin:
    """承载 MainWindow 的文件打开、保存、导入、导出流程。"""

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

    def _sync_project_bpm_to_ui(self, bpm: float):
        """将项目 BPM 同步到主界面相关控件。"""
        self.sequencer.set_bpm(bpm)
        self.bpm_spinbox.blockSignals(True)
        self.bpm_spinbox.setValue(int(bpm))
        self.bpm_spinbox.blockSignals(False)
        self.sequence_widget.set_bpm(bpm)
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
        self._sync_project_bpm_to_ui(float(self.sequencer.get_bpm()))
        self.sequence_widget.refresh(force_full_refresh=True)
        self.refresh_ui()

    def _refresh_project_after_midi_import(self, project):
        """MIDI 导入后刷新主界面和关联面板。"""
        self.sequence_widget.set_tracks(project.tracks, preserve_selection=False)
        self.sequence_widget.refresh(force_full_refresh=True)
        self.sequence_widget.view.update()
        self.sequence_widget.view.repaint()
        if hasattr(self.sequence_widget, "scene"):
            self.sequence_widget.scene.update()
        QApplication.processEvents()

        QTimer.singleShot(
            200,
            lambda: (
                self.sequence_widget.refresh(force_full_refresh=True),
                self.sequence_widget.view.update(),
                self.sequence_widget.view.repaint(),
            ),
        )

        self._sync_project_bpm_to_ui(float(project.bpm))

        if hasattr(self, "playback_settings_panel"):
            self.playback_settings_panel.set_tracks(project.tracks)
            self.playback_settings_panel.set_volume_ratios(self.sequencer.playback_volume_ratios)

        if hasattr(self, "bpm_editor_panel"):
            self.bpm_editor_panel.set_project(project)

        if hasattr(self.sequence_widget, "progress_bar"):
            total_duration = project.get_total_duration()
            self.sequence_widget.progress_bar.set_total_time(total_duration)

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
        self._sync_project_bpm_to_ui(float(self.sequencer.get_bpm()))
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

    def import_midi_file(self, file_path: str):
        """导入 MIDI 文件。"""
        try:
            if not self.check_unsaved_changes():
                return

            progress = QProgressDialog("正在导入MIDI文件...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            QApplication.processEvents()

            progress.setLabelText("正在读取MIDI文件...")
            progress.setValue(10)
            QApplication.processEvents()

            self._clear_project_panel_state()

            progress.setLabelText("正在解析MIDI数据...")
            progress.setValue(20)
            QApplication.processEvents()

            default_waveform = self.unified_editor.selected_waveform

            progress.setLabelText("正在导入MIDI文件...")
            progress.setValue(40)
            QApplication.processEvents()

            load_result = import_midi_document(
                file_path,
                default_waveform=default_waveform,
                snap_to_beat=False,
                allow_overlap=True,
            )
            project = load_result.project

            progress.setLabelText("正在设置项目...")
            progress.setValue(60)
            QApplication.processEvents()

            self.sequencer.set_project(project)
            self.current_file_path = load_result.current_file_path
            self.current_midi_file_path = load_result.current_midi_file_path

            progress.setLabelText("正在更新界面...")
            progress.setValue(70)
            QApplication.processEvents()

            self._reset_project_selection()

            progress.setLabelText("正在刷新显示...")
            progress.setValue(80)
            QApplication.processEvents()

            self._refresh_project_after_midi_import(project)

            progress.setLabelText("正在完成导入...")
            progress.setValue(95)
            QApplication.processEvents()

            self._update_file_name_display()

            progress.setValue(100)
            progress.setLabelText("导入完成！")
            QApplication.processEvents()

            time.sleep(0.1)
            progress.close()

            self.statusBar().showMessage(f"已导入MIDI: {file_path}")

            directory = os.path.dirname(file_path)
            self.settings.setValue("last_midi_directory", directory)
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
