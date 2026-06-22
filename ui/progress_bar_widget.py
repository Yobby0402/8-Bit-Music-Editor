"""
进度条控件模块

类似音乐播放器的进度条，支持拖动播放线位置，显示当前时间、剩余时间和总时间。
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSlider, QWidget

from ui.theme import theme_manager


class ProgressBarWidget(QWidget):
    """进度条控件（类似音乐播放器）"""
    
    # 信号：播放线位置改变
    playhead_time_changed = pyqtSignal(float)  # 发送新的播放线时间（秒）
    
    def __init__(self, parent=None):
        """初始化进度条"""
        super().__init__(parent)
        
        self.bpm = 120.0
        self.project = None
        self.current_time = 0.0
        self.total_time = 0.0  # 总时长（秒）
        self.is_dragging = False
        self._current_time_text = "00:00"
        self._total_time_text = "00:00"
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        self.setLayout(layout)
        
        # 当前时间标签
        self.current_time_label = QLabel(self._current_time_text)
        self.current_time_label.setMinimumWidth(50)
        self.current_time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_time_label)
        
        # 进度条滑块
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)  # 使用1000作为最大值，提供足够的精度
        self.progress_slider.setValue(0)
        self.progress_slider.setMinimumHeight(20)
        # 连接信号
        self.progress_slider.sliderPressed.connect(self.on_slider_pressed)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.progress_slider.sliderReleased.connect(self.on_slider_released)
        layout.addWidget(self.progress_slider, 1)  # 可拉伸
        
        # 总时间标签
        self.total_time_label = QLabel(self._total_time_text)
        self.total_time_label.setMinimumWidth(50)
        self.total_time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.total_time_label)
        
        # 设置固定高度
        self.setMinimumHeight(40)
        self.setMaximumHeight(40)
        
        # 应用主题
        self.apply_theme()
    
    def apply_theme(self):
        """应用主题"""
        theme = theme_manager.current_theme
        bg_color = theme.get_color("background")
        text_color = theme.get_color("text_primary")
        
        # 设置背景色
        self.setStyleSheet(f"background-color: {bg_color};")
        
        # 设置标签颜色
        label_style = f"color: {text_color};"
        self.current_time_label.setStyleSheet(label_style)
        self.total_time_label.setStyleSheet(label_style)
    
    def format_time(self, seconds: float) -> str:
        """格式化时间为 MM:SS 格式"""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _set_current_time_text(self, seconds: float) -> None:
        text = self.format_time(seconds)
        if text == self._current_time_text:
            return
        self._current_time_text = text
        self.current_time_label.setText(text)

    def _set_total_time_text(self, seconds: float) -> None:
        text = self.format_time(seconds)
        if text == self._total_time_text:
            return
        self._total_time_text = text
        self.total_time_label.setText(text)
    
    def set_project(self, project):
        """Set the project used for beat/second conversion."""
        self.project = project

    def _safe_bpm(self) -> float:
        return self.bpm if self.bpm > 0 else 120.0

    def _seconds_to_beats(self, seconds: float) -> float:
        if self.project is not None:
            return self.project.seconds_to_beats(seconds)
        return max(0.0, seconds) * self._safe_bpm() / 60.0

    def _beats_to_seconds(self, beats: float) -> float:
        if self.project is not None:
            return self.project.beats_to_seconds(beats)
        return max(0.0, beats) * 60.0 / self._safe_bpm()

    def on_slider_pressed(self):
        """滑块按下"""
        self.is_dragging = True
    
    def on_slider_moved(self, value: int):
        """滑块移动"""
        if self.total_time > 0:
            # 计算新的时间位置
            new_time = (value / 1000.0) * self.total_time
            
            # 根据设置决定是否吸附
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            if settings_manager.is_snap_to_beat_enabled():
                # 吸附到最近的1/4拍
                beat_position = self._seconds_to_beats(new_time)
                beat_subdivision = 4
                snapped_beat = round(beat_position * beat_subdivision) / beat_subdivision
                new_time = self._beats_to_seconds(snapped_beat)
                # 更新滑块位置以反映吸附
                new_value = int((new_time / self.total_time) * 1000)
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(new_value)
                self.progress_slider.blockSignals(False)
            
            # 更新当前时间显示
            self.current_time = new_time
            self._set_current_time_text(new_time)
            
            # 发送信号（仅在拖动时发送，避免与播放更新冲突）
            if self.is_dragging:
                self.playhead_time_changed.emit(new_time)
    
    def on_slider_released(self):
        """滑块释放"""
        self.is_dragging = False
        # 确保最终位置正确
        value = self.progress_slider.value()
        if self.total_time > 0:
            new_time = (value / 1000.0) * self.total_time
            self.current_time = new_time
            self._set_current_time_text(new_time)
            self.playhead_time_changed.emit(new_time)
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
    
    def set_current_time(self, time: float):
        """设置当前时间（从外部调用，如播放时）"""
        if not self.is_dragging:  # 只有在不拖动时才更新
            self.current_time = time
            self._set_current_time_text(time)
            
            # 更新滑块位置
            if self.total_time > 0:
                value = int((time / self.total_time) * 1000)
                if value != self.progress_slider.value():
                    self.progress_slider.blockSignals(True)
                    self.progress_slider.setValue(value)
                    self.progress_slider.blockSignals(False)
    
    def set_total_time(self, time: float):
        """设置总时长"""
        self.total_time = max(0.0, time)
        self._set_total_time_text(self.total_time)
        
        # 如果总时长改变，更新当前时间显示
        if self.current_time > self.total_time:
            self.current_time = self.total_time
            self._set_current_time_text(self.current_time)
        
        # 更新滑块位置
        if self.total_time > 0:
            value = int((self.current_time / self.total_time) * 1000)
            if value != self.progress_slider.value():
                self.progress_slider.blockSignals(True)
                self.progress_slider.setValue(value)
                self.progress_slider.blockSignals(False)
    
    def set_playhead_time(self, time: float):
        """设置播放线时间（从外部调用，兼容TimelineWidget接口）"""
        self.set_current_time(time)

