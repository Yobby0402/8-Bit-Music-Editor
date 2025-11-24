"""
音符编辑对话框

用于添加和编辑音符的简单对话框。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QPushButton, QComboBox
)
from PyQt5.QtCore import Qt

from core.models import WaveformType


class NoteEditorDialog(QDialog):
    """音符编辑对话框"""
    
    def __init__(self, parent=None, pitch: int = 60, start_time: float = 0.0, 
                 duration: float = 0.5, waveform: WaveformType = WaveformType.SQUARE):
        """初始化对话框"""
        super().__init__(parent)
        self.setWindowTitle("添加/编辑音符")
        self.setModal(True)
        
        self.pitch = pitch
        self.start_time = start_time
        self.duration = duration
        self.waveform = waveform
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 音高选择
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(QLabel("音高 (MIDI 0-127):"))
        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(0, 127)
        self.pitch_spinbox.setValue(self.pitch)
        pitch_layout.addWidget(self.pitch_spinbox)
        
        # 显示音名
        self.note_name_label = QLabel()
        self.update_note_name()
        self.pitch_spinbox.valueChanged.connect(self.update_note_name)
        pitch_layout.addWidget(self.note_name_label)
        layout.addLayout(pitch_layout)
        
        # 开始时间（可以隐藏）
        self.time_layout = QHBoxLayout()
        self.start_time_label = QLabel("开始时间 (秒):")
        self.time_layout.addWidget(self.start_time_label)
        self.start_time_spinbox = QDoubleSpinBox()
        self.start_time_spinbox.setRange(0.0, 999.0)
        self.start_time_spinbox.setSingleStep(0.1)
        self.start_time_spinbox.setValue(self.start_time)
        self.time_layout.addWidget(self.start_time_spinbox)
        layout.addLayout(self.time_layout)
        
        # 持续时间
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("持续时间 (秒):"))
        self.duration_spinbox = QDoubleSpinBox()
        self.duration_spinbox.setRange(0.01, 10.0)
        self.duration_spinbox.setSingleStep(0.1)
        self.duration_spinbox.setValue(self.duration)
        duration_layout.addWidget(self.duration_spinbox)
        layout.addLayout(duration_layout)
        
        # 波形选择
        waveform_layout = QHBoxLayout()
        waveform_layout.addWidget(QLabel("波形:"))
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        waveform_map = {
            WaveformType.SQUARE: 0,
            WaveformType.TRIANGLE: 1,
            WaveformType.SAWTOOTH: 2,
            WaveformType.SINE: 3,
            WaveformType.NOISE: 4,
        }
        self.waveform_combo.setCurrentIndex(waveform_map.get(self.waveform, 0))
        waveform_layout.addWidget(self.waveform_combo)
        layout.addLayout(waveform_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
    
    def update_note_name(self):
        """更新音名显示"""
        pitch = self.pitch_spinbox.value()
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        self.note_name_label.setText(f"({note_name}{octave})")
    
    def get_values(self):
        """获取输入值"""
        waveform_map = {
            0: WaveformType.SQUARE,
            1: WaveformType.TRIANGLE,
            2: WaveformType.SAWTOOTH,
            3: WaveformType.SINE,
            4: WaveformType.NOISE,
        }
        return {
            "pitch": self.pitch_spinbox.value(),
            "start_time": self.start_time_spinbox.value(),
            "duration": self.duration_spinbox.value(),
            "waveform": waveform_map[self.waveform_combo.currentIndex()]
        }

