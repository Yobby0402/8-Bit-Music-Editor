"""
钢琴卷帘窗模块

提供可视化的音符编辑界面。
"""

from PyQt5.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QVBoxLayout, QHBoxLayout, QScrollBar, QLabel
)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont

from core.models import Note, Track, WaveformType


class NoteItem(QGraphicsItem):
    """音符图形项"""
    
    def __init__(self, note: Note, track_index: int, pixels_per_beat: float = 100.0):
        """
        初始化音符项
        
        Args:
            note: 音符对象
            track_index: 轨道索引
            pixels_per_beat: 每拍的像素数
        """
        super().__init__()
        self.note = note
        self.track_index = track_index
        self.pixels_per_beat = pixels_per_beat
        
        # 音符颜色（根据轨道索引）
        colors = [
            QColor(255, 100, 100),  # 红色
            QColor(100, 255, 100),  # 绿色
            QColor(100, 100, 255),  # 蓝色
            QColor(255, 255, 100),  # 黄色
        ]
        self.color = colors[track_index % len(colors)]
        
        # 设置可拖拽和可选择
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        self.update_position()
    
    def update_position(self):
        """更新音符位置和大小"""
        # 计算位置（X轴：时间，Y轴：音高）
        # Y轴：从下往上，MIDI 0在底部，127在顶部
        note_height = 20  # 每个音符的高度
        x = self.note.start_time * self.pixels_per_beat * 4  # 假设4/4拍
        y = (127 - self.note.pitch) * note_height
        
        # 计算大小
        width = self.note.duration * self.pixels_per_beat * 4
        height = note_height
        
        self.setPos(x, y)
        self._rect = QRectF(0, 0, width, height)
    
    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        if hasattr(self, '_rect'):
            return self._rect
        return QRectF(0, 0, 100, 20)
    
    def rect(self) -> QRectF:
        """返回矩形"""
        return self.boundingRect()
    
    def paint(self, painter: QPainter, option, widget):
        """绘制音符"""
        rect = self.rect()
        
        # 选择状态
        if self.isSelected():
            pen = QPen(QColor(255, 255, 0), 2)  # 黄色边框
        else:
            pen = QPen(QColor(0, 0, 0), 1)  # 黑色边框
        
        painter.setPen(pen)
        
        # 填充颜色
        brush = QBrush(self.color)
        painter.setBrush(brush)
        
        # 绘制矩形
        painter.drawRoundedRect(rect, 3, 3)
        
        # 绘制音高标签（如果足够大）
        if rect.width() > 30:
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Arial", 8)
            painter.setFont(font)
            # MIDI音高转换为音名
            note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            octave = self.note.pitch // 12 - 1
            note_name = note_names[self.note.pitch % 12]
            label = f"{note_name}{octave}"
            painter.drawText(rect.adjusted(2, 2, -2, -2), Qt.AlignLeft | Qt.AlignTop, label)
    
    def itemChange(self, change, value):
        """项目改变时更新音符数据"""
        if change == QGraphicsItem.ItemPositionChange:
            # 限制在有效范围内
            new_pos = value
            # 可以在这里添加边界检查
            return new_pos
        
        return super().itemChange(change, value)


class PianoRollWidget(QWidget):
    """钢琴卷帘窗"""
    
    # 信号
    note_selected = pyqtSignal(Note, Track)
    note_changed = pyqtSignal(Note)
    note_added = pyqtSignal(Note, Track)
    note_removed = pyqtSignal(Note, Track)
    
    def __init__(self, parent=None):
        """初始化钢琴卷帘窗"""
        super().__init__(parent)
        
        self.tracks = []
        self.pixels_per_beat = 100.0  # 每拍的像素数
        self.note_height = 20  # 每个音符的高度
        self.selected_note = None
        self.selected_track = None
        self.current_track = None  # 当前选中的轨道（用于添加音符）
        self.key_width = 60  # 钢琴键盘宽度
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 创建图形视图和场景
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setMouseTracking(True)
        
        layout.addWidget(self.view)
        
        # 连接鼠标事件
        self.view.mousePressEvent = self.on_mouse_press
        self.view.mouseMoveEvent = self.on_mouse_move
        self.view.mouseReleaseEvent = self.on_mouse_release
    
    def set_tracks(self, tracks: list):
        """设置轨道列表"""
        self.tracks = tracks
        # 如果没有当前轨道，选择第一个启用的轨道
        if self.current_track is None and tracks:
            for track in tracks:
                if track.enabled:
                    self.current_track = track
                    break
        self.refresh()
    
    def set_current_track(self, track: Track):
        """设置当前轨道（用于添加音符）"""
        self.current_track = track
    
    def set_pixels_per_beat(self, pixels: float):
        """设置每拍的像素数"""
        self.pixels_per_beat = pixels
        self.refresh()
    
    def refresh(self):
        """刷新显示"""
        self.scene.clear()
        
        # 绘制钢琴键盘背景
        self.draw_piano_keys()
        
        # 绘制网格
        self.draw_grid()
        
        # 绘制音符
        self.draw_notes()
    
    def draw_piano_keys(self):
        """绘制钢琴键盘"""
        # 绘制键盘区域（左侧）
        key_width = self.key_width
        total_height = 128 * self.note_height
        
        # 绘制白键和黑键
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        
        for midi_note in range(128):
            y = (127 - midi_note) * self.note_height
            octave = midi_note // 12 - 1
            note_name = note_names[midi_note % 12]
            
            # 判断是黑键还是白键
            is_black = note_name.endswith("#")
            
            if is_black:
                color = QColor(50, 50, 50)
            else:
                color = QColor(255, 255, 255)
            
            # 绘制键
            rect = QRectF(0, y, key_width, self.note_height)
            self.scene.addRect(rect, QPen(QColor(0, 0, 0), 1), QBrush(color))
            
            # 绘制标签（白键）
            if not is_black:
                text_item = self.scene.addText(f"{note_name}{octave}", QFont("Arial", 8))
                text_item.setPos(5, y + 2)
    
    def draw_grid(self):
        """绘制网格"""
        # 绘制时间网格
        # 这里简化处理，实际应该根据BPM和拍号绘制
        
        # 绘制音高网格线
        for midi_note in range(128):
            y = (127 - midi_note) * self.note_height
            pen = QPen(QColor(200, 200, 200), 1, Qt.DashLine)
            self.scene.addLine(self.key_width, y, 2000, y, pen)
    
    def draw_notes(self):
        """绘制所有音符"""
        for track_index, track in enumerate(self.tracks):
            if not track.enabled:
                continue
            
            for note in track.notes:
                note_item = NoteItem(note, track_index, self.pixels_per_beat)
                note_item.setZValue(1)  # 音符在网格之上
                self.scene.addItem(note_item)
    
    def on_mouse_press(self, event):
        """鼠标按下事件"""
        # 先调用原始事件处理（用于选择等）
        QGraphicsView.mousePressEvent(self.view, event)
        
        # 然后处理我们的逻辑
        if event.button() == Qt.LeftButton:
            # 获取点击位置
            scene_pos = self.view.mapToScene(event.pos())
            scene_x = scene_pos.x()
            scene_y = scene_pos.y()
            
            # 检查是否点击了音符
            item = self.scene.itemAt(scene_pos, self.view.transform())
            if isinstance(item, NoteItem):
                # 选中音符
                self.selected_note = item.note
                # 找到对应的轨道
                for track in self.tracks:
                    if self.selected_note in track.notes:
                        self.selected_track = track
                        break
                self.note_selected.emit(self.selected_note, self.selected_track)
            # 不再在编辑区域点击添加音符，改为通过按钮添加
    
    def on_mouse_move(self, event):
        """鼠标移动事件"""
        QGraphicsView.mouseMoveEvent(self.view, event)
    
    def on_mouse_release(self, event):
        """鼠标释放事件"""
        QGraphicsView.mouseReleaseEvent(self.view, event)
    
    def add_note(self, track: Track, pitch: int, start_time: float, duration: float):
        """添加音符"""
        from core.models import Note
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            waveform=track.waveform
        )
        track.add_note(note)
        self.refresh()
        self.note_added.emit(note, track)
    
    def remove_selected_note(self):
        """删除选中的音符"""
        if self.selected_note and self.selected_track:
            note_to_remove = self.selected_note
            track_to_remove = self.selected_track
            self.selected_track.remove_note(self.selected_note)
            self.selected_note = None
            self.selected_track = None
            self.refresh()
            # 发送信号
            self.note_removed.emit(note_to_remove, track_to_remove)

