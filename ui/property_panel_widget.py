"""
属性面板模块

用于编辑选中音符的属性（音高、时长、力度、波形、ADSR等）。
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.effect_processor import (
    DelayParams,
    FilterParams,
    FilterType,
    TremoloParams,
)
from core.models import Note, Track, TrackRole, TrackType, WaveformType, infer_track_role
from core.track_events import DrumEvent

TIMING_SNAP_BEATS = 0.25
TRACK_PROPERTY_CHANGE_EFFECTS = "effects"
TRACK_PROPERTY_CHANGE_METADATA = "metadata"
TRACK_PROPERTY_CHANGE_PRESENTATION = "presentation"
TRACK_PROPERTY_CHANGE_STRUCTURE = "structure"


def build_note_sort_key(note: Note, project=None) -> tuple[float, float, int]:
    """Build a stable note sort key preferring musical time when available."""
    if project is not None:
        return (
            float(note.get_start_tick(project)),
            float(note.start_time),
            int(note.pitch),
        )
    return (float(note.start_time), float(note.duration), int(note.pitch))


def snap_tick_to_grid(tick: int, grid_ticks: int) -> int:
    """Snap a tick position to the nearest grid boundary."""
    safe_tick = max(0, int(tick))
    safe_grid_ticks = max(1, int(grid_ticks))
    return int(round(safe_tick / safe_grid_ticks) * safe_grid_ticks)


def get_track_type_editor_index(track: Track) -> int:
    """Map the canonical track type to the property-panel combo index."""
    return 1 if track.track_type == TrackType.DRUM_TRACK else 0


def resolve_track_type_from_editor_index(index: int) -> TrackType:
    """Resolve the property-panel combo index to the canonical track type."""
    return TrackType.DRUM_TRACK if index == 1 else TrackType.NOTE_TRACK


TRACK_ROLE_EDITOR_OPTIONS: tuple[tuple[str, TrackRole], ...] = (
    ("主旋律", TrackRole.MELODY),
    ("低音", TrackRole.BASS),
    ("和声", TrackRole.HARMONY),
    ("效果", TrackRole.EFFECT),
)


def get_track_role_editor_index(track: Track) -> int:
    """Map the canonical track role to the property-panel combo index."""
    role = track.role or TrackRole.MELODY
    for index, (_, candidate_role) in enumerate(TRACK_ROLE_EDITOR_OPTIONS):
        if candidate_role == role:
            return index
    return 0


def resolve_track_role_from_editor_index(index: int) -> TrackRole:
    """Resolve the property-panel combo index to the canonical track role."""
    if 0 <= index < len(TRACK_ROLE_EDITOR_OPTIONS):
        return TRACK_ROLE_EDITOR_OPTIONS[index][1]
    return TrackRole.MELODY


def can_change_track_type_on_existing_track(track: Track, new_track_type: TrackType) -> bool:
    """Only allow cross-type switching on empty tracks to avoid silent data hiding."""
    if track.track_type == new_track_type:
        return True
    return not track.notes and not track.drum_events


def resolve_note_timing_for_start_time(
    note: Note,
    project,
    new_start_time: float,
    *,
    snap_to_beat: bool = False,
    snap_beats: float = TIMING_SNAP_BEATS,
) -> tuple[int, int] | None:
    """Resolve a start-time edit into tick timing while keeping the note end fixed."""
    old_start_tick = note.get_start_tick(project)
    old_duration_ticks = note.get_duration_ticks(project)
    old_end_tick = old_start_tick + old_duration_ticks
    new_start_tick = project.seconds_to_ticks(new_start_time)
    if snap_to_beat:
        new_start_tick = snap_tick_to_grid(new_start_tick, project.beats_to_ticks(snap_beats))
    if new_start_tick >= old_end_tick:
        return None
    return new_start_tick, old_end_tick - new_start_tick


def resolve_note_timing_for_end_time(
    note: Note,
    project,
    new_end_time: float,
    *,
    snap_to_beat: bool = False,
    snap_beats: float = TIMING_SNAP_BEATS,
) -> tuple[int, int] | None:
    """Resolve an end-time edit into tick timing while keeping the note start fixed."""
    start_tick = note.get_start_tick(project)
    new_end_tick = project.seconds_to_ticks(new_end_time)
    if snap_to_beat:
        new_end_tick = snap_tick_to_grid(new_end_tick, project.beats_to_ticks(snap_beats))
    if new_end_tick <= start_tick:
        return None
    return start_tick, new_end_tick - start_tick


def resolve_note_timing_for_duration_beats(
    note: Note,
    project,
    duration_beats: float,
    *,
    snap_to_beat: bool = False,
    snap_beats: float = TIMING_SNAP_BEATS,
) -> tuple[int, int] | None:
    """Resolve a duration edit expressed in beats into tick timing."""
    start_tick = note.get_start_tick(project)
    duration_ticks = project.beats_to_ticks(duration_beats)
    if snap_to_beat:
        duration_ticks = snap_tick_to_grid(duration_ticks, project.beats_to_ticks(snap_beats))
    if duration_ticks <= 0:
        return None
    return start_tick, duration_ticks


def shift_contiguous_following_notes_by_ticks(
    current_note: Note,
    following_notes: list[Note],
    project,
    *,
    old_end_tick: int,
    new_end_tick: int,
    tolerance_ticks: int = 1,
) -> list[Note]:
    """Shift a contiguous note chain after a duration change using tick timing."""
    if not following_notes:
        return []

    note_infos = [
        (
            note,
            note.get_start_tick(project),
            note.get_duration_ticks(project),
        )
        for note in following_notes
    ]

    first_note, first_original_start_tick, first_duration_ticks = note_infos[0]
    if first_original_start_tick > old_end_tick + max(0, tolerance_ticks):
        return []

    adjusted_notes: list[Note] = []
    next_start_tick = new_end_tick
    previous_original_end_tick = first_original_start_tick + first_duration_ticks

    first_note.apply_tick_timing(project, next_start_tick, first_duration_ticks)
    adjusted_notes.append(first_note)
    next_start_tick += first_duration_ticks

    for note, original_start_tick, duration_ticks in note_infos[1:]:
        if original_start_tick > previous_original_end_tick + max(0, tolerance_ticks):
            break
        note.apply_tick_timing(project, next_start_tick, duration_ticks)
        adjusted_notes.append(note)
        next_start_tick += duration_ticks
        previous_original_end_tick = original_start_tick + duration_ticks

    return adjusted_notes


class PropertyPanelWidget(QWidget):
    """属性面板"""
    
    # 信号：属性改变时发出
    property_changed = pyqtSignal(Note, Track)  # 属性改变（单个音符）
    property_update_requested = pyqtSignal(Note, Track)  # 请求更新UI显示
    batch_property_changed = pyqtSignal(list)  # 批量属性改变 [(note, track), ...]
    track_property_changed = pyqtSignal(Track, str)  # 音轨属性改变
    
    def __init__(self, parent=None):
        """初始化属性面板"""
        super().__init__(parent)
        
        self.current_note: Note = None
        self.project = None
        self.current_track: Track = None
        self.current_notes: list = []  # 多选音符列表 [(note, track), ...]
        self.current_track_for_edit: Track = None  # 当前编辑的音轨
        self.bpm: float = 120.0  # 默认BPM
        # 批量编辑控件是否被用户主动修改的标记（用于区分"未触碰"与"需要应用"）
        self._batch_waveform_dirty: bool = False
        self._batch_velocity_dirty: bool = False
        self._batch_velocity_offset_dirty: bool = False
        self._batch_duty_dirty: bool = False
        
        self.init_ui()
        self.set_note(None, None)  # 初始化为空
    
    def init_ui(self):
        """初始化UI"""
        self.setObjectName("propertyPanel")
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.setLayout(layout)
        
        # 设置属性面板的最大高度，确保不挡住面板切换按钮
        # 使用滚动区域来容纳内容，而不是让面板无限增长
        scroll_area = QScrollArea()
        scroll_area.setObjectName("propertyPanelScroll")
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(6)
        content_widget.setLayout(content_layout)
        
        # 将内容添加到滚动区域
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        layout.addWidget(scroll_area)
        
        # 保存引用以便后续添加控件
        self.content_layout = content_layout
        self.scroll_area = scroll_area
        
        # 标题
        title = QLabel("属性面板")
        title.setObjectName("panelTitle")
        self.content_layout.addWidget(title)
        
        # 空状态提示
        self.empty_label = QLabel("未选中音符\n\n请点击序列编辑器中的音符来编辑属性")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.empty_label)
        
        # 多选提示
        self.multi_select_label = QLabel("")
        self.multi_select_label.setObjectName("selectionSummary")
        self.multi_select_label.setAlignment(Qt.AlignCenter)
        self.multi_select_label.setVisible(False)
        self.content_layout.addWidget(self.multi_select_label)
        
        # 属性编辑区域（初始隐藏）
        self.properties_group = QGroupBox("音符属性")
        self.properties_group.setProperty("inspectorGroup", True)
        properties_layout = QVBoxLayout()
        properties_layout.setContentsMargins(8, 6, 8, 6)
        properties_layout.setSpacing(6)
        self.properties_group.setLayout(properties_layout)
        self.properties_group.setVisible(False)
        self.content_layout.addWidget(self.properties_group)
        
        # 音轨编辑区域（初始隐藏）
        self.track_edit_group = QGroupBox("音轨编辑")
        self.track_edit_group.setProperty("inspectorGroup", True)
        track_edit_layout = QVBoxLayout()
        track_edit_layout.setContentsMargins(8, 6, 8, 6)
        track_edit_layout.setSpacing(6)
        self.track_edit_group.setLayout(track_edit_layout)
        self.track_edit_group.setVisible(False)
        self.content_layout.addWidget(self.track_edit_group)
        
        # 音轨类型选择
        track_type_layout = QHBoxLayout()
        track_type_layout.setContentsMargins(0, 0, 0, 0)
        track_type_layout.setSpacing(6)
        track_type_layout.addWidget(QLabel("音轨类型:"))
        self.track_type_combo = QComboBox()
        self.track_type_combo.addItems(["音符音轨", "打击乐音轨"])
        self.track_type_combo.currentIndexChanged.connect(self.on_track_type_changed)
        track_type_layout.addWidget(self.track_type_combo)
        track_type_layout.addStretch()
        track_edit_layout.addLayout(track_type_layout)

        # 音轨角色选择
        self.track_role_row_widget = QWidget()
        track_role_layout = QHBoxLayout()
        track_role_layout.setContentsMargins(0, 0, 0, 0)
        track_role_layout.setSpacing(6)
        self.track_role_row_widget.setLayout(track_role_layout)
        track_role_layout.addWidget(QLabel("音轨角色:"))
        self.track_role_combo = QComboBox()
        self.track_role_combo.addItems(
            [label for label, _ in TRACK_ROLE_EDITOR_OPTIONS]
        )
        self.track_role_combo.currentIndexChanged.connect(self.on_track_role_changed)
        track_role_layout.addWidget(self.track_role_combo)
        track_role_layout.addStretch()
        track_edit_layout.addWidget(self.track_role_row_widget)
        
        # 音轨名称编辑
        track_name_layout = QHBoxLayout()
        track_name_layout.setContentsMargins(0, 0, 0, 0)
        track_name_layout.setSpacing(6)
        track_name_layout.addWidget(QLabel("音轨名称:"))
        self.track_name_edit = QLineEdit()
        self.track_name_edit.setPlaceholderText("输入音轨名称")
        self.track_name_edit.editingFinished.connect(self.on_track_name_changed)
        track_name_layout.addWidget(self.track_name_edit)
        track_name_layout.addStretch()
        track_edit_layout.addLayout(track_name_layout)
        
        # 音轨不再有默认波形，波形是音符的属性
        # 移除音轨波形选择控件
        
        # 批量编辑区域（初始隐藏）
        self.batch_edit_group = QGroupBox("批量编辑（多选音符）")
        self.batch_edit_group.setProperty("inspectorGroup", True)
        batch_layout = QVBoxLayout()
        batch_layout.setContentsMargins(8, 6, 8, 6)
        batch_layout.setSpacing(6)
        self.batch_edit_group.setLayout(batch_layout)
        self.batch_edit_group.setVisible(False)
        self.content_layout.addWidget(self.batch_edit_group)
        
        # 批量编辑：波形（立即生效）
        batch_waveform_layout = QHBoxLayout()
        batch_waveform_layout.setContentsMargins(0, 0, 0, 0)
        batch_waveform_layout.setSpacing(6)
        batch_waveform_layout.addWidget(QLabel("统一设置波形:"))
        self.batch_waveform_combo = QComboBox()
        self.batch_waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        self.batch_waveform_combo.currentIndexChanged.connect(self.on_batch_waveform_changed)
        batch_waveform_layout.addWidget(self.batch_waveform_combo)
        batch_waveform_layout.addStretch()
        batch_layout.addLayout(batch_waveform_layout)
        
        # 批量编辑：力度（立即生效）
        batch_velocity_layout = QHBoxLayout()
        batch_velocity_layout.setContentsMargins(0, 0, 0, 0)
        batch_velocity_layout.setSpacing(6)
        batch_velocity_layout.addWidget(QLabel("统一设置力度:"))
        self.batch_velocity_slider = QSlider(Qt.Horizontal)
        self.batch_velocity_slider.setRange(0, 127)
        self.batch_velocity_slider.setValue(127)
        self.batch_velocity_slider.sliderReleased.connect(self.on_batch_velocity_changed)
        batch_velocity_layout.addWidget(self.batch_velocity_slider)
        self.batch_velocity_label = QLabel("127")
        self.batch_velocity_label.setMinimumWidth(40)
        batch_velocity_layout.addWidget(self.batch_velocity_label)
        self.batch_velocity_slider.valueChanged.connect(lambda v: self.batch_velocity_label.setText(str(v)))
        batch_velocity_layout.addStretch()
        batch_layout.addLayout(batch_velocity_layout)
        
        # 批量编辑：力度偏移（在原有基础上加减）
        batch_velocity_offset_layout = QHBoxLayout()
        batch_velocity_offset_layout.setContentsMargins(0, 0, 0, 0)
        batch_velocity_offset_layout.setSpacing(6)
        batch_velocity_offset_layout.addWidget(QLabel("力度偏移:"))
        self.batch_velocity_offset_spinbox = QSpinBox()
        self.batch_velocity_offset_spinbox.setRange(-127, 127)
        self.batch_velocity_offset_spinbox.setValue(0)
        self.batch_velocity_offset_spinbox.setSingleStep(1)
        self.batch_velocity_offset_spinbox.setSuffix(" (在原有基础上)")
        self.batch_velocity_offset_spinbox.valueChanged.connect(self.on_batch_velocity_offset_changed)
        batch_velocity_offset_layout.addWidget(self.batch_velocity_offset_spinbox)
        batch_velocity_offset_layout.addStretch()
        batch_layout.addLayout(batch_velocity_offset_layout)
        
        # 批量编辑：占空比（仅方波，立即生效）
        batch_duty_layout = QHBoxLayout()
        batch_duty_layout.setContentsMargins(0, 0, 0, 0)
        batch_duty_layout.setSpacing(6)
        batch_duty_layout.addWidget(QLabel("统一设置占空比:"))
        self.batch_duty_spinbox = QDoubleSpinBox()
        self.batch_duty_spinbox.setRange(0.0, 1.0)
        self.batch_duty_spinbox.setSingleStep(0.1)
        self.batch_duty_spinbox.setDecimals(2)
        self.batch_duty_spinbox.setValue(0.5)
        self.batch_duty_spinbox.editingFinished.connect(self.on_batch_duty_changed)
        batch_duty_layout.addWidget(self.batch_duty_spinbox)
        batch_duty_layout.addStretch()
        batch_layout.addLayout(batch_duty_layout)
        
        # 使用GridLayout更好地利用空间（2列布局）
        properties_grid = QGridLayout()
        properties_grid.setContentsMargins(0, 0, 0, 0)
        properties_grid.setHorizontalSpacing(8)
        properties_grid.setVerticalSpacing(6)
        properties_grid.setColumnStretch(1, 1)  # 第二列可拉伸
        
        row = 0
        
        # 基础信息
        properties_grid.addWidget(QLabel("音符信息:"), row, 0)
        self.note_info_label = QLabel("")
        properties_grid.addWidget(self.note_info_label, row, 1)
        row += 1
        
        # 音高（MIDI）
        properties_grid.addWidget(QLabel("音高 (MIDI):"), row, 0)
        pitch_container = QHBoxLayout()
        pitch_container.setContentsMargins(0, 0, 0, 0)
        pitch_container.setSpacing(4)
        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(0, 127)
        self.pitch_spinbox.setValue(60)
        self.pitch_spinbox.valueChanged.connect(self.on_pitch_changed)
        pitch_container.addWidget(self.pitch_spinbox)
        # 音高显示（音名）
        self.pitch_name_label = QLabel("C4")
        self.pitch_name_label.setMinimumWidth(50)
        pitch_container.addWidget(self.pitch_name_label)
        pitch_container.addStretch()
        pitch_widget = QWidget()
        pitch_widget.setLayout(pitch_container)
        properties_grid.addWidget(pitch_widget, row, 1)
        row += 1
        
        # 开始时间（秒）
        properties_grid.addWidget(QLabel("开始时间 (秒):"), row, 0)
        self.start_time_spinbox = QDoubleSpinBox()
        self.start_time_spinbox.setRange(0.0, 1000.0)
        self.start_time_spinbox.setSingleStep(0.1)
        self.start_time_spinbox.setDecimals(3)
        self.start_time_spinbox.setValue(0.0)
        self.start_time_spinbox.valueChanged.connect(self.on_start_time_changed)
        properties_grid.addWidget(self.start_time_spinbox, row, 1)
        row += 1
        
        # 结束时间（秒）
        properties_grid.addWidget(QLabel("结束时间 (秒):"), row, 0)
        self.end_time_spinbox = QDoubleSpinBox()
        self.end_time_spinbox.setRange(0.0, 1000.0)
        self.end_time_spinbox.setSingleStep(0.1)
        self.end_time_spinbox.setDecimals(3)
        self.end_time_spinbox.setValue(0.5)
        self.end_time_spinbox.valueChanged.connect(self.on_end_time_changed)
        properties_grid.addWidget(self.end_time_spinbox, row, 1)
        row += 1
        
        # 时长（节拍）
        properties_grid.addWidget(QLabel("时长 (拍):"), row, 0)
        duration_container = QHBoxLayout()
        duration_container.setContentsMargins(0, 0, 0, 0)
        duration_container.setSpacing(4)
        self.duration_spinbox = QDoubleSpinBox()
        self.duration_spinbox.setRange(0.25, 16.0)  # 从1/4拍到16拍
        self.duration_spinbox.setSingleStep(0.25)  # 1/4拍步进
        self.duration_spinbox.setDecimals(2)
        self.duration_spinbox.setValue(1.0)  # 默认1拍
        self.duration_spinbox.valueChanged.connect(self.on_duration_changed)
        duration_container.addWidget(self.duration_spinbox)
        # 时长（秒）显示
        self.duration_seconds_label = QLabel("(0.5秒)")
        duration_container.addWidget(self.duration_seconds_label)
        duration_container.addStretch()
        duration_widget = QWidget()
        duration_widget.setLayout(duration_container)
        properties_grid.addWidget(duration_widget, row, 1)
        row += 1
        
        # 力度
        properties_grid.addWidget(QLabel("力度:"), row, 0)
        velocity_container = QHBoxLayout()
        velocity_container.setContentsMargins(0, 0, 0, 0)
        velocity_container.setSpacing(4)
        self.velocity_slider = QSlider(Qt.Horizontal)
        self.velocity_slider.setRange(0, 127)
        self.velocity_slider.setValue(127)
        self.velocity_slider.valueChanged.connect(self.on_velocity_changed)
        velocity_container.addWidget(self.velocity_slider)
        self.velocity_label = QLabel("127")
        self.velocity_label.setMinimumWidth(40)
        velocity_container.addWidget(self.velocity_label)
        velocity_widget = QWidget()
        velocity_widget.setLayout(velocity_container)
        properties_grid.addWidget(velocity_widget, row, 1)
        row += 1
        
        # 波形
        properties_grid.addWidget(QLabel("波形:"), row, 0)
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        self.waveform_combo.currentIndexChanged.connect(self.on_waveform_changed)
        properties_grid.addWidget(self.waveform_combo, row, 1)
        row += 1
        
        properties_layout.addLayout(properties_grid)
        
        # ADSR参数（使用GridLayout）
        adsr_group = QGroupBox("ADSR包络")
        adsr_group.setProperty("inspectorGroup", True)
        adsr_group.setProperty("innerGroup", True)
        adsr_grid = QGridLayout()
        adsr_grid.setContentsMargins(0, 0, 0, 0)
        adsr_grid.setHorizontalSpacing(8)
        adsr_grid.setVerticalSpacing(6)
        adsr_grid.setColumnStretch(1, 1)  # 第二列可拉伸
        adsr_group.setLayout(adsr_grid)
        properties_layout.addWidget(adsr_group)
        
        adsr_row = 0
        
        # Attack
        adsr_grid.addWidget(QLabel("起音 (Attack):"), adsr_row, 0)
        attack_container = QHBoxLayout()
        attack_container.setContentsMargins(0, 0, 0, 0)
        attack_container.setSpacing(4)
        self.attack_spinbox = QDoubleSpinBox()
        self.attack_spinbox.setRange(0.0, 1.0)
        self.attack_spinbox.setSingleStep(0.01)
        self.attack_spinbox.setDecimals(3)
        self.attack_spinbox.setValue(0.001)
        self.attack_spinbox.valueChanged.connect(self.on_adsr_changed)
        attack_container.addWidget(self.attack_spinbox)
        attack_container.addWidget(QLabel("秒"))
        attack_container.addStretch()
        attack_widget = QWidget()
        attack_widget.setLayout(attack_container)
        adsr_grid.addWidget(attack_widget, adsr_row, 1)
        adsr_row += 1
        
        # Decay
        adsr_grid.addWidget(QLabel("衰减 (Decay):"), adsr_row, 0)
        decay_container = QHBoxLayout()
        decay_container.setContentsMargins(0, 0, 0, 0)
        decay_container.setSpacing(4)
        self.decay_spinbox = QDoubleSpinBox()
        self.decay_spinbox.setRange(0.0, 1.0)
        self.decay_spinbox.setSingleStep(0.01)
        self.decay_spinbox.setDecimals(3)
        self.decay_spinbox.setValue(0.05)
        self.decay_spinbox.valueChanged.connect(self.on_adsr_changed)
        decay_container.addWidget(self.decay_spinbox)
        decay_container.addWidget(QLabel("秒"))
        decay_container.addStretch()
        decay_widget = QWidget()
        decay_widget.setLayout(decay_container)
        adsr_grid.addWidget(decay_widget, adsr_row, 1)
        adsr_row += 1
        
        # Sustain
        adsr_grid.addWidget(QLabel("延音 (Sustain):"), adsr_row, 0)
        sustain_container = QHBoxLayout()
        sustain_container.setContentsMargins(0, 0, 0, 0)
        sustain_container.setSpacing(4)
        self.sustain_spinbox = QDoubleSpinBox()
        self.sustain_spinbox.setRange(0.0, 1.0)
        self.sustain_spinbox.setSingleStep(0.01)
        self.sustain_spinbox.setDecimals(2)
        self.sustain_spinbox.setValue(0.8)
        self.sustain_spinbox.valueChanged.connect(self.on_adsr_changed)
        sustain_container.addWidget(self.sustain_spinbox)
        sustain_container.addWidget(QLabel("(0-1)"))
        sustain_container.addStretch()
        sustain_widget = QWidget()
        sustain_widget.setLayout(sustain_container)
        adsr_grid.addWidget(sustain_widget, adsr_row, 1)
        adsr_row += 1
        
        # Release
        adsr_grid.addWidget(QLabel("释音 (Release):"), adsr_row, 0)
        release_container = QHBoxLayout()
        release_container.setContentsMargins(0, 0, 0, 0)
        release_container.setSpacing(4)
        self.release_spinbox = QDoubleSpinBox()
        self.release_spinbox.setRange(0.0, 1.0)
        self.release_spinbox.setSingleStep(0.01)
        self.release_spinbox.setDecimals(3)
        self.release_spinbox.setValue(0.1)
        self.release_spinbox.valueChanged.connect(self.on_adsr_changed)
        release_container.addWidget(self.release_spinbox)
        release_container.addWidget(QLabel("秒"))
        release_container.addStretch()
        release_widget = QWidget()
        release_widget.setLayout(release_container)
        adsr_grid.addWidget(release_widget, adsr_row, 1)
        
        # 移除应用按钮，属性改变立即生效
        # 保留重置按钮
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self.reset_changes)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()

        properties_layout.addLayout(button_layout)
        
        # ========== 单个音符效果编辑区域 ==========
        self.note_effects_group = QGroupBox("音符效果")
        self.note_effects_group.setProperty("inspectorGroup", True)
        note_effects_layout = QVBoxLayout()
        note_effects_layout.setContentsMargins(8, 6, 8, 6)
        note_effects_layout.setSpacing(6)
        self.note_effects_group.setLayout(note_effects_layout)
        self.note_effects_group.setVisible(False)
        self.content_layout.addWidget(self.note_effects_group)
        
        # 音符颤音（音高调制）
        note_vibrato_group = QGroupBox("颤音 (Vibrato)")
        note_vibrato_group.setProperty("inspectorGroup", True)
        note_vibrato_group.setProperty("innerGroup", True)
        note_vibrato_layout = QVBoxLayout()
        note_vibrato_layout.setContentsMargins(6, 5, 6, 5)
        note_vibrato_layout.setSpacing(6)
        note_vibrato_group.setLayout(note_vibrato_layout)
        
        # 启用复选框
        self.note_vibrato_enabled_checkbox = QCheckBox("启用颤音")
        self.note_vibrato_enabled_checkbox.toggled.connect(self.on_note_vibrato_enabled_changed)
        note_vibrato_layout.addWidget(self.note_vibrato_enabled_checkbox)
        
        # 速度
        note_vibrato_rate_layout = QHBoxLayout()
        note_vibrato_rate_layout.setContentsMargins(0, 0, 0, 0)
        note_vibrato_rate_layout.setSpacing(6)
        note_vibrato_rate_layout.addWidget(QLabel("速度 (Hz):"))
        self.note_vibrato_rate_spinbox = QDoubleSpinBox()
        self.note_vibrato_rate_spinbox.setRange(0.1, 20.0)
        self.note_vibrato_rate_spinbox.setValue(6.0)
        self.note_vibrato_rate_spinbox.setSingleStep(0.5)
        self.note_vibrato_rate_spinbox.valueChanged.connect(self.on_note_vibrato_params_changed)
        note_vibrato_rate_layout.addWidget(self.note_vibrato_rate_spinbox)
        note_vibrato_rate_layout.addStretch()
        note_vibrato_layout.addLayout(note_vibrato_rate_layout)
        
        # 深度
        note_vibrato_depth_layout = QHBoxLayout()
        note_vibrato_depth_layout.setContentsMargins(0, 0, 0, 0)
        note_vibrato_depth_layout.setSpacing(6)
        note_vibrato_depth_layout.addWidget(QLabel("深度 (半音):"))
        self.note_vibrato_depth_spinbox = QDoubleSpinBox()
        self.note_vibrato_depth_spinbox.setRange(0.0, 12.0)
        self.note_vibrato_depth_spinbox.setValue(2.0)
        self.note_vibrato_depth_spinbox.setSingleStep(0.1)
        self.note_vibrato_depth_spinbox.setDecimals(2)
        self.note_vibrato_depth_spinbox.valueChanged.connect(self.on_note_vibrato_params_changed)
        note_vibrato_depth_layout.addWidget(self.note_vibrato_depth_spinbox)
        note_vibrato_depth_layout.addStretch()
        note_vibrato_layout.addLayout(note_vibrato_depth_layout)
        
        note_effects_layout.addWidget(note_vibrato_group)
        
        # ========== 轨道效果编辑区域 ==========
        self.effects_group = QGroupBox("轨道效果")
        self.effects_group.setProperty("inspectorGroup", True)
        effects_layout = QVBoxLayout()
        effects_layout.setContentsMargins(8, 6, 8, 6)
        effects_layout.setSpacing(6)
        self.effects_group.setLayout(effects_layout)
        self.content_layout.addWidget(self.effects_group)
        
        # 滤波器
        filter_group = QGroupBox("滤波器")
        filter_group.setProperty("inspectorGroup", True)
        filter_group.setProperty("innerGroup", True)
        filter_layout = QVBoxLayout()
        filter_layout.setContentsMargins(6, 5, 6, 5)
        filter_layout.setSpacing(6)
        filter_group.setLayout(filter_layout)
        
        # 启用复选框
        self.filter_enabled_checkbox = QCheckBox("启用滤波器")
        self.filter_enabled_checkbox.toggled.connect(self.on_filter_enabled_changed)
        filter_layout.addWidget(self.filter_enabled_checkbox)
        
        # 滤波器类型
        filter_type_layout = QHBoxLayout()
        filter_type_layout.setContentsMargins(0, 0, 0, 0)
        filter_type_layout.setSpacing(6)
        filter_type_layout.addWidget(QLabel("类型:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["低通", "高通", "带通"])
        self.filter_type_combo.currentIndexChanged.connect(self.on_filter_type_changed)
        filter_type_layout.addWidget(self.filter_type_combo)
        filter_type_layout.addStretch()
        filter_layout.addLayout(filter_type_layout)
        
        # 截止频率
        cutoff_layout = QHBoxLayout()
        cutoff_layout.setContentsMargins(0, 0, 0, 0)
        cutoff_layout.setSpacing(6)
        cutoff_layout.addWidget(QLabel("截止频率 (Hz):"))
        self.cutoff_spinbox = QDoubleSpinBox()
        self.cutoff_spinbox.setRange(20.0, 20000.0)
        self.cutoff_spinbox.setValue(1000.0)
        self.cutoff_spinbox.setSingleStep(100.0)
        self.cutoff_spinbox.valueChanged.connect(self.on_filter_params_changed)
        cutoff_layout.addWidget(self.cutoff_spinbox)
        cutoff_layout.addStretch()
        filter_layout.addLayout(cutoff_layout)
        
        # 共振
        resonance_layout = QHBoxLayout()
        resonance_layout.setContentsMargins(0, 0, 0, 0)
        resonance_layout.setSpacing(6)
        resonance_layout.addWidget(QLabel("共振 (Q):"))
        self.resonance_spinbox = QDoubleSpinBox()
        self.resonance_spinbox.setRange(0.1, 10.0)
        self.resonance_spinbox.setValue(1.0)
        self.resonance_spinbox.setSingleStep(0.1)
        self.resonance_spinbox.valueChanged.connect(self.on_filter_params_changed)
        resonance_layout.addWidget(self.resonance_spinbox)
        resonance_layout.addStretch()
        filter_layout.addLayout(resonance_layout)
        
        effects_layout.addWidget(filter_group)
        
        # 延迟效果
        delay_group = QGroupBox("延迟")
        delay_group.setProperty("inspectorGroup", True)
        delay_group.setProperty("innerGroup", True)
        delay_layout = QVBoxLayout()
        delay_layout.setContentsMargins(6, 5, 6, 5)
        delay_layout.setSpacing(6)
        delay_group.setLayout(delay_layout)
        
        # 启用复选框
        self.delay_enabled_checkbox = QCheckBox("启用延迟")
        self.delay_enabled_checkbox.toggled.connect(self.on_delay_enabled_changed)
        delay_layout.addWidget(self.delay_enabled_checkbox)
        
        # 延迟时间
        delay_time_layout = QHBoxLayout()
        delay_time_layout.setContentsMargins(0, 0, 0, 0)
        delay_time_layout.setSpacing(6)
        delay_time_layout.addWidget(QLabel("延迟时间 (秒):"))
        self.delay_time_spinbox = QDoubleSpinBox()
        self.delay_time_spinbox.setRange(0.01, 2.0)
        self.delay_time_spinbox.setValue(0.1)
        self.delay_time_spinbox.setSingleStep(0.01)
        self.delay_time_spinbox.setDecimals(3)
        self.delay_time_spinbox.valueChanged.connect(self.on_delay_params_changed)
        delay_time_layout.addWidget(self.delay_time_spinbox)
        delay_time_layout.addStretch()
        delay_layout.addLayout(delay_time_layout)
        
        # 反馈
        feedback_layout = QHBoxLayout()
        feedback_layout.setContentsMargins(0, 0, 0, 0)
        feedback_layout.setSpacing(6)
        feedback_layout.addWidget(QLabel("反馈:"))
        self.feedback_spinbox = QDoubleSpinBox()
        self.feedback_spinbox.setRange(0.0, 1.0)
        self.feedback_spinbox.setValue(0.3)
        self.feedback_spinbox.setSingleStep(0.1)
        self.feedback_spinbox.setDecimals(2)
        self.feedback_spinbox.valueChanged.connect(self.on_delay_params_changed)
        feedback_layout.addWidget(self.feedback_spinbox)
        feedback_layout.addStretch()
        delay_layout.addLayout(feedback_layout)
        
        # 混合比例
        mix_layout = QHBoxLayout()
        mix_layout.setContentsMargins(0, 0, 0, 0)
        mix_layout.setSpacing(6)
        mix_layout.addWidget(QLabel("混合比例:"))
        self.mix_spinbox = QDoubleSpinBox()
        self.mix_spinbox.setRange(0.0, 1.0)
        self.mix_spinbox.setValue(0.5)
        self.mix_spinbox.setSingleStep(0.1)
        self.mix_spinbox.setDecimals(2)
        self.mix_spinbox.valueChanged.connect(self.on_delay_params_changed)
        mix_layout.addWidget(self.mix_spinbox)
        mix_layout.addStretch()
        delay_layout.addLayout(mix_layout)
        
        effects_layout.addWidget(delay_group)
        
        # 颤音（音量调制）
        tremolo_group = QGroupBox("颤音 (Tremolo)")
        tremolo_group.setProperty("inspectorGroup", True)
        tremolo_group.setProperty("innerGroup", True)
        tremolo_layout = QVBoxLayout()
        tremolo_layout.setContentsMargins(6, 5, 6, 5)
        tremolo_layout.setSpacing(6)
        tremolo_group.setLayout(tremolo_layout)
        
        # 启用复选框
        self.tremolo_enabled_checkbox = QCheckBox("启用颤音")
        self.tremolo_enabled_checkbox.toggled.connect(self.on_tremolo_enabled_changed)
        tremolo_layout.addWidget(self.tremolo_enabled_checkbox)
        
        # 速度
        tremolo_rate_layout = QHBoxLayout()
        tremolo_rate_layout.setContentsMargins(0, 0, 0, 0)
        tremolo_rate_layout.setSpacing(6)
        tremolo_rate_layout.addWidget(QLabel("速度 (Hz):"))
        self.tremolo_rate_spinbox = QDoubleSpinBox()
        self.tremolo_rate_spinbox.setRange(0.1, 20.0)
        self.tremolo_rate_spinbox.setValue(6.0)
        self.tremolo_rate_spinbox.setSingleStep(0.5)
        self.tremolo_rate_spinbox.valueChanged.connect(self.on_tremolo_params_changed)
        tremolo_rate_layout.addWidget(self.tremolo_rate_spinbox)
        tremolo_rate_layout.addStretch()
        tremolo_layout.addLayout(tremolo_rate_layout)
        
        # 深度
        tremolo_depth_layout = QHBoxLayout()
        tremolo_depth_layout.setContentsMargins(0, 0, 0, 0)
        tremolo_depth_layout.setSpacing(6)
        tremolo_depth_layout.addWidget(QLabel("深度:"))
        self.tremolo_depth_spinbox = QDoubleSpinBox()
        self.tremolo_depth_spinbox.setRange(0.0, 1.0)
        self.tremolo_depth_spinbox.setValue(0.5)
        self.tremolo_depth_spinbox.setSingleStep(0.1)
        self.tremolo_depth_spinbox.setDecimals(2)
        self.tremolo_depth_spinbox.valueChanged.connect(self.on_tremolo_params_changed)
        tremolo_depth_layout.addWidget(self.tremolo_depth_spinbox)
        tremolo_depth_layout.addStretch()
        tremolo_layout.addLayout(tremolo_depth_layout)
        
        effects_layout.addWidget(tremolo_group)
        
        self.content_layout.addStretch()
    
    def set_note(self, note, track: Track):
        """
        设置当前编辑的音符或打击乐事件（单个）
        
        Args:
            note: Note 或 DrumEvent 对象
            track: 所属轨道
        """
        self.current_note = note
        self.current_track = track
        self.current_notes = []  # 清空多选
        
        if note is None or track is None:
            # 空状态
            self.empty_label.setVisible(True)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)
            self.effects_group.setVisible(False)
            self.batch_edit_group.setVisible(False)
            self.multi_select_label.setVisible(False)
        elif isinstance(note, DrumEvent):
            # 打击乐事件：不显示音符属性面板（打击乐事件属性较少，暂时不显示）
            self.empty_label.setVisible(True)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)
            self.effects_group.setVisible(False)
            self.batch_edit_group.setVisible(False)
            self.multi_select_label.setVisible(False)
        else:
            # 显示属性编辑（音符）
            self.empty_label.setVisible(False)
            self.properties_group.setVisible(True)
            self.note_effects_group.setVisible(True)  # 显示单个音符效果
            self.effects_group.setVisible(False)  # 编辑音符时不显示音轨效果
            self.batch_edit_group.setVisible(False)
            self.multi_select_label.setVisible(False)
            
            # 更新UI显示
            self.update_ui()
            self.update_note_effects_ui()
            # 不更新音轨效果UI（因为编辑的是音符，不是音轨）
    
    def set_notes(self, notes: list):
        """
        设置多选音符列表
        
        Args:
            notes: [(note, track), ...] 音符和轨道对列表
        """
        self.current_notes = notes
        self.current_note = None
        self.current_track = None
        
        if not notes:
            # 空状态
            self.empty_label.setVisible(True)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)
            self.effects_group.setVisible(False)
            self.batch_edit_group.setVisible(False)
            self.track_edit_group.setVisible(False)
            self.multi_select_label.setVisible(False)
        else:
            # 显示批量编辑
            self.empty_label.setVisible(False)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)
            self.effects_group.setVisible(False)
            self.batch_edit_group.setVisible(True)
            self.track_edit_group.setVisible(False)
            self.multi_select_label.setVisible(True)
            self.multi_select_label.setText(f"已选中 {len(notes)} 个音符\n可以统一编辑共有属性")
            # 进入多选批量编辑时，认为所有批量控件尚未被用户触碰
            self._batch_waveform_dirty = False
            self._batch_velocity_dirty = False
            self._batch_velocity_offset_dirty = False
            self._batch_duty_dirty = False
            # 重置力度偏移控件
            self.batch_velocity_offset_spinbox.blockSignals(True)
            self.batch_velocity_offset_spinbox.setValue(0)
            self.batch_velocity_offset_spinbox.blockSignals(False)
    
    def set_track(self, track: Track):
        """
        设置当前编辑的音轨
        
        Args:
            track: 要编辑的音轨
        """
        self.current_track_for_edit = track
        self.current_note = None
        self.current_track = None
        self.current_notes = []
        
        if track is None:
            # 空状态
            self.empty_label.setVisible(True)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)
            self.effects_group.setVisible(False)
            self.batch_edit_group.setVisible(False)
            self.track_edit_group.setVisible(False)
            self.multi_select_label.setVisible(False)
            self.track_role_row_widget.setVisible(False)
        else:
            # 显示音轨编辑和批量编辑（同时显示）
            self.empty_label.setVisible(False)
            self.properties_group.setVisible(False)
            self.note_effects_group.setVisible(False)  # 编辑音轨时不显示单个音符效果
            self.effects_group.setVisible(True)  # 编辑音轨时显示音轨效果
            self.batch_edit_group.setVisible(True)  # 显示批量编辑
            self.track_edit_group.setVisible(True)  # 显示音轨编辑
            self.multi_select_label.setVisible(True)
            
            # 更新音轨效果UI
            self.update_effects_ui()
            
            # 获取该轨道上的所有音符或打击乐事件
            if track.track_type == TrackType.DRUM_TRACK:
                # 打击乐音轨：暂时不支持批量编辑打击乐事件
                notes_and_tracks = []
                self.multi_select_label.setText(f"音轨: {track.name}\n已选中 {len(track.drum_events)} 个打击乐事件\n（打击乐事件暂不支持批量编辑）")
            else:
                # 音符音轨：获取所有音符
                notes_and_tracks = [(note, track) for note in track.notes]
                self.multi_select_label.setText(f"音轨: {track.name}\n已选中 {len(notes_and_tracks)} 个音符\n可以统一编辑共有属性")
            self.current_notes = notes_and_tracks
            
            # 更新音轨信息
            self.track_name_edit.setText(track.name)
            
            # 根据真实结构类型设置类型选择框。
            self.track_type_combo.blockSignals(True)
            self.track_type_combo.setCurrentIndex(get_track_type_editor_index(track))
            self.track_type_combo.blockSignals(False)
            self.track_role_combo.blockSignals(True)
            self.track_role_combo.setCurrentIndex(get_track_role_editor_index(track))
            self.track_role_combo.blockSignals(False)
            self._refresh_track_role_editor(track)
            # 进入音轨批量编辑模式时，同样重置"脏标记"
            self._batch_waveform_dirty = False
            self._batch_velocity_dirty = False
            self._batch_velocity_offset_dirty = False
            self._batch_duty_dirty = False
            # 重置力度偏移控件
            self.batch_velocity_offset_spinbox.blockSignals(True)
            self.batch_velocity_offset_spinbox.setValue(0)
            self.batch_velocity_offset_spinbox.blockSignals(False)

    def _refresh_track_role_editor(self, track: Track | None) -> None:
        """Show the role editor only for note tracks."""
        self.track_role_row_widget.setVisible(
            track is not None and track.track_type == TrackType.NOTE_TRACK
        )
    
    def set_project(self, project):
        """Set the project used for beat/second conversion."""
        self.project = project
        if self.current_note is not None:
            self.update_ui()

    def _safe_bpm(self) -> float:
        return self.bpm if self.bpm > 0 else 120.0

    def _seconds_to_beats(self, seconds: float) -> float:
        if self.project is not None:
            return self.project.seconds_to_beats(seconds)
        return max(0.0, seconds) * self._safe_bpm() / 60.0

    def _beats_to_seconds(self, beats: float) -> float:
        if self.project is not None:
            return self.project.beats_to_seconds(beats)
        return max(0.0, beats) * 60.0 / self._safe_bpm()

    def _duration_seconds_to_beats(self, start_time: float, duration: float) -> float:
        start_beat = self._seconds_to_beats(start_time)
        end_beat = self._seconds_to_beats(start_time + duration)
        return max(0.0, end_beat - start_beat)

    def _is_snap_to_beat_enabled(self) -> bool:
        from ui.settings_manager import get_settings_manager

        return get_settings_manager().is_snap_to_beat_enabled()

    def _sort_current_track_notes(self) -> None:
        if self.current_track and self.current_track.track_type == TrackType.NOTE_TRACK:
            self.current_track.notes.sort(
                key=lambda note: build_note_sort_key(note, self.project)
            )

    def update_ui(self):
        """更新UI显示"""
        if self.current_note is None:
            return
        
        note = self.current_note
        # 检查是否是 DrumEvent（打击乐事件不支持在属性面板编辑）
        if isinstance(note, DrumEvent):
            return
        
        # 更新音高
        self.pitch_spinbox.blockSignals(True)
        self.pitch_spinbox.setValue(note.pitch)
        self.pitch_spinbox.blockSignals(False)
        self.update_pitch_name()
        
        # 更新开始时间
        self.start_time_spinbox.blockSignals(True)
        self.start_time_spinbox.setValue(note.start_time)
        self.start_time_spinbox.blockSignals(False)
        
        # 更新结束时间
        end_time = note.start_time + note.duration
        self.end_time_spinbox.blockSignals(True)
        self.end_time_spinbox.setValue(end_time)
        self.end_time_spinbox.blockSignals(False)
        
        # 更新时长（将秒数转换为节拍数）
        duration_beats = self._duration_seconds_to_beats(note.start_time, note.duration)
        self.duration_spinbox.blockSignals(True)
        self.duration_spinbox.setValue(duration_beats)
        self.duration_spinbox.blockSignals(False)
        self.update_duration_seconds()
        
        # 更新力度
        self.velocity_slider.blockSignals(True)
        self.velocity_slider.setValue(note.velocity)
        self.velocity_label.setText(str(note.velocity))
        self.velocity_slider.blockSignals(False)
        
        # 更新波形
        waveform_map = {
            WaveformType.SQUARE: 0,
            WaveformType.TRIANGLE: 1,
            WaveformType.SAWTOOTH: 2,
            WaveformType.SINE: 3,
            WaveformType.NOISE: 4,
        }
        self.waveform_combo.blockSignals(True)
        self.waveform_combo.setCurrentIndex(waveform_map.get(note.waveform, 0))
        self.waveform_combo.blockSignals(False)
        
        # 更新ADSR
        if note.adsr:
            self.attack_spinbox.blockSignals(True)
            self.attack_spinbox.setValue(note.adsr.attack)
            self.attack_spinbox.blockSignals(False)
            
            self.decay_spinbox.blockSignals(True)
            self.decay_spinbox.setValue(note.adsr.decay)
            self.decay_spinbox.blockSignals(False)
            
            self.sustain_spinbox.blockSignals(True)
            self.sustain_spinbox.setValue(note.adsr.sustain)
            self.sustain_spinbox.blockSignals(False)
            
            self.release_spinbox.blockSignals(True)
            self.release_spinbox.setValue(note.adsr.release)
            self.release_spinbox.blockSignals(False)
        
        # 更新音符信息
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = note.pitch // 12 - 1
        note_name = note_names[note.pitch % 12]
        self.note_info_label.setText(f"{note_name}{octave} @ {note.start_time:.2f}s")
    
    def update_note_effects_ui(self):
        """更新单个音符效果UI显示"""
        if self.current_note is None:
            return
        
        note = self.current_note
        
        # 检查是否是 DrumEvent
        if isinstance(note, DrumEvent):
            return
        
        # 更新颤音
        if note.vibrato_params:
            self.note_vibrato_enabled_checkbox.blockSignals(True)
            self.note_vibrato_enabled_checkbox.setChecked(note.vibrato_params.enabled)
            self.note_vibrato_enabled_checkbox.blockSignals(False)
            
            self.note_vibrato_rate_spinbox.blockSignals(True)
            self.note_vibrato_rate_spinbox.setValue(note.vibrato_params.rate)
            self.note_vibrato_rate_spinbox.blockSignals(False)
            
            self.note_vibrato_depth_spinbox.blockSignals(True)
            self.note_vibrato_depth_spinbox.setValue(note.vibrato_params.depth)
            self.note_vibrato_depth_spinbox.blockSignals(False)
        else:
            # 创建默认颤音参数
            from core.effect_processor import VibratoParams
            note.vibrato_params = VibratoParams()
            self.update_note_effects_ui()  # 递归更新
    
    def update_pitch_name(self):
        """更新音高显示（音名）"""
        if self.current_note is None:
            return
        
        pitch = self.pitch_spinbox.value()
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        self.pitch_name_label.setText(f"{note_name}{octave}")
    
    def update_duration_seconds(self):
        """更新时长显示（秒数）"""
        if self.current_note is None or self.current_track is None:
            return
        
        # 将节拍数转换为秒数
        duration_beats = self.duration_spinbox.value()
        duration_seconds = self._beats_to_seconds(
            self._seconds_to_beats(self.current_note.start_time) + duration_beats
        ) - self.current_note.start_time
        self.duration_seconds_label.setText(f"({duration_seconds:.3f}秒)")
    
    def on_pitch_changed(self, value: int):
        """音高改变"""
        self.update_pitch_name()
        if self.current_note:
            self.current_note.pitch = value
            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_start_time_changed(self, value: float):
        """开始时间改变"""
        if self.current_note and self.current_track:
            new_start_time = value
            if self.project is not None:
                timing = resolve_note_timing_for_start_time(
                    self.current_note,
                    self.project,
                    new_start_time,
                    snap_to_beat=self._is_snap_to_beat_enabled(),
                )
                if timing is not None:
                    self.current_note.apply_tick_timing(self.project, *timing)
                    self._sort_current_track_notes()
                    self.update_ui()
                    self.property_changed.emit(self.current_note, self.current_track)
                return

            if self._is_snap_to_beat_enabled():
                start_beats = self._seconds_to_beats(new_start_time)
                start_beats = round(start_beats * 4) / 4
                new_start_time = self._beats_to_seconds(start_beats)
                self.start_time_spinbox.blockSignals(True)
                self.start_time_spinbox.setValue(new_start_time)
                self.start_time_spinbox.blockSignals(False)

            old_start_time = self.current_note.start_time
            old_end_time = old_start_time + self.current_note.duration
            new_duration = old_end_time - new_start_time

            if new_duration > 0:
                self.current_note.start_time = new_start_time
                self.current_note.duration = new_duration
                self.current_note.sync_tick_timing(self.project, prefer_existing=False) if self.project else None
                duration_beats = self._duration_seconds_to_beats(new_start_time, new_duration)
                self.duration_spinbox.blockSignals(True)
                self.duration_spinbox.setValue(duration_beats)
                self.duration_spinbox.blockSignals(False)
                self.update_duration_seconds()

                self.end_time_spinbox.blockSignals(True)
                self.end_time_spinbox.setValue(old_end_time)
                self.end_time_spinbox.blockSignals(False)

                self.property_changed.emit(self.current_note, self.current_track)
    
    def on_end_time_changed(self, value: float):
        """结束时间改变"""
        if self.current_note and self.current_track:
            new_end_time = value
            if self.project is not None:
                timing = resolve_note_timing_for_end_time(
                    self.current_note,
                    self.project,
                    new_end_time,
                    snap_to_beat=self._is_snap_to_beat_enabled(),
                )
                if timing is not None:
                    self.current_note.apply_tick_timing(self.project, *timing)
                    self._sort_current_track_notes()
                    self.update_ui()
                    self.property_changed.emit(self.current_note, self.current_track)
                return

            if self._is_snap_to_beat_enabled():
                end_beats = self._seconds_to_beats(new_end_time)
                end_beats = round(end_beats * 4) / 4
                new_end_time = self._beats_to_seconds(end_beats)
                self.end_time_spinbox.blockSignals(True)
                self.end_time_spinbox.setValue(new_end_time)
                self.end_time_spinbox.blockSignals(False)

            start_time = self.current_note.start_time
            new_duration = new_end_time - start_time

            if new_duration > 0 and new_end_time > start_time:
                self.current_note.duration = new_duration
                self.current_note.sync_tick_timing(self.project, prefer_existing=False) if self.project else None
                duration_beats = self._duration_seconds_to_beats(start_time, new_duration)
                self.duration_spinbox.blockSignals(True)
                self.duration_spinbox.setValue(duration_beats)
                self.duration_spinbox.blockSignals(False)
                self.update_duration_seconds()

            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_duration_changed(self, value: float):
        """时长改变（value是节拍数）"""
        if self.current_note and self.current_track:
            if self.project is not None:
                timing = resolve_note_timing_for_duration_beats(
                    self.current_note,
                    self.project,
                    value,
                    snap_to_beat=self._is_snap_to_beat_enabled(),
                )
                if timing is None:
                    self.update_duration_seconds()
                    return

                old_start_tick = self.current_note.get_start_tick(self.project)
                old_duration_ticks = self.current_note.get_duration_ticks(self.project)
                old_end_tick = old_start_tick + old_duration_ticks
                self.current_note.apply_tick_timing(self.project, *timing)
                new_duration_ticks = self.current_note.get_duration_ticks(self.project)
                duration_delta_ticks = new_duration_ticks - old_duration_ticks

                self.end_time_spinbox.blockSignals(True)
                self.end_time_spinbox.setValue(self.current_note.start_time + self.current_note.duration)
                self.end_time_spinbox.blockSignals(False)
                self.update_duration_seconds()

                if duration_delta_ticks != 0:
                    adjusted_notes = self.adjust_following_notes(
                        0.0,
                        old_end_tick=old_end_tick,
                        duration_delta_ticks=duration_delta_ticks,
                    )
                    if adjusted_notes:
                        from PyQt5.QtCore import QTimer

                        QTimer.singleShot(
                            0,
                            lambda: self.property_changed.emit(self.current_note, self.current_track),
                        )
                        return

                self._sort_current_track_notes()
                self.update_ui()
                self.property_changed.emit(self.current_note, self.current_track)
                return

            duration_seconds = self._beats_to_seconds(
                self._seconds_to_beats(self.current_note.start_time) + value
            ) - self.current_note.start_time
            self.update_duration_seconds()

            if self._is_snap_to_beat_enabled():
                duration_beats = self._duration_seconds_to_beats(
                    self.current_note.start_time,
                    duration_seconds,
                )
                duration_beats = round(duration_beats * 4) / 4
                duration_seconds = self._beats_to_seconds(
                    self._seconds_to_beats(self.current_note.start_time) + duration_beats
                ) - self.current_note.start_time
                self.duration_spinbox.blockSignals(True)
                self.duration_spinbox.setValue(duration_beats)
                self.duration_spinbox.blockSignals(False)
                self.update_duration_seconds()

            old_duration = self.current_note.duration
            new_duration = duration_seconds
            duration_delta = new_duration - old_duration

            self.current_note.duration = new_duration

            new_end_time = self.current_note.start_time + new_duration
            self.end_time_spinbox.blockSignals(True)
            self.end_time_spinbox.setValue(new_end_time)
            self.end_time_spinbox.blockSignals(False)

            if abs(duration_delta) > 0.001:
                adjusted_notes = self.adjust_following_notes(duration_delta)
                if adjusted_notes:
                    from PyQt5.QtCore import QTimer

                    QTimer.singleShot(0, lambda: self.property_changed.emit(self.current_note, self.current_track))
                    return

            self.property_changed.emit(self.current_note, self.current_track)
    
    def adjust_following_notes(
        self,
        duration_delta: float,
        *,
        old_end_tick: int | None = None,
        duration_delta_ticks: int | None = None,
    ):
        """调整后续音符的位置，使它们保持连续
        
        Returns:
            被调整的音符列表
        """
        if not self.current_note or not self.current_track:
            return []

        all_notes = sorted(
            self.current_track.notes,
            key=lambda note: build_note_sort_key(note, self.project),
        )

        current_index = -1
        for index, note in enumerate(all_notes):
            if note == self.current_note:
                current_index = index
                break

        if current_index == -1:
            return []

        following_notes = all_notes[current_index + 1:]
        if not following_notes:
            return []

        if self.project is not None:
            current_start_tick = self.current_note.get_start_tick(self.project)
            current_duration_ticks = self.current_note.get_duration_ticks(self.project)
            current_end_tick = current_start_tick + current_duration_ticks
            if duration_delta_ticks is None:
                duration_delta_ticks = int(
                    round(
                        self.project.seconds_to_ticks(self.current_note.duration)
                        - self.project.seconds_to_ticks(
                            max(0.0, self.current_note.duration - duration_delta)
                        )
                    )
                )
            if old_end_tick is None:
                old_end_tick = current_end_tick - duration_delta_ticks

            adjusted_notes = shift_contiguous_following_notes_by_ticks(
                self.current_note,
                following_notes,
                self.project,
                old_end_tick=old_end_tick,
                new_end_tick=current_end_tick,
            )
            if adjusted_notes:
                self._sort_current_track_notes()
            return adjusted_notes

        current_note_end = self.current_note.start_time + self.current_note.duration
        old_end_time = self.current_note.start_time + (self.current_note.duration - duration_delta)
        adjusted_notes = []

        first_following = following_notes[0]
        if first_following.start_time <= old_end_time + 0.01:
            first_following.start_time = current_note_end
            adjusted_notes.append(first_following)
            current_note_end = first_following.start_time + first_following.duration

            for i in range(1, len(following_notes)):
                note = following_notes[i]
                prev_note = following_notes[i - 1]
                prev_end = prev_note.start_time + prev_note.duration
                if note.start_time <= prev_end + 0.01:
                    note.start_time = prev_end
                    adjusted_notes.append(note)
                    current_note_end = note.start_time + note.duration
                else:
                    break

        return adjusted_notes
    
    def on_velocity_changed(self, value: int):
        """力度改变"""
        self.velocity_label.setText(str(value))
        if self.current_note:
            self.current_note.velocity = value
            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_waveform_changed(self, index: int):
        """波形改变"""
        waveform_map = {
            0: WaveformType.SQUARE,
            1: WaveformType.TRIANGLE,
            2: WaveformType.SAWTOOTH,
            3: WaveformType.SINE,
            4: WaveformType.NOISE,
        }
        waveform = waveform_map.get(index, WaveformType.SQUARE)
        if self.current_note:
            self.current_note.waveform = waveform
            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_adsr_changed(self):
        """ADSR参数改变"""
        if self.current_note and self.current_note.adsr:
            self.current_note.adsr.attack = self.attack_spinbox.value()
            self.current_note.adsr.decay = self.decay_spinbox.value()
            self.current_note.adsr.sustain = self.sustain_spinbox.value()
            self.current_note.adsr.release = self.release_spinbox.value()
            self.property_changed.emit(self.current_note, self.current_track)
    
    def apply_changes(self):
        """应用更改"""
        if self.current_note and self.current_track:
            self.property_changed.emit(self.current_note, self.current_track)
            self.property_update_requested.emit(self.current_note, self.current_track)
    
    def reset_changes(self):
        """重置更改"""
        self.update_ui()
    
    def set_bpm(self, bpm: float):
        """设置BPM（用于计算节拍数和秒数转换）"""
        self.bpm = bpm
        # 如果当前有选中的音符，需要更新显示
        if self.current_note:
            # 重新计算节拍数显示
            duration_beats = self._duration_seconds_to_beats(
                self.current_note.start_time,
                self.current_note.duration,
            )
            self.duration_spinbox.blockSignals(True)
            self.duration_spinbox.setValue(duration_beats)
            self.duration_spinbox.blockSignals(False)
            self.update_duration_seconds()
    
    def update_effects_ui(self):
        """更新效果UI显示"""
        # 优先使用current_track_for_edit（编辑音轨时），否则使用current_track（编辑音符时）
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track is None:
            return
        
        # 更新滤波器
        if track.filter_params:
            self.filter_enabled_checkbox.blockSignals(True)
            self.filter_enabled_checkbox.setChecked(track.filter_params.enabled)
            self.filter_enabled_checkbox.blockSignals(False)
            
            filter_type_map = {
                FilterType.LOWPASS: 0,
                FilterType.HIGHPASS: 1,
                FilterType.BANDPASS: 2,
            }
            self.filter_type_combo.blockSignals(True)
            self.filter_type_combo.setCurrentIndex(filter_type_map.get(track.filter_params.filter_type, 0))
            self.filter_type_combo.blockSignals(False)
            
            self.cutoff_spinbox.blockSignals(True)
            self.cutoff_spinbox.setValue(track.filter_params.cutoff_frequency)
            self.cutoff_spinbox.blockSignals(False)
            
            self.resonance_spinbox.blockSignals(True)
            self.resonance_spinbox.setValue(track.filter_params.resonance)
            self.resonance_spinbox.blockSignals(False)
        else:
            # 创建默认滤波器参数
            track.filter_params = FilterParams()
            self.update_effects_ui()  # 递归更新
        
        # 更新延迟
        if track.delay_params:
            self.delay_enabled_checkbox.blockSignals(True)
            self.delay_enabled_checkbox.setChecked(track.delay_params.enabled)
            self.delay_enabled_checkbox.blockSignals(False)
            
            self.delay_time_spinbox.blockSignals(True)
            self.delay_time_spinbox.setValue(track.delay_params.delay_time)
            self.delay_time_spinbox.blockSignals(False)
            
            self.feedback_spinbox.blockSignals(True)
            self.feedback_spinbox.setValue(track.delay_params.feedback)
            self.feedback_spinbox.blockSignals(False)
            
            self.mix_spinbox.blockSignals(True)
            self.mix_spinbox.setValue(track.delay_params.mix)
            self.mix_spinbox.blockSignals(False)
        else:
            track.delay_params = DelayParams()
            self.update_effects_ui()
        
        # 更新颤音
        if track.tremolo_params:
            self.tremolo_enabled_checkbox.blockSignals(True)
            self.tremolo_enabled_checkbox.setChecked(track.tremolo_params.enabled)
            self.tremolo_enabled_checkbox.blockSignals(False)
            
            self.tremolo_rate_spinbox.blockSignals(True)
            self.tremolo_rate_spinbox.setValue(track.tremolo_params.rate)
            self.tremolo_rate_spinbox.blockSignals(False)
            
            self.tremolo_depth_spinbox.blockSignals(True)
            self.tremolo_depth_spinbox.setValue(track.tremolo_params.depth)
            self.tremolo_depth_spinbox.blockSignals(False)
        else:
            track.tremolo_params = TremoloParams()
            self.update_effects_ui()
    
    def on_filter_enabled_changed(self, enabled: bool):
        """滤波器启用状态改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.filter_params:
            track.filter_params.enabled = enabled
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_filter_type_changed(self, index: int):
        """滤波器类型改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.filter_params:
            filter_type_map = {
                0: FilterType.LOWPASS,
                1: FilterType.HIGHPASS,
                2: FilterType.BANDPASS,
            }
            track.filter_params.filter_type = filter_type_map.get(index, FilterType.LOWPASS)
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_filter_params_changed(self):
        """滤波器参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.filter_params:
            track.filter_params.cutoff_frequency = self.cutoff_spinbox.value()
            track.filter_params.resonance = self.resonance_spinbox.value()
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_delay_enabled_changed(self, enabled: bool):
        """延迟启用状态改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.delay_params:
            track.delay_params.enabled = enabled
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_delay_params_changed(self):
        """延迟参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.delay_params:
            track.delay_params.delay_time = self.delay_time_spinbox.value()
            track.delay_params.feedback = self.feedback_spinbox.value()
            track.delay_params.mix = self.mix_spinbox.value()
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_tremolo_enabled_changed(self, enabled: bool):
        """颤音启用状态改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.tremolo_params:
            track.tremolo_params.enabled = enabled
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_batch_waveform_changed(self, index: int):
        """批量波形改变（立即生效）"""
        if not self.current_notes:
            return
        # 标记为用户确实修改过波形，下次批量应用时才会真正修改波形
        self._batch_waveform_dirty = True
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_batch_velocity_changed(self):
        """批量力度改变（立即生效）"""
        if not self.current_notes:
            return
        # 标记为用户确实修改过力度
        self._batch_velocity_dirty = True
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_batch_duty_changed(self):
        """批量占空比改变（立即生效）"""
        if not self.current_notes:
            return
        # 标记为用户确实修改过占空比
        self._batch_duty_dirty = True
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_batch_velocity_offset_changed(self, value: int):
        """批量力度偏移改变（立即生效）"""
        if not self.current_notes:
            return
        # 如果偏移值为0，不标记为脏（避免无意义的修改）
        if value == 0:
            self._batch_velocity_offset_dirty = False
        else:
            # 标记为用户确实修改过力度偏移
            self._batch_velocity_offset_dirty = True
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_track_type_changed(self, index: int):
        """音轨类型改变"""
        if not self.current_track_for_edit:
            return

        new_track_type = resolve_track_type_from_editor_index(index)
        if self.current_track_for_edit.track_type == new_track_type:
            return

        if not can_change_track_type_on_existing_track(
            self.current_track_for_edit,
            new_track_type,
        ):
            self.track_type_combo.blockSignals(True)
            self.track_type_combo.setCurrentIndex(
                get_track_type_editor_index(self.current_track_for_edit)
            )
            self.track_type_combo.blockSignals(False)
            QMessageBox.information(
                self,
                "暂不支持直接转换",
                "当前音轨已经包含音符或鼓点数据。\n\n"
                "“音符音轨”和“打击乐音轨”是两种不同的数据结构，不是简单的音色切换。"
                "请先新建目标类型音轨并迁移内容，或清空当前音轨后再切换。",
            )
            return

        self.current_track_for_edit.track_type = new_track_type
        if new_track_type == TrackType.DRUM_TRACK:
            self.current_track_for_edit.role = None
        else:
            self.current_track_for_edit.role = infer_track_role(
                self.current_track_for_edit.name,
                new_track_type,
            )
        self.track_role_combo.blockSignals(True)
        self.track_role_combo.setCurrentIndex(
            get_track_role_editor_index(self.current_track_for_edit)
        )
        self.track_role_combo.blockSignals(False)
        self._refresh_track_role_editor(self.current_track_for_edit)

        self.track_property_changed.emit(
            self.current_track_for_edit,
            TRACK_PROPERTY_CHANGE_STRUCTURE,
        )

    def on_track_role_changed(self, index: int):
        """音轨角色改变。"""
        if not self.current_track_for_edit:
            return
        if self.current_track_for_edit.track_type != TrackType.NOTE_TRACK:
            return

        new_track_role = resolve_track_role_from_editor_index(index)
        if self.current_track_for_edit.role == new_track_role:
            return

        self.current_track_for_edit.role = new_track_role
        self.track_property_changed.emit(
            self.current_track_for_edit,
            TRACK_PROPERTY_CHANGE_PRESENTATION,
        )
    
    def on_track_name_changed(self):
        """音轨名称改变"""
        if not self.current_track_for_edit:
            return
        
        new_name = self.track_name_edit.text().strip()
        if new_name:
            self.current_track_for_edit.name = new_name
            # 发送音轨属性改变信号
            self.track_property_changed.emit(
                self.current_track_for_edit,
                TRACK_PROPERTY_CHANGE_METADATA,
            )
    
    # 音轨不再有默认波形，波形是音符的属性
    # on_track_waveform_changed 方法已移除
    
    def on_tremolo_params_changed(self):
        """颤音参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.tremolo_params:
            track.tremolo_params.rate = self.tremolo_rate_spinbox.value()
            track.tremolo_params.depth = self.tremolo_depth_spinbox.value()
            self.track_property_changed.emit(track, TRACK_PROPERTY_CHANGE_EFFECTS)
    
    def on_note_vibrato_enabled_changed(self, enabled: bool):
        """单个音符颤音启用状态改变"""
        if self.current_note and self.current_note.vibrato_params:
            self.current_note.vibrato_params.enabled = enabled
            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_note_vibrato_params_changed(self):
        """单个音符颤音参数改变"""
        if self.current_note and self.current_note.vibrato_params:
            self.current_note.vibrato_params.rate = self.note_vibrato_rate_spinbox.value()
            self.current_note.vibrato_params.depth = self.note_vibrato_depth_spinbox.value()
            self.property_changed.emit(self.current_note, self.current_track)

