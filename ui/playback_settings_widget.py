"""
播放设置面板

用于设置每个音轨在播放时的音量占比，支持多选统一设置。
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.models import Track


class PlaybackSettingsWidget(QWidget):
    """播放设置面板"""
    
    # 信号：音量占比改变
    volume_ratios_changed = pyqtSignal(dict)  # {track_id: ratio}
    # 信号：音轨勾选状态改变
    track_selection_changed = pyqtSignal(dict)  # {track_id: enabled}
    
    def __init__(self, parent=None):
        """初始化播放设置面板"""
        super().__init__(parent)
        self.tracks = []
        self.track_volume_ratios = {}  # {track_id: ratio (0-1)}
        self.track_widgets = {}  # {track_id: widget_data}
        self.selected_track_ids = set()  # 选中的音轨ID集合
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.setLayout(layout)
        
        # 说明文字
        info_label = QLabel("设置每个音轨在播放时的音量占比（0-100%）。\n"
                           "占比越高，该音轨在混音中的音量越大。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(info_label)
        
        # 批量设置区域
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批量设置选中音轨:"))
        
        self.batch_ratio_spinbox = QSpinBox()
        self.batch_ratio_spinbox.setRange(0, 100)
        self.batch_ratio_spinbox.setValue(100)
        self.batch_ratio_spinbox.setSuffix("%")
        batch_layout.addWidget(self.batch_ratio_spinbox)
        
        self.batch_apply_button = QPushButton("应用")
        self.batch_apply_button.clicked.connect(self.apply_batch_ratio)
        batch_layout.addWidget(self.batch_apply_button)
        
        batch_layout.addStretch()
        layout.addLayout(batch_layout)
        
        # 全选/取消全选按钮
        select_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.select_all)
        select_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton("取消全选")
        self.deselect_all_button.clicked.connect(self.deselect_all)
        select_layout.addWidget(self.deselect_all_button)
        
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        # 滚动区域（包含所有音轨设置）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll_layout.setSpacing(8)
        self.scroll_content.setLayout(self.scroll_layout)
        
        scroll_area.setWidget(self.scroll_content)
        layout.addWidget(scroll_area)

    def _clear_track_layout(self) -> None:
        """Remove all current track rows and spacers from the scroll layout."""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _get_enabled_tracks_payload(self) -> dict[int, bool]:
        """Build the current enabled-track mapping from the selection state."""
        return {
            id(track): id(track) in self.selected_track_ids
            for track in self.tracks
        }

    def set_state(self, tracks: list, ratios: dict | None):
        """Batch-update tracks and ratios with a single rebuild."""
        self.tracks = tracks
        self.track_volume_ratios = ratios.copy() if ratios else {}
        self.refresh_tracks()
    
    def set_tracks(self, tracks: list):
        """设置音轨列表"""
        self.tracks = tracks
        self.refresh_tracks()
    
    def set_volume_ratios(self, ratios: dict):
        """设置音量占比字典"""
        self.track_volume_ratios = ratios.copy() if ratios else {}
        self.refresh_tracks()
    
    def refresh_tracks(self):
        """刷新音轨列表显示"""
        # 清除现有控件和旧的拉伸项，避免布局项不断堆积
        self._clear_track_layout()
        self.track_widgets.clear()
        active_track_ids = {id(track) for track in self.tracks}
        self.selected_track_ids.intersection_update(active_track_ids)
        
        # 为每个音轨创建控件
        # 默认所有音轨都被勾选（启用）
        for track in self.tracks:
            track_id = id(track)
            if track_id not in self.selected_track_ids:
                self.selected_track_ids.add(track_id)
            track_widget = self.create_track_volume_widget(track, track_id)
            self.scroll_layout.addWidget(track_widget)
        
        self.scroll_layout.addStretch()
        
        # 初始化时发出信号，确保外部同步到最新勾选状态
        if self.tracks:
            self.track_selection_changed.emit(self._get_enabled_tracks_payload())
    
    def create_track_volume_widget(self, track: Track, track_id: int) -> QWidget:
        """为单个音轨创建音量占比控件"""
        widget = QWidget()
        # 使用垂直布局，包含两行
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        widget.setLayout(main_layout)
        
        # 获取当前占比（如果没有设置，默认为100%）
        current_ratio = self.track_volume_ratios.get(track_id, 1.0)
        
        # 第一行：选择框、名称、主音按钮
        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(8)
        
        # 多选复选框
        checkbox = QCheckBox()
        checkbox.setChecked(track_id in self.selected_track_ids)
        checkbox.stateChanged.connect(lambda state, tid=track_id: self.on_track_selected(tid, state == Qt.Checked))
        first_row.addWidget(checkbox)
        
        # 音轨名称
        name_label = QLabel(track.name)
        name_label.setMinimumWidth(100)
        # 如果是主音轨，加粗显示
        if track_id in self.track_volume_ratios and self.track_volume_ratios[track_id] > 0.7:
            font = name_label.font()
            font.setBold(True)
            name_label.setFont(font)
        first_row.addWidget(name_label)
        
        first_row.addStretch()  # 添加弹性空间
        
        # 主音按钮（快速设置为100%）
        main_button = QPushButton("主音")
        main_button.setCheckable(True)
        main_button.setMinimumWidth(50)
        main_button.setMaximumWidth(60)
        if current_ratio >= 0.95:  # 如果占比接近100%，视为主音
            main_button.setChecked(True)
        first_row.addWidget(main_button)
        
        main_layout.addLayout(first_row)
        
        # 第二行：滑条和占比显示标签
        second_row = QHBoxLayout()
        second_row.setContentsMargins(0, 0, 0, 0)
        second_row.setSpacing(8)
        
        # 音量占比滑块
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(int(current_ratio * 100))
        slider.valueChanged.connect(lambda v, tid=track_id: self.on_ratio_changed(tid, v))
        second_row.addWidget(slider, 1)  # 滑条占据剩余空间
        
        # 占比显示标签
        ratio_label = QLabel(f"{int(current_ratio * 100)}%")
        ratio_label.setMinimumWidth(45)
        ratio_label.setMaximumWidth(50)
        ratio_label.setAlignment(Qt.AlignCenter)
        second_row.addWidget(ratio_label)
        
        main_layout.addLayout(second_row)
        
        # 连接主音按钮（在所有控件创建完成后）
        main_button.clicked.connect(lambda checked, tid=track_id, s=slider, rl=ratio_label: 
                                   self.on_main_clicked(checked, tid, s, rl))
        
        # 保存引用
        self.track_widgets[track_id] = {
            'widget': widget,
            'checkbox': checkbox,
            'slider': slider,
            'label': ratio_label,
            'name_label': name_label,
            'main_button': main_button,
            'track': track
        }
        
        return widget
    
    def on_track_selected(self, track_id: int, selected: bool):
        """音轨选择状态改变（勾选框状态改变）"""
        if selected:
            self.selected_track_ids.add(track_id)
        else:
            self.selected_track_ids.discard(track_id)
        
        # 发出信号通知勾选状态改变
        self.track_selection_changed.emit(self._get_enabled_tracks_payload())
    
    def select_all(self):
        """全选所有音轨"""
        for track_id, widget_data in self.track_widgets.items():
            widget_data['checkbox'].setChecked(True)
            self.selected_track_ids.add(track_id)
    
    def deselect_all(self):
        """取消全选"""
        for track_id, widget_data in self.track_widgets.items():
            widget_data['checkbox'].setChecked(False)
        self.selected_track_ids.clear()
        # 发出信号
        enabled_tracks = {tid: False for tid in self.track_widgets.keys()}
        self.track_selection_changed.emit(enabled_tracks)
    
    def apply_batch_ratio(self):
        """批量应用占比到选中的音轨"""
        if not self.selected_track_ids:
            return
        
        ratio = self.batch_ratio_spinbox.value() / 100.0
        
        for track_id in self.selected_track_ids:
            if track_id in self.track_widgets:
                widget_data = self.track_widgets[track_id]
                widget_data['slider'].setValue(int(ratio * 100))
                widget_data['label'].setText(f"{int(ratio * 100)}%")
                widget_data['main_button'].setChecked(ratio >= 0.95)
                self.track_volume_ratios[track_id] = ratio
        
        # 发出信号
        self.volume_ratios_changed.emit(self.track_volume_ratios.copy())
    
    def on_ratio_changed(self, track_id: int, value: int):
        """音量占比改变"""
        ratio = value / 100.0
        self.track_volume_ratios[track_id] = ratio
        
        # 更新标签和主音按钮状态
        if track_id in self.track_widgets:
            widget_data = self.track_widgets[track_id]
            widget_data['label'].setText(f"{value}%")
            widget_data['main_button'].setChecked(value >= 95)
            
            # 更新名称标签的加粗状态
            font = widget_data['name_label'].font()
            if ratio > 0.7:
                font.setBold(True)
            else:
                font.setBold(False)
            widget_data['name_label'].setFont(font)
        
        # 发出信号
        self.volume_ratios_changed.emit(self.track_volume_ratios.copy())
    
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
        
        # 发出信号
        self.volume_ratios_changed.emit(self.track_volume_ratios.copy())
    
    def get_volume_ratios(self) -> dict:
        """获取所有音轨的音量占比"""
        return self.track_volume_ratios.copy()
