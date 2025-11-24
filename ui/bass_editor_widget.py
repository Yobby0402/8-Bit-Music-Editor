"""
低音编辑器

用于添加低音事件。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.piano_keyboard_widget import PianoKeyboardWidget
from core.models import WaveformType


class BassEditorWidget(QWidget):
    """低音编辑器"""
    
    add_event_requested = pyqtSignal(int, float)  # pitch, duration_beats
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化低音编辑器"""
        super().__init__(parent)
        self.bpm = bpm
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI - 横向布局：空 | 音符按钮 | 拍数选择"""
        # 先初始化默认值
        self.selected_duration = 1.0
        
        # 主布局（水平）
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # 左侧占位（对齐主旋律编辑器的波形选择区域）
        spacer_left = QWidget()
        spacer_left.setMaximumWidth(150)
        main_layout.addWidget(spacer_left)
        main_layout.addSpacing(10)
        
        # 中间：音符按钮（钢琴键盘）
        piano_container = QWidget()
        piano_container_layout = QVBoxLayout()
        piano_container.setLayout(piano_container_layout)
        
        # 上方：信息显示区域
        info_area = QWidget()
        info_area.setMaximumHeight(40)
        info_layout = QHBoxLayout()
        info_area.setLayout(info_layout)
        
        self.pitch_info_label = QLabel("C4 (MIDI 60)")
        self.pitch_info_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        self.pitch_info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.pitch_info_label)
        
        piano_container_layout.addWidget(info_area)
        
        # 钢琴键盘（与主旋律使用相同的布局和八度范围）
        self.piano_keyboard = PianoKeyboardWidget()
        # 默认设置为C4（与主旋律一致），但用户可以选择任意八度
        # 连接点击信号，直接添加
        self.piano_keyboard.note_clicked.connect(self.on_piano_note_clicked)
        # 连接音高变化信号，更新显示
        self.piano_keyboard.pitch_changed.connect(self.on_pitch_changed)
        # 初始化预览参数（低音通常使用三角波）
        self.piano_keyboard.set_preview_params(WaveformType.TRIANGLE, self.selected_duration, self.bpm)
        piano_container_layout.addWidget(self.piano_keyboard, 1)
        
        main_layout.addWidget(piano_container, 1)  # 可拉伸
        main_layout.addSpacing(10)
        
        # 右侧：拍数选择
        duration_area = QWidget()
        duration_area.setMaximumWidth(150)
        duration_layout = QVBoxLayout()
        duration_area.setLayout(duration_layout)
        
        duration_label = QLabel("拍数")
        duration_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        duration_label.setAlignment(Qt.AlignCenter)
        duration_layout.addWidget(duration_label)
        
        duration_buttons_layout = QVBoxLayout()
        self.duration_buttons = []
        self.duration_group = QButtonGroup()
        
        duration_options = [
            ("1/4拍", 0.25),
            ("1/2拍", 0.5),
            ("1拍", 1.0),
            ("2拍", 2.0),
            ("4拍", 4.0)
        ]
        
        for name, beats in duration_options:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 12px;")
            if name == "1拍":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, b=beats: self.on_duration_selected(b))
            self.duration_buttons.append(btn)
            self.duration_group.addButton(btn)
            duration_buttons_layout.addWidget(btn)
        
        duration_buttons_layout.addStretch()
        duration_layout.addLayout(duration_buttons_layout)
        
        main_layout.addWidget(duration_area)
        
        # 初始化时更新显示（使用默认的C4）
        self.on_pitch_changed(self.piano_keyboard.get_pitch())
    
    def on_pitch_changed(self, pitch: int):
        """音高改变时更新显示"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        if hasattr(self, 'pitch_info_label'):
            self.pitch_info_label.setText(f"{note_name}{octave} (MIDI {pitch})")
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        # 更新预览参数
        self.piano_keyboard.set_preview_params(WaveformType.TRIANGLE, self.selected_duration, self.bpm)
    
    def on_duration_selected(self, beats: float):
        """时长选择"""
        self.selected_duration = beats
        # 更新预览参数
        self.piano_keyboard.set_preview_params(WaveformType.TRIANGLE, self.selected_duration, self.bpm)
    
    def on_piano_note_clicked(self, pitch: int):
        """钢琴键盘音符点击（直接添加）"""
        self.add_event_requested.emit(pitch, self.selected_duration)

