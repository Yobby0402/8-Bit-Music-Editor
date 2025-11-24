"""
音高滑块组件

大滑块，支持滑动试听。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QFont

from core.waveform_generator import WaveformGenerator
from core.audio_engine import AudioEngine


class PitchSliderWidget(QWidget):
    """音高滑块"""
    
    pitch_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        """初始化音高滑块"""
        super().__init__(parent)
        
        self.current_pitch = 60  # 默认C4
        self.audio_engine = AudioEngine()
        self.waveform_gen = WaveformGenerator()
        self.preview_sound = None
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.play_preview)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("音高选择")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)
        
        # 滑块容器
        slider_layout = QHBoxLayout()
        
        # MIDI编号标签（左侧）
        self.midi_label = QLabel("60")
        self.midi_label.setMinimumWidth(40)
        self.midi_label.setAlignment(Qt.AlignCenter)
        slider_layout.addWidget(self.midi_label)
        
        # 大滑块（垂直）
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 127)
        self.slider.setValue(60)
        self.slider.setMinimumHeight(200)  # 大滑块
        self.slider.setMaximumHeight(300)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderMoved.connect(self.on_slider_moved)
        slider_layout.addWidget(self.slider)
        
        # 音名标签（右侧）
        self.note_label = QLabel("C4")
        self.note_label.setMinimumWidth(60)
        self.note_label.setAlignment(Qt.AlignCenter)
        self.note_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        slider_layout.addWidget(self.note_label)
        
        layout.addLayout(slider_layout)
        
        # 更新显示
        self.update_labels()
    
    def on_slider_changed(self, value: int):
        """滑块值改变"""
        self.current_pitch = value
        self.update_labels()
        self.pitch_changed.emit(value)
    
    def on_slider_pressed(self):
        """滑块按下"""
        self.play_preview()
    
    def on_slider_moved(self, value: int):
        """滑块移动（实时试听）"""
        self.current_pitch = value
        self.update_labels()
        # 防抖：延迟播放，避免播放太频繁
        self.preview_timer.stop()
        self.preview_timer.start(100)  # 100ms后播放
    
    def update_labels(self):
        """更新标签"""
        self.midi_label.setText(str(self.current_pitch))
        
        # 计算音名
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = self.current_pitch // 12 - 1
        note_name = note_names[self.current_pitch % 12]
        self.note_label.setText(f"{note_name}{octave}")
    
    def play_preview(self):
        """播放预览"""
        # 停止之前的预览
        if self.preview_sound:
            self.audio_engine.stop_all()
        
        # 生成短音频（0.2秒）
        from core.models import Note, WaveformType
        note = Note(
            pitch=self.current_pitch,
            start_time=0.0,
            duration=0.2,
            waveform=WaveformType.SQUARE
        )
        
        audio = self.audio_engine.generate_note_audio(note)
        self.preview_sound = self.audio_engine.play_audio(audio, loop=False)
    
    def get_pitch(self) -> int:
        """获取当前音高"""
        return self.current_pitch
    
    def set_pitch(self, pitch: int):
        """设置音高"""
        pitch = max(0, min(127, pitch))
        self.slider.setValue(pitch)
        self.current_pitch = pitch
        self.update_labels()

