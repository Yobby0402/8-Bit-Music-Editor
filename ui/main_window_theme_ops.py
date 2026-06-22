"""
主窗口中的主题、显示设置与窗口外壳辅助逻辑。
"""

from __future__ import annotations

from typing import Iterable

from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QApplication

from ui.theme import theme_manager


def build_main_background_style(
    background_color: str,
    *,
    gradient_enabled: bool,
    gradient_color2: str,
    gradient_mode: str,
) -> str:
    """根据设置构建主区域背景样式。"""
    if not gradient_enabled or gradient_mode == "none":
        return f"background-color: {background_color};"

    gradient_styles = {
        "center": (
            "background-image: qradialgradient("
            f"cx:0.5, cy:0.5, radius:1, fx:0.5, fy:0.5, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
        "top_bottom": (
            "background-image: qlineargradient("
            f"x1:0, y1:0, x2:0, y2:1, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
        "bottom_top": (
            "background-image: qlineargradient("
            f"x1:0, y1:1, x2:0, y2:0, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
        "left_right": (
            "background-image: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:0, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
        "right_left": (
            "background-image: qlineargradient("
            f"x1:1, y1:0, x2:0, y2:0, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
        "diagonal": (
            "background-image: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:1, stop:0 {background_color}, stop:1 {gradient_color2}"
            ");"
        ),
    }
    background_image = gradient_styles.get(gradient_mode)
    if background_image is None:
        return f"background-color: {background_color};"
    return f"background-color: {background_color}; {background_image}"


def sync_locked_dock_width(
    docks: Iterable[object | None],
    current_width: int | None,
    new_width: int,
) -> int | None:
    """Record the current right dock width without fighting manual resizing."""
    if new_width <= 0 or new_width == current_width:
        return current_width

    return new_width


def has_significant_size_change(current_size, target_size, *, threshold: int = 10) -> bool:
    """判断窗口尺寸变化是否足够明显，值得恢复。"""
    return (
        abs(current_size.width() - target_size.width()) > threshold
        or abs(current_size.height() - target_size.height()) > threshold
    )


class MainWindowThemeOpsMixin:
    """承载 MainWindow 中的主题、显示设置和窗口尺寸辅助逻辑。"""

    def _tracked_right_docks(self):
        """返回需要同步宽度的右侧 Dock。"""
        return (
            getattr(self, "right_panel_dock", None) or getattr(self, "property_dock", None),
        )

    def eventFilter(self, obj, event):
        """
        统一处理右侧 Dock（属性面板 / 乐谱面板）的宽度锁定逻辑。
        """
        tracked_docks = self._tracked_right_docks()
        if event.type() == QEvent.Resize and obj in tracked_docks:
            self._right_dock_width = sync_locked_dock_width(
                tracked_docks,
                self._right_dock_width,
                obj.width(),
            )
        return super().eventFilter(obj, event)

    def apply_theme(self):
        """应用主题到所有 UI 组件。"""
        theme_manager.apply_to_widget(self)
        if hasattr(self, "oscilloscope_widget"):
            self.oscilloscope_widget.apply_theme()

    def _apply_global_ui_font_size(self):
        """应用全局 UI 字体大小。"""
        try:
            app = QApplication.instance()
            if app is not None:
                font = app.font()
                font.setPointSize(self.settings_manager.get_ui_font_size())
                app.setFont(font)
        except Exception as exc:
            import traceback

            print("应用全局字体设置时出错：", exc)
            traceback.print_exc()

    def apply_display_settings_from_settings(
        self,
        central_widget=None,
        note_selection_area=None,
        track_area=None,
        playback_control_area=None,
    ):
        """根据设置管理器应用显示相关设置。"""
        background_color = self.settings_manager.get_ui_background_color()
        foreground_color = self.settings_manager.get_ui_foreground_color()
        try:
            gradient_enabled = self.settings_manager.is_background_gradient_enabled()
            gradient_color2 = self.settings_manager.get_background_gradient_color2()
            gradient_mode = self.settings_manager.get_background_gradient_mode()
        except Exception:
            gradient_enabled = False
            gradient_color2 = background_color
            gradient_mode = "none"

        self._apply_global_ui_font_size()

        if central_widget is None:
            central_widget = self.centralWidget()
        if central_widget is not None:
            central_widget.setStyleSheet(
                build_main_background_style(
                    background_color,
                    gradient_enabled=gradient_enabled,
                    gradient_color2=gradient_color2,
                    gradient_mode=gradient_mode,
                )
            )

        for area in (note_selection_area, track_area, playback_control_area):
            if area is not None:
                area.setStyleSheet("background: transparent;")

        if self.statusBar() is not None:
            self.statusBar().setStyleSheet(f"color: {foreground_color};")

    def _refresh_update_timer_interval(self):
        """根据设置刷新播放线刷新率。"""
        try:
            if hasattr(self, "update_timer") and self.update_timer is not None:
                interval = self.settings_manager.get_playhead_refresh_interval()
                self.update_timer.setInterval(interval)
        except Exception:
            pass

    def _refresh_sequence_widget_theme(self, theme):
        """刷新序列编辑器相关主题。"""
        if not hasattr(self, "sequence_widget"):
            return

        background = QColor(theme.get_color("background"))
        if hasattr(self.sequence_widget, "view"):
            self.sequence_widget.view.setBackgroundBrush(QBrush(background))
        if hasattr(self.sequence_widget, "draw_grid"):
            self.sequence_widget.draw_grid()

        button_small_style = theme.get_style("button_small")
        for button_name in ("add_track_button", "delete_track_button", "render_waveform_button"):
            if hasattr(self.sequence_widget, button_name):
                button = getattr(self.sequence_widget, button_name)
                if button is not None:
                    button.setStyleSheet(button_small_style)

        if hasattr(self.sequence_widget, "progress_bar"):
            try:
                self.sequence_widget.progress_bar.apply_theme()
            except Exception:
                pass

    def _refresh_unified_editor_theme(self, theme):
        """刷新统一编辑器主题。"""
        if not hasattr(self, "unified_editor"):
            return
        try:
            background = theme.get_color("background")
            self.unified_editor.setStyleSheet(f"background-color: {background};")
            if hasattr(self.unified_editor, "apply_theme_to_buttons"):
                self.unified_editor.apply_theme_to_buttons()
        except Exception:
            pass

    def _refresh_oscilloscope_theme(self):
        """刷新示波器主题。"""
        if hasattr(self, "oscilloscope_widget"):
            try:
                self.oscilloscope_widget.apply_theme()
            except Exception:
                pass

    def refresh_theme_from_settings(self):
        """从当前设置重新应用主题和样式。"""
        self.apply_theme()
        self.apply_display_settings_from_settings()
        self._refresh_update_timer_interval()

        theme = theme_manager.current_theme
        self._refresh_sequence_widget_theme(theme)
        self._refresh_unified_editor_theme(theme)
        self._refresh_oscilloscope_theme()

        if hasattr(self, "refresh_ui"):
            self.refresh_ui(preserve_selection=True, force_full_refresh=False)
        self.repaint()

    def _restore_window_size(self, size):
        """恢复窗口大小，避免刷新时自动调整。"""
        if size.isValid() and self.isVisible():
            current_size = self.size()
            if has_significant_size_change(current_size, size):
                self.resize(size)
