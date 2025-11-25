"""
拨动开关组件

实现一个带有动画效果的拨动开关，只有两个挡位。
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush


class ToggleSwitchWidget(QWidget):
    """拨动开关组件"""
    
    position_changed = pyqtSignal(int)  # 位置改变信号
    
    def __init__(self, parent=None):
        """初始化拨动开关"""
        super().__init__(parent)
        self._position = 0  # 0 = 左侧，1 = 右侧
        self.animation = None
        self.setMinimumSize(80, 30)
        self.setMaximumSize(80, 30)
    
    def set_position(self, position: int):
        """设置位置（0=左侧，1=右侧）"""
        if position not in [0, 1]:
            return
        self._position = position
        self.update()
    
    def get_position(self) -> int:
        """获取位置"""
        return self._position
    
    position = pyqtProperty(int, get_position, set_position)
    
    def toggle(self):
        """切换位置"""
        new_position = 1 - self._position
        self.animate_to(new_position)
    
    def animate_to(self, target_position: int):
        """动画移动到目标位置"""
        if target_position not in [0, 1]:
            return
        
        if self.animation:
            self.animation.stop()
        
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setDuration(200)  # 200ms动画
        self.animation.setStartValue(self._position)
        self.animation.setEndValue(target_position)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.finished.connect(lambda: self.position_changed.emit(self._position))
        self.animation.start()
    
    def paintEvent(self, event):
        """绘制拨动开关"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 背景轨道
        track_height = height - 4
        track_y = 2
        track_radius = track_height // 2
        
        # 未选中状态：灰色背景
        bg_color = QColor(200, 200, 200)
        # 选中状态：根据位置显示不同颜色
        if self._position == 0:
            # 左侧选中：绿色
            active_color = QColor(76, 175, 80)  # #4CAF50
        else:
            # 右侧选中：蓝色
            active_color = QColor(33, 150, 243)  # #2196F3
        
        # 绘制背景轨道
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(2, track_y, width - 4, track_height, track_radius, track_radius)
        
        # 绘制选中部分的背景
        if self._position == 0:
            # 左侧选中
            painter.setBrush(QBrush(active_color))
            painter.drawRoundedRect(2, track_y, width // 2, track_height, track_radius, track_radius)
        else:
            # 右侧选中
            painter.setBrush(QBrush(active_color))
            painter.drawRoundedRect(width // 2, track_y, width // 2 - 2, track_height, track_radius, track_radius)
        
        # 绘制滑块
        slider_size = track_height - 4
        slider_x = 4 + self._position * (width - slider_size - 8)
        slider_y = track_y + 2
        
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawEllipse(slider_x, slider_y, slider_size, slider_size)
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            # 切换位置
            self.toggle()

