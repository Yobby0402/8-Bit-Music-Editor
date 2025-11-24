"""
打击乐编辑器

用于添加打击乐事件。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer

from core.track_events import DrumType
from core.audio_engine import AudioEngine


class DrumEditorWidget(QWidget):
    """打击乐编辑器"""
    
    add_event_requested = pyqtSignal(DrumType, float)  # drum_type, duration_beats
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化打击乐编辑器"""
        super().__init__(parent)
        self.bpm = bpm
        self.audio_engine = AudioEngine()
        self.preview_sound = None
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.play_preview)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI - 横向布局：打击乐类型 | 空 | 拍数选择"""
        # 主布局（水平）
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # 左侧：打击乐类型选择
        drum_type_area = QWidget()
        drum_type_area.setMaximumWidth(150)
        drum_type_layout = QVBoxLayout()
        drum_type_area.setLayout(drum_type_layout)
        
        type_label = QLabel("打击乐类型")
        type_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        type_label.setAlignment(Qt.AlignCenter)
        drum_type_layout.addWidget(type_label)
        
        type_buttons_layout = QVBoxLayout()
        self.drum_buttons = []
        self.drum_group = QButtonGroup()
        
        drum_types = [
            ("底鼓", DrumType.KICK),
            ("军鼓", DrumType.SNARE),
            ("踩镲", DrumType.HIHAT),
            ("吊镲", DrumType.CRASH),
        ]
        
        self.selected_drum_type = DrumType.KICK
        
        for name, drum_type in drum_types:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 12px;")
            btn._drum_type = drum_type  # 保存类型引用
            if name == "底鼓":
                btn.setChecked(True)
            # 鼠标悬停播放预览
            btn.installEventFilter(self)
            # 点击打击乐类型按钮直接添加
            btn.clicked.connect(lambda checked, dt=drum_type: self.on_drum_type_clicked(dt))
            self.drum_buttons.append(btn)
            self.drum_group.addButton(btn)
            type_buttons_layout.addWidget(btn)
        
        type_buttons_layout.addStretch()
        drum_type_layout.addLayout(type_buttons_layout)
        
        main_layout.addWidget(drum_type_area)
        main_layout.addSpacing(10)
        
        # 中间：信息显示区域（占位，对齐钢琴键盘位置）
        info_container = QWidget()
        info_container_layout = QVBoxLayout()
        info_container.setLayout(info_container_layout)
        
        info_area = QWidget()
        info_area.setMaximumHeight(40)
        info_layout = QHBoxLayout()
        info_area.setLayout(info_layout)
        
        self.drum_info_label = QLabel("底鼓")
        self.drum_info_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        self.drum_info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.drum_info_label)
        
        info_container_layout.addWidget(info_area)
        info_container_layout.addStretch()
        
        main_layout.addWidget(info_container, 1)  # 可拉伸
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
            ("1拍", 1.0)
        ]
        
        self.selected_duration = 0.25
        
        for name, beats in duration_options:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 12px;")
            if name == "1/4拍":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, b=beats: self.on_duration_selected(b))
            self.duration_buttons.append(btn)
            self.duration_group.addButton(btn)
            duration_buttons_layout.addWidget(btn)
        
        duration_buttons_layout.addStretch()
        duration_layout.addLayout(duration_buttons_layout)
        
        main_layout.addWidget(duration_area)
    
    def on_drum_type_clicked(self, drum_type: DrumType):
        """打击乐类型点击（直接添加）"""
        self.selected_drum_type = drum_type
        # 更新按钮选中状态
        for btn in self.drum_buttons:
            if btn._drum_type == drum_type:
                btn.setChecked(True)
                break
        
        # 更新显示
        drum_names = {
            DrumType.KICK: "底鼓",
            DrumType.SNARE: "军鼓",
            DrumType.HIHAT: "踩镲",
            DrumType.CRASH: "吊镲"
        }
        if hasattr(self, 'drum_info_label'):
            self.drum_info_label.setText(drum_names.get(drum_type, "打击乐"))
        
        self.add_drum()
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
    
    def on_drum_type_selected(self, drum_type: DrumType):
        """打击乐类型选择（仅选中，不添加）"""
        self.selected_drum_type = drum_type
    
    def on_drum_type_clicked(self, drum_type: DrumType):
        """打击乐类型点击（直接添加）"""
        self.selected_drum_type = drum_type
        # 更新按钮选中状态
        for btn in self.drum_buttons:
            if btn._drum_type == drum_type:
                btn.setChecked(True)
                break
        self.add_drum()
    
    def on_duration_selected(self, beats: float):
        """时长选择"""
        self.selected_duration = beats
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于处理鼠标悬停"""
        if event.type() == QEvent.Enter:
            if hasattr(obj, '_drum_type'):
                self.on_drum_hover(obj._drum_type)
        return super().eventFilter(obj, event)
    
    def on_drum_hover(self, drum_type: DrumType):
        """打击乐悬停（播放预览）"""
        self.selected_drum_type = drum_type
        self.play_preview()
    
    def play_preview(self):
        """播放预览"""
        # 停止之前的预览
        if self.preview_sound:
            self.audio_engine.stop_all()
        
        # 将拍数转换为秒
        duration = self.selected_duration * 60.0 / self.bpm
        
        # 生成预览音频
        audio = self.audio_engine.generate_drum_audio(
            drum_type=self.selected_drum_type,
            duration=duration,
            velocity=127
        )
        
        self.preview_sound = self.audio_engine.play_audio(audio, loop=False)
    
    def add_drum(self):
        """添加打击乐（供外部调用）"""
        self.add_event_requested.emit(self.selected_drum_type, self.selected_duration)

