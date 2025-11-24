"""
多行文本按钮

支持显示多行文本，用于显示快捷键。
"""

from PyQt5.QtWidgets import QPushButton, QStyleOptionButton, QStyle
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QFontMetrics, QFont, QPen


class MultilineButton(QPushButton):
    """支持多行文本的按钮"""
    
    def __init__(self, text="", parent=None):
        """初始化多行按钮"""
        super().__init__(text, parent)
        self.setMinimumHeight(40)  # 确保有足够高度显示两行文本
        self._main_text = ""
        self._shortcut_text = ""
        self._update_text_parts()
    
    def setText(self, text: str):
        """设置文本，自动分割为主文本和快捷键"""
        super().setText("")  # 清空原始文本，避免显示
        self._update_text_parts(text)
        self.update()  # 触发重绘
    
    def _update_text_parts(self, text=None):
        """更新文本部分"""
        if text is None:
            text = super().text()
        
        if '\n' in text:
            lines = text.split('\n')
            self._main_text = lines[0] if len(lines) > 0 else ""
            self._shortcut_text = lines[1] if len(lines) > 1 else ""
        else:
            self._main_text = text
            self._shortcut_text = ""
    
    def text(self):
        """获取完整文本"""
        if self._shortcut_text:
            return f"{self._main_text}\n{self._shortcut_text}"
        return self._main_text
    
    def paintEvent(self, event):
        """自定义绘制，支持多行文本"""
        # 先绘制按钮背景和边框
        option = QStyleOptionButton()
        self.initStyleOption(option)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制按钮样式（背景、边框等）
        self.style().drawControl(QStyle.CE_PushButton, option, painter, self)
        
        # 绘制文本
        if self._main_text or self._shortcut_text:
            rect = self.rect()
            font = self.font()
            painter.setFont(font)
            
            # 获取文本颜色
            # 如果按钮被选中（checked），使用白色文字以确保在彩色背景上清晰可见
            if self.isCheckable() and self.isChecked():
                from PyQt5.QtGui import QColor
                text_color = QColor(255, 255, 255)  # 白色
            elif self.isEnabled():
                text_color = self.palette().color(self.foregroundRole())
            else:
                text_color = self.palette().color(self.foregroundRole())
                text_color.setAlpha(128)
            
            painter.setPen(QPen(text_color))
            
            # 绘制主文本（居中偏上）
            if self._main_text:
                metrics = QFontMetrics(font)
                main_rect = rect.adjusted(2, 2, -2, -rect.height() // 2)
                painter.drawText(main_rect, Qt.AlignHCenter | Qt.AlignVCenter, self._main_text)
            
            # 绘制快捷键（小字体，居中偏下）
            if self._shortcut_text:
                small_font = QFont(font)
                small_font.setPointSize(max(7, font.pointSize() - 3))
                painter.setFont(small_font)
                
                # 使用较淡的颜色显示快捷键
                shortcut_color = text_color
                shortcut_color.setAlpha(180)  # 半透明
                painter.setPen(QPen(shortcut_color))
                
                shortcut_rect = rect.adjusted(2, rect.height() // 2, -2, -2)
                painter.drawText(shortcut_rect, Qt.AlignHCenter | Qt.AlignVCenter, self._shortcut_text)

