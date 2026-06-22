"""
带网格的序列编辑器

显示多个轨道，支持网格对齐。
"""

from contextlib import contextmanager
from time import perf_counter

from PyQt5.QtCore import QObject, QPoint, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QWheelEvent
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.models import Note, Track, TrackRole, TrackType, WaveformType
from core.track_events import DrumEvent, DrumType
from ui.theme import theme_manager

GRID_REFRESH_PROFILE_THRESHOLD_MS = 100.0
PLAYHEAD_AUTOSCROLL_PROFILE_THRESHOLD_MS = 16.0
PLAYHEAD_FOLLOW_MARGIN_RATIO = 0.14
PLAYHEAD_FOLLOW_TARGET_RATIO = 0.72
PLAYHEAD_SCROLL_MIN_DELTA_PX = 12
PLAYHEAD_FIXED_TARGET_RATIO = 0.35
PLAYHEAD_FIXED_SCROLL_MIN_DELTA_PX = 1
TRACK_DEFAULT_HEIGHT = 60.0
TRACK_MIN_HEIGHT = 24.0
TRACK_MAX_HEIGHT = 360.0
TRACK_HEIGHT_ZOOM_MIN = 0.5
TRACK_HEIGHT_ZOOM_MAX = 3.0
TRACK_HEIGHT_ZOOM_STEP = 1.12
LOCATOR_BAR_HEIGHT = 28
TRACK_TOP_PADDING = float(LOCATOR_BAR_HEIGHT)
TRACK_BOTTOM_PADDING = 20.0
TRACK_NAME_PANEL_MIN_WIDTH = 120
TRACK_NAME_PANEL_MAX_WIDTH = 280
TRACK_RESIZE_HANDLE_HEIGHT = 6
NOTE_BLOCK_HEIGHT = 40.0
NOTE_BLOCK_MIN_HEIGHT = 16.0
NOTE_BLOCK_VERTICAL_MARGIN = 8.0
BLOCK_LABEL_MIN_WIDTH = 24.0
SCENE_TAIL_PADDING_PX = 80.0
SCENE_MIN_WIDTH = 480.0
ZOOM_MIN_SCALE_HARD = 0.005
ZOOM_MAX_SCALE = 5.0
ZOOM_FIT_VIEW_MARGIN_PX = 24.0
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
NOTE_LABELS = tuple(
    "休" if pitch == 0 else f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"
    for pitch in range(128)
)
DRUM_TYPE_LABELS = {
    DrumType.KICK: "底鼓",
    DrumType.SNARE: "军鼓",
    DrumType.HIHAT: "踩镲",
    DrumType.CRASH: "吊镲",
}
DRUM_PITCH_LABELS = {
    36: "底鼓",
    38: "军鼓",
    42: "踩镲",
    49: "吊镲",
}


def distribute_integer_space(total: int, count: int) -> list[int]:
    """Split an integer total into nearly even integer chunks."""
    safe_count = max(0, int(count))
    if safe_count <= 0:
        return []
    safe_total = max(0, int(total))
    base = safe_total // safe_count
    remainder = safe_total % safe_count
    return [
        base + (1 if index < remainder else 0)
        for index in range(safe_count)
    ]


class SequenceBlockSignals(QObject):
    """序列块的信号对象"""
    clicked = pyqtSignal(object)  # 发送Note/BassEvent/DrumEvent
    position_changed = pyqtSignal(object, float, float)  # 发送item、旧的start_time和新的start_time（秒）


class TrackListItemWidget(QWidget):
    """左侧音轨列表项，支持点击选中和拖动调整单轨高度。"""

    clicked = pyqtSignal(object, object)
    resize_requested = pyqtSignal(object, int)
    resize_finished = pyqtSignal(object, int)

    def __init__(self, track: Track, height_px: float, parent=None):
        super().__init__(parent)
        self.track = track
        self._drag_start_global_y = None
        self._drag_start_height = None

        self.label = QLabel(track.name, self)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.label.setWordWrap(False)
        self.label.mousePressEvent = self._on_label_mouse_press

        self.resize_handle = QWidget(self)
        self.resize_handle.setFixedHeight(TRACK_RESIZE_HANDLE_HEIGHT)
        self.resize_handle.setCursor(Qt.SizeVerCursor)
        self.resize_handle.mousePressEvent = self._on_resize_handle_mouse_press
        self.resize_handle.mouseMoveEvent = self._on_resize_handle_mouse_move
        self.resize_handle.mouseReleaseEvent = self._on_resize_handle_mouse_release

        self.set_track_height(height_px)

    def set_track_height(self, height_px: float) -> None:
        safe_height = max(TRACK_MIN_HEIGHT, float(height_px))
        rounded_height = int(round(safe_height))
        self.setFixedHeight(rounded_height)
        self._update_child_geometries()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_child_geometries()

    def _update_child_geometries(self) -> None:
        widget_width = max(0, self.width())
        widget_height = max(0, self.height())
        label_margin_x = 4
        self.label.setGeometry(
            label_margin_x,
            0,
            max(0, widget_width - label_margin_x * 2),
            widget_height,
        )
        self.resize_handle.setGeometry(
            0,
            max(0, widget_height - TRACK_RESIZE_HANDLE_HEIGHT),
            widget_width,
            TRACK_RESIZE_HANDLE_HEIGHT,
        )
        self.resize_handle.raise_()

    def _on_label_mouse_press(self, event) -> None:
        self.clicked.emit(self.track, event)

    def _on_resize_handle_mouse_press(self, event) -> None:
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        self._drag_start_global_y = event.globalY()
        self._drag_start_height = self.height()
        event.accept()

    def _on_resize_handle_mouse_move(self, event) -> None:
        if self._drag_start_global_y is None or self._drag_start_height is None:
            event.ignore()
            return
        requested_height = self._drag_start_height + (event.globalY() - self._drag_start_global_y)
        self.set_track_height(requested_height)
        self.resize_requested.emit(self.track, requested_height)
        event.accept()

    def _on_resize_handle_mouse_release(self, event) -> None:
        requested_height = self.height()
        if self._drag_start_global_y is not None and self._drag_start_height is not None:
            requested_height = self._drag_start_height + (
                event.globalY() - self._drag_start_global_y
            )
        self.resize_finished.emit(self.track, int(round(requested_height)))
        self._drag_start_global_y = None
        self._drag_start_height = None
        event.accept()


class TrackHeaderPanel(QWidget):
    """Paint the left-side track headers in the same vertical coordinate model as the grid."""

    clicked = pyqtSignal(object, object)
    resize_requested = pyqtSignal(object, int)
    resize_finished = pyqtSignal(object, int)

    def __init__(self, grid_widget, parent=None):
        super().__init__(parent or grid_widget)
        self._grid_widget = grid_widget
        self._tracks: list[Track] = []
        self._layout_metrics: list[tuple[float, float]] = []
        self._scene_top = 0.0
        self._selected_track_ids: set[int] = set()
        self._hover_track_index: int | None = None
        self._hover_handle_track_index: int | None = None
        self._resize_track_index: int | None = None
        self._drag_start_global_y: int | None = None
        self._drag_start_height: float | None = None
        self.setMouseTracking(True)
        self.setMinimumWidth(TRACK_NAME_PANEL_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def sync_state(
        self,
        *,
        tracks: list[Track],
        layout_metrics: list[tuple[float, float]],
        scene_top: float,
        selected_tracks: list[Track],
    ) -> None:
        self._tracks = list(tracks)
        self._layout_metrics = list(layout_metrics)
        self._scene_top = max(0.0, float(scene_top))
        self._selected_track_ids = {id(track) for track in selected_tracks}
        self.update()

    def clear_state(self) -> None:
        self._tracks = []
        self._layout_metrics = []
        self._scene_top = 0.0
        self._selected_track_ids.clear()
        self._hover_track_index = None
        self._hover_handle_track_index = None
        self._resize_track_index = None
        self.update()

    def sizeHint(self):
        return QSize(TRACK_NAME_PANEL_MIN_WIDTH, 200)

    def minimumSizeHint(self):
        return QSize(TRACK_NAME_PANEL_MIN_WIDTH, 80)

    def _row_rect_for_track_index(self, track_index: int) -> QRectF | None:
        if not (0 <= track_index < len(self._layout_metrics)):
            return None
        track_top, track_height = self._layout_metrics[track_index]
        return QRectF(
            0.0,
            track_top - self._scene_top,
            float(self.width()),
            float(track_height),
        )

    def _track_index_at_pos(self, pos: QPoint) -> int | None:
        scene_y = self._scene_top + float(pos.y())
        for index, (track_top, track_height) in enumerate(self._layout_metrics):
            if track_top <= scene_y < track_top + track_height:
                return index
        return None

    def _is_resize_handle_hit(self, track_index: int | None, pos: QPoint) -> bool:
        if track_index is None:
            return False
        row_rect = self._row_rect_for_track_index(track_index)
        if row_rect is None:
            return False
        return float(pos.y()) >= row_rect.bottom() - TRACK_RESIZE_HANDLE_HEIGHT

    def _update_hover_state(self, pos: QPoint | None) -> None:
        previous_hover = self._hover_track_index
        previous_handle_hover = self._hover_handle_track_index
        track_index = None if pos is None else self._track_index_at_pos(pos)
        handle_track_index = (
            track_index
            if self._is_resize_handle_hit(track_index, pos)
            else None
        ) if pos is not None else None

        self._hover_track_index = track_index
        self._hover_handle_track_index = handle_track_index
        if handle_track_index is not None or self._resize_track_index is not None:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

        if (
            previous_hover != self._hover_track_index
            or previous_handle_hover != self._hover_handle_track_index
        ):
            self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._update_hover_state(None)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setClipRect(event.rect())

        theme = theme_manager.current_theme
        background = QColor(theme.get_color("background"))
        hover_background = QColor(theme.get_color("hover"))
        selected_background = QColor(theme.get_color("accent_light"))
        border_color = QColor(theme.get_color("border"))
        accent_color = QColor(theme.get_color("accent"))
        text_color = QColor(theme.get_color("text_primary"))
        muted_text_color = QColor(theme.get_color("text_secondary"))

        painter.fillRect(self.rect(), background)

        width = self.width()
        height = self.height()
        painter.setPen(QPen(border_color, 1))
        painter.drawLine(width - 1, 0, width - 1, height)

        if not self._tracks or not self._layout_metrics:
            painter.setPen(QPen(muted_text_color))
            painter.drawText(
                self.rect().adjusted(10, 0, -10, 0),
                Qt.AlignCenter,
                "无音轨",
            )
            return

        font_metrics = painter.fontMetrics()
        text_left = 10
        text_right = 12
        handle_margin = 10

        for index, track in enumerate(self._tracks):
            row_rect = self._row_rect_for_track_index(index)
            if row_rect is None:
                continue
            if row_rect.bottom() < 0 or row_rect.top() > height:
                continue

            is_selected = id(track) in self._selected_track_ids
            is_hovered = index == self._hover_track_index
            is_handle_hovered = (
                index == self._hover_handle_track_index
                or index == self._resize_track_index
            )
            fill_color = None
            if is_selected:
                fill_color = selected_background
            elif is_hovered:
                fill_color = hover_background
            if fill_color is not None:
                painter.fillRect(row_rect, fill_color)

            row_top = int(round(row_rect.top()))
            row_bottom = int(round(row_rect.bottom()))
            painter.setPen(QPen(border_color, 1))
            painter.drawLine(0, row_bottom, width, row_bottom)

            label_rect = row_rect.adjusted(
                text_left,
                0.0,
                -text_right,
                -TRACK_RESIZE_HANDLE_HEIGHT,
            )
            if label_rect.height() > 0:
                painter.setPen(QPen(text_color))
                label = font_metrics.elidedText(
                    track.name,
                    Qt.ElideRight,
                    max(0, int(label_rect.width())),
                )
                painter.drawText(
                    QRectF(label_rect),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    label,
                )

            handle_y = int(round(row_rect.bottom() - (TRACK_RESIZE_HANDLE_HEIGHT / 2.0)))
            handle_pen = QPen(accent_color if is_handle_hovered else border_color, 1)
            painter.setPen(handle_pen)
            painter.drawLine(handle_margin, handle_y, max(handle_margin, width - handle_margin), handle_y)

            if row_top <= 0 <= row_bottom:
                painter.setPen(QPen(border_color, 1))
                painter.drawLine(0, 0, width, 0)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        track_index = self._track_index_at_pos(event.pos())
        if track_index is None or not (0 <= track_index < len(self._tracks)):
            event.ignore()
            return

        if self._is_resize_handle_hit(track_index, event.pos()):
            _, track_height = self._layout_metrics[track_index]
            self._resize_track_index = track_index
            self._drag_start_global_y = event.globalY()
            self._drag_start_height = float(track_height)
            self.setCursor(Qt.SizeVerCursor)
            self.update()
            event.accept()
            return

        self.clicked.emit(self._tracks[track_index], event)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._resize_track_index is not None:
            if (
                self._drag_start_global_y is None
                or self._drag_start_height is None
                or not (0 <= self._resize_track_index < len(self._tracks))
            ):
                event.ignore()
                return
            requested_height = self._drag_start_height + (
                event.globalY() - self._drag_start_global_y
            )
            self.resize_requested.emit(
                self._tracks[self._resize_track_index],
                int(round(requested_height)),
            )
            event.accept()
            return

        self._update_hover_state(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self._resize_track_index is None:
            super().mouseReleaseEvent(event)
            return

        track_index = self._resize_track_index
        self._resize_track_index = None
        track = self._tracks[track_index] if 0 <= track_index < len(self._tracks) else None
        requested_height = None
        if (
            track is not None
            and self._drag_start_global_y is not None
            and self._drag_start_height is not None
        ):
            requested_height = self._drag_start_height + (
                event.globalY() - self._drag_start_global_y
            )

        self._drag_start_global_y = None
        self._drag_start_height = None
        self._update_hover_state(event.pos())
        if track is not None and requested_height is not None:
            self.resize_finished.emit(track, int(round(requested_height)))
        event.accept()

    def wheelEvent(self, event) -> None:
        if self._grid_widget is None:
            super().wheelEvent(event)
            return
        self._grid_widget.handle_track_header_wheel_event(event)


class TrackGroup(QGraphicsItemGroup):
    """轨道组，包含一个轨道的所有元素（标签、勾选框、轨道线、音符块）"""
    
    def __init__(self, track: Track, track_index: int, parent_widget=None, parent=None):
        """
        初始化轨道组
        
        Args:
            track: 轨道对象
            track_index: 轨道索引
            parent_widget: 父widget引用
            parent: 父QGraphicsItem
        """
        super().__init__(parent)
        self.track = track
        self.track_index = track_index
        self.parent_widget = parent_widget
        self.track_y = track_index * TRACK_DEFAULT_HEIGHT + TRACK_TOP_PADDING  # 轨道Y坐标
        
        # 轨道元素引用
        self.track_label = None  # ClickableTrackLabel
        self.checkbox_proxy = None  # QGraphicsProxyWidget
        self.track_line = None  # QGraphicsLineItem
        self.note_blocks = {}  # {(id(note), id(track)): SequenceBlock} - 该轨道上的所有音符块
        
        # 设置z值，确保轨道组在网格线之上
        self.setZValue(5)
    
    def set_track_y(self, y: float):
        """设置轨道Y坐标"""
        self.track_y = y
        # TrackGroup的x位置是0，音符从x=0开始，与播放线对齐
        self.setPos(0, y)
    
    def add_track_label(self, label_item):
        """添加轨道标签到组"""
        self.track_label = label_item
        # 确保标签可以接收鼠标事件
        label_item.setAcceptHoverEvents(True)
        label_item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        label_item.setFlag(QGraphicsItem.ItemIsFocusable, False)
        self.addToGroup(label_item)
        # 标签使用相对于轨道组的坐标
        label_item.setPos(30, 5)
    
    def add_checkbox(self, checkbox_proxy):
        """添加勾选框到组"""
        self.checkbox_proxy = checkbox_proxy
        self.addToGroup(checkbox_proxy)
        # 勾选框使用相对于轨道组的坐标
        checkbox_proxy.setPos(5, 15)
    
    def add_track_line(self, line_item, scene_width: float):
        """添加轨道线到组"""
        self.track_line = line_item
        self.addToGroup(line_item)
        # 轨道线与音符内容同样从 x=0 开始，避免遗留固定左边距导致前段缺横线。
        line_item.setLine(0, 0, scene_width, 0)
        line_item.setZValue(0)  # 轨道线在组内最低层
    
    def add_note_block(self, block_key, block):
        """添加音符块到组（仅用于记录，实际不添加到Group）"""
        # 重构：音符块不添加到TrackGroup，而是直接添加到场景
        # 这样可以避免Group拦截鼠标事件
        self.note_blocks[block_key] = block
        # 注意：不调用 self.addToGroup(block)，音符块将直接添加到场景
    
    def remove_note_block(self, block_key):
        """从组中移除音符块（仅用于记录）"""
        if block_key in self.note_blocks:
            # 重构：音符块不在Group中，所以不需要removeFromGroup
            # 如果block在场景中，由调用者负责移除
            del self.note_blocks[block_key]
    
    def update_track_line(self, scene_width: float):
        """更新轨道线长度"""
        if self.track_line:
            self.track_line.setLine(0, 0, scene_width, 0)
    
    def update_highlight(self, is_highlighted: bool):
        """更新轨道高亮状态"""
        if self.track_label:
            theme = theme_manager.current_theme
            if is_highlighted:
                highlight_color = QColor(theme.get_color("highlight"))
                self.track_label.setDefaultTextColor(highlight_color)
                self.track_label.setFont(QFont("Arial", 12, QFont.Bold))
            else:
                text_color = QColor(theme.get_color("text_primary"))
                self.track_label.setDefaultTextColor(text_color)
                self.track_label.setFont(QFont("Arial", 12, QFont.Bold))
            self.track_label.is_highlighted = is_highlighted


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
        self.track_height = TRACK_DEFAULT_HEIGHT
        self.bpm = bpm
        self.pixels_per_beat = pixels_per_beat
        self.beat_subdivision = 4  # 1/4拍对齐
        self.signals = SequenceBlockSignals()  # 创建信号对象
        self.original_y = track_y  # 保存原始Y坐标，用于限制拖动
        self.parent_widget = parent_widget  # 保存父widget引用，用于重叠检测

        # 记录在同一时间位置上的“堆叠层级”（用于蜘蛛纸牌式垂直错位显示）
        self.stack_index: int = 0

        waveform_colors = {}
        if parent_widget is not None and hasattr(parent_widget, "_get_waveform_color_map"):
            waveform_colors = parent_widget._get_waveform_color_map()
        
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
                self.label = NOTE_LABELS[item.pitch] if 0 <= item.pitch < len(NOTE_LABELS) else str(item.pitch)
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
                self.label = NOTE_LABELS[item.pitch] if 0 <= item.pitch < len(NOTE_LABELS) else str(item.pitch)
        else:  # drum
            self.color = QColor(255, 150, 100)  # 橙色
            # 根据打击乐类型判断（DrumEvent对象）
            if isinstance(item, DrumEvent):
                self.label = DRUM_TYPE_LABELS.get(item.drum_type, "打击")
            else:
                # 兼容旧的Note对象（根据音高判断）
                self.label = DRUM_PITCH_LABELS.get(item.pitch, "打击")
        
        # 初始状态下，音符不可拖动，需要先选中再点击才能拖动
        self.setFlag(QGraphicsItem.ItemIsMovable, False)  # 初始禁用拖动
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        # 用于跟踪是否正在拖动
        self.is_dragging = False
        self.drag_start_pos = None  # 拖动开始时的位置
        self.drag_start_time = None  # 拖动开始时的start_time
        self._is_selected_for_drag = False  # 标记是否已选中并准备拖动
        self.refresh_geometry_cache()

    def _safe_bpm(self) -> float:
        return self.bpm if self.bpm > 0 else 120.0

    def _get_project(self):
        if self.parent_widget is None:
            return None
        return getattr(self.parent_widget, "project", None)

    def _seconds_to_beats(self, seconds: float) -> float:
        project = self._get_project()
        if project is not None:
            return project.seconds_to_beats(seconds)
        return max(0.0, seconds) * self._safe_bpm() / 60.0

    def _beats_to_seconds(self, beats: float) -> float:
        project = self._get_project()
        if project is not None:
            return project.beats_to_seconds(beats)
        return max(0.0, beats) * 60.0 / self._safe_bpm()

    def _duration_to_beats(self, start_time: float, duration: float) -> float:
        start_beat = self._seconds_to_beats(start_time)
        end_beat = self._seconds_to_beats(start_time + duration)
        return max(0.0, end_beat - start_beat)

    def _ticks_to_beats_fast(self, ticks: int) -> float:
        project = self._get_project()
        resolution = getattr(project, "resolution", None) if project is not None else None
        safe_resolution = max(1, int(resolution or 480))
        return max(0, int(ticks)) / safe_resolution

    def _get_block_height(self) -> float:
        track_height = getattr(self, "track_height", NOTE_BLOCK_HEIGHT)
        return min(
            NOTE_BLOCK_HEIGHT,
            max(
                NOTE_BLOCK_MIN_HEIGHT,
                float(track_height) - NOTE_BLOCK_VERTICAL_MARGIN,
            ),
        )

    def _item_start_beats(self) -> float:
        if hasattr(self.item, "start_beat"):
            return max(0.0, float(self.item.start_beat))
        start_tick = getattr(self.item, "start_tick", None)
        if start_tick is not None:
            return self._ticks_to_beats_fast(start_tick)
        project = self._get_project()
        if project is not None and hasattr(self.item, "get_start_tick"):
            return self._ticks_to_beats_fast(self.item.get_start_tick(project))
        return self._seconds_to_beats(getattr(self.item, "start_time", 0.0))

    def _item_duration_beats(self) -> float:
        if hasattr(self.item, "duration_beats"):
            return max(0.0, float(self.item.duration_beats))
        duration_ticks = getattr(self.item, "duration_ticks", None)
        if duration_ticks is not None:
            return self._ticks_to_beats_fast(duration_ticks)
        project = self._get_project()
        if project is not None and hasattr(self.item, "get_duration_ticks"):
            return self._ticks_to_beats_fast(self.item.get_duration_ticks(project))
        return self._duration_to_beats(
            getattr(self.item, "start_time", 0.0),
            getattr(self.item, "duration", 0.0),
        )

    def refresh_geometry_cache(self) -> None:
        """Cache beat-derived geometry for fast paint/boundingRect calls."""
        self._cached_start_beats = self._item_start_beats()
        self._cached_duration_beats = self._item_duration_beats()
        raw_width = self._cached_duration_beats * self.pixels_per_beat
        new_width = max(2.0, raw_width)
        new_height = self._get_block_height()
        cached_rect = getattr(self, "_cached_rect", None)
        if (
            cached_rect is not None
            and (
                abs(cached_rect.width() - new_width) > 0.1
                or abs(cached_rect.height() - new_height) > 0.1
            )
        ):
            self.prepareGeometryChange()
        self._cached_rect = QRectF(0, 0, new_width, new_height)

    def set_pixels_per_beat(self, pixels_per_beat: float) -> None:
        safe_pixels_per_beat = pixels_per_beat if pixels_per_beat > 0 else 40.0
        if abs(self.pixels_per_beat - safe_pixels_per_beat) < 1e-9:
            return
        self.pixels_per_beat = safe_pixels_per_beat
        self.refresh_geometry_cache()
    
    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        return self._cached_rect
    
    def paint(self, painter: QPainter, option, widget):
        """绘制块"""
        rect = self.boundingRect()
        
        # 选择状态
        if self.isSelected():
            pen = QPen(QColor(255, 255, 0), 2)
        else:
            pen = QPen(QColor(0, 0, 0), 1)
        
        painter.setPen(pen)
        
        # 根据力度设置透明度（如果启用）
        brush_color = QColor(self.color)
        from ui.settings_manager import get_settings_manager
        sm = get_settings_manager()
        if sm.is_velocity_opacity_enabled() and hasattr(self.item, 'velocity'):
            # 力度范围：0-127，映射到 alpha 范围：50-255
            # 力度越小，alpha越小（越透明）
            velocity = getattr(self.item, 'velocity', 127)
            # 确保velocity在有效范围内（0-127）
            velocity = max(0, min(127, int(velocity)))
            # 将力度 0-127 映射到 alpha 50-255
            # 公式：alpha = 50 + (velocity / 127) * (255 - 50)
            alpha = int(50 + (velocity / 127.0) * 205)
            # 确保alpha在有效范围内（0-255）
            alpha = max(0, min(255, alpha))
            brush_color.setAlpha(alpha)
        
        painter.setBrush(QBrush(brush_color))
        painter.drawRoundedRect(rect, 3, 3)
        
        # 绘制标签（标签始终使用黑色，不随透明度变化，确保清晰可见）
        if self.label and rect.width() >= BLOCK_LABEL_MIN_WIDTH and rect.height() >= 18.0:
            painter.setPen(QPen(QColor(0, 0, 0)))  # 黑色文字
            font = QFont("Arial", 10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, self.label)
    
    def itemChange(self, change, value):
        """项目改变时处理拖动和选择状态"""
        # 处理选择状态变化
        if change == QGraphicsItem.ItemSelectedChange:
            # 如果被取消选中，重置拖动状态
            if not value:  # value 是新的选中状态，False 表示取消选中
                self._is_selected_for_drag = False
                self.setFlag(QGraphicsItem.ItemIsMovable, False)  # 禁用拖动
                self.is_dragging = False
        
        if change == QGraphicsItem.ItemPositionChange:
            # 如果 ItemIsMovable 为 False，说明是程序设置位置（如堆叠布局），应该允许
            if not (self.flags() & QGraphicsItem.ItemIsMovable):
                # 程序设置位置，允许改变
                return value
            
            # 如果 ItemIsMovable 为 True，只有在准备拖动的情况下才允许位置改变
            if not self._is_selected_for_drag:
                # 未准备拖动，不允许移动
                return QPointF(self.pos())
            
            # 检查是否正在播放，如果正在播放，禁止拖动
            if self.parent_widget:
                main_window = self.parent_widget.parent()
                while main_window and not hasattr(main_window, 'sequencer'):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'sequencer'):
                    if main_window.sequencer.playback_state.is_playing:
                        # 播放中，禁止移动，返回原位置
                        return QPointF(self.pos())
            
            # 标记为正在拖动
            if not self.is_dragging:
                self.is_dragging = True
            
            # 拖动时自由移动，只限制Y坐标在当前轨道内，X坐标完全自由
            new_pos = value
            
            # 重构：音符块不在TrackGroup中，使用绝对坐标
            # 限制Y坐标在当前轨道内（垂直方向不动）
            track_y_min = self.original_y - 2  # 允许很小的浮动
            available_vertical_range = max(
                2.0,
                float(self.track_height) - self._get_block_height() + 2.0,
            )
            track_y_max = self.original_y + available_vertical_range
            new_y = max(track_y_min, min(track_y_max, new_pos.y()))
            
            # X坐标完全自由，不限制（但最小值为0，从起点开始）
            new_x = max(0, new_pos.x())  # 最小值是0（从起点开始）
            
            return QPointF(new_x, new_y)
        
        result = super().itemChange(change, value)
        return result
    
    def mousePressEvent(self, event):
        """鼠标按下"""
        # 检查是否正在播放，如果正在播放，禁止所有交互（包括点击和拖动）
        if self.parent_widget:
            main_window = self.parent_widget.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                if main_window.sequencer.playback_state.is_playing:
                    # 播放中，禁止所有交互（点击、拖动、选择）
                    event.ignore()
                    return

        if event.button() == Qt.LeftButton:
            # 第一次点击：仅用于选中，不允许立即拖动，防止误触
            if not self.isSelected():
                self.is_dragging = False
                self.drag_start_pos = None
                self._is_selected_for_drag = False
                # 手动设置选中状态，但不启用拖动
                self.setSelected(True)
                # 保持 ItemIsMovable 为 False，不允许拖动
                self.setFlag(QGraphicsItem.ItemIsMovable, False)
                self.signals.clicked.emit(self.item)
                event.accept()
                return

            # 已经选中的情况下，第二次点击按住才允许拖动
            if self.isSelected() and not self._is_selected_for_drag:
                # 第一次在已选中状态下点击，标记为准备拖动，启用拖动标志
                self._is_selected_for_drag = True
                self.setFlag(QGraphicsItem.ItemIsMovable, True)  # 启用拖动
                self.is_dragging = False  # 先不标记为正在拖动，等鼠标移动时再标记
                self.drag_start_pos = self.pos()  # 记录拖动开始位置
                self.signals.clicked.emit(self.item)
                # 调用基类方法，允许后续的拖动操作
                super().mousePressEvent(event)
                return
            elif self._is_selected_for_drag:
                # 已经准备拖动，直接允许拖动
                self.is_dragging = False  # 先不标记为正在拖动，等鼠标移动时再标记
                self.drag_start_pos = self.pos()
                self.signals.clicked.emit(self.item)
                super().mousePressEvent(event)
                return

        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放 - 在这里进行吸附和重叠检测"""
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            
            # 拖动结束后，在最终位置上吸附到网格
            pos = self.pos()
            # 重构：音符块不在TrackGroup中，使用绝对坐标（从0开始）
            x_offset = pos.x()  # 从0开始，与播放线对齐
            
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
                    # --------------------
                    # DrumEvent：使用节拍
                    # --------------------
                    new_start_beat = snapped_beats

                    # 检查重叠和交换位置（使用节拍）
                    if self.parent_widget and hasattr(self.parent_widget, 'check_and_resolve_drum_overlap'):
                        resolved_beat = self.parent_widget.check_and_resolve_drum_overlap(
                            self.item, self.track, new_start_beat, self
                        )
                        if resolved_beat is not None:
                            new_start_beat = resolved_beat
                            snapped_beats = new_start_beat

                    # 转换回像素位置（从0开始，与播放线对齐）
                    snapped_x = snapped_beats * self.pixels_per_beat

                    # 设置吸附后的位置
                    parent = self.parentItem()
                    if isinstance(parent, TrackGroup):
                        # 在TrackGroup中，使用相对坐标
                        self.setPos(snapped_x, 0)  # x从0开始，y为0
                    else:
                        # 不在TrackGroup中，使用绝对坐标
                        self.setPos(snapped_x, self.original_y)

                    # 更新事件的start_beat
                    if new_start_beat >= 0 and abs(self.item.start_beat - new_start_beat) > 0.001:
                        old_start_beat = self.item.start_beat
                        self.item.start_beat = new_start_beat
                        self.refresh_geometry_cache()
                        old_start_time = self._beats_to_seconds(old_start_beat)
                        new_start_time = self._beats_to_seconds(new_start_beat)
                        # 延迟发送位置改变信号（传递节拍）
                        QTimer.singleShot(
                            0,
                            lambda old_t=old_start_time, new_t=new_start_time: (
                                self.signals.position_changed.emit(self.item, old_t, new_t)
                            ),
                        )
                else:
                    # --------------------
                    # 普通音符：使用时间
                    # --------------------
                    new_start_time = self._beats_to_seconds(snapped_beats)

                    # 根据设置决定是否检查重叠
                    if not settings_manager.is_overlap_allowed() and self.parent_widget and hasattr(self.parent_widget, 'check_and_resolve_overlap'):
                        # 让父widget处理重叠检测和位置交换
                        resolved_time = self.parent_widget.check_and_resolve_overlap(
                            self.item, self.track, new_start_time, self
                        )
                        if resolved_time is not None:
                            new_start_time = resolved_time
                            # 重新计算吸附位置
                            snapped_beats = self._seconds_to_beats(new_start_time)

                    # 转换回像素位置（从0开始，因为左侧固定区域已经处理了标签和勾选框）
                    snapped_x = snapped_beats * self.pixels_per_beat

                    # 设置吸附后的位置（重构：音符块不在TrackGroup中，使用绝对坐标）
                    self.setPos(snapped_x, self.original_y)

                    # 更新音符的start_time（确保不小于0且与原来的值不同）
                    if new_start_time >= 0 and abs(self.item.start_time - new_start_time) > 0.001:
                        old_start_time = self.item.start_time
                        self.item.start_time = new_start_time
                        self.refresh_geometry_cache()
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
    render_waveform_requested = pyqtSignal(object)  # 请求渲染波形（发送Track或None）
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化序列编辑器"""
        super().__init__(parent)
        
        self.tracks = []
        self.project = None
        self.bpm = bpm
        self.pixels_per_beat = 40.0  # 每拍的像素数
        self.base_pixels_per_beat = 40.0  # 基础每拍像素数（用于缩放计算）
        self.beat_subdivision = 4  # 1/4拍对齐
        self.zoom_scale = 1.0  # 当前缩放比例
        self.track_height_zoom = 1.0  # 音轨区域纵向缩放比例
        self.zoom_direction_reversed = False  # 滚轮方向是否需要反转
        self.last_zoom_delta = 0  # 上次滚动的方向，用于检测
        self.last_zoom_scale = 1.0  # 上次缩放后的值
        
        # 播放头
        self.playhead_time = 0.0  # 当前播放时间（秒）
        self.playhead_item = None  # 播放头图形项
        self._last_playhead_pixel = None
        
        # 播放线拖动状态
        self.is_dragging_playhead = False  # 是否正在拖动播放线
        self.is_dragging_locator = False  # 是否正在拖动常显定位条
        
        # 网格线项列表（用于清除）
        self.grid_items = []
        
        # 轨道标签项列表（用于清除）
        self.track_label_items = []
        
        # 轨道线项列表（用于清除）
        self.track_line_items = []
        
        # 勾选框代理引用列表（用于断开信号连接）
        self.checkbox_proxies = []
        
        # TrackGroup列表（新架构）
        self.track_groups = []  # [TrackGroup, ...]
        
        # 是否使用增量更新（默认启用）
        self.use_incremental_update = True
        
        # 高亮显示的音轨（用于显示正在插入音符的目标音轨）
        self.highlighted_track = None
        
        # 刷新标志，防止在刷新过程中处理信号
        self._is_refreshing = False

        self._track_layout_cache = []
        self._track_layout_cache_signature = None
        self._track_layout_refresh_timer = QTimer(self)
        self._track_layout_refresh_timer.setSingleShot(True)
        self._track_layout_refresh_timer.timeout.connect(self._refresh_track_layout_for_viewport_change)
        
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
        track_selection_layout.setContentsMargins(4, 2, 4, 2)
        track_selection_layout.setSpacing(4)
        
        theme = theme_manager.current_theme
        button_small_style = theme.get_style("button_small")

        def configure_track_bar_button(button, text: str, tooltip: str, width: int) -> None:
            button.setText(text)
            button.setToolTip(tooltip)
            button.setStyleSheet(button_small_style)
            button.setFixedHeight(26)
            button.setMinimumWidth(width)
            button.setMaximumWidth(width)

        def add_track_bar_separator() -> None:
            separator = QFrame()
            separator.setFrameShape(QFrame.VLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setFixedHeight(22)
            track_selection_layout.addWidget(separator)
        
        # 添加音轨按钮（放在最左侧）
        self.add_track_button = QPushButton("添加音轨")
        configure_track_bar_button(self.add_track_button, "+ 音轨", "添加新音轨", 76)
        track_selection_layout.addWidget(self.add_track_button)
        
        # 删除选中音轨按钮
        self.delete_track_button = QPushButton("删除音轨")
        configure_track_bar_button(self.delete_track_button, "删除", "删除当前选中的音轨", 68)
        self.delete_track_button.clicked.connect(self.on_delete_track_clicked)
        track_selection_layout.addWidget(self.delete_track_button)
        
        # 示波器音轨选择按钮
        self.render_waveform_button = QPushButton("渲染音轨选择")
        configure_track_bar_button(
            self.render_waveform_button,
            "示波器",
            "选择要在示波器视图中渲染的音轨",
            68,
        )
        self.render_waveform_button.clicked.connect(self.on_render_waveform_clicked)
        track_selection_layout.addWidget(self.render_waveform_button)
        
        track_selection_layout.addSpacing(4)
        add_track_bar_separator()
        track_selection_layout.addSpacing(4)
        
        select_all_btn = QPushButton("☑")  # 全选图标
        configure_track_bar_button(select_all_btn, "全选", "选择所有音轨", 48)
        select_all_btn.clicked.connect(self.select_all_tracks)
        self.select_all_tracks_button = select_all_btn
        track_selection_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("☐")  # 全不选图标
        configure_track_bar_button(deselect_all_btn, "清空", "清空音轨选择", 54)
        deselect_all_btn.clicked.connect(self.deselect_all_tracks)
        self.deselect_all_tracks_button = deselect_all_btn
        track_selection_layout.addWidget(deselect_all_btn)
        
        invert_selection_btn = QPushButton("↻")  # 反选图标
        configure_track_bar_button(invert_selection_btn, "反选", "反选音轨", 58)
        invert_selection_btn.clicked.connect(self.invert_track_selection)
        self.invert_track_selection_button = invert_selection_btn
        track_selection_layout.addWidget(invert_selection_btn)

        track_selection_layout.addSpacing(4)
        add_track_bar_separator()
        track_selection_layout.addSpacing(4)
        
        # ========== 进度条（放在全选按钮那一行）==========
        from ui.progress_bar_widget import ProgressBarWidget
        self.progress_bar = ProgressBarWidget()
        # 连接进度条的播放线改变信号
        self.progress_bar.playhead_time_changed.connect(self.on_progress_bar_playhead_changed)
        track_selection_layout.addWidget(self.progress_bar, 1)  # 可拉伸，占满剩余空间
        
        layout.addLayout(track_selection_layout)
        
        # ========== 使用QSplitter分割左侧音轨名称列表和右侧序列区域 ==========
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)  # 防止子部件被完全折叠
        
        # ========== 左侧：固定音轨名称列表 ==========
        left_track_list_widget = QWidget()
        left_track_list_layout = QVBoxLayout()
        left_track_list_layout.setContentsMargins(0, 0, 0, 0)
        left_track_list_layout.setSpacing(0)
        left_track_list_widget.setLayout(left_track_list_layout)
        left_track_list_widget.setMinimumWidth(TRACK_NAME_PANEL_MIN_WIDTH)
        left_track_list_widget.setMaximumWidth(TRACK_NAME_PANEL_MAX_WIDTH)
        left_track_list_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.left_track_list_widget = left_track_list_widget
        
        # 顶部占位（对应右侧的顶部偏移20px）
        self.track_list_top_spacer = QWidget()
        self.track_list_top_spacer.setFixedHeight(int(TRACK_TOP_PADDING))
        left_track_list_layout.addWidget(self.track_list_top_spacer)
        
        # 音轨列表容器（动态显示可见轨道，与右侧视图同步）
        self.track_list_container = QWidget()
        self.track_list_container_layout = QVBoxLayout()
        self.track_list_container_layout.setContentsMargins(0, 0, 0, 0)
        self.track_list_container_layout.setSpacing(0)
        self.track_list_container.setLayout(self.track_list_container_layout)
        self.track_list_container_layout.setAlignment(Qt.AlignTop)  # 顶部对齐，防止重叠
        self.track_list_container.setLayout(self.track_list_container_layout)
        left_track_list_layout.addWidget(self.track_list_container, 1)
        
        # 底部占位（填充剩余空间）
        bottom_spacer = QWidget()
        self.track_list_bottom_spacer = bottom_spacer
        bottom_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_track_list_layout.addWidget(bottom_spacer)
        
        # 当前显示的轨道范围
        self.track_list_start_index = 0  # 左侧列表显示的起始轨道索引
        
        # 左侧列表的轨道项
        self.track_list_items = []  # [QWidget, ...] 每个轨道一个Widget
        self.track_header_panel = TrackHeaderPanel(self, self.track_list_container)
        self.track_header_panel.clicked.connect(self.on_track_list_label_clicked)
        self.track_header_panel.resize_requested.connect(self.on_track_height_resize_requested)
        self.track_header_panel.resize_finished.connect(self.on_track_height_resize_finished)
        self.track_header_panel.setToolTip("点击选择音轨，拖动底边调整高度，Ctrl+滚轮缩放高度")
        self.track_list_container_layout.addWidget(self.track_header_panel, 1)
        self.track_list_top_spacer.setFixedHeight(0)
        self.track_list_bottom_spacer.hide()
        
        self.main_splitter.addWidget(left_track_list_widget)
        
        # ========== 右侧：可滚动序列区域 ==========
        # 可滚动区域：场景和视图
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        # 设置为左上对齐，保证轨道始终从顶部开始绘制
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        
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
        
        # 连接滚动事件
        self.view.horizontalScrollBar().valueChanged.connect(self.on_horizontal_scroll)
        self.view.verticalScrollBar().valueChanged.connect(self.on_right_view_scrolled)
        
        # 重写鼠标事件以支持播放线拖动
        self.view.mousePressEvent = self.on_view_mouse_press
        self.view.mouseMoveEvent = self.on_view_mouse_move
        self.view.mouseReleaseEvent = self.on_view_mouse_release
        
        # 启用鼠标跟踪，以便在拖动时实时更新
        self.view.setMouseTracking(True)
        
        # 重写wheelEvent以支持Shift+滚轮和Alt+滚轮
        self.view.wheelEvent = self.on_wheel_event
        
        # 连接选择变化信号
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        # 设置视图最小高度，确保即使音轨较少也能占满区域
        # 适当降低高度上限，便于主窗口整体缩小
        self.view.setMinimumHeight(80)
        # 设置大小策略：允许垂直和水平拉伸，但不要超出父容器
        from PyQt5.QtWidgets import QSizePolicy
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 确保GridSequenceWidget本身不会因为内容变化而改变高度
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置视图背景色为主题色
        theme = theme_manager.current_theme
        self.view.setBackgroundBrush(QBrush(QColor(theme.get_color("background"))))
        # 使用透明样式，让主窗口背景（包括颜色/渐变）透出
        self.view.setStyleSheet("background: transparent;")
        
        # 将视图添加到splitter
        self.main_splitter.addWidget(self.view)
        self.main_splitter.setSizes([TRACK_NAME_PANEL_MIN_WIDTH, 1000])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        # ========== 常显定位条：始终可见，用于拖动/点击定位播放线 ==========
        locator_layout = QHBoxLayout()
        locator_layout.setContentsMargins(0, 0, 0, 0)
        locator_layout.setSpacing(0)

        self.locator_left_spacer = QLabel("定位")
        self.locator_left_spacer.setFixedHeight(LOCATOR_BAR_HEIGHT)
        self.locator_left_spacer.setMinimumWidth(TRACK_NAME_PANEL_MIN_WIDTH)
        self.locator_left_spacer.setAlignment(Qt.AlignCenter)
        self.locator_left_spacer.setStyleSheet(
            f"color: {theme.get_color('text_secondary')}; "
            f"border-top: 1px solid {theme.get_color('border')}; "
            f"border-right: 1px solid {theme.get_color('border')};"
        )
        locator_layout.addWidget(self.locator_left_spacer)
        self.locator_handle_spacer = QWidget()
        self.locator_handle_spacer.setFixedHeight(LOCATOR_BAR_HEIGHT)
        self.locator_handle_spacer.setFixedWidth(0)
        self.locator_handle_spacer.setStyleSheet(
            "background: transparent;"
            f"border-top: 1px solid {theme.get_color('border')};"
        )
        locator_layout.addWidget(self.locator_handle_spacer)

        self.locator_view = QGraphicsView(self.scene)
        self.locator_view.setFixedHeight(LOCATOR_BAR_HEIGHT)
        self.locator_view.setFrameShape(QFrame.NoFrame)
        self.locator_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.locator_view.setDragMode(QGraphicsView.NoDrag)
        self.locator_view.setInteractive(False)
        self.locator_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.locator_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.locator_view.setRenderHint(QPainter.Antialiasing)
        self.locator_view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.locator_view.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.locator_view.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.locator_view.setBackgroundBrush(QBrush(QColor(theme.get_color("background"))))
        self.locator_view.setStyleSheet(
            "background: transparent;"
            f"border-top: 1px solid {theme.get_color('border')};"
        )
        self.locator_view.mousePressEvent = self.on_locator_mouse_press
        self.locator_view.mouseMoveEvent = self.on_locator_mouse_move
        self.locator_view.mouseReleaseEvent = self.on_locator_mouse_release
        self.locator_view.wheelEvent = self.on_locator_wheel_event
        self.locator_view.setCursor(Qt.PointingHandCursor)
        self.locator_view.setToolTip("点击或拖动这里定位播放线")
        locator_layout.addWidget(self.locator_view, 1)
        self.locator_right_spacer = QWidget()
        self.locator_right_spacer.setFixedHeight(LOCATOR_BAR_HEIGHT)
        self.locator_right_spacer.setFixedWidth(0)
        self.locator_right_spacer.setStyleSheet(
            "background: transparent;"
            f"border-top: 1px solid {theme.get_color('border')};"
        )
        locator_layout.addWidget(self.locator_right_spacer)
        
        layout.addLayout(locator_layout)
        # 将splitter添加到主布局
        layout.addWidget(self.main_splitter, 1)  # 可拉伸，占满剩余空间
        
        # 连接右侧视图的滚动事件，用于同步高亮左侧列表
        self.view.verticalScrollBar().valueChanged.connect(self.on_right_view_scrolled)
        self.view.verticalScrollBar().rangeChanged.connect(
            lambda _min, _max: self._sync_locator_header_geometry()
        )
        self.main_splitter.splitterMoved.connect(self._sync_locator_header_geometry)
        
        # 初始化左侧列表
        self._update_track_list()
        self._sync_locator_header_geometry()
        
        # 选中的音符/事件（单个）
        self.selected_item = None
        self.selected_track = None
        
        # 选中的多个音符/事件
        self.selected_items = []  # [(note, track), ...]
        
        # 选中的多个音轨（用于多选功能）
        self.selected_tracks = []  # [Track, ...]
        self.last_selected_track_index = -1  # 用于Shift+点击的范围选择
        
        # 存储所有SequenceBlock的引用，用于重叠检测
        # 使用id()作为键，因为Note对象不可哈希
        self.note_blocks = {}  # {(id(note), id(track)): SequenceBlock}

        # 滚动同步标志，避免左右滚动条互相触发造成循环
        self._is_syncing_scroll = False

    def set_project(self, project):
        """Set the project used for time/beat conversion."""
        self.project = project
        self._invalidate_track_layout_cache()
        if hasattr(self, "progress_bar"):
            self.progress_bar.set_project(project)
        for block in self.note_blocks.values():
            if block:
                block.parent_widget = self
                block.refresh_geometry_cache()

    def _get_project(self):
        return self.project

    def _safe_bpm(self) -> float:
        return self.bpm if self.bpm > 0 else 120.0

    def _seconds_to_beats(self, seconds: float) -> float:
        project = self._get_project()
        if project is not None:
            return project.seconds_to_beats(seconds)
        return max(0.0, seconds) * self._safe_bpm() / 60.0

    def _beats_to_seconds(self, beats: float) -> float:
        project = self._get_project()
        if project is not None:
            return project.beats_to_seconds(beats)
        return max(0.0, beats) * 60.0 / self._safe_bpm()

    def _ticks_to_beats_fast(self, ticks: int) -> float:
        """Convert ticks to beats with the project's resolution and minimal overhead."""
        project = self._get_project()
        resolution = getattr(project, "resolution", None) if project is not None else None
        safe_resolution = max(1, int(resolution or 480))
        return max(0, int(ticks)) / safe_resolution

    def _get_content_end_beats(self) -> float:
        """Return the right-most musical beat that needs to remain visible."""
        max_end_beats = 0.0
        for track in self.tracks:
            if track.track_type == TrackType.DRUM_TRACK:
                for event in track.drum_events:
                    max_end_beats = max(max_end_beats, max(0.0, float(event.end_beat)))
            else:
                for note in track.notes:
                    max_end_beats = max(max_end_beats, self._item_end_beats(note))
        return max(32.0, max_end_beats)

    def _get_viewport_width(self) -> float:
        try:
            return float(self.view.viewport().width())
        except Exception:
            return SCENE_MIN_WIDTH

    def _sync_locator_header_geometry(self) -> None:
        """Keep the always-visible locator row aligned with the splitter panes."""
        if hasattr(self, "locator_left_spacer") and hasattr(self, "left_track_list_widget"):
            try:
                spacer_width = max(
                    TRACK_NAME_PANEL_MIN_WIDTH,
                    int(round(self.left_track_list_widget.width())),
                )
            except Exception:
                spacer_width = TRACK_NAME_PANEL_MIN_WIDTH
            self.locator_left_spacer.setFixedWidth(spacer_width)
        if hasattr(self, "locator_handle_spacer"):
            self.locator_handle_spacer.setFixedWidth(self._get_main_splitter_handle_width())
        if hasattr(self, "locator_right_spacer"):
            self.locator_right_spacer.setFixedWidth(
                self._get_main_view_vertical_scrollbar_reserve_width()
            )

        if hasattr(self, "locator_view") and hasattr(self, "view"):
            try:
                locator_bar = self.locator_view.horizontalScrollBar()
                main_bar = self.view.horizontalScrollBar()
                if locator_bar.value() != main_bar.value():
                    locator_bar.setValue(main_bar.value())
            except Exception:
                pass
            try:
                self.locator_view.verticalScrollBar().setValue(0)
            except Exception:
                pass
            self._sync_locator_view_scene_rect()

    def _sync_locator_view_scene_rect(self) -> None:
        """Limit the locator strip to the dedicated top scene band."""
        if not hasattr(self, "locator_view") or not hasattr(self, "scene"):
            return
        try:
            scene_width = max(SCENE_MIN_WIDTH, float(self.scene.sceneRect().width()))
        except Exception:
            scene_width = SCENE_MIN_WIDTH
        locator_height = max(1.0, float(TRACK_TOP_PADDING))
        try:
            self.locator_view.setSceneRect(
                0.0,
                0.0,
                scene_width,
                locator_height,
            )
        except Exception:
            pass

    def _get_main_view_vertical_scrollbar_reserve_width(self) -> int:
        """Return the width that should be reserved above the main view's vertical bar."""
        if not hasattr(self, "view"):
            return 0
        try:
            scroll_bar = self.view.verticalScrollBar()
        except Exception:
            return 0

        try:
            needs_reserve = scroll_bar.isVisible()
        except Exception:
            try:
                needs_reserve = scroll_bar.maximum() > scroll_bar.minimum()
            except Exception:
                needs_reserve = False
        if not needs_reserve:
            return 0

        try:
            width = int(scroll_bar.width())
        except Exception:
            width = 0
        if width <= 0:
            try:
                width = int(scroll_bar.sizeHint().width())
            except Exception:
                width = 0
        return max(0, width)

    def _get_main_splitter_handle_width(self) -> int:
        """Return the horizontal splitter handle width between headers and the main view."""
        splitter = getattr(self, "main_splitter", None)
        if splitter is None:
            return 0
        try:
            width = int(splitter.handleWidth())
        except Exception:
            width = 0
        if width <= 0:
            try:
                handle = splitter.handle(1)
                width = int(handle.width()) if handle is not None else 0
            except Exception:
                width = 0
        return max(0, width)

    def _get_scene_width_for_content(self) -> float:
        """Return the scene width needed for current notes at the current zoom."""
        content_width = (
            self._get_content_end_beats() * self.pixels_per_beat
            + SCENE_TAIL_PADDING_PX
        )
        viewport_width = self._get_viewport_width()
        return max(
            SCENE_MIN_WIDTH,
            viewport_width,
            content_width,
        )

    def _get_min_zoom_scale(self) -> float:
        """Allow zooming out far enough to fit the whole project into one viewport."""
        viewport_width = max(
            SCENE_MIN_WIDTH,
            self._get_viewport_width() - ZOOM_FIT_VIEW_MARGIN_PX,
        )
        content_beats = self._get_content_end_beats()
        safe_base_pixels = max(1e-6, float(self.base_pixels_per_beat))
        fit_pixels_per_beat = max(
            safe_base_pixels * ZOOM_MIN_SCALE_HARD,
            viewport_width / max(1.0, content_beats),
        )
        fit_scale = fit_pixels_per_beat / safe_base_pixels
        return max(ZOOM_MIN_SCALE_HARD, min(1.0, fit_scale))

    def _get_waveform_color_map(self) -> dict[WaveformType, QColor]:
        """Return a cached waveform-color map derived from current settings."""
        from ui.settings_manager import get_settings_manager

        settings_manager = get_settings_manager()
        cache_key = (
            settings_manager.get_waveform_color("waveform_color_square"),
            settings_manager.get_waveform_color("waveform_color_triangle"),
            settings_manager.get_waveform_color("waveform_color_sawtooth"),
            settings_manager.get_waveform_color("waveform_color_sine"),
            settings_manager.get_waveform_color("waveform_color_noise"),
        )
        if getattr(self, "_waveform_color_cache_key", None) != cache_key:
            self._waveform_color_cache_key = cache_key
            self._waveform_color_cache = {
                WaveformType.SQUARE: QColor(cache_key[0]),
                WaveformType.TRIANGLE: QColor(cache_key[1]),
                WaveformType.SAWTOOTH: QColor(cache_key[2]),
                WaveformType.SINE: QColor(cache_key[3]),
                WaveformType.NOISE: QColor(cache_key[4]),
            }
        return self._waveform_color_cache

    def _invalidate_track_layout_cache(self) -> None:
        self._track_layout_cache_signature = None
        self._track_layout_cache = []

    def _get_track_height_override(self, track: Track) -> float | None:
        raw_height = getattr(track, "display_height", None)
        if raw_height is None:
            return None
        try:
            return max(TRACK_MIN_HEIGHT, min(TRACK_MAX_HEIGHT, float(raw_height)))
        except (TypeError, ValueError):
            return None

    def _get_scaled_track_height(self, base_height: float) -> int:
        safe_base_height = max(TRACK_MIN_HEIGHT, float(base_height))
        current_zoom = float(getattr(self, "track_height_zoom", 1.0))
        scaled_height = safe_base_height * max(
            TRACK_HEIGHT_ZOOM_MIN,
            min(TRACK_HEIGHT_ZOOM_MAX, current_zoom),
        )
        return max(TRACK_MIN_HEIGHT, int(round(scaled_height)))

    def _set_track_height_zoom(self, new_zoom: float) -> bool:
        safe_zoom = max(TRACK_HEIGHT_ZOOM_MIN, min(TRACK_HEIGHT_ZOOM_MAX, float(new_zoom)))
        if abs(self.track_height_zoom - safe_zoom) < 1e-6:
            return False
        self.track_height_zoom = safe_zoom
        self._invalidate_track_layout_cache()
        return True

    def _get_track_layout_metrics(self) -> list[tuple[float, float]]:
        """Return cached `(top, height)` tuples for each track lane."""
        try:
            viewport_height = float(self.view.viewport().height())
        except Exception:
            viewport_height = 0.0
        track_height_zoom = float(getattr(self, "track_height_zoom", 1.0))

        height_signature = tuple(
            None if self._get_track_height_override(track) is None else int(round(self._get_track_height_override(track)))
            for track in self.tracks
        )
        signature = (
            len(self.tracks),
            int(round(viewport_height)),
            int(round(track_height_zoom * 1000)),
            height_signature,
        )
        if self._track_layout_cache_signature == signature:
            return self._track_layout_cache

        available_height = max(
            0,
            int(round(viewport_height)) - int(round(TRACK_TOP_PADDING)) - int(round(TRACK_BOTTOM_PADDING)),
        )
        explicit_total = 0
        flexible_indices = []
        resolved_overrides: list[int | None] = []
        for index, track in enumerate(self.tracks):
            override = self._get_track_height_override(track)
            if override is None:
                resolved_overrides.append(None)
            else:
                scaled_override = self._get_scaled_track_height(override)
                resolved_overrides.append(scaled_override)
                explicit_total += scaled_override
            if override is None:
                flexible_indices.append(index)

        flexible_height = self._get_scaled_track_height(TRACK_DEFAULT_HEIGHT)
        flexible_heights: dict[int, int] = {}
        if flexible_indices:
            if abs(track_height_zoom - 1.0) < 1e-6:
                remaining_height = max(0, available_height - explicit_total)
                target_total = max(
                    flexible_height * len(flexible_indices),
                    remaining_height,
                )
            else:
                target_total = flexible_height * len(flexible_indices)
            distributed = distribute_integer_space(target_total, len(flexible_indices))
            flexible_heights = {
                track_index: height
                for track_index, height in zip(flexible_indices, distributed)
            }

        metrics: list[tuple[float, float]] = []
        top = int(round(TRACK_TOP_PADDING))
        for index, override in enumerate(resolved_overrides):
            height = override if override is not None else flexible_heights.get(index, flexible_height)
            safe_height = max(TRACK_MIN_HEIGHT, int(round(height)))
            metrics.append((float(top), float(safe_height)))
            top += safe_height

        self._track_layout_cache_signature = signature
        self._track_layout_cache = metrics
        return metrics

    def _get_track_top(self, track_index: int) -> float:
        metrics = self._get_track_layout_metrics()
        if 0 <= track_index < len(metrics):
            return metrics[track_index][0]
        return TRACK_TOP_PADDING

    def _get_track_height(self, track_index: int) -> float:
        metrics = self._get_track_layout_metrics()
        if 0 <= track_index < len(metrics):
            return metrics[track_index][1]
        return TRACK_DEFAULT_HEIGHT

    def _get_note_block_height(self, track_index: int) -> float:
        track_height = self._get_track_height(track_index)
        return min(
            NOTE_BLOCK_HEIGHT,
            max(
                NOTE_BLOCK_MIN_HEIGHT,
                float(track_height) - NOTE_BLOCK_VERTICAL_MARGIN,
            ),
        )

    def _get_track_base_note_y(self, track_index: int) -> float:
        track_top = self._get_track_top(track_index)
        track_height = self._get_track_height(track_index)
        note_block_height = self._get_note_block_height(track_index)
        vertical_padding = max(2.0, (track_height - note_block_height) / 2.0)
        return track_top + vertical_padding

    def _get_track_content_height(self) -> float:
        metrics = self._get_track_layout_metrics()
        if not metrics:
            return 200.0
        last_top, last_height = metrics[-1]
        return last_top + last_height + TRACK_BOTTOM_PADDING

    def _iter_visible_track_indices(self, scene_top: float, scene_bottom: float) -> list[int]:
        visible_indices = []
        for index, (track_top, track_height) in enumerate(self._get_track_layout_metrics()):
            track_bottom = track_top + track_height
            if track_bottom < scene_top:
                continue
            if track_top > scene_bottom:
                break
            visible_indices.append(index)
        return visible_indices

    def _get_visible_scene_y_range(self) -> tuple[float, float]:
        """Return the current viewport's top/bottom bounds in scene coordinates."""
        try:
            viewport_height = float(self.view.viewport().height())
        except Exception:
            viewport_height = 0.0

        try:
            scene_top = float(self.view.verticalScrollBar().value())
        except Exception:
            scene_top = self.view.mapToScene(0, 0).y()
        scene_bottom = scene_top + viewport_height
        return scene_top, scene_bottom

    def _get_track_list_scroll_offsets(
        self,
        scene_top: float,
        visible_start_index: int,
    ) -> tuple[int, int]:
        """Return top gap and clip offset for the left-side track list."""
        visible_track_top = self._get_track_top(visible_start_index)
        top_gap = max(0.0, visible_track_top - scene_top)
        clip_offset = max(0.0, scene_top - visible_track_top)
        return int(round(top_gap)), int(round(clip_offset))

    def _dispose_widget(self, widget) -> None:
        """Safely retire a QWidget without letting it escape as a top-level window."""
        if widget is None:
            return
        try:
            widget.hide()
        except Exception:
            pass
        try:
            widget.setParent(None)
        except Exception:
            pass
        try:
            widget.deleteLater()
        except Exception:
            pass

    def _sync_track_header_panel(self) -> None:
        """Refresh the custom-painted left-side track header panel."""
        panel = getattr(self, "track_header_panel", None)
        if panel is None:
            return
        scene_top, _ = self._get_visible_scene_y_range()
        panel.sync_state(
            tracks=self.tracks,
            layout_metrics=self._get_track_layout_metrics(),
            scene_top=scene_top,
            selected_tracks=getattr(self, "selected_tracks", []),
        )

    def _clear_track_list_items(self) -> None:
        """Remove the temporary visible track-list widgets before rebuilding them."""
        panel = getattr(self, "track_header_panel", None)
        if panel is not None:
            panel.clear_state()

        layout = getattr(self, "track_list_container_layout", None)
        for item in self.track_list_items:
            if layout is not None:
                try:
                    layout.removeWidget(item)
                except Exception:
                    pass
            self._dispose_widget(item)
        self.track_list_items.clear()

    def _sync_existing_track_list_items(self) -> bool:
        """Update currently visible track-list items in place without rebuilding them."""
        if getattr(self, "track_header_panel", None) is not None:
            self._sync_track_header_panel()
            return bool(self.tracks)

        if not self.tracks or not self.track_list_items:
            return False

        scene_top, scene_bottom = self._get_visible_scene_y_range()
        visible_indices = self._iter_visible_track_indices(scene_top, scene_bottom)
        if not visible_indices:
            return False

        visible_start_index = visible_indices[0]
        visible_end_index = visible_indices[-1] + 1
        visible_tracks = self.tracks[visible_start_index:visible_end_index]
        if len(self.track_list_items) != len(visible_tracks):
            return False

        if any(
            getattr(item, "track", None) is not track
            for item, track in zip(self.track_list_items, visible_tracks)
        ):
            return False

        self.track_list_start_index = visible_start_index
        top_offset, clip_offset = self._get_track_list_scroll_offsets(
            scene_top,
            visible_start_index,
        )
        if hasattr(self, "track_list_top_spacer"):
            self.track_list_top_spacer.setFixedHeight(top_offset)
        if hasattr(self, "track_list_container_layout"):
            self.track_list_container_layout.setContentsMargins(0, -clip_offset, 0, 0)

        for track_index, track_item in enumerate(
            self.track_list_items,
            start=visible_start_index,
        ):
            track_item.set_track_height(self._get_track_height(track_index))

        self._update_track_list_highlight()
        return True

    def _set_track_display_height(self, track: Track, requested_height: float) -> bool:
        safe_height = int(
            round(
                max(TRACK_MIN_HEIGHT, min(TRACK_MAX_HEIGHT, float(requested_height)))
            )
        )
        if getattr(track, "display_height", None) == safe_height:
            return False
        track.display_height = safe_height
        self._invalidate_track_layout_cache()
        return True

    def _refresh_track_layout_for_viewport_change(self, *, rebuild_track_list: bool = True) -> None:
        if not hasattr(self, "view") or not hasattr(self, "scene"):
            return

        self._invalidate_track_layout_cache()
        if not self.tracks:
            self._update_track_list()
            return

        self.view.setUpdatesEnabled(False)
        try:
            for track_index, track in enumerate(self.tracks):
                track_group = self._get_track_group(track_index)
                if track_group is not None:
                    track_group.set_track_y(self._get_track_top(track_index))
                    track_group.update_track_line(self.scene.sceneRect().width())

                for block in self._get_track_group_blocks(track_index):
                    old_track_height = getattr(block, "track_height", TRACK_DEFAULT_HEIGHT)
                    block.track_y = self._get_track_top(track_index)
                    block.track_height = self._get_track_height(track_index)
                    block.original_y = self._get_track_base_note_y(track_index)
                    if abs(old_track_height - block.track_height) >= 0.1:
                        block.refresh_geometry_cache()

                if self._track_needs_stack_layout(track):
                    self._apply_stack_layout_for_track(track, track_index)
                else:
                    base_y = self._get_track_base_note_y(track_index)
                    for block in self._get_track_group_blocks(track_index):
                        start_beats = self._item_start_beats(block.item)
                        self._set_block_pos_if_changed(
                            block,
                            max(0.0, start_beats * self.pixels_per_beat),
                            base_y,
                        )

            if self._update_scene_rect_for_content():
                self.draw_grid()
            if rebuild_track_list:
                self._update_track_list()
            else:
                self._sync_existing_track_list_items()
            self.draw_playhead()
        finally:
            self.view.setUpdatesEnabled(True)
            self.view.update()

    def _duration_to_beats(self, start_time: float, duration: float) -> float:
        start_beat = self._seconds_to_beats(start_time)
        end_beat = self._seconds_to_beats(start_time + duration)
        return max(0.0, end_beat - start_beat)

    def _item_start_beats(self, item) -> float:
        if hasattr(item, "start_beat"):
            return max(0.0, float(item.start_beat))
        start_tick = getattr(item, "start_tick", None)
        if start_tick is not None:
            return self._ticks_to_beats_fast(start_tick)
        project = self._get_project()
        if project is not None and hasattr(item, "get_start_tick"):
            return self._ticks_to_beats_fast(item.get_start_tick(project))
        return self._seconds_to_beats(item.start_time)

    def _item_duration_beats(self, item) -> float:
        if hasattr(item, "duration_beats"):
            return max(0.0, float(item.duration_beats))
        duration_ticks = getattr(item, "duration_ticks", None)
        if duration_ticks is not None:
            return self._ticks_to_beats_fast(duration_ticks)
        project = self._get_project()
        if project is not None and hasattr(item, "get_duration_ticks"):
            return self._ticks_to_beats_fast(item.get_duration_ticks(project))
        return self._duration_to_beats(item.start_time, item.duration)

    def _item_end_beats(self, item) -> float:
        return self._item_start_beats(item) + self._item_duration_beats(item)

    def _get_total_note_count(self) -> int:
        """Return the total note/event count currently shown in the scene."""
        total = 0
        for track in self.tracks:
            if track.track_type == TrackType.DRUM_TRACK:
                total += len(track.drum_events)
            else:
                total += len(track.notes)
        return total

    def _log_grid_refresh_profile(self, operation: str, **stage_timings_ms: float) -> None:
        """Print a compact stage breakdown for slow grid refreshes."""
        total_ms = sum(stage_timings_ms.values())
        if total_ms < GRID_REFRESH_PROFILE_THRESHOLD_MS:
            return

        stage_parts = " ".join(
            f"{name}={elapsed_ms:.1f}ms"
            for name, elapsed_ms in stage_timings_ms.items()
        )
        print(
            f"[PROFILE] {operation} "
            f"total={total_ms:.1f}ms "
            f"{stage_parts} "
            f"track_count={len(self.tracks)} "
            f"note_count={self._get_total_note_count()}"
        )

    def _log_playhead_autoscroll_profile(self, elapsed_ms: float, *, delta_px: int) -> None:
        """Print a timing breadcrumb when auto-scrolling the playhead is slow."""
        if elapsed_ms < PLAYHEAD_AUTOSCROLL_PROFILE_THRESHOLD_MS:
            return

        print(
            "[PROFILE] grid.playhead_autoscroll "
            f"{elapsed_ms:.1f}ms "
            f"delta_px={delta_px} "
            f"track_count={len(self.tracks)} "
            f"note_count={self._get_total_note_count()}"
        )

    @contextmanager
    def _bulk_scene_update(self):
        """Temporarily suspend expensive scene/view updates during bulk rebuilds."""
        previous_updates_enabled = None
        previous_viewport_mode = None
        previous_index_method = None

        if hasattr(self, "view"):
            try:
                previous_updates_enabled = self.view.updatesEnabled()
            except Exception:
                previous_updates_enabled = True
            self.view.setUpdatesEnabled(False)
            try:
                previous_viewport_mode = self.view.viewportUpdateMode()
                self.view.setViewportUpdateMode(QGraphicsView.NoViewportUpdate)
            except Exception:
                previous_viewport_mode = None

        if hasattr(self, "scene"):
            try:
                previous_index_method = self.scene.itemIndexMethod()
                self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
            except Exception:
                previous_index_method = None

        try:
            yield
        finally:
            if previous_index_method is not None:
                try:
                    self.scene.setItemIndexMethod(previous_index_method)
                except Exception:
                    pass

            if previous_viewport_mode is not None:
                try:
                    self.view.setViewportUpdateMode(previous_viewport_mode)
                except Exception:
                    pass

            if previous_updates_enabled is not None:
                try:
                    self.view.setUpdatesEnabled(previous_updates_enabled)
                except Exception:
                    pass

            if previous_updates_enabled:
                try:
                    self.view.update()
                except Exception:
                    pass

    def _get_visible_scene_x_range(self) -> tuple[float, float]:
        """Return the current visible horizontal scene range using scroll state."""
        scroll_bar = self.view.horizontalScrollBar()
        left = float(scroll_bar.value())
        try:
            viewport_width = float(self.view.viewport().width())
        except Exception:
            viewport_width = 0.0
        if viewport_width <= 0:
            scene_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
            return float(scene_rect.left()), float(scene_rect.right())
        return left, left + viewport_width

    def _follow_playhead_during_playback(self, playhead_x: float) -> None:
        """Scroll horizontally in small steps so playback follow stays smooth."""
        scroll_bar = self.view.horizontalScrollBar()
        current_left, current_right = self._get_visible_scene_x_range()
        viewport_width = max(1.0, current_right - current_left)
        follow_margin = max(48.0, viewport_width * PLAYHEAD_FOLLOW_MARGIN_RATIO)

        desired_left = None
        if playhead_x > current_right - follow_margin:
            desired_left = playhead_x - viewport_width * PLAYHEAD_FOLLOW_TARGET_RATIO
        elif playhead_x < current_left + follow_margin:
            desired_left = playhead_x - viewport_width * (1.0 - PLAYHEAD_FOLLOW_TARGET_RATIO)

        if desired_left is None:
            return

        desired_value = int(round(max(0.0, desired_left)))
        desired_value = max(scroll_bar.minimum(), min(desired_value, scroll_bar.maximum()))
        current_value = scroll_bar.value()
        delta_px = desired_value - current_value
        if abs(delta_px) < PLAYHEAD_SCROLL_MIN_DELTA_PX:
            return

        started_at = perf_counter()
        scroll_bar.setValue(desired_value)
        elapsed_ms = (perf_counter() - started_at) * 1000.0
        self._log_playhead_autoscroll_profile(elapsed_ms, delta_px=delta_px)

    def _get_playback_view_mode(self) -> str:
        """Return the persisted playback viewport behavior."""
        try:
            from ui.settings_manager import get_settings_manager

            mode = get_settings_manager().get_playback_view_mode()
        except Exception:
            mode = "moving_playhead"
        if mode not in {"moving_playhead", "fixed_playhead"}:
            return "moving_playhead"
        return mode

    def _lock_playhead_during_playback(self, playhead_x: float) -> None:
        """Keep the playhead near a fixed viewport anchor while content scrolls."""
        scroll_bar = self.view.horizontalScrollBar()
        current_left, current_right = self._get_visible_scene_x_range()
        viewport_width = max(1.0, current_right - current_left)
        desired_left = playhead_x - viewport_width * PLAYHEAD_FIXED_TARGET_RATIO
        desired_value = int(round(max(0.0, desired_left)))
        desired_value = max(scroll_bar.minimum(), min(desired_value, scroll_bar.maximum()))
        current_value = scroll_bar.value()
        delta_px = desired_value - current_value
        if abs(delta_px) < PLAYHEAD_FIXED_SCROLL_MIN_DELTA_PX:
            return

        started_at = perf_counter()
        scroll_bar.setValue(desired_value)
        elapsed_ms = (perf_counter() - started_at) * 1000.0
        self._log_playhead_autoscroll_profile(elapsed_ms, delta_px=delta_px)
    
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
        # 临时设置selected_tracks为单个轨道，然后调用多选方法
        old_selected = self.selected_tracks.copy()
        self.selected_tracks = [track]
        self.select_tracks_notes()
        self.selected_tracks = old_selected
    
    def select_tracks_notes(self):
        """选中所有selected_tracks中的轨道上的所有音符（优化处理，避免卡死）"""
        # 清除当前选择（批量处理，避免逐个处理导致卡顿）
        self.scene.clearSelection()
        
        if not self.selected_tracks:
            # 如果没有选中的轨道，清除选择并返回
            self.selected_items.clear()
            self.selected_item = None
            self.selected_track = None
            self.selection_changed.emit()
            return
        
        # 收集所有选中轨道上的音符块
        selected_track_ids = {id(track) for track in self.selected_tracks}
        selected_blocks = []
        for (note_id, track_id), block in self.note_blocks.items():
            if block and block.scene() and id(block.track) in selected_track_ids:
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
        """选择变化时更新选中列表

        注意：在窗口关闭 / 场景销毁过程中，Qt 可能会在 QGraphicsScene
        已经被销毁后仍然触发 selectionChanged 信号，此时直接访问
        self.scene.selectedItems() 会抛出
        'wrapped C/C++ object of type QGraphicsScene has been deleted'。

        为了避免在退出或刷新时刷屏，这里增加防御性判断和异常捕获。
        """
        try:
            # 场景尚未创建或已被清理
            if not hasattr(self, "scene") or self.scene is None:
                return

            # 访问 selectedItems 时如果底层 C++ 对象已被删除，会抛 RuntimeError
            selected_blocks = [
                item for item in self.scene.selectedItems()
                if isinstance(item, SequenceBlock)
            ]
        except RuntimeError:
            # 场景已销毁（例如窗口正在关闭），忽略这次回调
            return

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
            
            # 获取当前吸附位置（场景坐标，x=0 对应第 0 拍）
            pos = block.pos()
            x_offset = pos.x()
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
                new_start_time = self._beats_to_seconds(snapped_beats)
                
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
                    snapped_beats = self._seconds_to_beats(new_start_time)
                    snapped_x = snapped_beats * block.pixels_per_beat  # 从0开始，因为左侧固定区域已经处理了标签和勾选框
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
        drum_deleted = False
        
        # 先处理单个选中
        if self.selected_item and self.selected_track:
            if isinstance(self.selected_item, DrumEvent):
                # 打击乐事件：直接删除，并刷新界面
                if self.selected_item in self.selected_track.drum_events:
                    self.selected_track.remove_drum_event(self.selected_item)
                    drum_deleted = True
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
                        drum_deleted = True
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

        # 如果有打击乐事件被删除，需要刷新一次界面以更新轨道显示
        if drum_deleted:
            self.refresh(force_full_refresh=True)
    
    def set_tracks(
        self,
        tracks: list,
        preserve_selection: bool = False,
        *,
        refresh: bool = True,
    ):
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
        self._invalidate_track_layout_cache()
        # 更新左侧列表
        if hasattr(self, 'track_list_container'):
            self._update_track_list()
        if refresh:
            self.refresh()
        
        # 恢复选中状态
        if preserve_selection and selected_note and selected_track:
            self.selected_item = selected_note
            self.selected_track = selected_track
            # 重新选中对应的block
            block = self.note_blocks.get((id(selected_note), id(selected_track)))
            if block:
                block.setSelected(True)
    
    def set_bpm(self, bpm: float, *, refresh: bool = True):
        """设置显示用 BPM，不修改项目中的音符时间数据"""
        new_bpm = bpm if bpm > 0 else 120.0
        self.bpm = new_bpm
        
        # 更新所有SequenceBlock的bpm属性
        for block in self.note_blocks.values():
            if block:
                block.bpm = new_bpm
        
        # 更新进度条的BPM
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_bpm(new_bpm)
        if refresh:
            self.refresh()
    
    def _update_track_list(self):
        """更新左侧音轨名称列表，动态显示右侧视图可见的轨道"""
        if getattr(self, "track_header_panel", None) is not None:
            self._sync_track_header_panel()
            return

        # 清除现有项
        self._clear_track_list_items()

        if hasattr(self, "track_list_container_layout"):
            self.track_list_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 计算右侧视图可见的轨道范围
        total_tracks = len(self.tracks)
        if total_tracks == 0:
            if hasattr(self, "track_list_top_spacer"):
                self.track_list_top_spacer.setFixedHeight(int(TRACK_TOP_PADDING))
            return
        
        # 获取右侧视图的可见区域
        scene_top, scene_bottom = self._get_visible_scene_y_range()

        visible_indices = self._iter_visible_track_indices(scene_top, scene_bottom)
        if not visible_indices:
            visible_start_index = 0
            visible_end_index = min(1, total_tracks)
        else:
            visible_start_index = visible_indices[0]
            visible_end_index = visible_indices[-1] + 1
        
        # 更新起始索引
        self.track_list_start_index = visible_start_index
        top_offset, clip_offset = self._get_track_list_scroll_offsets(
            scene_top,
            visible_start_index,
        )
        if hasattr(self, "track_list_top_spacer"):
            self.track_list_top_spacer.setFixedHeight(top_offset)
        if hasattr(self, "track_list_container_layout"):
            self.track_list_container_layout.setContentsMargins(0, -clip_offset, 0, 0)
        
        # 创建可见的轨道项
        for i in range(visible_start_index, visible_end_index):
            track = self.tracks[i]
            track_item_widget = TrackListItemWidget(
                track,
                self._get_track_height(i),
            )
            track_item_widget.clicked.connect(self.on_track_list_label_clicked)
            track_item_widget.resize_requested.connect(self.on_track_height_resize_requested)
            track_item_widget.resize_finished.connect(self.on_track_height_resize_finished)
            self.track_list_items.append(track_item_widget)
            self.track_list_container_layout.addWidget(track_item_widget)
        
        # 更新高亮状态（只高亮选中的音轨）
        self._update_track_list_highlight()
    
    def on_track_list_label_clicked(self, track: Track, event=None):
        """左侧列表标签点击，支持Ctrl和Shift多选"""
        from PyQt5.QtCore import Qt
        
        # 获取键盘修饰键
        modifiers = Qt.NoModifier
        if event:
            modifiers = event.modifiers()
        
        track_index = self.tracks.index(track) if track in self.tracks else -1
        
        if modifiers & Qt.ControlModifier:
            # Ctrl+点击：切换选择状态
            if track in self.selected_tracks:
                # 取消选择
                self.selected_tracks.remove(track)
                if self.last_selected_track_index == track_index:
                    self.last_selected_track_index = -1
            else:
                # 添加到选择
                self.selected_tracks.append(track)
                self.last_selected_track_index = track_index
        elif modifiers & Qt.ShiftModifier:
            # Shift+点击：范围选择
            if self.last_selected_track_index >= 0:
                # 选择从上次选择到当前点击的范围
                start_index = min(self.last_selected_track_index, track_index)
                end_index = max(self.last_selected_track_index, track_index)
                for i in range(start_index, end_index + 1):
                    if i < len(self.tracks):
                        t = self.tracks[i]
                        if t not in self.selected_tracks:
                            self.selected_tracks.append(t)
            else:
                # 如果没有上次选择，只选择当前
                if track not in self.selected_tracks:
                    self.selected_tracks.append(track)
                self.last_selected_track_index = track_index
        else:
            # 普通点击：只选择当前音轨
            self.selected_tracks.clear()
            self.selected_tracks.append(track)
            self.last_selected_track_index = track_index
        
        # 更新高亮显示
        self._update_track_list_highlight()
        
        # 选中所有选中轨道上的音符
        self.select_tracks_notes()
        
        # 发送信号（只发送当前点击的音轨）
        self.track_clicked.emit(track)
    
    def on_right_view_scrolled(self, value: int):
        """右侧视图滚动时，同步更新左侧列表"""
        if getattr(self, "track_header_panel", None) is not None:
            self._sync_track_header_panel()
            return

        if not self._sync_existing_track_list_items():
            self._update_track_list()

    def on_track_height_resize_requested(self, track: Track, requested_height: int):
        """Handle drag-resize requests from the left-side track list."""
        if track not in self.tracks:
            return
        if not self._set_track_display_height(track, requested_height):
            return
        self._refresh_track_layout_for_viewport_change(rebuild_track_list=False)

    def on_track_height_resize_finished(self, track: Track, requested_height: int):
        """Finalize a track-height resize after the drag handle is released."""
        if track not in self.tracks:
            return
        self._set_track_display_height(track, requested_height)
        self._refresh_track_layout_for_viewport_change()

    def resizeEvent(self, event):
        """Keep the track layout responsive to viewport-height changes."""
        super().resizeEvent(event)
        self._sync_locator_header_geometry()
        if hasattr(self, "_track_layout_refresh_timer"):
            self._track_layout_refresh_timer.start(0)

    def minimumSizeHint(self):
        """Keep the sequence area shrinkable inside the main splitter."""
        return QSize(360, 120)
    
    def _update_track_list_highlight(self):
        """高亮选中的音轨（selected_tracks）"""
        if getattr(self, "track_header_panel", None) is not None:
            self._sync_track_header_panel()
            return

        if not self.tracks or not self.track_list_items:
            return
        
        theme = theme_manager.current_theme
        highlight_color = theme.get_color("accent_light")
        normal_color = theme.get_color("text_primary")
        hover_color = theme.get_color("hover")
        
        # 创建选中音轨的ID集合，用于快速查找
        selected_track_ids = {id(track) for track in self.selected_tracks}
        
        # 只高亮选中的音轨
        for track_item in self.track_list_items:
            track = track_item.track
            
            # 检查是否是选中的音轨
            is_selected = id(track) in selected_track_ids
            
            if is_selected:
                # 高亮显示选中的音轨
                track_item.label.setStyleSheet(f"""
                    QLabel {{
                        color: {normal_color};
                        background-color: {highlight_color};
                        padding: 2px;
                        border: 1px solid {theme.get_color('accent')};
                        font-weight: bold;
                    }}
                    QLabel:hover {{
                        background-color: {theme.get_color('accent')};
                        border: 1px solid {theme.get_color('accent_dark')};
                    }}
                """)
            else:
                # 正常显示
                track_item.label.setStyleSheet(f"""
                    QLabel {{
                        color: {normal_color};
                        padding: 2px;
                        border: 1px solid transparent;
                    }}
                    QLabel:hover {{
                        background-color: {hover_color};
                        border: 1px solid {theme.get_color('border')};
                    }}
                """)
    
    def refresh(self, force_full_refresh: bool = False):
        """刷新显示（增量更新模式，避免空白闪烁）"""
        # 设置刷新标志，防止在刷新过程中处理信号
        self._is_refreshing = True
        
        try:
            # 如果禁用增量更新或强制全量刷新，使用传统方式
            if not self.use_incremental_update or force_full_refresh:
                with self._bulk_scene_update():
                    self._full_refresh()
                return
            
            # 增量更新模式
            # 保存播放头时间
            old_playhead_time = self.playhead_time
            
            # 禁用视图自动更新，减少闪烁
            self.view.setUpdatesEnabled(False)
            
            try:
                # 根据轨道数量调整场景高度（增加额外高度确保最后一行能显示）
                if self.tracks:
                    # 每个轨道60px高度，顶部偏移20px，确保与左侧列表对齐
                    scene_height = self._get_track_content_height()
                else:
                    scene_height = 200
                
                # 根据内容调整场景大小，并允许缩到“整曲预览”需要的宽度。
                scene_width = self._get_scene_width_for_content()
                self.scene.setSceneRect(0, 0, scene_width, scene_height)
                self._sync_locator_view_scene_rect()
                
                # 更新进度条的总时长
                if hasattr(self, 'progress_bar'):
                    # 计算总时长（从场景宽度计算）
                    total_beats = max(32, int(scene_width / self.pixels_per_beat) + 4)
                    total_time = self._beats_to_seconds(total_beats)
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
                self._last_playhead_pixel = None
                self.draw_playhead()
                
                # 恢复播放头时间
                self.playhead_time = old_playhead_time
                
            finally:
                # 重新启用视图更新
                self.view.setUpdatesEnabled(True)
                self.view.update()
                
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            # 重置刷新标志
            self._is_refreshing = False
    
    def _full_refresh(self):
        """全量刷新（传统方式，用于首次加载或强制刷新）"""
        # 保存播放头时间
        old_playhead_time = self.playhead_time

        stage_started_at = perf_counter()
        # 在清除场景前，断开所有勾选框的信号连接并阻止信号
        for i, proxy in enumerate(self.checkbox_proxies):
            if proxy:
                try:
                    widget = proxy.widget()
                    if widget:
                        widget.blockSignals(True)
                        try:
                            widget.stateChanged.disconnect()
                        except Exception:
                            pass
                        if proxy.scene():
                            self.scene.removeItem(proxy)
                        self._dispose_widget(widget)
                except (AttributeError, RuntimeError):
                    pass
        self.checkbox_proxies.clear()
        checkbox_cleanup_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        # 清除所有引用
        self.playhead_item = None
        self._last_playhead_pixel = None
        self.grid_items.clear()
        self.track_label_items.clear()
        self.track_line_items.clear()
        self.note_blocks.clear()
        self.track_groups.clear()  # 清除TrackGroup列表
        
        # 清除场景
        self.scene.clear()
        clear_scene_ms = (perf_counter() - stage_started_at) * 1000.0

        # 恢复播放头时间
        self.playhead_time = old_playhead_time

        stage_started_at = perf_counter()
        # 继续执行绘制逻辑（与原来的refresh相同）
        draw_content_timings = self._draw_all_content()
        draw_content_ms = (perf_counter() - stage_started_at) * 1000.0

        self._log_grid_refresh_profile(
            "grid.full_refresh",
            checkbox_cleanup_ms=checkbox_cleanup_ms,
            clear_scene_ms=clear_scene_ms,
            draw_content_ms=draw_content_ms,
            **draw_content_timings,
        )
    
    def _draw_all_content(self):
        """绘制所有内容（用于全量刷新）"""
        stage_started_at = perf_counter()
        scene_width, scene_height = self._calculate_scene_dimensions()
        calculate_dimensions_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.scene.setSceneRect(0, 0, scene_width, scene_height)
        self._sync_locator_view_scene_rect()
        set_scene_rect_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.draw_grid()
        draw_grid_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        track_draw_timings = self._draw_tracks_and_blocks()
        draw_tracks_total_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        if hasattr(self, 'track_list_container'):
            self._update_track_list()
        update_track_list_ms = (perf_counter() - stage_started_at) * 1000.0

        stage_started_at = perf_counter()
        self.draw_playhead()
        draw_playhead_ms = (perf_counter() - stage_started_at) * 1000.0

        return {
            "calculate_dimensions_ms": calculate_dimensions_ms,
            "set_scene_rect_ms": set_scene_rect_ms,
            "draw_grid_ms": draw_grid_ms,
            "draw_tracks_total_ms": draw_tracks_total_ms,
            **track_draw_timings,
            "update_track_list_ms": update_track_list_ms,
            "draw_playhead_ms": draw_playhead_ms,
        }
    
    def _incremental_update_tracks_and_blocks(self):
        """增量更新轨道和块（只更新变化的部分）"""
        self._invalidate_track_layout_cache()
        
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
                                except Exception:
                                    pass
                                if proxy.scene():
                                    self.scene.removeItem(proxy)
                                self._dispose_widget(widget)
                        except (AttributeError, RuntimeError):
                            pass
                self.checkbox_proxies = self.checkbox_proxies[:new_track_count]
            
            # 截断列表
            self.track_label_items = self.track_label_items[:new_track_count]
            self.track_line_items = self.track_line_items[:new_track_count]
        
        # 收集当前应该存在的块
        expected_blocks = {}
        for i, track in enumerate(self.tracks):
            y = self._get_track_top(i)
            
            if track.track_type == TrackType.DRUM_TRACK:
                for event in track.drum_events:
                    block_key = (id(event), id(track))
                    expected_blocks[block_key] = (event, track, i, y, "drum")
            else:
                for note in track.notes:
                    block_key = (id(note), id(track))
                    expected_blocks[block_key] = (note, track, i, y, self.get_track_type(track))
        
        # 删除不再存在的块（安全删除，断开信号连接）
        # 首先，收集所有应该存在的音轨ID
        valid_track_ids = {id(track) for track in self.tracks}
        
        blocks_to_remove = []
        for block_key in self.note_blocks:
            # block_key格式: (id(note), id(track))
            if len(block_key) >= 2:
                track_id = block_key[1]
                # 如果音轨不在有效列表中，或者块不在expected_blocks中，都需要删除
                if track_id not in valid_track_ids or block_key not in expected_blocks:
                    blocks_to_remove.append(block_key)
            elif block_key not in expected_blocks:
                blocks_to_remove.append(block_key)
        
        for block_key in blocks_to_remove:
            block = self.note_blocks.get(block_key)
            if block:
                try:
                    # 断开信号连接，防止访问已删除的对象
                    if hasattr(block, 'signals'):
                        try:
                            block.signals.clicked.disconnect()
                        except Exception:
                            pass
                        try:
                            block.signals.position_changed.disconnect()
                        except Exception:
                            pass
                    
                    # 从TrackGroup中移除（如果存在）
                    # 查找block所属的TrackGroup
                    for track_group in self.track_groups:
                        if block_key in track_group.note_blocks:
                            track_group.remove_note_block(block_key)
                            break
                    
                    # 从场景中移除（无论是否在TrackGroup中）
                    if block.scene():
                        self.scene.removeItem(block)
                except (AttributeError, RuntimeError):
                    # 如果对象已被删除，忽略错误
                    pass
            # 从字典中删除
            if block_key in self.note_blocks:
                del self.note_blocks[block_key]
        
        # ========== 重构：每个轨道完全独立管理 ==========
        # 第一步：同步TrackGroup列表与tracks列表
        # 删除多余的TrackGroup
        while len(self.track_groups) > len(self.tracks):
            last_group = self.track_groups.pop()
            # 清除该TrackGroup的所有音符块
            old_blocks = list(last_group.note_blocks.keys())
            for block_key in old_blocks:
                last_group.remove_note_block(block_key)
                if block_key in self.note_blocks:
                    block = self.note_blocks[block_key]
                    if block and block.scene():
                        self.scene.removeItem(block)
                    del self.note_blocks[block_key]
            if last_group.scene():
                self.scene.removeItem(last_group)
        
        # 第二步：为每个轨道创建或更新TrackGroup（完全独立）
        for i, track in enumerate(self.tracks):
            y = self._get_track_top(i)
            
            # 创建或获取TrackGroup
            if i >= len(self.track_groups):
                # 创建新的TrackGroup
                self._create_track_ui(track, i, y)
            else:
                # 更新现有TrackGroup
                track_group = self.track_groups[i]
                
                # 关键：清除该TrackGroup的所有旧音符块（确保完全独立）
                old_blocks = list(track_group.note_blocks.keys())
                for block_key in old_blocks:
                    track_group.remove_note_block(block_key)
                    if block_key in self.note_blocks:
                        block = self.note_blocks[block_key]
                        if block and block.scene():
                            self.scene.removeItem(block)
                        del self.note_blocks[block_key]
                
                # 更新TrackGroup属性
                track_group.track = track
                track_group.track_index = i
                track_group.set_track_y(y)
                
                # 更新UI元素
                if track_group.track_label:
                    track_group.track_label.track = track
                    track_group.track_label.setPlainText(track.name)
                    is_highlighted = (self.highlighted_track is not None and id(track) == id(self.highlighted_track))
                    track_group.update_highlight(is_highlighted)
                
                if track_group.checkbox_proxy:
                    try:
                        widget = track_group.checkbox_proxy.widget()
                        if widget:
                            widget.blockSignals(True)
                            widget.setChecked(track.enabled)
                            widget.blockSignals(False)
                    except (AttributeError, RuntimeError):
                        pass
                
                scene_width = max(SCENE_MIN_WIDTH, self.scene.sceneRect().width())
                track_group.update_track_line(scene_width)
        
        # 第三步：为每个轨道重新创建所有音符块（确保正确分配）并应用堆叠布局
        for i, track in enumerate(self.tracks):
            y = self._get_track_top(i)

            # 确保TrackGroup存在
            if i < len(self.track_groups):
                track_group = self.track_groups[i]

                # 为该轨道创建所有音符块
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

                # 为当前轨道应用蜘蛛纸牌式堆叠布局（仅影响显示，不改变音符时间）
                self._apply_stack_layout_for_track(track, i)
    
    # 不再需要音轨名称列表，改为鼠标悬停时在状态栏显示
    
    def on_render_waveform_clicked(self):
        """渲染音轨选择按钮点击"""
        # 总是发送None信号，让主窗口弹出选择对话框
        self.render_waveform_requested.emit(None)
    
    def _is_playing(self):
        """检查是否正在播放"""
        if hasattr(self, 'parent') and self.parent():
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'sequencer'):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'sequencer'):
                return main_window.sequencer.playback_state.is_playing
        return False
    
    def sceneEventFilter(self, obj, event):
        """场景事件过滤器，用于处理音轨标签的点击事件"""
        from PyQt5.QtCore import QEvent
        from PyQt5.QtWidgets import QGraphicsTextItem
        
        # 检查是否是音轨标签的鼠标按下事件
        if isinstance(obj, QGraphicsTextItem) and hasattr(obj, 'track'):
            if event.type() == QEvent.GraphicsSceneMousePress:
                # 点击音轨标签，选中整个音轨的所有音符
                track = obj.track
                self.select_track_notes(track)
                # 更新高亮状态
                self.highlighted_track = track
                # 发送音轨点击信号
                self.track_clicked.emit(track)
                return True
        
        return False
    
    def set_highlighted_track(self, track: Track):
        """设置高亮音轨"""
        # 更新高亮状态
        self.highlighted_track = track
        # 更新所有TrackGroup的高亮状态
        for i, t in enumerate(self.tracks):
            if i < len(self.track_groups):
                track_group = self.track_groups[i]
                is_highlighted = (track is not None and id(t) == id(track))
                track_group.update_highlight(is_highlighted)

    def sync_track_presentation(self, track: Track) -> bool:
        """Update track labels and toggles without a full scene rebuild."""
        if track not in self.tracks:
            return False

        track_index = self.tracks.index(track)
        updated = False

        if track_index < len(self.track_groups):
            track_group = self.track_groups[track_index]
            if track_group.track_label is not None:
                track_group.track_label.track = track
                track_group.track_label.setPlainText(track.name)
                updated = True

            if track_group.checkbox_proxy:
                try:
                    widget = track_group.checkbox_proxy.widget()
                    if widget is not None:
                        widget.blockSignals(True)
                        widget.setChecked(track.enabled)
                        widget.blockSignals(False)
                        updated = True
                except (AttributeError, RuntimeError):
                    pass

            scene_width = max(SCENE_MIN_WIDTH, self.scene.sceneRect().width())
            track_group.update_track_line(scene_width)
            updated = True

        if hasattr(self, "track_list_container"):
            self._update_track_list()
            updated = True
        elif hasattr(self, "_update_track_list_highlight"):
            self._update_track_list_highlight()

        if self.highlighted_track is not None and id(self.highlighted_track) == id(track):
            self.set_highlighted_track(track)
            updated = True

        if updated:
            self.view.update()

        return updated

    def _get_track_group(self, track_index: int):
        """Return the track group for a valid track index."""
        if 0 <= track_index < len(self.track_groups):
            return self.track_groups[track_index]
        return None

    def _get_track_group_blocks(self, track_index: int) -> list[object]:
        """Return the blocks currently owned by a track group."""
        track_group = self._get_track_group(track_index)
        if track_group is None:
            return []
        return [block for block in track_group.note_blocks.values() if block is not None]

    def _set_block_pos_if_changed(self, block, x: float, y: float, *, tolerance: float = 0.1) -> bool:
        """Avoid redundant QGraphicsItem position updates when the target stays the same."""
        try:
            current_pos = block.pos()
            if abs(current_pos.x() - x) < tolerance and abs(current_pos.y() - y) < tolerance:
                return False
        except (AttributeError, RuntimeError):
            pass

        block.setPos(x, y)
        return True

    def _track_needs_stack_layout(self, track: Track) -> bool:
        """Only note-like tracks need overlap stack layout work."""
        return track.track_type != TrackType.DRUM_TRACK
    
    def _update_or_create_block(self, block_key, item, track, track_index, y, track_type):
        """更新或创建块"""
        from core.track_events import DrumEvent
        from ui.settings_manager import get_settings_manager

        settings_manager = get_settings_manager()
        waveform_colors = self._get_waveform_color_map()
        
        if block_key in self.note_blocks:
            # 更新现有块
            block = self.note_blocks[block_key]
            if block and block.scene():
                # 重构：音符块不在TrackGroup中，直接管理
                # 如果块在TrackGroup中，需要先移除（向后兼容）
                current_parent = block.parentItem()
                if isinstance(current_parent, TrackGroup):
                    current_parent.remove_note_block(block_key)
                    if block.scene():
                        self.scene.removeItem(block)
                
                # 记录到TrackGroup（仅用于管理）
                if track_index < len(self.track_groups):
                    track_group = self.track_groups[track_index]
                    track_group.add_note_block(block_key, block)
                
                block.item = item
                block.track = track
                block.track_index = track_index
                block.track_y = y
                block.bpm = self.bpm
                block.set_pixels_per_beat(self.pixels_per_beat)
                
                # 更新颜色（如果波形改变了）
                if hasattr(item, 'waveform') and not isinstance(item, DrumEvent):
                    if item.waveform in waveform_colors:
                        block.color = waveform_colors[item.waveform]
                block.refresh_geometry_cache()
                
                # 重新计算位置
                start_beats = self._item_start_beats(item)

                # 根据设置决定是否对齐
                if settings_manager.is_snap_to_beat_enabled():
                    start_beats = round(start_beats * 4) / 4
                # 确保start_beats不小于0
                start_beats = max(0, start_beats)

                # 计算绝对x坐标（从0开始，与播放线对齐）
                # 确保pixels_per_beat有效
                pixels_per_beat = self.pixels_per_beat if self.pixels_per_beat > 0 else 40.0
                x = start_beats * pixels_per_beat

                # 计算基础Y坐标：轨道中间位置
                track_height = self._get_track_height(track_index)
                base_note_y = self._get_track_base_note_y(track_index)

                absolute_x = max(0, x)
                note_y = base_note_y
                # Overlap layout is recalculated once per affected track in
                # `_apply_stack_layout_for_track()`, so this hot path only
                # places the block at its base track position.
                block.stack_index = 0
                block.track_height = track_height
                block.refresh_geometry_cache()

                self._set_block_pos_if_changed(block, absolute_x, note_y)
                block.original_y = base_note_y
                
                # 确保音符块在场景中（如果不在）
                if not block.scene():
                    self.scene.addItem(block)
                
                # 记录到TrackGroup（仅用于管理，不实际添加到Group）
                if track_index < len(self.track_groups):
                    track_group = self.track_groups[track_index]
                    track_group.add_note_block(block_key, block)
                
                # 更新选中状态
                if self.selected_item == item:
                    block.setSelected(True)
                elif (item, track) in self.selected_items:
                    block.setSelected(True)
                else:
                    block.setSelected(False)
                
                # 触发重绘以更新大小和颜色
                block.update()
        else:
            # 创建新块
            block = SequenceBlock(item, track, track_index, track_type, y, self.bpm, self.pixels_per_beat, parent_widget=self)
            
            # 计算位置
            start_beats = self._item_start_beats(item)

            # 根据设置决定是否对齐
            if settings_manager.is_snap_to_beat_enabled():
                start_beats = round(start_beats * 4) / 4
            # 确保start_beats不小于0
            start_beats = max(0, start_beats)

            # 计算绝对x坐标（从0开始，与播放线对齐）
            # 确保pixels_per_beat有效
            pixels_per_beat = self.pixels_per_beat if self.pixels_per_beat > 0 else 40.0
            x = start_beats * pixels_per_beat

            # 计算基础Y坐标：轨道中间位置
            track_height = self._get_track_height(track_index)
            base_note_y = self._get_track_base_note_y(track_index)

            absolute_x = max(0, x)
            note_y = base_note_y
            block.stack_index = 0

            block.track_height = track_height
            block.refresh_geometry_cache()
            block.setPos(absolute_x, note_y)
            block.original_y = base_note_y
            
            # 直接添加到场景
            self.scene.addItem(block)
            
            # 记录到TrackGroup（仅用于管理）
            if track_index < len(self.track_groups):
                track_group = self.track_groups[track_index]
                track_group.add_note_block(block_key, block)
            
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
            
            self.note_blocks[block_key] = block

    def _apply_stack_layout_for_track(self, track: Track, track_index: int):
        """为指定轨道应用蜘蛛纸牌式堆叠布局（仅显示层级，不改变时间）"""
        from core.track_events import DrumEvent
        from ui.settings_manager import get_settings_manager

        settings_manager = get_settings_manager()
        track_blocks = self._get_track_group_blocks(track_index)
        if not track_blocks:
            return
        if not settings_manager.is_stack_overlapped_notes_enabled():
            # 关闭时，所有块恢复到轨道中线
            base_y = self._get_track_base_note_y(track_index)
            pixels_per_beat = self.pixels_per_beat if self.pixels_per_beat > 0 else 40.0
            for block in track_blocks:
                if block.track is track and not isinstance(block.item, DrumEvent):
                    # 重新计算X坐标，而不是依赖block.pos()
                    item = block.item
                    start_beats = self._item_start_beats(item)
                    x = start_beats * pixels_per_beat
                    x = max(0, x)
                    block.stack_index = 0
                    block.track_height = self._get_track_height(track_index)
                    self._set_block_pos_if_changed(block, x, base_y)
            return

        # 收集本轨道上的非打击乐块
        note_entries = []
        for block in track_blocks:
            if block.track is not track:
                continue
            if isinstance(block.item, DrumEvent):
                continue
            item = block.item
            # 统一使用项目节拍语义计算时间范围
            start_beats = self._item_start_beats(item)
            duration_beats = self._item_duration_beats(item)
            end_beats = start_beats + duration_beats
            note_entries.append({
                "block": block,
                "start": start_beats,
                "end": end_beats,
                "duration": duration_beats,
            })

        if not note_entries:
            return

        # 按开始时间排序，若相同则按时长从长到短排序（便于后面把长音放在底层）
        note_entries.sort(key=lambda e: (e["start"], -e["duration"]))

        # 按时间重叠分组（同一组内任意两音有交集）
        clusters = []
        current_cluster = []
        current_end = None
        eps = 1e-4
        for entry in note_entries:
            if not current_cluster:
                current_cluster = [entry]
                current_end = entry["end"]
            else:
                if entry["start"] < current_end - eps:  # 有交集视为一组
                    current_cluster.append(entry)
                    current_end = max(current_end, entry["end"])
                else:
                    clusters.append(current_cluster)
                    current_cluster = [entry]
                    current_end = entry["end"]
        if current_cluster:
            clusters.append(current_cluster)

        # 轨道与音符高度
        track_height = self._get_track_height(track_index)
        block_height = self._get_note_block_height(track_index)
        base_y = self._get_track_base_note_y(track_index)

        for cluster in clusters:
            n = len(cluster)
            if n <= 1:
                # 单个音符保持在中线
                entry = cluster[0]
                block = entry["block"]
                # 使用entry中的start信息重新计算X坐标，而不是依赖block.pos()
                # 因为block.pos()可能在堆叠布局调用时还没有正确设置
                start_beats = entry["start"]
                pixels_per_beat = self.pixels_per_beat if self.pixels_per_beat > 0 else 40.0
                x = start_beats * pixels_per_beat  # 从0开始，与播放线对齐
                x = max(0, x)  # 确保不小于0
                block.stack_index = 0
                self._set_block_pos_if_changed(block, x, base_y)
                continue

            # 长音在底层：按 duration 从长到短排序
            cluster_sorted = sorted(cluster, key=lambda e: -e["duration"])

            # 最大可用垂直偏移，避免溢出轨道
            max_offset = max(8.0, track_height - block_height - 4.0)
            step = max(3.0, min(10.0, max_offset / (n - 1)))

            # 0 号是最长的，放在最下层；其余依次向上
            for idx, entry in enumerate(cluster_sorted):
                block = entry["block"]
                # 使用entry中的start信息重新计算X坐标，而不是依赖block.pos()
                # 因为block.pos()可能在堆叠布局调用时还没有正确设置
                start_beats = entry["start"]
                pixels_per_beat = self.pixels_per_beat if self.pixels_per_beat > 0 else 40.0
                x = start_beats * pixels_per_beat  # 从0开始，与播放线对齐
                x = max(0, x)  # 确保不小于0
                stack_index = idx  # 0 = 最下层（最长），数字越大越靠上
                block.stack_index = stack_index
                block.track_height = track_height
                # 最顶层贴近 base_y，底层在最下面
                y_offset = step * (n - 1 - stack_index)
                new_y = base_y + y_offset
                self._set_block_pos_if_changed(block, x, new_y)
    
    def _create_track_ui(self, track, track_index, y):
        """创建轨道的UI元素（仅轨道线）- 标签和勾选框现在在左侧固定区域"""
        from PyQt5.QtGui import QColor, QPen
        from PyQt5.QtWidgets import QGraphicsLineItem
        
        # 重构：确保TrackGroup存在且完全独立
        # 如果track_index超出范围，创建新的TrackGroup
        while track_index >= len(self.track_groups):
            # 创建新的TrackGroup（使用当前track，而不是占位符）
            new_track_group = TrackGroup(track, len(self.track_groups), parent_widget=self)
            new_track_group.set_track_y(self._get_track_top(len(self.track_groups)))
            self.scene.addItem(new_track_group)
            self.track_groups.append(new_track_group)
        
        # 获取TrackGroup
        track_group = self.track_groups[track_index]
        
        # 关键：如果TrackGroup的track引用改变，清除所有旧音符块
        if id(track_group.track) != id(track):
            # 清除旧音符块
            old_blocks = list(track_group.note_blocks.keys())
            for block_key in old_blocks:
                track_group.remove_note_block(block_key)
                if block_key in self.note_blocks:
                    block = self.note_blocks[block_key]
                    if block and block.scene():
                        self.scene.removeItem(block)
                    del self.note_blocks[block_key]
        
        # 更新TrackGroup属性
        track_group.track = track
        track_group.track_index = track_index
        track_group.set_track_y(y)

        # 不再创建音轨名称标签，音符从起点开始显示

        # 创建或更新轨道线
        scene_width = max(SCENE_MIN_WIDTH, self.scene.sceneRect().width())
        if not track_group.track_line:
            from PyQt5.QtGui import QPen
            from PyQt5.QtWidgets import QGraphicsLineItem
            theme = theme_manager.current_theme
            line_item = QGraphicsLineItem(100, 0, scene_width, 0, track_group)
            line_item.setPen(QPen(QColor(theme.get_color("border")), 1))
            line_item.setZValue(0)
            track_group.add_track_line(line_item, scene_width)
        else:
            track_group.update_track_line(scene_width)
    
    def _draw_tracks_and_blocks(self):
        """绘制所有轨道和块（用于全量刷新）"""
        self._invalidate_track_layout_cache()
        build_blocks_started_at = perf_counter()

        # 全量刷新时，为了与增量刷新保持完全一致的行为，
        # 不再在这里重复实现一套坐标/缩放逻辑，而是直接复用
        # `_update_or_create_block` 的实现：这样缩放、对齐、重叠检查
        # 都只在一处维护，避免出现“缩放不同步”“位置错乱”等问题。
        for i, track in enumerate(self.tracks):
            y = self._get_track_top(i)
            # 先确保轨道基础 UI（轨道线等）存在
            self._create_track_ui(track, i, y)

            if track.track_type == TrackType.DRUM_TRACK:
                sorted_events = sorted(track.drum_events, key=lambda e: e.start_beat)
                for event in sorted_events:
                    block_key = (id(event), id(track))
                    self._update_or_create_block(block_key, event, track, i, y, "drum")
            else:
                sorted_notes = sorted(track.notes, key=lambda n: n.start_time)
                track_type = self.get_track_type(track)
                for note in sorted_notes:
                    block_key = (id(note), id(track))
                    self._update_or_create_block(block_key, note, track, i, y, track_type)
        build_blocks_ms = (perf_counter() - build_blocks_started_at) * 1000.0

        # 在所有轨道和块创建完成后，统一应用堆叠布局
        # 这样可以确保所有块都已经添加到note_blocks中，堆叠逻辑可以正确工作
        # 注意：堆叠布局只调整Y坐标，不会改变X坐标
        stack_layout_started_at = perf_counter()
        for i, track in enumerate(self.tracks):
            self._apply_stack_layout_for_track(track, i)
        stack_layout_ms = (perf_counter() - stack_layout_started_at) * 1000.0
        
        # 调试输出：检查堆叠后的位置
        if hasattr(self, '_debug_note_count') and self._debug_note_count > 0:
            print("DEBUG: After stack layout, checking first few notes:")
            count = 0
            for (item_id, track_id), block in list(self.note_blocks.items())[:5]:
                if block and block.scene():
                    pos = block.pos()
                    print(f"DEBUG: Block pos: x={pos.x():.1f}, y={pos.y():.1f}, track={block.track.name if block.track else 'None'}")
                    count += 1
                    if count >= 5:
                        break
            self._debug_note_count = 0  # 重置计数器

        return {
            "build_blocks_ms": build_blocks_ms,
            "stack_layout_ms": stack_layout_ms,
        }
    
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

        # 再次与视口高度取一个最大值，保证纵向网格线可以一直画到底部，
        # 避免轨道较少时下方出现一大片“没有拍线”的空白区域。
        try:
            viewport_height = self.view.viewport().height()
        except Exception:
            viewport_height = scene_height
        if viewport_height > scene_height:
            scene_height = viewport_height
        
        if scene_width <= 0 or scene_height <= 0:
            return  # 场景无效，不绘制
        
        # 计算整个场景的拍数范围
        max_beats = int(scene_width / self.pixels_per_beat) + 4  # 多绘制一些，确保覆盖
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
            x = beat * self.pixels_per_beat  # 从0开始，因为左侧固定区域已经处理了标签和勾选框
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
                    x = beat * self.pixels_per_beat  # 从0开始，因为左侧固定区域已经处理了标签和勾选框
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
                    x = beat * self.pixels_per_beat / 4  # 从0开始，因为左侧固定区域已经处理了标签和勾选框
                    if x <= scene_width:  # 只绘制在场景范围内的线
                        pen = QPen(border_lighter_color, 1, Qt.DashLine)
                        line_item = self.scene.addLine(x, 0, x, scene_height, pen)
                        line_item.setZValue(1)  # 设置低z值，确保在音符之下
                        self.grid_items.append(line_item)
    
    def draw_playhead(self):
        """绘制播放头"""
        # 计算播放头X位置（时间转像素）
        # 使用与时间轴相同的计算方式，确保对齐
        beat_position = self._seconds_to_beats(self.playhead_time)
        # 使用浮点数计算，然后转换为整数，确保与时间轴的播放线对齐（从0开始，因为左侧固定区域已经处理了标签和勾选框）
        x = beat_position * self.pixels_per_beat
        x = int(x)  # 转换为整数用于绘制
        
        # 绘制播放头线（使用主题错误色，2像素宽）
        theme = theme_manager.current_theme
        playhead_color = QColor(theme.get_color("error"))  # 红色用于播放线
        pen = QPen(playhead_color, 2)
        scene_height = self.scene.sceneRect().height()
        if self.playhead_item is not None:
            try:
                scene = self.playhead_item.scene()
                if scene is not None and scene == self.scene:
                    current_line = self.playhead_item.line()
                    line_changed = (
                        abs(current_line.x1() - x) >= 0.1
                        or abs(current_line.x2() - x) >= 0.1
                        or abs(current_line.y2() - scene_height) >= 0.1
                    )
                    if line_changed:
                        self.playhead_item.setLine(x, 0, x, scene_height)

                    current_pen = self.playhead_item.pen()
                    pen_changed = (
                        current_pen.color() != pen.color()
                        or abs(current_pen.widthF() - pen.widthF()) >= 0.1
                        or current_pen.style() != pen.style()
                    )
                    if pen_changed:
                        self.playhead_item.setPen(pen)
                    self.playhead_item.setZValue(10000)
                    return
            except (RuntimeError, AttributeError):
                pass

            self.playhead_item = None

        self.playhead_item = self.scene.addLine(x, 0, x, scene_height, pen)
        self.playhead_item.setZValue(10000)  # 确保播放头始终在最上层（提高到10000）

    def _calculate_scene_dimensions(self) -> tuple[float, float]:
        """Calculate the scene size needed for the current tracks."""
        content_height = self._get_track_content_height() if self.tracks else 200

        try:
            viewport_height = self.view.viewport().height()
        except Exception:
            viewport_height = 200

        scene_height = max(content_height, viewport_height)
        scene_width = self._get_scene_width_for_content()
        return scene_width, scene_height

    def _update_scene_rect_for_content(self) -> bool:
        """Resize the scene if local edits changed the content bounds."""
        scene_width, scene_height = self._calculate_scene_dimensions()
        scene_rect = self.scene.sceneRect()
        if (
            abs(scene_rect.width() - scene_width) < 0.1
            and abs(scene_rect.height() - scene_height) < 0.1
        ):
            return False

        self.scene.setSceneRect(0, 0, scene_width, scene_height)
        self._sync_locator_view_scene_rect()
        for track_group in self.track_groups:
            track_group.update_track_line(scene_width)
        return True

    def sync_note_block(self, note, track) -> bool:
        """Create or update a single note block without rebuilding the whole scene."""
        if track not in self.tracks:
            return False

        track_index = self.tracks.index(track)
        if track_index >= len(self.track_groups):
            return False

        track_y = self._get_track_top(track_index)
        track_type = "drum" if track.track_type == TrackType.DRUM_TRACK else self.get_track_type(track)
        block_key = (id(note), id(track))

        self.view.setUpdatesEnabled(False)
        try:
            self._update_or_create_block(
                block_key,
                note,
                track,
                track_index,
                track_y,
                track_type,
            )
            if self._track_needs_stack_layout(track):
                self._apply_stack_layout_for_track(track, track_index)
            if self._update_scene_rect_for_content():
                self.draw_grid()
            self.draw_playhead()
        finally:
            self.view.setUpdatesEnabled(True)
            self.view.update()

        return True

    def sync_note_blocks(self, notes_and_tracks: list[tuple[object, Track]]) -> bool:
        """Create or update multiple note blocks in a single lightweight pass."""
        if not notes_and_tracks:
            return False

        track_indices: dict[int, tuple[Track, int]] = {}
        for note, track in notes_and_tracks:
            if track not in self.tracks:
                return False
            track_index = self.tracks.index(track)
            if track_index >= len(self.track_groups):
                return False
            track_indices[id(track)] = (track, track_index)

        self.view.setUpdatesEnabled(False)
        try:
            for note, track in notes_and_tracks:
                track_index = track_indices[id(track)][1]
                track_y = self._get_track_top(track_index)
                track_type = (
                    "drum"
                    if track.track_type == TrackType.DRUM_TRACK
                    else self.get_track_type(track)
                )
                self._update_or_create_block(
                    (id(note), id(track)),
                    note,
                    track,
                    track_index,
                    track_y,
                    track_type,
                )

            for track, track_index in track_indices.values():
                if self._track_needs_stack_layout(track):
                    self._apply_stack_layout_for_track(track, track_index)

            if self._update_scene_rect_for_content():
                self.draw_grid()
            self.draw_playhead()
        finally:
            self.view.setUpdatesEnabled(True)
            self.view.update()

        return True

    def remove_note_block(self, note, track) -> bool:
        """Remove a single note block without forcing a full widget refresh."""
        block_key = (id(note), id(track))
        block = self.note_blocks.get(block_key)
        if block is None:
            return False

        track_index = self.tracks.index(track) if track in self.tracks else -1
        track_group = self._get_track_group(track_index)

        self.view.setUpdatesEnabled(False)
        try:
            try:
                if hasattr(block, "signals"):
                    try:
                        block.signals.clicked.disconnect()
                    except Exception:
                        pass
                    try:
                        block.signals.position_changed.disconnect()
                    except Exception:
                        pass

                if track_group is not None and block_key in track_group.note_blocks:
                    track_group.remove_note_block(block_key)

                if block.scene():
                    self.scene.removeItem(block)
            except (AttributeError, RuntimeError):
                pass

            del self.note_blocks[block_key]
            self.selected_items = [
                (item, item_track)
                for item, item_track in self.selected_items
                if not (item is note and item_track is track)
            ]
            if self.selected_item is note and self.selected_track is track:
                self.selected_item = None
                self.selected_track = None

            if track_index >= 0 and self._track_needs_stack_layout(track):
                if track_index < len(self.track_groups):
                    self._apply_stack_layout_for_track(track, track_index)

            if self._update_scene_rect_for_content():
                self.draw_grid()
            self.draw_playhead()
        finally:
            self.view.setUpdatesEnabled(True)
            self.view.update()

        return True

    def remove_note_blocks(self, notes_and_tracks: list[tuple[object, Track]]) -> bool:
        """Remove multiple note blocks in a single lightweight pass."""
        if not notes_and_tracks:
            return False

        removable_keys = [
            (id(note), id(track))
            for note, track in notes_and_tracks
            if (id(note), id(track)) in self.note_blocks
        ]
        if not removable_keys:
            return False

        affected_tracks: dict[int, tuple[Track, int]] = {}
        for note, track in notes_and_tracks:
            if track in self.tracks:
                track_index = self.tracks.index(track)
                if track_index < len(self.track_groups):
                    affected_tracks[id(track)] = (track, track_index)

        self.view.setUpdatesEnabled(False)
        try:
            for note, track in notes_and_tracks:
                block_key = (id(note), id(track))
                block = self.note_blocks.get(block_key)
                if block is None:
                    continue

                track_group = None
                track_info = affected_tracks.get(id(track))
                if track_info is not None:
                    track_group = self._get_track_group(track_info[1])

                try:
                    if hasattr(block, "signals"):
                        try:
                            block.signals.clicked.disconnect()
                        except Exception:
                            pass
                        try:
                            block.signals.position_changed.disconnect()
                        except Exception:
                            pass

                    if track_group is not None and block_key in track_group.note_blocks:
                        track_group.remove_note_block(block_key)

                    if block.scene():
                        self.scene.removeItem(block)
                except (AttributeError, RuntimeError):
                    pass

                del self.note_blocks[block_key]

            removed_pairs = {(id(note), id(track)) for note, track in notes_and_tracks}
            self.selected_items = [
                (item, item_track)
                for item, item_track in self.selected_items
                if (id(item), id(item_track)) not in removed_pairs
            ]
            if (
                self.selected_item is not None
                and self.selected_track is not None
                and (id(self.selected_item), id(self.selected_track)) in removed_pairs
            ):
                self.selected_item = None
                self.selected_track = None

            for track, track_index in affected_tracks.values():
                if self._track_needs_stack_layout(track):
                    self._apply_stack_layout_for_track(track, track_index)

            if self._update_scene_rect_for_content():
                self.draw_grid()
            self.draw_playhead()
        finally:
            self.view.setUpdatesEnabled(True)
            self.view.update()

        return True
    
    def set_playhead_time(self, time: float):
        """设置播放头时间"""
        self.playhead_time = time
        beat_position = self._seconds_to_beats(self.playhead_time)
        x = beat_position * self.pixels_per_beat  # 从0开始，因为左侧固定区域已经处理了标签和勾选框
        playhead_pixel = int(x)
        pixel_changed = playhead_pixel != self._last_playhead_pixel

        if pixel_changed:
            self._last_playhead_pixel = playhead_pixel
            self.draw_playhead()

        # 更新进度条的播放线位置。ProgressBarWidget 内部会跳过重复的文本/滑块更新。
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_playhead_time(time)

        if self._is_playing():
            if self._get_playback_view_mode() == "fixed_playhead":
                self._lock_playhead_during_playback(x)
            else:
                self._follow_playhead_during_playback(x)
            return

        # 非播放状态下仍保留原有的一次性居中行为，便于拖动/跳转后快速定位
        view_left, view_right = self._get_visible_scene_x_range()
        if x < view_left or x > view_right:
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
        new_grid_pos = round(self._seconds_to_beats(new_start_time) / grid_unit)
        # 检查同一轨道上的其他音符
        for other_note in moved_track.notes:
            if other_note == moved_note:
                continue
            
            # 计算其他音符的时间范围
            other_start_time = other_note.start_time
            other_end_time = other_start_time + other_note.duration
            other_grid_pos = round(self._seconds_to_beats(other_start_time) / grid_unit)
            
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
                        old_start_beats = self._seconds_to_beats(old_start_time)
                        # 从第 0 拍开始计算绝对坐标
                        other_snapped_x = old_start_beats * self.pixels_per_beat
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
    
    def on_drum_event_position_changed(self, event: DrumEvent, track: Track, old_start_time: float, new_start_time: float):
        """打击乐事件位置改变时处理"""
        # 注意：event.start_beat 已经在 itemChange 中更新了，不需要再次更新
        
        # 重新排序轨道的打击乐事件
        track.drum_events.sort(key=lambda e: e.start_beat)
        self.sync_note_block(event, track)
    
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
        
        # 检查是否点击到了可交互的项
        has_interactive_item = False
        for item in items_at_pos:
            if isinstance(item, SequenceBlock):
                # 点击到了音符块，只选择音符，不移动播放线
                has_interactive_item = True
                break
        
        if not has_interactive_item:
            # 点击空白处，清除选择
            self.scene.clearSelection()
            self.selected_items.clear()
            self.selected_item = None
            self.selected_track = None
            self.selected_tracks.clear()
            self.last_selected_track_index = -1
            self._update_track_list_highlight()
            self.selection_changed.emit()
            event.accept()
            return
        
        # 如果点击到了音符块或其他可交互项，直接传递给默认处理（不移动播放线）
        if has_interactive_item:
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
        
        # 调用原始事件处理（用于音符拖动等）
        QGraphicsView.mouseMoveEvent(self.view, event)

    def on_locator_mouse_press(self, event):
        """常显定位条鼠标按下事件。"""
        if event.button() != Qt.LeftButton:
            event.ignore()
            return
        self.is_dragging_locator = True
        scene_pos = self._map_related_pos_to_main_scene(self.locator_view, event.pos())
        self.update_playhead_from_pos(scene_pos)
        event.accept()

    def on_locator_mouse_move(self, event):
        """常显定位条鼠标移动事件。"""
        if not self.is_dragging_locator:
            event.ignore()
            return
        scene_pos = self._map_related_pos_to_main_scene(self.locator_view, event.pos())
        self.update_playhead_from_pos(scene_pos)
        event.accept()

    def on_locator_mouse_release(self, event):
        """常显定位条鼠标释放事件。"""
        if event.button() == Qt.LeftButton:
            self.is_dragging_locator = False
            event.accept()
            return
        event.ignore()

    def _extract_wheel_delta(self, event: QWheelEvent) -> int | None:
        """Return a meaningful wheel delta from either angleDelta or pixelDelta."""
        angle_delta = event.angleDelta()
        if angle_delta.y() != 0:
            return int(angle_delta.y())
        if angle_delta.x() != 0:
            return int(angle_delta.x())
        if hasattr(event, "delta") and event.delta() != 0:
            return int(event.delta())
        pixel_delta = event.pixelDelta()
        if pixel_delta and pixel_delta.y() != 0:
            return int(pixel_delta.y())
        if pixel_delta and pixel_delta.x() != 0:
            return int(pixel_delta.x())
        return None

    def _map_wheel_pos_to_view(self, source_widget, pos: QPoint) -> QPoint:
        """Map wheel coordinates from any related widget back into the main view."""
        source = source_widget
        if isinstance(source_widget, QGraphicsView):
            source = source_widget.viewport()
        if source is None:
            return self.view.viewport().rect().center()
        try:
            global_pos = source.mapToGlobal(pos)
            return self.view.viewport().mapFromGlobal(global_pos)
        except Exception:
            return self.view.viewport().rect().center()

    def _map_related_pos_to_main_scene(self, source_widget, pos: QPoint):
        """Map a pointer position from a related widget into the main scene."""
        return self.view.mapToScene(self._map_wheel_pos_to_view(source_widget, pos))

    def _apply_track_height_zoom_from_delta(self, delta: int) -> None:
        current_zoom = self.track_height_zoom
        if delta > 0:
            new_zoom = current_zoom * TRACK_HEIGHT_ZOOM_STEP
        else:
            new_zoom = current_zoom / TRACK_HEIGHT_ZOOM_STEP
        if self._set_track_height_zoom(new_zoom):
            self._refresh_track_layout_for_viewport_change()

    def _apply_horizontal_zoom_from_delta(self, delta: int, view_pos: QPoint) -> None:
        current_scale = self.zoom_scale
        zoom_step = 1.15
        if delta > 0:
            new_scale = current_scale * zoom_step
        else:
            new_scale = current_scale / zoom_step

        min_scale = self._get_min_zoom_scale()
        if new_scale < min_scale:
            new_scale = min_scale
        elif new_scale > ZOOM_MAX_SCALE:
            new_scale = ZOOM_MAX_SCALE

        if abs(new_scale - current_scale) <= 0.001:
            return

        scene_pos_before = self.view.mapToScene(view_pos)
        scroll_bar = self.view.horizontalScrollBar()
        old_scroll_value = scroll_bar.value()

        self.zoom_scale = new_scale
        self.pixels_per_beat = self.base_pixels_per_beat * self.zoom_scale
        self.update_blocks_for_zoom()

        if abs(self.zoom_scale - new_scale) > 0.01:
            self.zoom_scale = new_scale
            self.pixels_per_beat = self.base_pixels_per_beat * self.zoom_scale

        scene_width = self._get_scene_width_for_content()
        scene_rect = self.scene.sceneRect()
        self.scene.setSceneRect(0, 0, scene_width, scene_rect.height())
        self._sync_locator_view_scene_rect()

        scene_pos_after = self.view.mapToScene(view_pos)
        if abs(scene_pos_after.x() - scene_pos_before.x()) > 0.1:
            delta_pixels = scene_pos_before.x() - scene_pos_after.x()
            new_scroll_value = old_scroll_value + int(delta_pixels)
        else:
            new_scroll_value = int(old_scroll_value * (new_scale / current_scale))
        new_scroll_value = max(
            scroll_bar.minimum(),
            min(new_scroll_value, scroll_bar.maximum()),
        )
        scroll_bar.setValue(new_scroll_value)

    def _apply_horizontal_scroll_from_delta(self, delta: int) -> None:
        scroll_bar = self.view.horizontalScrollBar()
        scroll_bar.setValue(scroll_bar.value() - delta)

    def _apply_vertical_scroll_from_delta(self, delta: int) -> bool:
        scroll_bar = self.view.verticalScrollBar()
        scene_rect = self.scene.sceneRect()
        view_height = self.view.viewport().height()
        scene_height = scene_rect.height()
        if scene_height <= view_height and scroll_bar.maximum() <= 0:
            return False

        new_value = scroll_bar.value() - delta
        new_value = max(scroll_bar.minimum(), min(new_value, scroll_bar.maximum()))
        scroll_bar.setValue(new_value)
        return True

    def _handle_wheel_event_from_source(self, event: QWheelEvent, source_widget) -> None:
        delta = self._extract_wheel_delta(event)
        modifiers = event.modifiers()

        if self._is_playing():
            if modifiers & (Qt.AltModifier | Qt.ShiftModifier | Qt.ControlModifier):
                event.ignore()
                return
            if delta is not None and self._apply_vertical_scroll_from_delta(delta):
                event.accept()
                return
            QGraphicsView.wheelEvent(self.view, event)
            return

        if delta is None:
            QGraphicsView.wheelEvent(self.view, event)
            return

        if modifiers & Qt.ControlModifier:
            self._apply_track_height_zoom_from_delta(delta)
            event.accept()
            return

        if modifiers & Qt.AltModifier:
            self._apply_horizontal_zoom_from_delta(
                delta,
                self._map_wheel_pos_to_view(source_widget, event.pos()),
            )
            event.accept()
            return

        if modifiers & Qt.ShiftModifier:
            self._apply_horizontal_scroll_from_delta(delta)
            event.accept()
            return

        if self._apply_vertical_scroll_from_delta(delta):
            event.accept()
            return

        QGraphicsView.wheelEvent(self.view, event)

    def on_wheel_event(self, event: QWheelEvent):
        """处理滚轮事件"""
        self._handle_wheel_event_from_source(event, self.view)

    def on_locator_wheel_event(self, event: QWheelEvent):
        """让常显定位条和主音轨区共享同一套滚轮交互。"""
        self._handle_wheel_event_from_source(event, self.locator_view)

    def handle_track_header_wheel_event(self, event: QWheelEvent):
        """让左侧音轨名称区也支持同一套滚轮交互。"""
        self._handle_wheel_event_from_source(event, self.track_header_panel)
    
    def on_horizontal_scroll(self, value):
        """横向滚动时，更新轨道标签位置，使其始终显示在左边（冻结窗格）"""
        # 播放期间禁止水平滚动
        if self._is_playing():
            self._sync_locator_header_geometry()
            return
        
        # 将视口坐标转换为场景坐标，确保标签始终显示在视口左侧
        # 视口左侧的x坐标是0，转换为场景坐标
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

        self._sync_locator_header_geometry()
    
    def on_vertical_scroll(self, value):
        """纵向滚动事件（保留用于其他用途）"""
        pass
    
    def update_playhead_from_pos(self, scene_pos):
        """根据场景坐标更新播放线位置"""
        scene_x = scene_pos.x()
        # 从0开始，因为左侧固定区域已经处理了标签和勾选框
        x_offset = scene_x
        if x_offset < 0:
            x_offset = 0
        
        # 计算对应的节拍数
        beat_position = x_offset / self.pixels_per_beat
        # 转换为时间（秒）
        time = self._beats_to_seconds(beat_position)
        
        # 根据设置决定是否吸附
        from ui.settings_manager import get_settings_manager
        settings_manager = get_settings_manager()
        if settings_manager.is_snap_to_beat_enabled():
            # 吸附到1/4拍
            beat_subdivision = 4
            snapped_beat = round(beat_position * beat_subdivision) / beat_subdivision
            time = self._beats_to_seconds(snapped_beat)
        
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
            track_indices = {id(track): index for index, track in enumerate(self.tracks)}
            affected_track_indices: set[int] = set()

            # 更新所有块的位置和大小
            for (item_id, track_id), block in self.note_blocks.items():
                if block and block.scene():
                    block.bpm = self.bpm
                    block.set_pixels_per_beat(self.pixels_per_beat)
                    track_index = track_indices.get(id(block.track))
                    if track_index is None:
                        continue
                    
                    # 重新计算位置
                    from core.track_events import DrumEvent
                    if isinstance(block.item, DrumEvent):
                        start_beats = block.item.start_beat
                    else:  # Note
                        start_beats = self._item_start_beats(block.item)
                    
                    # 根据设置决定是否对齐
                    from ui.settings_manager import get_settings_manager
                    settings_manager = get_settings_manager()
                    if settings_manager.is_snap_to_beat_enabled():
                        start_beats = round(start_beats * 4) / 4
                    # 缩放时统一使用从第 0 拍开始的场景坐标，避免与初始绘制、拖动计算不一致
                    x = start_beats * self.pixels_per_beat
                    block.original_y = self._get_track_base_note_y(track_index)
                    block.track_height = self._get_track_height(track_index)
                    
                    # 更新位置
                    block.setPos(x, block.original_y)
                    affected_track_indices.add(track_index)
                    
                    # 触发重绘以更新大小
                    block.update()

            for track_index in sorted(affected_track_indices):
                track = self.tracks[track_index]
                if self._track_needs_stack_layout(track):
                    self._apply_stack_layout_for_track(track, track_index)
            
            # 更新网格
            self.draw_grid()
            
            # 重新绘制播放头（使用新的pixels_per_beat）
            self.draw_playhead()
        finally:
            # 重新启用视图更新
            self.view.setUpdatesEnabled(True)
            self.view.update()
    
    def update_block_for_note(self, note, track):
        """Backward-compatible alias for local single-block sync."""
        self.sync_note_block(note, track)
    
    def get_track_type(self, track: Track) -> str:
        """获取轨道类型"""
        if track.track_type == TrackType.DRUM_TRACK:
            return "drum"
        if track.role == TrackRole.BASS:
            return "bass"
        return "melody"
