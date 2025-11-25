"""
节拍器可视化模块

显示节拍器状态和可视化指示器。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush


class MetronomeWidget(QWidget):
    """节拍器可视化"""
    
    metronome_toggled = pyqtSignal(bool)  # 节拍器开关
    
    def __init__(self, parent=None):
        """初始化节拍器"""
        super().__init__(parent)
        
        self.bpm = 120.0
        self.is_enabled = False
        self.is_playing = False
        self.current_beat = 0  # 当前节拍数（1-4）
        self.beat_flash = 0.0  # 节拍闪烁强度（0-1）
        
        # 节拍器定时器
        self.metronome_timer = QTimer()
        self.metronome_timer.timeout.connect(self.on_beat_tick)
        
        # 闪烁定时器（用于动画）
        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self.update_flash)
        self.flash_timer.start(50)  # 每50ms更新一次
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 使用水平布局，一排排列
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.setMaximumHeight(80)
        
        # 开关按钮（去掉"节拍器"标题，按钮显示"节拍器：开启"/"节拍器：关闭"）
        self.toggle_button = QPushButton("节拍器：开启")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setMinimumWidth(100)
        self.toggle_button.setMaximumWidth(120)
        self.toggle_button.clicked.connect(self.on_toggle)
        layout.addWidget(self.toggle_button)
        
        # 可视化指示器（水平排列）
        self.beat_indicator = BeatIndicatorWidget()
        self.beat_indicator.setMinimumWidth(200)
        self.beat_indicator.setMinimumHeight(60)
        self.beat_indicator.setMaximumHeight(70)
        layout.addWidget(self.beat_indicator)
        
        # BPM显示
        self.bpm_label = QLabel(f"BPM: {int(self.bpm)}")
        self.bpm_label.setAlignment(Qt.AlignCenter)
        self.bpm_label.setMinimumWidth(70)
        layout.addWidget(self.bpm_label)
        
        layout.addStretch()
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        self.bpm_label.setText(f"BPM: {int(bpm)}")
        
        # 更新定时器间隔
        if self.metronome_timer.isActive():
            interval = int(60000.0 / bpm)  # 毫秒
            self.metronome_timer.setInterval(interval)
    
    def set_enabled(self, enabled: bool):
        """设置节拍器启用状态"""
        self.is_enabled = enabled
        self.toggle_button.setChecked(enabled)
        self.toggle_button.setText("节拍器：关闭" if enabled else "节拍器：开启")
        
        if enabled and self.is_playing:
            self.start_metronome()
        else:
            self.stop_metronome()
        
        self.metronome_toggled.emit(enabled)
    
    def set_playing(self, playing: bool):
        """设置播放状态"""
        self.is_playing = playing
        
        if self.is_enabled and playing:
            self.start_metronome()
        else:
            self.stop_metronome()
    
    def start_metronome(self):
        """启动节拍器"""
        if not self.metronome_timer.isActive():
            interval = int(60000.0 / self.bpm)  # 毫秒
            self.metronome_timer.setInterval(interval)
            self.metronome_timer.start()
            self.current_beat = 0
    
    def stop_metronome(self):
        """停止节拍器"""
        if self.metronome_timer.isActive():
            self.metronome_timer.stop()
        self.current_beat = 0
        self.beat_flash = 0.0
        self.beat_indicator.set_beat(0, 0.0)
        self.update()
    
    def on_toggle(self, checked: bool = None):
        """节拍器开关"""
        if checked is None:
            # 如果没有传入checked参数，切换状态
            self.is_enabled = not self.is_enabled
        else:
            self.is_enabled = checked
        self.toggle_button.setChecked(self.is_enabled)
        self.toggle_button.setText("节拍器：关闭" if self.is_enabled else "节拍器：开启")
        self.metronome_toggled.emit(self.is_enabled)
    
    def on_beat_tick(self):
        """节拍器滴答"""
        if not self.is_playing:
            return
        
        # 更新节拍数（1-4循环）
        self.current_beat = (self.current_beat % 4) + 1
        self.beat_flash = 1.0  # 闪烁强度设为最大
        
        # 更新可视化
        self.beat_indicator.set_beat(self.current_beat, self.beat_flash)
        
        # 可以在这里播放滴答声
        # self.play_tick_sound()
    
    def update_flash(self):
        """更新闪烁动画"""
        if self.beat_flash > 0:
            self.beat_flash = max(0.0, self.beat_flash - 0.1)  # 逐渐衰减
            self.beat_indicator.set_beat(self.current_beat, self.beat_flash)
            self.update()


class BeatIndicatorWidget(QWidget):
    """节拍指示器"""
    
    def __init__(self, parent=None):
        """初始化指示器"""
        super().__init__(parent)
        self.current_beat = 0
        self.flash_intensity = 0.0
        self.setMinimumHeight(60)
        self.setMaximumHeight(70)
    
    def set_beat(self, beat: int, flash: float):
        """设置当前节拍和闪烁强度"""
        self.current_beat = beat
        self.flash_intensity = flash
        self.update()
    
    def paintEvent(self, event):
        """绘制指示器"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 绘制4个节拍指示器（水平排列）
        beat_width = (width - 30) / 4  # 左右各留15px边距
        beat_height = height - 20  # 上下各留10px边距
        
        # 圆圈直径（增大一些）
        circle_diameter = min(beat_width - 5, beat_height - 5, 45)  # 最大45px，确保足够大
        
        for i in range(4):
            x = 15 + i * beat_width
            y = 10
            
            # 判断是否激活（当前节拍或闪烁）
            is_active = (i + 1 == self.current_beat)
            alpha = 255 if is_active else 50
            
            # 如果是当前节拍，应用闪烁效果
            if is_active and self.flash_intensity > 0:
                alpha = int(50 + 205 * self.flash_intensity)
            
            # 第一拍（强拍）用不同颜色
            if i == 0:
                color = QColor(255, 100, 100, alpha)  # 红色（强拍）
            else:
                color = QColor(100, 150, 255, alpha)  # 蓝色（弱拍）
            
            # 绘制节拍指示器
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0, alpha), 2))  # 边框稍微粗一点
            
            # 圆形指示器（居中）
            circle_x = int(x + (beat_width - circle_diameter) / 2)
            circle_y = int(y + (beat_height - circle_diameter) / 2)
            painter.drawEllipse(
                circle_x,
                circle_y,
                int(circle_diameter),
                int(circle_diameter)
            )

