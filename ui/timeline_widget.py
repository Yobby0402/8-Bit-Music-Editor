"""
时间轴模块

显示时间轴、播放头和网格。
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QColor


class TimelineWidget(QWidget):
    """时间轴"""
    
    def __init__(self, parent=None):
        """初始化时间轴"""
        super().__init__(parent)
        
        self.bpm = 120.0
        self.time_signature = (4, 4)
        self.current_time = 0.0
        self.pixels_per_beat = 100.0
        self.total_beats = 16  # 总节拍数
        
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
    
    def paintEvent(self, event):
        """绘制时间轴"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 绘制背景
        painter.fillRect(0, 0, width, height, QColor(240, 240, 240))
        
        # 绘制网格线
        beats_per_measure = self.time_signature[0]
        pixels_per_measure = self.pixels_per_beat * beats_per_measure
        
        # 绘制小节线
        pen = QPen(QColor(100, 100, 100), 2)
        num_measures = int(self.total_beats / beats_per_measure) + 1
        for i in range(num_measures + 1):
            x = int(i * pixels_per_measure)
            if x <= width:
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
        
        # 绘制拍线
        pen = QPen(QColor(200, 200, 200), 1)
        for i in range(self.total_beats + 1):
            x = int(i * self.pixels_per_beat)
            if x <= width:
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
        
        # 绘制标签
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        for i in range(num_measures + 1):
            x = int(i * pixels_per_measure)
            if x <= width:
                painter.drawText(x + 2, 15, f"{i + 1}")
        
        # 绘制播放头
        if self.current_time >= 0:
            x = int(self.current_time * self.pixels_per_beat * 4)  # 假设4/4拍
            if x <= width:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawLine(x, 0, x, height)
    
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

