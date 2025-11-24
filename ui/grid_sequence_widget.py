"""
带网格的序列编辑器

显示多个轨道，支持网格对齐。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QPushButton, QGraphicsTextItem, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPointF, QObject, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QWheelEvent

from core.models import Note, Track, TrackType
from core.track_events import BassEvent, DrumEvent, DrumType
from ui.theme import theme_manager


class SequenceBlockSignals(QObject):
    """序列块的信号对象"""
    clicked = pyqtSignal(object)  # 发送Note/BassEvent/DrumEvent
    position_changed = pyqtSignal(object, float, float)  # 发送item、旧的start_time和新的start_time（秒）


class SequenceBlock(QGraphicsItem):
    """序列块（音符或事件）"""
    
    def __init__(self, item, track: Track, track_index: int, track_type: str, 
                 track_y: float, bpm: float = 120.0, pixels_per_beat: float = 40.0, 
                 parent_widget=None, parent=None):
        """
        初始化序列块
        
        Args:
            item: Note、BassEvent或DrumEvent对象
            track: 所属轨道
            track_index: 轨道索引
            track_type: "melody", "bass", "drum"
            track_y: 轨道的Y坐标
            bpm: BPM值，用于计算宽度
            pixels_per_beat: 每拍的像素数
        """
        super().__init__(parent)
        self.item = item
        self.track = track
        self.track_index = track_index
        self.track_type = track_type
        self.track_y = track_y
        self.bpm = bpm
        self.pixels_per_beat = pixels_per_beat
        self.beat_subdivision = 4  # 1/4拍对齐
        self.signals = SequenceBlockSignals()  # 创建信号对象
        self.original_y = track_y  # 保存原始Y坐标，用于限制拖动
        self.parent_widget = parent_widget  # 保存父widget引用，用于重叠检测
        
        # 波形颜色映射
        from core.models import WaveformType
        waveform_colors = {
            WaveformType.SQUARE: QColor(255, 107, 107),    # 红色 #FF6B6B
            WaveformType.TRIANGLE: QColor(78, 205, 196),   # 青色 #4ECDC4
            WaveformType.SAWTOOTH: QColor(255, 230, 109), # 黄色 #FFE66D
            WaveformType.SINE: QColor(149, 225, 211),     # 浅绿色 #95E1D3
            WaveformType.NOISE: QColor(150, 150, 150),    # 灰色
        }
        
        # 根据类型设置颜色和标签
        if track_type == "melody":
            # 如果是音符且有波形属性，使用波形颜色；否则使用默认颜色
            if hasattr(item, 'waveform') and item.waveform in waveform_colors:
                self.color = waveform_colors[item.waveform]
            else:
                self.color = QColor(100, 150, 255)  # 蓝色（默认）
            
            # 处理空白音符
            if hasattr(item, 'pitch') and item.pitch == 0:
                self.label = "休"
                self.color = QColor(180, 180, 180)  # 灰色
            else:
                note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
                octave = item.pitch // 12 - 1
                note_name = note_names[item.pitch % 12]
                self.label = f"{note_name}{octave}"
        elif track_type == "bass":
            # 如果是音符且有波形属性，使用波形颜色
            if hasattr(item, 'waveform') and item.waveform in waveform_colors:
                self.color = waveform_colors[item.waveform]
            else:
                self.color = QColor(150, 255, 150)  # 绿色（默认）
            
            if hasattr(item, 'pitch') and item.pitch == 0:
                self.label = "休"
                self.color = QColor(180, 180, 180)
            else:
                note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
                octave = item.pitch // 12 - 1
                note_name = note_names[item.pitch % 12]
                self.label = f"{note_name}{octave}"
        else:  # drum
            self.color = QColor(255, 150, 100)  # 橙色
            # 根据打击乐类型判断（DrumEvent对象）
            if isinstance(item, DrumEvent):
                drum_type_names = {
                    DrumType.KICK: "底鼓",
                    DrumType.SNARE: "军鼓",
                    DrumType.HIHAT: "踩镲",
                    DrumType.CRASH: "吊镲",
                }
                self.label = drum_type_names.get(item.drum_type, "打击")
            else:
                # 兼容旧的Note对象（根据音高判断）
                pitch_to_drum = {
                    36: "底鼓",   # C2
                    38: "军鼓",   # D2
                    42: "踩镲",   # F#2
                    49: "吊镲",   # C#3
                }
                self.label = pitch_to_drum.get(item.pitch, "打击")
        
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # 用于跟踪是否正在拖动
        self.is_dragging = False
        self.drag_start_pos = None  # 拖动开始时的位置
        self.drag_start_time = None  # 拖动开始时的start_time
    
    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        # 根据对象类型计算宽度
        if isinstance(self.item, DrumEvent):
            # DrumEvent 使用节拍
            duration_beats = self.item.duration_beats
        else:
            # Note 使用时间，需要转换为节拍
            duration_beats = self.item.duration * self.bpm / 60.0
        width = max(20, duration_beats * self.pixels_per_beat)  # 最小20像素
        
        return QRectF(0, 0, width, 40)
    
    def paint(self, painter: QPainter, option, widget):
        """绘制块"""
        rect = self.boundingRect()
        
        # 选择状态
        if self.isSelected():
            pen = QPen(QColor(255, 255, 0), 2)
        else:
            pen = QPen(QColor(0, 0, 0), 1)
        
        painter.setPen(pen)
        painter.setBrush(QBrush(self.color))
        painter.drawRoundedRect(rect, 3, 3)
        
        # 绘制标签
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.label)
    
    def itemChange(self, change, value):
        """项目改变时处理拖动"""
        if change == QGraphicsItem.ItemPositionChange:
            # 检查是否正在播放，如果正在播放，禁止拖动
            if self.parent_widget:
                main_window = self.parent_widget.parent()
                while main_window and not hasattr(main_window, 'sequencer'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'sequencer'):
                    if main_window.sequencer.playback_state.is_playing:
                        # 播放中，禁止移动，返回原位置
                        return QPointF(self.pos())
            
            # 拖动时自由移动，只限制Y坐标在当前轨道内，X坐标完全自由
            new_pos = value
            
            # 限制Y坐标在当前轨道内（垂直方向不动）
            track_y_min = self.original_y - 2  # 允许很小的浮动
            track_y_max = self.original_y + 42  # 轨道高度约40像素
            new_y = max(track_y_min, min(track_y_max, new_pos.y()))
            
            # X坐标完全自由，不限制（但最小值为轨道标签宽度）
            new_x = max(100, new_pos.x())  # 最小值是轨道标签宽度
            
            return QPointF(new_x, new_y)
        
        result = super().itemChange(change, value)
        return result
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        # 检查是否正在播放，如果正在播放，禁止拖动音符
        if self.parent_widget:
            main_window = self.parent_widget.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                if main_window.sequencer.playback_state.is_playing:
                    # 播放中，禁止拖动，只允许选择
                    if event.button() == Qt.LeftButton:
                        self.signals.clicked.emit(self.item)
                    event.accept()
                    return
        
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_start_pos = self.pos()  # 记录拖动开始位置
            self.signals.clicked.emit(self.item)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放 - 在这里进行吸附和重叠检测"""
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            
            # 拖动结束后，在最终位置上吸附到网格
            pos = self.pos()
            x_offset = pos.x() - 100  # 减去轨道标签宽度
            
            if x_offset >= 0:
                # 转换为节拍
                beats = x_offset / self.pixels_per_beat
                
                # 根据设置决定是否吸附对齐
                from ui.settings_manager import get_settings_manager
                settings_manager = get_settings_manager()
                if settings_manager.is_snap_to_beat_enabled():
                    # 吸附到1/4拍网格
                    snapped_beats = round(beats * self.beat_subdivision) / self.beat_subdivision
                else:
                    # 不吸附，保持原始位置
                    snapped_beats = beats
                # 确保不小于0
                snapped_beats = max(0, snapped_beats)
                
                # 根据对象类型处理
                if isinstance(self.item, DrumEvent):
                    # DrumEvent 使用节拍
                    new_start_beat = snapped_beats
                    
                    # 检查重叠和交换位置（使用节拍）
                    if self.parent_widget and hasattr(self.parent_widget, 'check_and_resolve_drum_overlap'):
                        resolved_beat = self.parent_widget.check_and_resolve_drum_overlap(
                            self.item, self.track, new_start_beat, self
                        )
                        if resolved_beat is not None:
                            new_start_beat = resolved_beat
                            snapped_beats = new_start_beat
                    
                    # 转换回像素位置
                    snapped_x = 100 + snapped_beats * self.pixels_per_beat
                    
                    # 设置吸附后的位置
                    self.setPos(snapped_x, self.original_y)
                    
                    # 更新事件的start_beat
                    if new_start_beat >= 0 and abs(self.item.start_beat - new_start_beat) > 0.001:
                        old_start_beat = self.item.start_beat
                        self.item.start_beat = new_start_beat
                        # 延迟发送位置改变信号（传递节拍）
                        QTimer.singleShot(0, lambda: self.signals.position_changed.emit(
                            self.item, old_start_beat * 60.0 / self.bpm, new_start_beat * 60.0 / self.bpm
                        ))
                else:
                    # Note 使用时间
                    new_start_time = snapped_beats * 60.0 / self.bpm
                    
                    # 根据设置决定是否检查重叠
                    from ui.settings_manager import get_settings_manager
                    settings_manager = get_settings_manager()
                    if not settings_manager.is_overlap_allowed() and self.parent_widget and hasattr(self.parent_widget, 'check_and_resolve_overlap'):
                        # 让父widget处理重叠检测和位置交换
                        resolved_time = self.parent_widget.check_and_resolve_overlap(
                            self.item, self.track, new_start_time, self
                        )
                        if resolved_time is not None:
                            new_start_time = resolved_time
                            # 重新计算吸附位置
                            snapped_beats = new_start_time * self.bpm / 60.0
                    
                    # 转换回像素位置
                snapped_x = 100 + snapped_beats * self.pixels_per_beat
                
                # 设置吸附后的位置
                self.setPos(snapped_x, self.original_y)
                
                # 更新音符的start_time（确保不小于0且与原来的值不同）
                if new_start_time >= 0 and abs(self.item.start_time - new_start_time) > 0.001:
                    old_start_time = self.item.start_time
                    self.item.start_time = new_start_time
                    # 延迟发送位置改变信号，传递旧位置和新位置
                    QTimer.singleShot(0, lambda: self.signals.position_changed.emit(self.item, old_start_time, new_start_time))
            
            self.drag_start_pos = None
        
        super().mouseReleaseEvent(event)


class GridSequenceWidget(QWidget):
    """带网格的序列编辑器"""
    
    note_clicked = pyqtSignal(object, Track)
    note_position_changed = pyqtSignal(object, Track, float, float)  # 音符位置改变 (note, track, old_start_time, new_start_time)
    note_deleted = pyqtSignal(object, Track)  # 音符删除（单个）
    notes_deleted = pyqtSignal(list)  # 批量删除音符 [(note, track), ...]
    selection_changed = pyqtSignal()  # 选择变化
    track_clicked = pyqtSignal(Track)  # 音轨被点击
    track_enabled_changed = pyqtSignal(Track, bool)  # 音轨启用状态改变
    track_deleted = pyqtSignal(Track)  # 音轨删除
    playhead_time_changed = pyqtSignal(float)  # 播放线时间改变
    add_melody_note = pyqtSignal(Track)
    add_bass_event = pyqtSignal(Track)
    add_drum_event = pyqtSignal(Track)
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化序列编辑器"""
        super().__init__(parent)
        
        self.tracks = []
        self.bpm = bpm
        self.pixels_per_beat = 40.0  # 每拍的像素数
        self.base_pixels_per_beat = 40.0  # 基础每拍像素数（用于缩放计算）
        self.beat_subdivision = 4  # 1/4拍对齐
        self.zoom_scale = 1.0  # 当前缩放比例
        self.zoom_direction_reversed = False  # 滚轮方向是否需要反转
        self.last_zoom_delta = 0  # 上次滚动的方向，用于检测
        self.last_zoom_scale = 1.0  # 上次缩放后的值
        
        # 播放头
        self.playhead_time = 0.0  # 当前播放时间（秒）
        self.playhead_item = None  # 播放头图形项
        
        # 播放线拖动状态
        self.is_dragging_playhead = False  # 是否正在拖动播放线
        
        # 网格线项列表（用于清除）
        self.grid_items = []
        
        # 轨道标签项列表（用于清除）
        self.track_label_items = []
        
        # 轨道线项列表（用于清除）
        self.track_line_items = []
        
        # 勾选框代理引用列表（用于断开信号连接）
        self.checkbox_proxies = []
        
        # 是否使用增量更新（默认启用）
        self.use_incremental_update = True
        
        # 高亮显示的音轨（用于显示正在插入音符的目标音轨）
        self.highlighted_track = None
        
        # 刷新标志，防止在刷新过程中处理信号
        self._is_refreshing = False
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # 设置大小策略：允许垂直和水平拉伸，但保持固定高度
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 音轨选择控制按钮
        track_selection_layout = QHBoxLayout()
        track_selection_layout.setContentsMargins(0, 0, 0, 0)
        track_selection_layout.setSpacing(6)
        
        theme = theme_manager.current_theme
        button_small_style = theme.get_style("button_small")
        
        # 添加音轨按钮（放在最左侧）
        self.add_track_button = QPushButton("添加音轨")
        self.add_track_button.setStyleSheet(button_small_style)
        track_selection_layout.addWidget(self.add_track_button)
        
        # 删除选中音轨按钮
        self.delete_track_button = QPushButton("删除音轨")
        self.delete_track_button.setStyleSheet(button_small_style)
        self.delete_track_button.setToolTip("删除当前选中的音轨")
        self.delete_track_button.clicked.connect(self.on_delete_track_clicked)
        track_selection_layout.addWidget(self.delete_track_button)
        
        track_selection_layout.addSpacing(8)
        
        select_all_btn = QPushButton("☑")  # 全选图标
        select_all_btn.setToolTip("全选")
        select_all_btn.setStyleSheet(button_small_style)
        select_all_btn.clicked.connect(self.select_all_tracks)
        track_selection_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("☐")  # 全不选图标
        deselect_all_btn.setToolTip("全不选")
        deselect_all_btn.setStyleSheet(button_small_style)
        deselect_all_btn.clicked.connect(self.deselect_all_tracks)
        track_selection_layout.addWidget(deselect_all_btn)
        
        invert_selection_btn = QPushButton("↻")  # 反选图标
        invert_selection_btn.setToolTip("反选")
        invert_selection_btn.setStyleSheet(button_small_style)
        invert_selection_btn.clicked.connect(self.invert_track_selection)
        track_selection_layout.addWidget(invert_selection_btn)
        
        # ========== 进度条（放在全选按钮那一行）==========
        from ui.progress_bar_widget import ProgressBarWidget
        self.progress_bar = ProgressBarWidget()
        # 连接进度条的播放线改变信号
        self.progress_bar.playhead_time_changed.connect(self.on_progress_bar_playhead_changed)
        track_selection_layout.addWidget(self.progress_bar, 1)  # 可拉伸，占满剩余空间
        
        layout.addLayout(track_selection_layout)
        
        # 场景和视图（直接添加到布局，不使用QScrollArea）
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        
        # 启用框选模式（RubberBandDrag）
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        
        # 设置QGraphicsView的滚动条策略：始终显示横向滚动条，垂直滚动条按需显示
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 确保垂直滚动条在需要时可用
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 启用键盘焦点，以便接收键盘事件
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.keyPressEvent = self.on_key_press
        
        # 连接滚动事件，实现轨道名称冻结（始终显示在左边）
        self.view.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll)
        self.view.verticalScrollBar().valueChanged.connect(self.on_vertical_scroll)
        
        # 重写鼠标事件以支持播放线拖动
        self.view.mousePressEvent = self.on_view_mouse_press
        self.view.mouseMoveEvent = self.on_view_mouse_move
        self.view.mouseReleaseEvent = self.on_view_mouse_release
        
        # 启用鼠标跟踪，以便在拖动时实时更新
        self.view.setMouseTracking(True)
        
        # 重写wheelEvent以支持Shift+滚轮和Alt+滚轮
        original_wheel_event = self.view.wheelEvent
        self.view.wheelEvent = self.on_wheel_event
        
        # 连接选择变化信号
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        # 设置视图最小高度，确保即使音轨较少也能占满区域
        # 注意：不要设置最大高度，让布局管理器控制，但保持最小高度固定
        self.view.setMinimumHeight(200)
        # 设置大小策略：允许垂直和水平拉伸，但不要超出父容器
        from PyQt5.QtWidgets import QSizePolicy
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 确保GridSequenceWidget本身不会因为内容变化而改变高度
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置视图背景色为主题色
        theme = theme_manager.current_theme
        self.view.setStyleSheet(f"background-color: {theme.get_color('background')};")
        
        # 直接添加到布局，不使用QScrollArea包装
        layout.addWidget(self.view, 1)  # 可拉伸，占满剩余空间
        
        # 选中的音符/事件（单个）
        self.selected_item = None
        self.selected_track = None
        
        # 选中的多个音符/事件
        self.selected_items = []  # [(note, track), ...]
        
        # 存储所有SequenceBlock的引用，用于重叠检测
        # 使用id()作为键，因为Note对象不可哈希
        self.note_blocks = {}  # {(id(note), id(track)): SequenceBlock}
    
    def on_key_press(self, event):
        """键盘按下事件"""
        # 检查是否正在播放，如果正在播放，禁止删除操作
        is_playing = False
        if hasattr(self, 'parent') and self.parent():
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                is_playing = main_window.sequencer.playback_state.is_playing
        
        # 处理Delete键删除选中的音符（支持多选）
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if not is_playing and self.selected_items:
                self.delete_selected_note()
            event.accept()
            return
        # 处理Ctrl+A全选
        elif event.key() == Qt.Key_A and event.modifiers() == Qt.ControlModifier:
            if not is_playing:
                for item in self.scene.items():
                    if isinstance(item, SequenceBlock):
                        item.setSelected(True)
            event.accept()
            return
        # 处理ESC取消选择
        elif event.key() == Qt.Key_Escape:
            for item in self.scene.selectedItems():
                item.setSelected(False)
            event.accept()
            return
        else:
            # 其他按键传递给默认处理
            QGraphicsView.keyPressEvent(self.view, event)
    
    def select_track_notes(self, track: Track):
        """选中指定轨道上的所有音符（优化处理，避免卡死）"""
        # 清除当前选择（批量处理，避免逐个处理导致卡顿）
        self.scene.clearSelection()
        
        # 收集该轨道上的所有音符块
        selected_blocks = []
        for (note_id, track_id), block in self.note_blocks.items():
            if block and block.scene() and id(block.track) == id(track):
                selected_blocks.append(block)
        
        # 如果音符数量过多，分批选中以避免卡死
        if len(selected_blocks) > 100:
            # 分批选中，每批100个，使用QTimer延迟处理
            from PyQt5.QtCore import QTimer
            
            def select_batch(start_idx):
                end_idx = min(start_idx + 100, len(selected_blocks))
                for i in range(start_idx, end_idx):
                    selected_blocks[i].setSelected(True)
                
                if end_idx < len(selected_blocks):
                    # 继续处理下一批
                    QTimer.singleShot(10, lambda: select_batch(end_idx))
                else:
                    # 所有批次处理完成，更新选中列表
                    self._update_selection_from_blocks(selected_blocks)
            
            # 开始第一批
            QTimer.singleShot(0, lambda: select_batch(0))
        else:
            # 音符数量不多，直接选中
            for block in selected_blocks:
                block.setSelected(True)
            self._update_selection_from_blocks(selected_blocks)
    
    def _update_selection_from_blocks(self, selected_blocks):
        """从选中的块更新选中列表"""
        # 更新选中列表
        self.selected_items = [(block.item, block.track) for block in selected_blocks]
        if self.selected_items:
            self.selected_item, self.selected_track = self.selected_items[0]
        else:
            self.selected_item = None
            self.selected_track = None
        
        # 发送选择变化信号
        self.selection_changed.emit()
    
    def on_selection_changed(self):
        """选择变化时更新选中列表"""
        selected_blocks = [item for item in self.scene.selectedItems() if isinstance(item, SequenceBlock)]
        self.selected_items = [(block.item, block.track) for block in selected_blocks]
        
        # 更新单个选中项（用于兼容原有代码）
        if self.selected_items:
            self.selected_item, self.selected_track = self.selected_items[0]
        else:
            self.selected_item = None
            self.selected_track = None
        
        # 发送选择变化信号（用于更新属性面板）
        if hasattr(self, 'selection_changed'):
            self.selection_changed.emit()
    
    def select_all_tracks(self):
        """全选所有音轨"""
        for track in self.tracks:
            track.enabled = True
        self.refresh()
    
    def deselect_all_tracks(self):
        """全不选所有音轨"""
        for track in self.tracks:
            track.enabled = False
        self.refresh()
    
    def invert_track_selection(self):
        """反选所有音轨"""
        for track in self.tracks:
            track.enabled = not track.enabled
        self.refresh()
    
    def on_delete_track_clicked(self):
        """删除选中音轨按钮点击"""
        # 获取当前选中的音轨（通过高亮音轨或选中的音符所在音轨）
        target_track = None
        
        # 优先使用高亮音轨
        if hasattr(self, 'highlighted_track') and self.highlighted_track:
            target_track = self.highlighted_track
        # 否则使用选中音符所在的音轨
        elif self.selected_track:
            target_track = self.selected_track
        
        if target_track:
            # 发送删除信号
            self.track_deleted.emit(target_track)
        else:
            # 如果没有选中的音轨，提示用户
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择一个音轨（点击音轨名称）")
    
    def on_track_enabled_changed(self, track: Track, enabled: bool):
        """音轨启用状态改变"""
        # 防止在刷新过程中触发（避免访问已删除的对象）
        if not hasattr(self, 'tracks') or track not in self.tracks:
            return
        
        if hasattr(self, '_is_refreshing') and self._is_refreshing:
            return
        
        track.enabled = enabled
        # 发送信号通知主窗口（主窗口会负责刷新UI，这里不刷新）
        self.track_enabled_changed.emit(track, enabled)
    
    def handle_multiple_drag_end(self):
        """处理多选拖动结束"""
        # 获取所有选中的blocks
        selected_blocks = [item for item in self.scene.selectedItems() if isinstance(item, SequenceBlock)]
        
        # 对每个选中的block进行重叠检测和位置交换
        for block in selected_blocks:
            if not block.is_dragging:
                continue
            
            # 获取当前吸附位置
            pos = block.pos()
            x_offset = pos.x() - 100
            if x_offset >= 0:
                beats = x_offset / block.pixels_per_beat
                
                # 根据设置决定是否吸附对齐
                from ui.settings_manager import get_settings_manager
                settings_manager = get_settings_manager()
                if settings_manager.is_snap_to_beat_enabled():
                    snapped_beats = round(beats * block.beat_subdivision) / block.beat_subdivision
                else:
                    snapped_beats = beats
                snapped_beats = max(0, snapped_beats)
                new_start_time = snapped_beats * 60.0 / block.bpm
                
                # 根据设置决定是否检查重叠
                if not settings_manager.is_overlap_allowed():
                    # 检查重叠和交换
                    resolved_time = self.check_and_resolve_overlap(
                        block.item, block.track, new_start_time, block
                    )
                else:
                    resolved_time = new_start_time
                if resolved_time is not None:
                    new_start_time = resolved_time
                    snapped_beats = new_start_time * block.bpm / 60.0
                    snapped_x = 100 + snapped_beats * block.pixels_per_beat
                    block.setPos(snapped_x, block.original_y)
                    
                    if abs(block.item.start_time - new_start_time) > 0.001:
                        old_time = block.item.start_time
                        block.item.start_time = new_start_time
                        QTimer.singleShot(0, lambda n=block.item, old_t=old_time, new_t=new_start_time: 
                                        block.signals.position_changed.emit(n, old_t, new_t))
    
    def delete_selected_note(self):
        """删除选中的音符（支持多选，通过信号通知主窗口处理）"""
        # 收集所有要删除的音符
        notes_to_delete = []
        
        # 先处理单个选中
        if self.selected_item and self.selected_track:
            if isinstance(self.selected_item, DrumEvent):
                # 打击乐事件：直接删除（暂时不支持批量删除打击乐事件）
                if self.selected_item in self.selected_track.drum_events:
                    self.selected_track.remove_drum_event(self.selected_item)
                    self.refresh_ui()
            elif self.selected_item in self.selected_track.notes:
                notes_to_delete.append((self.selected_item, self.selected_track))
        self.selected_item = None
        self.selected_track = None
        
        # 处理多选
        if self.selected_items:
            for item, track in self.selected_items[:]:  # 使用切片复制，避免在迭代时修改
                if isinstance(item, DrumEvent):
                    # 打击乐事件：直接删除
                    if item in track.drum_events:
                        track.remove_drum_event(item)
                elif item in track.notes:
                    notes_to_delete.append((item, track))
            self.selected_items.clear()
        
        # 批量删除音符
        if notes_to_delete:
            if len(notes_to_delete) == 1:
                # 单个删除，使用原有信号
                self.note_deleted.emit(notes_to_delete[0][0], notes_to_delete[0][1])
            else:
                # 批量删除，使用新信号
                self.notes_deleted.emit(notes_to_delete)
    
    def set_tracks(self, tracks: list, preserve_selection: bool = False):
        """设置轨道列表
        
        Args:
            tracks: 轨道列表
            preserve_selection: 是否保持选中状态
        """
        # 保存当前选中状态
        selected_note = None
        selected_track = None
        if preserve_selection:
            selected_note = self.selected_item
            selected_track = self.selected_track
        
        self.tracks = tracks
        self.refresh()
        
        # 恢复选中状态
        if preserve_selection and selected_note and selected_track:
            self.selected_item = selected_note
            self.selected_track = selected_track
            # 重新选中对应的block
            block = self.note_blocks.get((id(selected_note), id(selected_track)))
            if block:
                block.setSelected(True)
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        # 更新进度条的BPM
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_bpm(bpm)
        self.refresh()
    
    def set_highlighted_track(self, track):
        """设置高亮显示的音轨（用于显示正在插入音符的目标音轨）"""
        self.highlighted_track = track
        # 更新显示以反映高亮状态
        if self.use_incremental_update:
            # 使用增量更新，只更新轨道标签
            for i, label_item in enumerate(self.track_label_items):
                if label_item and label_item.scene() and i < len(self.tracks):
                    track = self.tracks[i]
                    is_highlighted = (self.highlighted_track is not None and id(track) == id(self.highlighted_track))
                    theme = theme_manager.current_theme
                    if is_highlighted:
                        highlight_color = QColor(theme.get_color("highlight"))
                        label_item.setDefaultTextColor(highlight_color)
                    else:
                        text_color = QColor(theme.get_color("text_primary"))
                        label_item.setDefaultTextColor(text_color)
                    label_item.is_highlighted = is_highlighted
        else:
            # 全量刷新
            self.refresh()
    
    def refresh(self, force_full_refresh: bool = False):
        """刷新显示（增量更新模式，避免空白闪烁）"""
        # 设置刷新标志，防止在刷新过程中处理信号
        self._is_refreshing = True
        
        try:
            # 如果禁用增量更新或强制全量刷新，使用传统方式
            if not self.use_incremental_update or force_full_refresh:
                self._full_refresh()
                return
            
            # 增量更新模式
            # 保存播放头时间
            old_playhead_time = self.playhead_time
            
            # 禁用视图自动更新，减少闪烁
            self.view.setUpdatesEnabled(False)
            
            try:
                # 计算内容的最大宽度（根据音符位置）
                max_x = 100  # 至少100像素（轨道标签宽度）
                for track in self.tracks:
                    if track.track_type == TrackType.DRUM_TRACK:
                        for event in track.drum_events:
                            end_beats = event.end_beat
                            x = 100 + end_beats * self.pixels_per_beat + 20
                            max_x = max(max_x, x)
                    else:
                        for note in track.notes:
                            start_beats = note.start_time * self.bpm / 60.0
                            duration_beats = note.duration * self.bpm / 60.0
                            end_beats = start_beats + duration_beats
                            x = 100 + end_beats * self.pixels_per_beat + 20
                            max_x = max(max_x, x)
                
                # 根据轨道数量调整场景高度（增加额外高度确保最后一行能显示）
                if self.tracks:
                    # 每个轨道60px高度，加上底部边距和额外空间确保滚动到底部时最后一行可见
                    scene_height = len(self.tracks) * 60 + 100  # 增加额外高度
                else:
                    scene_height = 200
                
                # 根据内容调整场景大小
                scene_width = max(2000, max_x)
                self.scene.setSceneRect(0, 0, scene_width, scene_height)
                
                # 更新进度条的总时长
                if hasattr(self, 'progress_bar'):
                    # 计算总时长（从场景宽度计算）
                    total_beats = max(32, int((scene_width - 100) / self.pixels_per_beat) + 4)
                    total_time = total_beats * 60.0 / self.bpm
                    self.progress_bar.set_total_time(total_time)
                
                # 动态调整视图最小高度（但不限制最大高度，允许滚动）
                # 注意：不要动态调整最小高度，这会导致布局不稳定
                # 保持固定的最小高度，让滚动条处理内容超出
                # self.view.setMinimumHeight 已经在 init_ui 中设置为 200，这里不再修改
                
                # 更新网格（只更新网格线，不重建）
                self.draw_grid()
                
                # 增量更新轨道和块
                self._incremental_update_tracks_and_blocks()
                
                # 更新播放头
                self.draw_playhead()
                
                # 恢复播放头时间
                self.playhead_time = old_playhead_time
                
            finally:
                # 重新启用视图更新
                self.view.setUpdatesEnabled(True)
                self.view.update()
                
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            # 重置刷新标志
            self._is_refreshing = False
    
    def _full_refresh(self):
        """全量刷新（传统方式，用于首次加载或强制刷新）"""
        # 保存播放头时间
        old_playhead_time = self.playhead_time
        
        # 在清除场景前，断开所有勾选框的信号连接并阻止信号
        for i, proxy in enumerate(self.checkbox_proxies):
            if proxy:
                try:
                    widget = proxy.widget()
                    if widget:
                        widget.blockSignals(True)
                        try:
                            widget.stateChanged.disconnect()
                        except:
                            pass
                        if proxy.scene():
                            self.scene.removeItem(proxy)
                        widget.setParent(None)
                except (AttributeError, RuntimeError) as e:
                    pass
        self.checkbox_proxies.clear()
        
        # 清除所有引用
        self.playhead_item = None
        self.grid_items.clear()
        self.track_label_items.clear()
        self.track_line_items.clear()
        self.note_blocks.clear()
        
        # 清除场景
        self.scene.clear()
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        # 恢复播放头时间
        self.playhead_time = old_playhead_time
        
        # 继续执行绘制逻辑（与原来的refresh相同）
        self._draw_all_content()
    
    def _draw_all_content(self):
        """绘制所有内容（用于全量刷新）"""
        # 计算内容的最大宽度
        max_x = 100
        for track in self.tracks:
            if track.track_type == TrackType.DRUM_TRACK:
                for event in track.drum_events:
                    end_beats = event.end_beat
                    x = 100 + end_beats * self.pixels_per_beat + 20
                    max_x = max(max_x, x)
            else:
                for note in track.notes:
                    start_beats = note.start_time * self.bpm / 60.0
                    duration_beats = note.duration * self.bpm / 60.0
                    end_beats = start_beats + duration_beats
                    x = 100 + end_beats * self.pixels_per_beat + 20
                    max_x = max(max_x, x)
        
        # 根据轨道数量调整场景高度
        if self.tracks:
            # 每个轨道60px高度，加上底部边距和额外空间确保滚动到底部时最后一行可见
            scene_height = len(self.tracks) * 60 + 100  # 增加额外高度
        else:
            scene_height = 200
        
        # 根据内容调整场景大小
        scene_width = max(2000, max_x)
        self.scene.setSceneRect(0, 0, scene_width, scene_height)
        
        # 注意：不要动态调整视图高度，这会导致布局不稳定
        # 保持固定的最小高度（已在 init_ui 中设置），让滚动条处理内容超出
        # self.view.setMinimumHeight 已经在 init_ui 中设置为 200，这里不再修改
        
        # 绘制网格
        self.draw_grid()
        
        # 绘制轨道和块
        self._draw_tracks_and_blocks()
        
        # 绘制播放头
        self.draw_playhead()
    
    def _incremental_update_tracks_and_blocks(self):
        """增量更新轨道和块（只更新变化的部分）"""
        track_spacing = 60
        
        # 如果轨道数量变化，需要处理轨道UI
        current_track_count = len(self.track_label_items)
        new_track_count = len(self.tracks)
        
        # 如果轨道数量减少，删除多余的轨道UI
        if new_track_count < current_track_count:
            # 删除多余的轨道标签和线
            for i in range(new_track_count, current_track_count):
                if i < len(self.track_label_items):
                    label_item = self.track_label_items[i]
                    if label_item and label_item.scene():
                        self.scene.removeItem(label_item)
                if i < len(self.track_line_items):
                    line_item = self.track_line_items[i]
                    if line_item and line_item.scene():
                        self.scene.removeItem(line_item)
            # 删除多余的勾选框
            if new_track_count < len(self.checkbox_proxies):
                for i in range(new_track_count, len(self.checkbox_proxies)):
                    proxy = self.checkbox_proxies[i]
                    if proxy:
                        try:
                            widget = proxy.widget()
                            if widget:
                                widget.blockSignals(True)
                                try:
                                    widget.stateChanged.disconnect()
                                except:
                                    pass
                                if proxy.scene():
                                    self.scene.removeItem(proxy)
                                widget.setParent(None)
                        except (AttributeError, RuntimeError):
                            pass
                self.checkbox_proxies = self.checkbox_proxies[:new_track_count]
            
            # 截断列表
            self.track_label_items = self.track_label_items[:new_track_count]
            self.track_line_items = self.track_line_items[:new_track_count]
        
        # 收集当前应该存在的块
        expected_blocks = {}
        for i, track in enumerate(self.tracks):
            y = i * track_spacing + 20
            
            if track.track_type == TrackType.DRUM_TRACK:
                for event in track.drum_events:
                    block_key = (id(event), id(track))
                    expected_blocks[block_key] = (event, track, i, y, "drum")
            else:
                for note in track.notes:
                    block_key = (id(note), id(track))
                    expected_blocks[block_key] = (note, track, i, y, self.get_track_type(track))
        
        # 删除不再存在的块（安全删除，断开信号连接）
        blocks_to_remove = []
        for block_key in self.note_blocks:
            if block_key not in expected_blocks:
                blocks_to_remove.append(block_key)
        
        for block_key in blocks_to_remove:
            block = self.note_blocks.get(block_key)
            if block:
                try:
                    # 断开信号连接，防止访问已删除的对象
                    if hasattr(block, 'signals'):
                        try:
                            block.signals.clicked.disconnect()
                        except:
                            pass
                        try:
                            block.signals.position_changed.disconnect()
                        except:
                            pass
                    # 从场景中移除
                    if block.scene():
                        self.scene.removeItem(block)
                except (AttributeError, RuntimeError):
                    # 如果对象已被删除，忽略错误
                    pass
            # 从字典中删除
            if block_key in self.note_blocks:
                del self.note_blocks[block_key]
        
        # 更新或创建块
        for i, track in enumerate(self.tracks):
            y = i * track_spacing + 20
            
            # 更新或创建轨道标签和勾选框
            if i >= len(self.track_label_items):
                # 需要创建新的轨道标签和勾选框
                self._create_track_ui(track, i, y)
            elif i < len(self.track_label_items):
                # 更新现有轨道标签
                label_item = self.track_label_items[i]
                if label_item and label_item.scene():
                    # 重要：更新track引用，确保点击时使用的是正确的track对象
                    label_item.track = track
                    label_item.setPlainText(track.name)
                    # 更新高亮状态
                    is_highlighted = (self.highlighted_track is not None and id(track) == id(self.highlighted_track))
                    theme = theme_manager.current_theme
                    if is_highlighted:
                        highlight_color = QColor(theme.get_color("highlight"))
                        label_item.setDefaultTextColor(highlight_color)
                    else:
                        text_color = QColor(theme.get_color("text_primary"))
                        label_item.setDefaultTextColor(text_color)
                    label_item.is_highlighted = is_highlighted
                # 更新勾选框状态
                if i < len(self.checkbox_proxies):
                    proxy = self.checkbox_proxies[i]
                    if proxy:
                        try:
                            widget = proxy.widget()
                            if widget:
                                widget.blockSignals(True)
                                widget.setChecked(track.enabled)
                                widget.blockSignals(False)
                        except (AttributeError, RuntimeError):
                            pass
            
            # 更新或创建块（渲染所有音符）
            if track.track_type == TrackType.DRUM_TRACK:
                sorted_events = sorted(track.drum_events, key=lambda e: e.start_beat)
                for event in sorted_events:
                    block_key = (id(event), id(track))
                    self._update_or_create_block(block_key, event, track, i, y, "drum")
            else:
                sorted_notes = sorted(track.notes, key=lambda n: n.start_time)
                for note in sorted_notes:
                    block_key = (id(note), id(track))
                    track_type = self.get_track_type(track)
                    self._update_or_create_block(block_key, note, track, i, y, track_type)
    
    def _update_or_create_block(self, block_key, item, track, track_index, y, track_type):
        """更新或创建块"""
        from core.track_events import DrumEvent
        from core.models import WaveformType
        
        if block_key in self.note_blocks:
            # 更新现有块
            block = self.note_blocks[block_key]
            if block and block.scene():
                # 更新块的pixels_per_beat
                block.pixels_per_beat = self.pixels_per_beat
                
                # 更新颜色（如果波形改变了）
                if hasattr(item, 'waveform') and not isinstance(item, DrumEvent):
                    waveform_colors = {
                        WaveformType.SQUARE: QColor(255, 107, 107),    # 红色 #FF6B6B
                        WaveformType.TRIANGLE: QColor(78, 205, 196),   # 青色 #4ECDC4
                        WaveformType.SAWTOOTH: QColor(255, 230, 109), # 黄色 #FFE66D
                        WaveformType.SINE: QColor(149, 225, 211),     # 浅绿色 #95E1D3
                        WaveformType.NOISE: QColor(150, 150, 150),    # 灰色
                    }
                    if item.waveform in waveform_colors:
                        block.color = waveform_colors[item.waveform]
                
                # 重新计算位置
                if isinstance(item, DrumEvent):
                    start_beats = item.start_beat
                else:  # Note
                    start_beats = item.start_time * self.bpm / 60.0
                
                # 根据设置决定是否对齐
                from ui.settings_manager import get_settings_manager
                settings_manager = get_settings_manager()
                if settings_manager.is_snap_to_beat_enabled():
                    start_beats = round(start_beats * 4) / 4
                x = 100 + start_beats * self.pixels_per_beat
                
                # 更新位置
                block.setPos(x, y)
                block.original_y = y
                
                # 更新选中状态
                if self.selected_item == item:
                    block.setSelected(True)
                elif (item, track) in self.selected_items:
                    block.setSelected(True)
                else:
                    block.setSelected(False)
                
                # 触发重绘以更新大小和颜色
                block.prepareGeometryChange()
                block.update()
        else:
            # 创建新块
            block = SequenceBlock(item, track, track_index, track_type, y, self.bpm, self.pixels_per_beat, parent_widget=self)
            
            # 计算位置
            if isinstance(item, DrumEvent):
                start_beats = item.start_beat
            else:  # Note
                start_beats = item.start_time * self.bpm / 60.0
            
            # 根据设置决定是否对齐
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            if settings_manager.is_snap_to_beat_enabled():
                start_beats = round(start_beats * 4) / 4
            x = 100 + start_beats * self.pixels_per_beat
            
            block.setPos(x, y)
            
            # 设置高z值，确保音符在网格线之上
            block.setZValue(10)  # 音符在网格线(z=1)之上，但在播放头(z=1000)之下
            
            # 设置选中状态
            if self.selected_item == item:
                block.setSelected(True)
            if (item, track) in self.selected_items:
                block.setSelected(True)
            
            # 连接信号
            if isinstance(item, DrumEvent):
                block.signals.clicked.connect(lambda e, t=track: self.on_note_block_clicked(e, t))
                block.signals.position_changed.connect(lambda e, old_st, new_st, t=track: self.on_drum_event_position_changed(e, t, old_st, new_st))
            else:
                block.signals.clicked.connect(lambda n, t=track: self.on_note_block_clicked(n, t))
                block.signals.position_changed.connect(lambda n, old_st, new_st, t=track: self.on_note_position_changed(n, t, old_st, new_st))
            
            self.scene.addItem(block)
            self.note_blocks[block_key] = block
    
    def _create_track_ui(self, track, track_index, y):
        """创建轨道的UI元素（标签、勾选框、线）"""
        from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsProxyWidget, QCheckBox
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont, QColor
        
        # 创建可点击的轨道标签
        class ClickableTrackLabel(QGraphicsTextItem):
            """可点击的轨道标签"""
            def __init__(self, text, track, parent_widget, is_highlighted=False):
                super().__init__(text)
                self.track = track
                self.parent_widget = parent_widget
                self.is_highlighted = is_highlighted
                # 根据是否高亮设置颜色
                theme = theme_manager.current_theme
                if is_highlighted:
                    highlight_color = QColor(theme.get_color("highlight"))
                    self.setDefaultTextColor(highlight_color)
                    self.setFont(QFont("Arial", 12, QFont.Bold))
                else:
                    text_color = QColor(theme.get_color("text_primary"))
                    self.setDefaultTextColor(text_color)
                    self.setFont(QFont("Arial", 12, QFont.Bold))
                self.setCursor(Qt.PointingHandCursor)
            
            def mousePressEvent(self, event):
                try:
                    if event.button() == Qt.LeftButton:
                        if hasattr(self, 'parent_widget') and self.parent_widget and hasattr(self, 'track') and self.track:
                            self.parent_widget.select_track_notes(self.track)
                            self.parent_widget.track_clicked.emit(self.track)
                    super().mousePressEvent(event)
                except (RuntimeError, AttributeError):
                    pass
        
        # 创建勾选框
        checkbox_widget = QCheckBox()
        enabled_state = track.enabled
        
        def on_checkbox_changed(state, captured_track=track):
            if hasattr(self, '_is_refreshing') and self._is_refreshing:
                return
            try:
                if not hasattr(self, 'tracks') or captured_track not in self.tracks:
                    return
                captured_track.enabled = (state == Qt.Checked)
                self.on_track_enabled_changed(captured_track, state == Qt.Checked)
            except (AttributeError, RuntimeError):
                pass
        
        checkbox_widget.stateChanged.connect(on_checkbox_changed)
        checkbox_widget.blockSignals(True)
        checkbox_widget.setChecked(enabled_state)
        checkbox_widget.blockSignals(False)
        
        checkbox_proxy = QGraphicsProxyWidget()
        checkbox_proxy.setWidget(checkbox_widget)
        # 初始位置使用场景坐标，但会在滚动时更新为视口坐标
        initial_x = 5  # 初始场景x坐标
        checkbox_proxy.setPos(initial_x, y + 15)
        checkbox_proxy.setZValue(200)  # 设置高z值，确保在最上层
        self.scene.addItem(checkbox_proxy)
        self.checkbox_proxies.append(checkbox_proxy)
        
        # 立即更新一次位置，确保勾选框显示在正确位置
        self.on_horizontal_scroll(self.view.horizontalScrollBar().value())
        
        # 创建轨道标签（检查是否高亮）
        # 设置高z值，确保标签始终可见，并且可以响应点击
        is_highlighted = (self.highlighted_track is not None and id(track) == id(self.highlighted_track))
        label_item = ClickableTrackLabel(track.name, track, self, is_highlighted)
        # 初始位置使用场景坐标，但会在滚动时更新为视口坐标
        # 先设置为场景坐标，滚动时会自动转换为视口坐标
        initial_x = 30  # 初始场景x坐标
        label_item.setPos(initial_x, y + 5)
        label_item.setZValue(200)  # 设置高z值，确保在最上层
        # 保存原始y坐标，用于滚动时更新位置
        label_item.original_y = y + 5
        self.scene.addItem(label_item)
        self.track_label_items.append(label_item)
        
        # 立即更新一次位置，确保标签显示在正确位置
        self.on_horizontal_scroll(self.view.horizontalScrollBar().value())
        
        # 创建轨道线（设置低z值，确保在底层）
        pen = QPen(QColor(200, 200, 200), 1)
        scene_width = max(2000, self.scene.sceneRect().width())
        line_item = self.scene.addLine(100, y, scene_width, y, pen)
        line_item.setZValue(0)  # 设置最低z值，确保在底层
        self.track_line_items.append(line_item)
    
    def _draw_tracks_and_blocks(self):
        """绘制所有轨道和块（用于全量刷新）"""
        track_spacing = 60
        
        for i, track in enumerate(self.tracks):
            y = i * track_spacing + 20
            self._create_track_ui(track, i, y)
            
            track_type = self.get_track_type(track)
            
            if track.track_type == TrackType.DRUM_TRACK:
                sorted_events = sorted(track.drum_events, key=lambda e: e.start_beat)
                for event in sorted_events:
                    start_beats = event.start_beat
                    # 根据设置决定是否对齐
                    from ui.settings_manager import get_settings_manager
                    settings_manager = get_settings_manager()
                    if settings_manager.is_snap_to_beat_enabled():
                        start_beats = round(start_beats * 4) / 4
                    x = 100 + start_beats * self.pixels_per_beat
                    block = SequenceBlock(event, track, i, "drum", y, self.bpm, self.pixels_per_beat, parent_widget=self)
                    block.setPos(x, y)
                    block.setZValue(10)  # 确保音符在网格线之上
                    if self.selected_item == event:
                        block.setSelected(True)
                    if (event, track) in self.selected_items:
                        block.setSelected(True)
                    block.signals.clicked.connect(lambda e, t=track: self.on_note_block_clicked(e, t))
                    block.signals.position_changed.connect(lambda e, old_st, new_st, t=track: self.on_drum_event_position_changed(e, t, old_st, new_st))
                    self.scene.addItem(block)
                    self.note_blocks[(id(event), id(track))] = block
            else:
                sorted_notes = sorted(track.notes, key=lambda n: n.start_time)
                for note in sorted_notes:
                    start_beats = note.start_time * self.bpm / 60.0
                    # 根据设置决定是否对齐
                    from ui.settings_manager import get_settings_manager
                    settings_manager = get_settings_manager()
                    if settings_manager.is_snap_to_beat_enabled():
                        start_beats = round(start_beats * 4) / 4
                    x = 100 + start_beats * self.pixels_per_beat
                block = SequenceBlock(note, track, i, track_type, y, self.bpm, self.pixels_per_beat, parent_widget=self)
                block.setPos(x, y)
                block.setZValue(10)  # 确保音符在网格线之上
                if self.selected_item == note:
                    block.setSelected(True)
                if (note, track) in self.selected_items:
                    block.setSelected(True)
                block.signals.clicked.connect(lambda n, t=track: self.on_note_block_clicked(n, t))
                block.signals.position_changed.connect(lambda n, old_st, new_st, t=track: self.on_note_position_changed(n, t, old_st, new_st))
                self.scene.addItem(block)
                self.note_blocks[(id(note), id(track))] = block
    
    def on_note_block_clicked(self, note, track):
        """音符块被点击"""
        self.selected_item = note
        self.selected_track = track
        # 发送点击信号
        self.note_clicked.emit(note, track)
        # 确保视图有焦点以便接收键盘事件
        self.view.setFocus()
    
    def draw_grid(self):
        """绘制网格（根据缩放级别自适应显示，绘制全部网格）"""
        # 先清除旧的网格线
        for item in self.grid_items:
            try:
                if item.scene() == self.scene:
                    self.scene.removeItem(item)
            except (RuntimeError, AttributeError):
                pass
        self.grid_items.clear()
        
        # 获取场景尺寸
        scene_rect = self.scene.sceneRect()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()
        
        if scene_width <= 0 or scene_height <= 0:
            return  # 场景无效，不绘制
        
        # 计算整个场景的拍数范围
        max_beats = int((scene_width - 100) / self.pixels_per_beat) + 4  # 多绘制一些，确保覆盖
        start_beat = 0
        
        # 根据缩放级别决定显示哪些网格线
        # pixels_per_beat 越大，缩放越大
        # 阈值设置：
        # - pixels_per_beat < 20: 只显示小节线（每4拍）
        # - 20 <= pixels_per_beat < 40: 显示小节线和拍线
        # - pixels_per_beat >= 40: 显示小节线、拍线和1/4拍线
        
        # 使用主题颜色
        theme = theme_manager.current_theme
        border_color = QColor(theme.get_color("border_dark"))
        border_light_color = QColor(theme.get_color("border"))
        border_lighter_color = QColor(theme.get_color("border_light"))
        
        # 绘制小节线（每4拍）- 始终显示，设置低z值确保在底层
        first_measure_beat = (start_beat // 4) * 4  # 第一个小节
        for beat in range(first_measure_beat, start_beat + max_beats, 4):
            x = 100 + beat * self.pixels_per_beat
            if x <= scene_width:  # 只绘制在场景范围内的线
                pen = QPen(border_color, 2)
                line_item = self.scene.addLine(x, 0, x, scene_height, pen)
                line_item.setZValue(1)  # 设置低z值，确保在音符之下
                self.grid_items.append(line_item)
        
        # 绘制拍线（每拍）- 当 pixels_per_beat >= 20 时显示，设置低z值确保在底层
        if self.pixels_per_beat >= 20:
            for beat in range(start_beat, start_beat + max_beats):
                # 跳过小节线（每4拍），避免重复
                if beat % 4 != 0:
                    x = 100 + beat * self.pixels_per_beat
                    if x <= scene_width:  # 只绘制在场景范围内的线
                        pen = QPen(border_light_color, 1)
                        line_item = self.scene.addLine(x, 0, x, scene_height, pen)
                        line_item.setZValue(1)  # 设置低z值，确保在音符之下
                        self.grid_items.append(line_item)
        
        # 绘制1/4拍线（虚线）- 当 pixels_per_beat >= 40 时显示，设置低z值确保在底层
        if self.pixels_per_beat >= 40:
            start_quarter_beat = start_beat * 4
            end_quarter_beat = (start_beat + max_beats) * 4
            for beat in range(start_quarter_beat, end_quarter_beat):
                # 跳过拍线（每拍），避免重复
                if beat % 4 != 0:
                    x = 100 + beat * self.pixels_per_beat / 4
                    if x <= scene_width:  # 只绘制在场景范围内的线
                        pen = QPen(border_lighter_color, 1, Qt.DashLine)
                        line_item = self.scene.addLine(x, 0, x, scene_height, pen)
                        line_item.setZValue(1)  # 设置低z值，确保在音符之下
                        self.grid_items.append(line_item)
    
    def draw_playhead(self):
        """绘制播放头"""
        # 移除旧的播放头（如果存在且有效）
        if self.playhead_item is not None:
            try:
                # 检查项是否还在场景中（如果对象已被删除，scene()会返回None或抛出异常）
                scene = self.playhead_item.scene()
                if scene is not None and scene == self.scene:
                    self.scene.removeItem(self.playhead_item)
            except (RuntimeError, AttributeError):
                # 如果对象已被删除，忽略错误
                pass
            finally:
                self.playhead_item = None
        
        # 计算播放头X位置（时间转像素）
        # 使用与时间轴相同的计算方式，确保对齐
        beats_per_second = self.bpm / 60.0
        beat_position = self.playhead_time * beats_per_second
        # 使用浮点数计算，然后转换为整数，确保与时间轴的播放线对齐
        x = 100 + beat_position * self.pixels_per_beat
        x = int(x)  # 转换为整数用于绘制
        
        # 绘制播放头线（使用主题错误色，2像素宽）
        theme = theme_manager.current_theme
        playhead_color = QColor(theme.get_color("error"))  # 红色用于播放线
        pen = QPen(playhead_color, 2)
        self.playhead_item = self.scene.addLine(x, 0, x, 1000, pen)
        self.playhead_item.setZValue(1000)  # 确保播放头在最上层
    
    def set_playhead_time(self, time: float):
        """设置播放头时间"""
        self.playhead_time = time
        self.draw_playhead()
        
        # 更新进度条的播放线位置
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_playhead_time(time)
        
        # 如果播放头超出视图范围，自动滚动
        beats_per_second = self.bpm / 60.0
        beat_position = self.playhead_time * beats_per_second
        x = 100 + beat_position * self.pixels_per_beat
        
        # 获取当前视图范围
        view_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        if x < view_rect.left() or x > view_rect.right():
            # 居中播放头
            self.view.centerOn(x, self.view.mapToScene(self.view.viewport().rect().center()).y())
    
    def check_and_resolve_overlap(self, moved_note: Note, moved_track: Track, 
                                   new_start_time: float, moved_block) -> float:
        """
        检查并解决重叠问题
        
        Args:
            moved_note: 被移动的音符
            moved_track: 音符所在的轨道
            new_start_time: 新的开始时间
            moved_block: 被移动的SequenceBlock对象
        
        Returns:
            解决后的开始时间（如果发生交换，返回交换后的时间；如果有重叠且无法交换，返回原时间）
        """
        # 如果允许重叠，直接返回新位置
        from ui.settings_manager import get_settings_manager
        settings_manager = get_settings_manager()
        if settings_manager.is_overlap_allowed():
            return new_start_time
        # 计算新位置的时间范围
        new_end_time = new_start_time + moved_note.duration
        old_start_time = moved_note.start_time
        old_end_time = old_start_time + moved_note.duration
        
        # 计算网格位置（1/4拍为单位），用于精确位置检测
        grid_unit = 0.25  # 1/4拍
        new_grid_pos = round(new_start_time * self.bpm / 60.0 / grid_unit)
        old_grid_pos = round(old_start_time * self.bpm / 60.0 / grid_unit)
        
        # 检查同一轨道上的其他音符
        for other_note in moved_track.notes:
            if other_note == moved_note:
                continue
            
            # 计算其他音符的时间范围
            other_start_time = other_note.start_time
            other_end_time = other_start_time + other_note.duration
            other_grid_pos = round(other_start_time * self.bpm / 60.0 / grid_unit)
            
            # 检查时间范围是否重叠
            # 重叠条件：新开始时间 < 其他结束时间 且 新结束时间 > 其他开始时间
            # 但排除完全相邻的情况（一个音符的结束时间等于另一个的开始时间）
            overlaps = (new_start_time < other_end_time and new_end_time > other_start_time)
            
            if overlaps:
                # 检查是否拖动到另一个音符的位置（交换）
                # 使用id()作为键，因为Note对象不可哈希
                other_block = self.note_blocks.get((id(other_note), id(moved_track)))
                if other_block and hasattr(other_block, 'drag_start_pos') and other_block.drag_start_pos is not None:
                    # 另一个音符也在拖动，跳过（让它们各自处理）
                    continue
                
                # 只有当拖动到另一个音符的精确开始位置（网格对齐）时，才考虑交换
                # 并且原始位置不与另一个音符重叠
                old_overlaps_other = (old_start_time < other_end_time and old_end_time > other_start_time)
                
                # 精确位置交换：新位置与另一个音符的开始位置对齐，且原始位置不重叠
                if new_grid_pos == other_grid_pos and not old_overlaps_other:
                    # 交换：另一个音符移动到原始位置
                    other_note.start_time = old_start_time
                    
                    # 更新另一个block的位置
                    if other_block:
                        old_start_beats = old_start_time * self.bpm / 60.0
                        other_snapped_x = 100 + old_start_beats * self.pixels_per_beat
                        other_block.setPos(other_snapped_x, other_block.original_y)
                        # 发送位置改变信号（需要3个参数：item, old_time, new_time）
                        QTimer.singleShot(0, lambda: other_block.signals.position_changed.emit(
                            other_note, old_start_time, other_note.start_time
                        ))
                    
                    # 当前音符使用新位置
                    return new_start_time
                else:
                    # 如果拖动会导致重叠但不是精确交换位置，不允许移动（避免重叠）
                    return moved_note.start_time
        
        # 没有重叠，返回新位置
        return new_start_time
    
    def on_view_mouse_release(self, event):
        """视图鼠标释放事件（结束播放线拖动或多选拖动）"""
        # 如果正在拖动播放线，结束拖动
        if self.is_dragging_playhead:
            self.is_dragging_playhead = False
            event.accept()
            return
        
        # 检查是否正在播放，如果正在播放，禁止多选拖动
        is_playing = False
        if hasattr(self, 'parent') and self.parent():
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                is_playing = main_window.sequencer.playback_state.is_playing
        
        # 先调用默认处理（用于多选拖动）
        QGraphicsView.mouseReleaseEvent(self.view, event)
        
        # 检查是否有多个选中的items在拖动（只有在非播放状态才处理）
        if not is_playing:
            selected_blocks = [item for item in self.scene.selectedItems() if isinstance(item, SequenceBlock)]
            if len(selected_blocks) > 1:
                # 多选拖动，处理重叠检测
                self.handle_multiple_drag_end()
    
    def on_note_position_changed(self, note: Note, track: Track, old_start_time: float, new_start_time: float):
        """音符位置改变时处理"""
        # 注意：note.start_time 已经在 itemChange 中更新了，不需要再次更新
        
        # 重新排序轨道的音符
        track.notes.sort(key=lambda n: n.start_time)
        
        # 发送信号通知主窗口（传递旧位置和新位置）
        self.note_position_changed.emit(note, track, old_start_time, new_start_time)
        
        # 延迟刷新显示，避免在 itemChange 执行时刷新导致对象被删除
        QTimer.singleShot(10, self.refresh)
    
    def on_drum_event_position_changed(self, event: DrumEvent, track: Track, old_start_time: float, new_start_time: float):
        """打击乐事件位置改变时处理"""
        # 注意：event.start_beat 已经在 itemChange 中更新了，不需要再次更新
        
        # 重新排序轨道的打击乐事件
        track.drum_events.sort(key=lambda e: e.start_beat)
        
        # 延迟刷新显示，避免在 itemChange 执行时刷新导致对象被删除
        QTimer.singleShot(10, self.refresh)
    
    def on_view_mouse_press(self, event):
        """视图鼠标按下事件（用于播放线定位和拖动）"""
        scene_pos = self.view.mapToScene(event.pos())
        scene_y = scene_pos.y()
        
        # 检查是否点击在第一个音轨上方（时间轴区域，y < 20）
        # 第一个音轨的y坐标是 20，所以 y < 20 的区域是时间轴区域
        if scene_y < 20:
            # 在时间轴区域点击，开始拖动播放线
            self.is_dragging_playhead = True
            self.update_playhead_from_pos(scene_pos)
            event.accept()
            return
        
        # 首先检查是否点击到了音符块或其他图形项
        # 使用 items() 方法查找点击位置的所有项，然后检查是否有 SequenceBlock
        items_at_pos = self.scene.items(scene_pos)
        
        # 如果点击到了音符块或其他可交互项，直接传递给默认处理（不移动播放线）
        for item in items_at_pos:
            if isinstance(item, SequenceBlock):
                # 点击到了音符块，只选择音符，不移动播放线
                QGraphicsView.mousePressEvent(self.view, event)
                return
        
        # 检查是否正在播放，如果正在播放，禁止操作音符
        if hasattr(self, 'parent') and self.parent():
            # 检查主窗口的播放状态
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                if main_window.sequencer.playback_state.is_playing:
                    # 播放中，禁止操作音符
                    event.accept()
                    return
        
        # 在音轨区域点击，只选择音符，不移动播放线
        # 调用原始事件处理（用于选择音符等）
        QGraphicsView.mousePressEvent(self.view, event)
    
    def on_view_mouse_move(self, event):
        """视图鼠标移动事件"""
        # 如果正在拖动播放线，更新播放线位置
        if self.is_dragging_playhead:
            scene_pos = self.view.mapToScene(event.pos())
            self.update_playhead_from_pos(scene_pos)
            event.accept()
            return
        
        # 否则调用原始事件处理（用于音符拖动等）
        QGraphicsView.mouseMoveEvent(self.view, event)
    
    def on_wheel_event(self, event: QWheelEvent):
        """处理滚轮事件"""
        # 获取修饰键
        modifiers = event.modifiers()
        angle_delta = event.angleDelta()
        
        # 尝试多种方式获取delta
        if angle_delta.y() != 0:
            delta = angle_delta.y()
        elif angle_delta.x() != 0:
            # 如果Y是0但X不是0，可能是水平滚轮
            delta = angle_delta.x()
        elif hasattr(event, 'delta') and event.delta() != 0:
            delta = event.delta()  # 旧版API
        else:
            # 如果都没有，尝试pixelDelta
            pixel_delta = event.pixelDelta()
            if pixel_delta and pixel_delta.y() != 0:
                delta = pixel_delta.y()
            elif pixel_delta and pixel_delta.x() != 0:
                delta = pixel_delta.x()
            else:
                # 默认处理
                QGraphicsView.wheelEvent(self.view, event)
                return
        
        # Alt + 滚轮：缩放（优先级最高）
        if modifiers & Qt.AltModifier:
            # Alt + 滚轮：缩放
            # 使用zoom_scale来跟踪当前缩放状态
            current_scale = self.zoom_scale
            
            # 计算缩放因子
            zoom_step = 1.15  # 每次缩放15%
            
            # 简化逻辑：直接根据delta计算，但先测试方向
            # 如果两个方向都缩小，说明逻辑有问题
            # 让我们使用最简单的方式：delta的正负决定放大缩小
            
            # 尝试1：标准方向（delta > 0 向上，放大）
            # delta > 0: 放大
            # delta < 0: 缩小
            
            # 但用户说两个方向都缩小，说明可能有其他问题
            # 让我们强制测试：如果current_scale已经是1.0，那么向上应该放大
            
            # 添加调试：打印delta和current_scale
            # print(f"Delta: {delta}, Current scale: {current_scale}, Zoom scale attr: {self.zoom_scale}")
            
            # 强制测试：直接使用相反的判断
            # 因为用户说两个方向都缩小，说明当前的"放大"逻辑实际上是缩小
            # 让我们强制反转
            
            # 简单粗暴的方法：如果current_scale是1.0且new_scale计算后还是1.0以下，说明方向反了
            # 或者更简单：直接硬编码一个测试方向
            
            # 完全反转方向测试：delta > 0 放大，delta < 0 缩小（标准方向）
            # 如果用户说两个方向都缩小，可能是限制范围的问题
            # 让我们强制一个方向测试
            if delta > 0:
                # delta > 0，放大（向上滚动）
                new_scale = current_scale * zoom_step
            else:
                # delta < 0，缩小（向下滚动）
                new_scale = current_scale / zoom_step
            
            # 确保 new_scale 真的改变了
            # 如果 current_scale 已经是 0.2（最小值），向下滚动无法再缩小
            # 如果 current_scale 已经是 5.0（最大值），向上滚动无法再放大
            
            # 限制缩放范围（0.2倍到5倍）
            if new_scale < 0.2:
                new_scale = 0.2
            elif new_scale > 5.0:
                new_scale = 5.0
            
            # 如果缩放确实改变了，才应用
            if abs(new_scale - current_scale) > 0.001:  # 避免无意义的缩放
                # 保存当前鼠标位置的场景坐标和滚动位置
                view_pos = event.pos()
                scene_pos_before = self.view.mapToScene(view_pos)
                scroll_bar = self.view.horizontalScrollBar()
                old_scroll_value = scroll_bar.value()
                
                # 直接修改pixels_per_beat，不使用视图变换（更简单可靠）
                # 先更新缩放值，确保刷新时使用新值
                old_pixels = self.pixels_per_beat
                self.zoom_scale = new_scale
                self.pixels_per_beat = self.base_pixels_per_beat * self.zoom_scale
                
                # 使用增量更新（只更新块的位置和大小，不重建场景）
                self.update_blocks_for_zoom()
                
                # 刷新后检查是否被重置
                if abs(self.zoom_scale - new_scale) > 0.01:
                    self.zoom_scale = new_scale
                    self.pixels_per_beat = self.base_pixels_per_beat * self.zoom_scale
                
                # 缩放后，调整滚动位置，使鼠标位置的场景坐标保持不变
                scene_pos_after = self.view.mapToScene(view_pos)
                if abs(scene_pos_after.x() - scene_pos_before.x()) > 0.1:
                    # 计算需要调整的像素数
                    delta_pixels = scene_pos_before.x() - scene_pos_after.x()
                    # 调整滚动条位置
                    new_scroll_value = old_scroll_value + int(delta_pixels)
                    scroll_bar.setValue(new_scroll_value)
                else:
                    # 如果没有明显偏移，保持原滚动位置按比例调整
                    scroll_bar.setValue(int(old_scroll_value * (new_scale / current_scale)))
                
            event.accept()
            return
        
        # Shift + 滚轮：水平滚动
        if modifiers & Qt.ShiftModifier:
            # 水平滚动
            scroll_bar = self.view.horizontalScrollBar()
            scroll_bar.setValue(scroll_bar.value() - delta)
            event.accept()
            return
        
        # 默认：垂直滚动（上下滑动音轨区域）
        scroll_bar = self.view.verticalScrollBar()
        
        # 检查是否有内容需要滚动
        scene_rect = self.scene.sceneRect()
        view_height = self.view.viewport().height()
        scene_height = scene_rect.height()
        
        # 如果场景高度大于视图高度，或者滚动条已经可用，执行滚动
        if scene_height > view_height or scroll_bar.maximum() > 0:
            # 执行垂直滚动
            current_value = scroll_bar.value()
            new_value = current_value - delta
            # 确保滚动值在有效范围内
            new_value = max(scroll_bar.minimum(), min(new_value, scroll_bar.maximum()))
            scroll_bar.setValue(new_value)
            event.accept()
            return
        
        # 如果没有可滚动内容，调用默认处理
        QGraphicsView.wheelEvent(self.view, event)
    
    def on_horizontal_scroll(self, value):
        """横向滚动时，更新轨道标签位置，使其始终显示在左边（冻结窗格）"""
        # 将视口坐标转换为场景坐标，确保标签始终显示在视口左侧
        # 视口左侧的x坐标是0，转换为场景坐标
        viewport_left = self.view.mapToScene(0, 0).x()
        # 标签固定在视口左侧30像素处（视口坐标）
        fixed_viewport_x = 30
        # 转换为场景坐标
        fixed_scene_x = self.view.mapToScene(fixed_viewport_x, 0).x()
        
        # 更新所有轨道标签的x坐标
        for label_item in self.track_label_items:
            if label_item and label_item.scene():
                # 保持y坐标不变，只更新x坐标到固定位置（使用场景坐标）
                if hasattr(label_item, 'original_y'):
                    label_item.setPos(fixed_scene_x, label_item.original_y)
                else:
                    # 如果没有original_y，保持当前y坐标
                    current_y = label_item.pos().y()
                    label_item.original_y = current_y
                    label_item.setPos(fixed_scene_x, current_y)
        
        # 更新所有勾选框的x坐标
        for checkbox_proxy in self.checkbox_proxies:
            if checkbox_proxy and checkbox_proxy.scene():
                # 勾选框固定在视口左侧5像素处
                fixed_checkbox_x = self.view.mapToScene(5, 0).x()
                current_y = checkbox_proxy.pos().y()
                checkbox_proxy.setPos(fixed_checkbox_x, current_y)
    
    def on_vertical_scroll(self, value):
        """纵向滚动时，更新轨道标签位置，使其始终显示在左边（冻结窗格）"""
        # 将视口坐标转换为场景坐标，确保标签始终显示在视口左侧
        fixed_viewport_x = 30
        fixed_scene_x = self.view.mapToScene(fixed_viewport_x, 0).x()
        
        # 更新所有轨道标签的位置，使其跟随垂直滚动
        track_spacing = 60
        for i, label_item in enumerate(self.track_label_items):
            if label_item and label_item.scene() and i < len(self.tracks):
                # 计算标签应该的y坐标（基于轨道索引）
                y = i * track_spacing + 20 + 5
                label_item.original_y = y
                label_item.setPos(fixed_scene_x, y)
        
        # 更新所有勾选框的y坐标
        for i, checkbox_proxy in enumerate(self.checkbox_proxies):
            if checkbox_proxy and checkbox_proxy.scene() and i < len(self.tracks):
                y = i * track_spacing + 20 + 15
                fixed_checkbox_x = self.view.mapToScene(5, 0).x()
                checkbox_proxy.setPos(fixed_checkbox_x, y)
    
    def update_playhead_from_pos(self, scene_pos):
        """根据场景坐标更新播放线位置"""
        scene_x = scene_pos.x()
        # 减去轨道标签宽度（100像素）
        x_offset = scene_x - 100
        if x_offset < 0:
            x_offset = 0
        
        # 计算对应的节拍数
        beat_position = x_offset / self.pixels_per_beat
        # 转换为时间（秒）
        beats_per_second = self.bpm / 60.0
        time = beat_position / beats_per_second
        
        # 根据设置决定是否吸附
        from ui.settings_manager import get_settings_manager
        settings_manager = get_settings_manager()
        if settings_manager.is_snap_to_beat_enabled():
            # 吸附到1/4拍
            beat_subdivision = 4
            snapped_beat = round(beat_position * beat_subdivision) / beat_subdivision
            time = snapped_beat / beats_per_second
        
        # 更新播放线位置
        self.set_playhead_time(time)
        # 发送信号通知主窗口
        self.playhead_time_changed.emit(time)
    
    def on_progress_bar_playhead_changed(self, time: float):
        """进度条播放线位置改变"""
        # 只有在不拖动播放线时才更新（避免冲突）
        if not self.is_dragging_playhead:
            # 设置序列编辑器的播放线位置
            self.set_playhead_time(time)
            # 发送信号通知主窗口
            self.playhead_time_changed.emit(time)
    
    
    def update_blocks_for_zoom(self):
        """更新所有块的位置和大小以适应新的缩放比例（不重建场景）"""
        # 禁用视图自动更新，减少闪烁
        self.view.setUpdatesEnabled(False)
        
        try:
            # 更新所有块的位置和大小
            for (item_id, track_id), block in self.note_blocks.items():
                if block and block.scene():
                    # 更新块的pixels_per_beat
                    block.pixels_per_beat = self.pixels_per_beat
                    
                    # 重新计算位置
                    from core.track_events import DrumEvent
                    if isinstance(block.item, DrumEvent):
                        start_beats = block.item.start_beat
                    else:  # Note
                        start_beats = block.item.start_time * self.bpm / 60.0
                    
                    # 根据设置决定是否对齐
                    from ui.settings_manager import get_settings_manager
                    settings_manager = get_settings_manager()
                    if settings_manager.is_snap_to_beat_enabled():
                        start_beats = round(start_beats * 4) / 4
                    x = 100 + start_beats * self.pixels_per_beat
                    
                    # 更新位置
                    block.setPos(x, block.original_y)
                    
                    # 触发重绘以更新大小
                    block.prepareGeometryChange()
                    block.update()
            
            # 更新网格
            self.draw_grid()
            
            # 重新绘制播放头（使用新的pixels_per_beat）
            self.draw_playhead()
        finally:
            # 重新启用视图更新
            self.view.setUpdatesEnabled(True)
            self.view.update()
    
    def update_block_for_note(self, note, track):
        """更新单个音符块的位置和大小（不重建场景）"""
        from core.track_events import DrumEvent
        from core.models import WaveformType
        
        block_key = (id(note), id(track))
        if block_key in self.note_blocks:
            block = self.note_blocks[block_key]
            if block and block.scene():
                # 更新块的pixels_per_beat
                block.pixels_per_beat = self.pixels_per_beat
                
                # 更新颜色（如果波形改变了）
                if hasattr(note, 'waveform') and not isinstance(note, DrumEvent):
                    waveform_colors = {
                        WaveformType.SQUARE: QColor(255, 107, 107),    # 红色 #FF6B6B
                        WaveformType.TRIANGLE: QColor(78, 205, 196),   # 青色 #4ECDC4
                        WaveformType.SAWTOOTH: QColor(255, 230, 109), # 黄色 #FFE66D
                        WaveformType.SINE: QColor(149, 225, 211),     # 浅绿色 #95E1D3
                        WaveformType.NOISE: QColor(150, 150, 150),    # 灰色
                    }
                    if note.waveform in waveform_colors:
                        block.color = waveform_colors[note.waveform]
                
                # 重新计算位置
                if isinstance(note, DrumEvent):
                    start_beats = note.start_beat
                else:  # Note
                    start_beats = note.start_time * self.bpm / 60.0
                
                # 根据设置决定是否对齐
                from ui.settings_manager import get_settings_manager
                settings_manager = get_settings_manager()
                if settings_manager.is_snap_to_beat_enabled():
                    start_beats = round(start_beats * 4) / 4
                x = 100 + start_beats * self.pixels_per_beat
                
                # 更新位置
                block.setPos(x, block.original_y)
                
                # 触发重绘以更新大小和颜色
                block.prepareGeometryChange()
                block.update()
    
    def get_track_type(self, track: Track) -> str:
        """获取轨道类型"""
        if track.name == "主旋律":
            return "melody"
        elif track.name == "低音":
            return "bass"
        elif track.name == "打击乐":
            return "drum"
        else:
            return "melody"  # 默认

