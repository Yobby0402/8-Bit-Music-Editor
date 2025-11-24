"""
时间轴模块

显示时间轴、播放头和网格。支持点击和拖动来设置播放线位置。
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QMouseEvent

from ui.theme import theme_manager


class TimelineWidget(QWidget):
    """时间轴"""
    
    # 信号：播放线位置改变
    playhead_time_changed = pyqtSignal(float)  # 发送新的播放线时间（秒）
    
    def __init__(self, parent=None):
        """初始化时间轴"""
        super().__init__(parent)
        
        self.bpm = 120.0
        self.time_signature = (4, 4)
        self.current_time = 0.0
        self.pixels_per_beat = 100.0
        self.total_beats = 16  # 总节拍数
        self.is_dragging = False
        
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)
        self.setMouseTracking(True)
    
    def paintEvent(self, event):
        """绘制时间轴"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 使用主题背景色
        theme = theme_manager.current_theme
        bg_color = QColor(theme.get_color("background"))
        painter.fillRect(0, 0, width, height, bg_color)
        
        # 绘制网格线
        beats_per_measure = self.time_signature[0]
        pixels_per_measure = self.pixels_per_beat * beats_per_measure
        
        # 计算需要绘制的拍数（考虑横向滚动）
        max_beats = max(self.total_beats, int((width - 100) / self.pixels_per_beat) + 4)
        
        # 绘制小节线
        border_color = QColor(theme.get_color("border_dark"))
        pen = QPen(border_color, 2)
        num_measures = int(max_beats / beats_per_measure) + 1
        for i in range(num_measures + 1):
            x = 100 + int(i * pixels_per_measure)  # 左边留100px给轨道标签
            if x <= width:
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
        
        # 绘制拍线
        border_light_color = QColor(theme.get_color("border"))
        pen = QPen(border_light_color, 1)
        for i in range(max_beats + 1):
            x = 100 + int(i * self.pixels_per_beat)
            if x <= width:
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
        
        # 绘制标签
        text_color = QColor(theme.get_color("text_primary"))
        painter.setPen(QPen(text_color))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        for i in range(num_measures + 1):
            x = 100 + int(i * pixels_per_measure)
            if x <= width:
                painter.drawText(x + 2, 15, f"{i + 1}")
        
        # 绘制播放头
        if self.current_time >= 0:
            beats_per_second = self.bpm / 60.0
            beat_position = self.current_time * beats_per_second
            # 使用浮点数计算，然后转换为整数，确保与音轨区域的播放线对齐
            x = 100 + beat_position * self.pixels_per_beat
            x = int(x)  # 转换为整数用于绘制
            if 0 <= x <= width:
                error_color = QColor(theme.get_color("error"))
                pen = QPen(error_color, 2)
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 设置播放线位置"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.update_playhead_from_pos(event.pos())
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 拖动播放线"""
        if self.is_dragging:
            self.update_playhead_from_pos(event.pos())
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
    
    def update_playhead_from_pos(self, pos: QPoint):
        """根据鼠标位置更新播放线"""
        x = pos.x() - 100  # 减去轨道标签宽度
        if x < 0:
            x = 0
        
        # 计算对应的节拍数
        beat_position = x / self.pixels_per_beat
        # 转换为时间（秒）
        beats_per_second = self.bpm / 60.0
        time = beat_position / beats_per_second
        
        # 根据设置决定是否吸附
        from ui.settings_manager import get_settings_manager
        settings_manager = get_settings_manager()
        if settings_manager.is_snap_to_beat_enabled():
            # 吸附到1/4拍
            beat_subdivision = 4
            snapped_beat = round(beat_position * beat_subdivision) / beat_subdivision
            snapped_time = snapped_beat / beats_per_second
        else:
            # 不吸附，直接使用计算的时间
            snapped_time = time
        
        self.current_time = snapped_time
        self.update()
        
        # 发送信号
        self.playhead_time_changed.emit(snapped_time)
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        self.update()
    
    def set_time_signature(self, numerator: int, denominator: int):
        """设置拍号"""
        self.time_signature = (numerator, denominator)
        self.update()
    
    def set_current_time(self, time: float):
        """设置当前时间"""
        self.current_time = time
        self.update()
    
    def set_pixels_per_beat(self, pixels: float):
        """设置每拍的像素数"""
        self.pixels_per_beat = pixels
        self.update()
    
    def set_total_beats(self, beats: int):
        """设置总节拍数"""
        self.total_beats = beats
        self.update()
    
    def set_playhead_time(self, time: float):
        """设置播放线时间（从外部调用）"""
        self.current_time = time
        self.update()

