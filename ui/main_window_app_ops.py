"""
主窗口中的应用级动作、快捷键与面板切换逻辑。
"""

from __future__ import annotations

from collections.abc import Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QMessageBox, QSpinBox

from app_info import APP_NAME, APP_VERSION
from ui.main_window_dialogs import prompt_new_track

SHORTCUT_BINDINGS = (
    ("octave_up", "octave_up"),
    ("octave_down", "octave_down"),
    ("delete_last_note", "delete_last_note"),
)


def build_about_text(app_name: str, app_version: str) -> str:
    """构建“关于”对话框文本。"""
    return (
        f"{app_name} {app_version}\n\n"
        "一个功能完备的 8bit 音乐和音效制作器。\n\n"
        "使用 PyQt5 开发。"
    )


def get_first_segment_bpm(bpm_segments: Sequence[object]) -> float | None:
    """获取 BPM 段列表中的首个 BPM。"""
    if not bpm_segments:
        return None
    return float(bpm_segments[0].bpm)


def find_category_index(category_names: Sequence[str], target_name: str) -> int | None:
    """在设置分类列表中查找目标分类索引。"""
    for index, name in enumerate(category_names):
        if name == target_name:
            return index
    return None


class MainWindowAppOpsMixin:
    """承载 MainWindow 中的应用级动作与面板切换逻辑。"""

    def _clear_main_window_shortcut_actions(self):
        """清理已注册的主窗口快捷键 action，避免重复绑定。"""
        for action in getattr(self, "_main_window_shortcut_actions", []):
            self.removeAction(action)
            action.deleteLater()
        self._main_window_shortcut_actions = []

    def _register_main_window_shortcut(self, shortcut_key: str, handler_name: str):
        """按快捷键配置创建并注册主窗口 action。"""
        key_sequence = self.shortcut_manager.get_key_sequence(shortcut_key)
        if not key_sequence:
            return

        action = QAction(self)
        action.setShortcut(key_sequence)
        action.triggered.connect(getattr(self, handler_name))
        self.addAction(action)
        self._main_window_shortcut_actions.append(action)

    def _refresh_unified_editor_shortcuts(self):
        """刷新统一编辑器和钢琴键盘上的快捷键显示。"""
        if not hasattr(self, "unified_editor"):
            return

        self.unified_editor.setup_shortcuts(self.shortcut_manager)
        if hasattr(self.unified_editor, "piano_keyboard"):
            self.unified_editor.piano_keyboard.update_button_texts()

    def _refresh_after_settings_dialog(self):
        """设置应用后刷新序列编辑器，避免局部状态残留。"""
        if hasattr(self, "sequence_widget") and hasattr(self.sequencer, "project"):
            try:
                self.sequence_widget.set_tracks(
                    self.sequencer.project.tracks,
                    preserve_selection=True,
                )
                self.sequence_widget.refresh(force_full_refresh=True)
            except Exception:
                pass

    def show_about(self):
        """显示关于对话框。"""
        QMessageBox.about(self, "关于", build_about_text(APP_NAME, APP_VERSION))

    def setup_shortcuts(self):
        """设置主窗口快捷键。"""
        self._clear_main_window_shortcut_actions()
        for shortcut_key, handler_name in SHORTCUT_BINDINGS:
            self._register_main_window_shortcut(shortcut_key, handler_name)
        self._refresh_unified_editor_shortcuts()

    def octave_up(self):
        """增加一度（八度）。"""
        if hasattr(self, "unified_editor") and hasattr(self.unified_editor, "piano_keyboard"):
            current_octave = self.unified_editor.piano_keyboard.current_octave
            if current_octave < 8:
                self.unified_editor.piano_keyboard.on_octave_changed(current_octave + 1)

    def octave_down(self):
        """减少一度（八度）。"""
        if hasattr(self, "unified_editor") and hasattr(self.unified_editor, "piano_keyboard"):
            current_octave = self.unified_editor.piano_keyboard.current_octave
            if current_octave > 0:
                self.unified_editor.piano_keyboard.on_octave_changed(current_octave - 1)

    def show_settings(self):
        """显示设置对话框。"""
        from ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self, oscilloscope_widget=getattr(self, "oscilloscope_widget", None))
        if dialog.exec_():
            self._refresh_after_settings_dialog()
            self.statusBar().showMessage("设置已更新")

    def show_shortcut_config(self):
        """显示快捷键配置对话框。"""
        from ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self, oscilloscope_widget=getattr(self, "oscilloscope_widget", None))
        category_names = [
            dialog.category_list.item(index).text()
            for index in range(dialog.category_list.count())
            if dialog.category_list.item(index) is not None
        ]
        shortcut_index = find_category_index(category_names, "快捷键")
        if shortcut_index is not None:
            dialog.category_list.setCurrentRow(shortcut_index)

        if dialog.exec_():
            self.setup_shortcuts()
            self.statusBar().showMessage("快捷键配置已更新")

    def keyPressEvent(self, event):
        """全局键盘事件。"""
        if event.key() == Qt.Key_Space:
            focus_widget = self.focusWidget()
            if not isinstance(focus_widget, QSpinBox):
                self.toggle_play_pause()
                event.accept()
                return

        super().keyPressEvent(event)

    def toggle_property_panel(self, visible: bool):
        """切换属性面板显示。"""
        self.property_dock.setVisible(visible)
        if visible and hasattr(self, "toggle_score_action"):
            self.toggle_score_action.setChecked(self.score_dock.isVisible())

    def _focus_property_panel(self):
        """确保属性面板可见并置前。"""
        if not hasattr(self, "property_dock"):
            return

        self.property_dock.setVisible(True)
        if hasattr(self, "toggle_property_action"):
            self.toggle_property_action.setChecked(True)
        try:
            self.property_dock.raise_()
        except Exception:
            pass

    def toggle_score_panel(self, visible: bool):
        """切换乐谱面板显示。"""
        if not hasattr(self, "score_dock"):
            return
        self.score_dock.setVisible(visible)
        if hasattr(self, "toggle_property_action"):
            self.toggle_property_action.setChecked(self.property_dock.isVisible())

    def toggle_style_params_panel(self, visible: bool):
        """切换风格参数面板显示。"""
        if hasattr(self, "style_dock"):
            self.style_dock.setVisible(visible)

    def toggle_playback_settings_panel(self, visible: bool):
        """切换播放设置面板显示。"""
        if hasattr(self, "playback_settings_dock"):
            self.playback_settings_dock.setVisible(visible)

    def toggle_bpm_editor_panel(self, visible: bool):
        """切换 BPM 编辑器面板显示。"""
        if hasattr(self, "bpm_editor_dock"):
            self.bpm_editor_dock.setVisible(visible)

    def on_bpm_segments_changed(self, bpm_segments):
        """BPM 段改变。"""
        if not hasattr(self, "sequencer") or not self.sequencer.project:
            return

        self.sequencer.project.bpm_segments = bpm_segments
        first_bpm = get_first_segment_bpm(bpm_segments)
        if first_bpm is not None:
            self.sequencer.project.bpm = first_bpm
            self.bpm_spinbox.blockSignals(True)
            self.bpm_spinbox.setValue(int(first_bpm))
            self.bpm_spinbox.blockSignals(False)

        self.refresh_ui()

    def undo(self):
        """撤销操作。"""
        description = self.sequencer.undo()
        if description:
            self.statusBar().showMessage(f"已撤销: {description}")
            self.refresh_ui()
            return
        self.statusBar().showMessage("无法撤销")

    def redo(self):
        """重做操作。"""
        description = self.sequencer.redo()
        if description:
            self.statusBar().showMessage(f"已重做: {description}")
            self.refresh_ui()
            return
        self.statusBar().showMessage("无法重做")

    def update_undo_redo_state(self):
        """更新撤销/重做按钮状态。"""
        self.undo_action.setEnabled(self.sequencer.can_undo())
        self.redo_action.setEnabled(self.sequencer.can_redo())

    def on_add_track_clicked(self):
        """添加音轨按钮点击。"""
        result = prompt_new_track(self, len(self.sequencer.project.tracks))
        if result is None:
            return

        track_name, track_type = result
        track = self.sequencer.add_track(name=track_name, track_type=track_type)
        self.refresh_ui()
        self.statusBar().showMessage(f"已添加音轨: {track.name}")
