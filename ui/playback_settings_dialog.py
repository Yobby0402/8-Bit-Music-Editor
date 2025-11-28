"""
播放设置对话框

用于设置每个音轨在播放时的音量占比。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QDialogButtonBox, QWidget, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from core.models import Track


class PlaybackSettingsDialog(QDialog):
    """播放设置对话框"""
    
    def __init__(self, tracks: list, track_volume_ratios: dict, parent=None):
        """
        初始化播放设置对话框
        
        Args:
            tracks: 音轨列表
            track_volume_ratios: 音轨音量占比字典 {track_id: ratio (0-1)}
            parent: 父窗口
        """
        super().__init__(parent)
        self.tracks = tracks
        self.track_volume_ratios = track_volume_ratios.copy() if track_volume_ratios else {}
        self.track_sliders = {}  # {track_id: slider}
        
        self.setWindowTitle("播放设置 - 音轨音量占比")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 说明文字
        info_label = QLabel("设置每个音轨在播放时的音量占比（0-100%）。\n"
                           "占比越高，该音轨在混音中的音量越大。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 8px;")
        layout.addWidget(info_label)
        
        # 滚动区域（包含所有音轨设置）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(12)
        scroll_content.setLayout(scroll_layout)
        
        # 为每个音轨创建音量占比滑块
        for track in self.tracks:
            track_id = id(track)
            track_widget = self.create_track_volume_widget(track, track_id)
            scroll_layout.addWidget(track_widget)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def create_track_volume_widget(self, track: Track, track_id: int) -> QWidget:
        """为单个音轨创建音量占比控件"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        widget.setLayout(layout)
        
        # 音轨名称
        name_label = QLabel(track.name)
        name_label.setMinimumWidth(120)
        name_label.setMaximumWidth(150)
        # 如果是主音轨，加粗显示
        if track_id in self.track_volume_ratios and self.track_volume_ratios[track_id] > 0.7:
            font = name_label.font()
            font.setBold(True)
            name_label.setFont(font)
        layout.addWidget(name_label)
        
        # 音量占比滑块
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        # 获取当前占比（如果没有设置，默认为100%）
        current_ratio = self.track_volume_ratios.get(track_id, 1.0)
        slider.setValue(int(current_ratio * 100))
        slider.valueChanged.connect(lambda v: self.on_ratio_changed(track_id, v))
        layout.addWidget(slider, 1)
        
        # 占比显示标签
        ratio_label = QLabel(f"{int(current_ratio * 100)}%")
        ratio_label.setMinimumWidth(50)
        ratio_label.setMaximumWidth(50)
        ratio_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(ratio_label)
        
        # 主音按钮（快速设置为100%）
        main_button = QPushButton("主音")
        main_button.setCheckable(True)
        main_button.setMaximumWidth(50)
        if current_ratio >= 0.95:  # 如果占比接近100%，视为主音
            main_button.setChecked(True)
        main_button.clicked.connect(lambda checked, tid=track_id, s=slider, rl=ratio_label: 
                                   self.on_main_clicked(checked, tid, s, rl))
        layout.addWidget(main_button)
        
        # 保存引用
        self.track_sliders[track_id] = {
            'slider': slider,
            'label': ratio_label,
            'main_button': main_button,
            'track': track
        }
        
        return widget
    
    def on_ratio_changed(self, track_id: int, value: int):
        """音量占比改变"""
        ratio = value / 100.0
        self.track_volume_ratios[track_id] = ratio
        
        # 更新标签
        if track_id in self.track_sliders:
            self.track_sliders[track_id]['label'].setText(f"{value}%")
            # 更新主音按钮状态
            self.track_sliders[track_id]['main_button'].setChecked(value >= 95)
    
    def on_main_clicked(self, checked: bool, track_id: int, slider: QSlider, ratio_label: QLabel):
        """主音按钮点击"""
        if checked:
            # 设置为100%
            slider.setValue(100)
            ratio_label.setText("100%")
            self.track_volume_ratios[track_id] = 1.0
        else:
            # 取消主音，设置为50%
            slider.setValue(50)
            ratio_label.setText("50%")
            self.track_volume_ratios[track_id] = 0.5
    
    def get_volume_ratios(self) -> dict:
        """获取所有音轨的音量占比"""
        return self.track_volume_ratios.copy()

