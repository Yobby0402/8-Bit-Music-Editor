"""
轨道列表模块

显示和管理多个轨道。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QCheckBox, QComboBox, QListWidget,
    QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMouseEvent

from core.models import Track, WaveformType


class TrackItemWidget(QWidget):
    """单个轨道项"""
    
    # 信号
    track_changed = pyqtSignal(Track)
    track_selected = pyqtSignal(Track)
    track_deleted = pyqtSignal(Track)
    
    def __init__(self, track: Track, parent=None):
        """初始化轨道项"""
        super().__init__(parent)
        self.track = track
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        # 启用复选框
        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(self.track.enabled)
        self.enabled_checkbox.stateChanged.connect(self.on_enabled_changed)
        layout.addWidget(self.enabled_checkbox)
        
        # 轨道名称
        self.name_label = QLabel(self.track.name)
        self.name_label.setMinimumWidth(100)
        layout.addWidget(self.name_label)
        
        # 波形选择
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        # 设置当前波形
        waveform_map = {
            WaveformType.SQUARE: 0,
            WaveformType.TRIANGLE: 1,
            WaveformType.SAWTOOTH: 2,
            WaveformType.SINE: 3,
            WaveformType.NOISE: 4,
        }
        self.waveform_combo.setCurrentIndex(waveform_map.get(self.track.waveform, 0))
        self.waveform_combo.currentIndexChanged.connect(self.on_waveform_changed)
        layout.addWidget(self.waveform_combo)
        
        # 音量滑块
        layout.addWidget(QLabel("音量:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.track.volume * 100))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel(f"{int(self.track.volume * 100)}%")
        self.volume_label.setMinimumWidth(40)
        layout.addWidget(self.volume_label)
        
        # 静音按钮
        self.mute_button = QPushButton("M")
        self.mute_button.setCheckable(True)
        self.mute_button.setMaximumWidth(30)
        self.mute_button.clicked.connect(self.on_mute_clicked)
        layout.addWidget(self.mute_button)
        
        # 独奏按钮
        self.solo_button = QPushButton("S")
        self.solo_button.setCheckable(True)
        self.solo_button.setMaximumWidth(30)
        layout.addWidget(self.solo_button)
        
        # 添加音符按钮
        self.add_note_button = QPushButton("添加音符")
        layout.addWidget(self.add_note_button)
        
        # 删除按钮
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.delete_button)
        
        # 设置鼠标事件，点击轨道项时选中
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 选中轨道"""
        if event.button() == Qt.LeftButton:
            # 检查是否点击在控件上（不是按钮）
            if event.pos().x() < self.width() - 200:  # 避免点击按钮时选中
                self.track_selected.emit(self.track)
        super().mousePressEvent(event)
    
    def on_enabled_changed(self, state):
        """启用状态改变"""
        self.track.enabled = (state == Qt.Checked)
        self.track_changed.emit(self.track)
    
    def on_waveform_changed(self, index):
        """波形改变"""
        waveform_map = {
            0: WaveformType.SQUARE,
            1: WaveformType.TRIANGLE,
            2: WaveformType.SAWTOOTH,
            3: WaveformType.SINE,
            4: WaveformType.NOISE,
        }
        self.track.waveform = waveform_map[index]
        self.track_changed.emit(self.track)
    
    def on_volume_changed(self, value):
        """音量改变"""
        self.track.volume = value / 100.0
        self.volume_label.setText(f"{value}%")
        self.track_changed.emit(self.track)
    
    def on_mute_clicked(self):
        """静音按钮点击"""
        # 这里可以添加静音逻辑
        pass
    
    def on_delete_clicked(self):
        """删除按钮点击"""
        self.track_deleted.emit(self.track)
    
    def update_track(self, track: Track):
        """更新轨道显示"""
        self.track = track
        self.name_label.setText(track.name)
        self.enabled_checkbox.setChecked(track.enabled)
        self.volume_slider.setValue(int(track.volume * 100))
        self.volume_label.setText(f"{int(track.volume * 100)}%")


class TrackListWidget(QWidget):
    """轨道列表"""
    
    # 信号
    track_selected = pyqtSignal(Track)
    track_changed = pyqtSignal(Track)
    track_added = pyqtSignal(Track)
    track_deleted = pyqtSignal(Track)
    add_note_requested = pyqtSignal(Track)  # 请求添加音符
    
    def __init__(self, parent=None):
        """初始化轨道列表"""
        super().__init__(parent)
        self.tracks = []
        self.track_widgets = []
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("轨道列表")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # 添加轨道按钮
        self.add_track_button = QPushButton("添加轨道")
        self.add_track_button.clicked.connect(self.add_track)
        layout.addWidget(self.add_track_button)
        
        # 轨道列表容器
        self.tracks_layout = QVBoxLayout()
        self.tracks_layout.setSpacing(5)
        layout.addLayout(self.tracks_layout)
        
        # 添加弹性空间
        layout.addStretch()
    
    def set_tracks(self, tracks: list):
        """设置轨道列表"""
        self.tracks = tracks
        self.refresh()
    
    def refresh(self):
        """刷新显示"""
        # 清除现有控件
        for widget in self.track_widgets:
            widget.setParent(None)
        self.track_widgets.clear()
        
        # 添加轨道控件
        for track in self.tracks:
            self.add_track_widget(track)
    
    def add_track_widget(self, track: Track):
        """添加轨道控件"""
        track_widget = TrackItemWidget(track)
        track_widget.track_changed.connect(self.on_track_changed)
        track_widget.track_selected.connect(self.on_track_selected)
        track_widget.track_deleted.connect(self.on_track_deleted)
        # 连接添加音符按钮
        track_widget.add_note_button.clicked.connect(
            lambda: self.add_note_requested.emit(track)
        )
        
        self.track_widgets.append(track_widget)
        self.tracks_layout.addWidget(track_widget)
    
    def add_track(self):
        """添加新轨道"""
        from core.models import Track, WaveformType
        # 检查是否已经存在，避免重复
        track_count = len([t for t in self.tracks if t.name.startswith("Track")])
        new_track = Track(
            name=f"Track {track_count + 1}",
            waveform=WaveformType.SQUARE
        )
        # 不在这里添加到tracks，让MainWindow统一管理
        # self.tracks.append(new_track)
        # self.add_track_widget(new_track)
        self.track_added.emit(new_track)
    
    def on_track_changed(self, track: Track):
        """轨道改变"""
        self.track_changed.emit(track)
    
    def on_track_selected(self, track: Track):
        """轨道选中"""
        self.track_selected.emit(track)
    
    def on_track_deleted(self, track: Track):
        """轨道删除"""
        if track in self.tracks:
            self.tracks.remove(track)
            # 找到并移除对应的控件
            for widget in self.track_widgets:
                if widget.track == track:
                    widget.setParent(None)
                    self.track_widgets.remove(widget)
                    break
            self.track_deleted.emit(track)

