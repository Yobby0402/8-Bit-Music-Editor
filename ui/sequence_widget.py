"""
序列编辑器模块

类似PR/AE的序列编辑器，显示音符序列条。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont

from core.models import Note, Track


class NoteBlock(QWidget):
    """音符块"""
    
    clicked = pyqtSignal(Note)
    
    def __init__(self, note: Note, parent=None):
        """初始化音符块"""
        super().__init__(parent)
        self.note = note
        self.setMinimumHeight(40)
        self.setMaximumHeight(40)
        self.setMouseTracking(True)
        
        # 计算显示文本
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = note.pitch // 12 - 1
        note_name = note_names[note.pitch % 12]
        self.label = f"{note_name}{octave}"
    
    def paintEvent(self, event):
        """绘制音符块"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # 绘制背景
        color = QColor(100, 150, 255)  # 蓝色
        painter.fillRect(rect, QBrush(color))
        
        # 绘制边框
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawRect(rect)
        
        # 绘制文本
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.label)
    
    def mousePressEvent(self, event):
        """鼠标点击"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.note)
        super().mousePressEvent(event)


class SequenceTrackWidget(QWidget):
    """序列轨道"""
    
    note_clicked = pyqtSignal(Note)
    add_note_requested = pyqtSignal()
    
    def __init__(self, track: Track, bpm: float = 120.0, parent=None):
        """初始化序列轨道"""
        super().__init__(parent)
        self.track = track
        self.bpm = bpm
        self.pixels_per_beat = 80.0  # 每拍的像素数
        self.selected_note = None
        
        self.init_ui()
        self.refresh()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 轨道标题栏
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(self.track.name))
        header_layout.addStretch()
        
        # 添加音符按钮
        add_button = QPushButton("+ 添加音符")
        add_button.clicked.connect(self.add_note_requested.emit)
        header_layout.addWidget(add_button)
        
        header_frame = QFrame()
        header_frame.setLayout(header_layout)
        header_frame.setStyleSheet("background-color: #e0e0e0; padding: 5px;")
        layout.addWidget(header_frame)
        
        # 序列区域（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.sequence_widget = QWidget()
        self.sequence_layout = QHBoxLayout()
        self.sequence_layout.setSpacing(2)
        self.sequence_layout.setContentsMargins(5, 5, 5, 5)
        self.sequence_widget.setLayout(self.sequence_layout)
        
        scroll.setWidget(self.sequence_widget)
        layout.addWidget(scroll)
        
        # 设置最小高度
        self.setMinimumHeight(80)
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        self.refresh()
    
    def refresh(self):
        """刷新显示"""
        # 清除现有音符块
        while self.sequence_layout.count():
            item = self.sequence_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 按时间排序音符
        sorted_notes = sorted(self.track.notes, key=lambda n: n.start_time)
        
        # 计算当前总时长（用于显示网格）
        current_time = 0.0
        
        # 添加音符块
        for note in sorted_notes:
            # 如果有间隔，添加空白
            if note.start_time > current_time:
                # 计算间隔的像素数
                gap_beats = (note.start_time - current_time) * self.bpm / 60.0
                gap_pixels = int(gap_beats * self.pixels_per_beat)
                if gap_pixels > 0:
                    spacer = QWidget()
                    spacer.setFixedWidth(gap_pixels)
                    self.sequence_layout.addWidget(spacer)
            
            # 创建音符块
            note_block = NoteBlock(note)
            note_block.clicked.connect(self.on_note_clicked)
            
            # 计算宽度（基于时长）
            duration_beats = note.duration * self.bpm / 60.0
            width = max(40, int(duration_beats * self.pixels_per_beat))
            note_block.setFixedWidth(width)
            
            self.sequence_layout.addWidget(note_block)
            
            # 更新当前时间
            current_time = note.end_time
        
        # 添加弹性空间
        self.sequence_layout.addStretch()
    
    def on_note_clicked(self, note: Note):
        """音符点击"""
        self.selected_note = note
        self.note_clicked.emit(note)
    
    def add_note_at_end(self, pitch: int, duration: float, waveform=None):
        """在序列末尾添加音符"""
        # 计算开始时间
        if self.track.notes:
            start_time = max(note.end_time for note in self.track.notes)
        else:
            start_time = 0.0
        
        # 创建音符
        from core.models import Note
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            waveform=waveform or self.track.waveform
        )
        self.track.add_note(note)
        self.refresh()
        return note


class SequenceWidget(QWidget):
    """序列编辑器主组件"""
    
    note_clicked = pyqtSignal(Note, Track)
    add_note_requested = pyqtSignal(Track)
    
    def __init__(self, parent=None):
        """初始化序列编辑器"""
        super().__init__(parent)
        
        self.tracks = []
        self.bpm = 120.0
        self.track_widgets = []
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("序列编辑器")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # 序列轨道容器
        self.tracks_layout = QVBoxLayout()
        self.tracks_layout.setSpacing(5)
        
        tracks_widget = QWidget()
        tracks_widget.setLayout(self.tracks_layout)
        
        # 可滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(tracks_widget)
        layout.addWidget(scroll)
    
    def set_tracks(self, tracks: list):
        """设置轨道列表"""
        self.tracks = tracks
        self.refresh()
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        for widget in self.track_widgets:
            widget.set_bpm(bpm)
    
    def refresh(self):
        """刷新显示"""
        # 清除现有轨道控件
        for widget in self.track_widgets:
            widget.setParent(None)
        self.track_widgets.clear()
        
        # 添加轨道控件
        for track in self.tracks:
            track_widget = SequenceTrackWidget(track, self.bpm)
            track_widget.note_clicked.connect(
                lambda note, t=track: self.note_clicked.emit(note, t)
            )
            track_widget.add_note_requested.connect(
                lambda t=track: self.add_note_requested.emit(t)
            )
            self.track_widgets.append(track_widget)
            self.tracks_layout.addWidget(track_widget)

