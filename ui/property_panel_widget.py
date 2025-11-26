"""
属性面板模块

用于编辑选中音符的属性（音高、时长、力度、波形、ADSR等）。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QSlider,
    QGroupBox, QPushButton, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from core.models import Note, Track, WaveformType, ADSRParams, TrackType
from core.track_events import DrumEvent
from core.effect_processor import (
    FilterParams, DelayParams, TremoloParams, VibratoParams, FilterType
)


class PropertyPanelWidget(QWidget):
    """属性面板"""
    
    # 信号：属性改变时发出
    property_changed = pyqtSignal(Note, Track)  # 属性改变（单个音符）
    property_update_requested = pyqtSignal(Note, Track)  # 请求更新UI显示
    batch_property_changed = pyqtSignal(list)  # 批量属性改变 [(note, track), ...]
    track_property_changed = pyqtSignal(Track)  # 音轨属性改变
    
    def __init__(self, parent=None):
        """初始化属性面板"""
        super().__init__(parent)
        
        self.current_note: Note = None
        self.current_track: Track = None
        self.current_notes: list = []  # 多选音符列表 [(note, track), ...]
        self.current_track_for_edit: Track = None  # 当前编辑的音轨
        self.bpm: float = 120.0  # 默认BPM
        
        self.init_ui()
        self.set_note(None, None)  # 初始化为空
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title = QLabel("属性面板")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)
        
        # 空状态提示
        self.empty_label = QLabel("未选中音符\n\n请点击序列编辑器中的音符来编辑属性")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; padding: 20px;")
        layout.addWidget(self.empty_label)
        
        # 多选提示
        self.multi_select_label = QLabel("")
        self.multi_select_label.setAlignment(Qt.AlignCenter)
        self.multi_select_label.setStyleSheet("color: blue; padding: 10px; font-weight: bold;")
        self.multi_select_label.setVisible(False)
        layout.addWidget(self.multi_select_label)
        
        # 属性编辑区域（初始隐藏）
        self.properties_group = QGroupBox("音符属性")
        properties_layout = QVBoxLayout()
        self.properties_group.setLayout(properties_layout)
        self.properties_group.setVisible(False)
        layout.addWidget(self.properties_group)
        
        # 音轨编辑区域（初始隐藏）
        self.track_edit_group = QGroupBox("音轨编辑")
        track_edit_layout = QVBoxLayout()
        self.track_edit_group.setLayout(track_edit_layout)
        self.track_edit_group.setVisible(False)
        layout.addWidget(self.track_edit_group)
        
        # 音轨类型选择
        track_type_layout = QHBoxLayout()
        track_type_layout.addWidget(QLabel("音轨类型:"))
        self.track_type_combo = QComboBox()
        self.track_type_combo.addItems(["主旋律", "低音", "打击乐"])
        self.track_type_combo.currentIndexChanged.connect(self.on_track_type_changed)
        track_type_layout.addWidget(self.track_type_combo)
        track_type_layout.addStretch()
        track_edit_layout.addLayout(track_type_layout)
        
        # 音轨名称编辑
        track_name_layout = QHBoxLayout()
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
        batch_layout = QVBoxLayout()
        self.batch_edit_group.setLayout(batch_layout)
        self.batch_edit_group.setVisible(False)
        layout.addWidget(self.batch_edit_group)
        
        # 批量编辑：波形（立即生效）
        batch_waveform_layout = QHBoxLayout()
        batch_waveform_layout.addWidget(QLabel("统一设置波形:"))
        self.batch_waveform_combo = QComboBox()
        self.batch_waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        self.batch_waveform_combo.currentIndexChanged.connect(self.on_batch_waveform_changed)
        batch_waveform_layout.addWidget(self.batch_waveform_combo)
        batch_waveform_layout.addStretch()
        batch_layout.addLayout(batch_waveform_layout)
        
        # 批量编辑：力度（立即生效）
        batch_velocity_layout = QHBoxLayout()
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
        
        # 批量编辑：占空比（仅方波，立即生效）
        batch_duty_layout = QHBoxLayout()
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
        
        # 基础信息
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("音符信息:"))
        self.note_info_label = QLabel("")
        info_layout.addWidget(self.note_info_label)
        info_layout.addStretch()
        properties_layout.addLayout(info_layout)
        
        # 音高（MIDI）
        pitch_layout = QHBoxLayout()
        pitch_layout.addWidget(QLabel("音高 (MIDI):"))
        self.pitch_spinbox = QSpinBox()
        self.pitch_spinbox.setRange(0, 127)
        self.pitch_spinbox.setValue(60)
        self.pitch_spinbox.valueChanged.connect(self.on_pitch_changed)
        pitch_layout.addWidget(self.pitch_spinbox)
        
        # 音高显示（音名）
        self.pitch_name_label = QLabel("C4")
        self.pitch_name_label.setMinimumWidth(50)
        pitch_layout.addWidget(self.pitch_name_label)
        pitch_layout.addStretch()
        properties_layout.addLayout(pitch_layout)
        
        # 开始时间（秒）
        start_time_layout = QHBoxLayout()
        start_time_layout.addWidget(QLabel("开始时间 (秒):"))
        self.start_time_spinbox = QDoubleSpinBox()
        self.start_time_spinbox.setRange(0.0, 1000.0)
        self.start_time_spinbox.setSingleStep(0.1)
        self.start_time_spinbox.setDecimals(3)
        self.start_time_spinbox.setValue(0.0)
        self.start_time_spinbox.valueChanged.connect(self.on_start_time_changed)
        start_time_layout.addWidget(self.start_time_spinbox)
        start_time_layout.addStretch()
        properties_layout.addLayout(start_time_layout)
        
        # 结束时间（秒）
        end_time_layout = QHBoxLayout()
        end_time_layout.addWidget(QLabel("结束时间 (秒):"))
        self.end_time_spinbox = QDoubleSpinBox()
        self.end_time_spinbox.setRange(0.0, 1000.0)
        self.end_time_spinbox.setSingleStep(0.1)
        self.end_time_spinbox.setDecimals(3)
        self.end_time_spinbox.setValue(0.5)
        self.end_time_spinbox.valueChanged.connect(self.on_end_time_changed)
        end_time_layout.addWidget(self.end_time_spinbox)
        end_time_layout.addStretch()
        properties_layout.addLayout(end_time_layout)
        
        # 时长（节拍）
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("时长 (拍):"))
        self.duration_spinbox = QDoubleSpinBox()
        self.duration_spinbox.setRange(0.25, 16.0)  # 从1/4拍到16拍
        self.duration_spinbox.setSingleStep(0.25)  # 1/4拍步进
        self.duration_spinbox.setDecimals(2)
        self.duration_spinbox.setValue(1.0)  # 默认1拍
        self.duration_spinbox.valueChanged.connect(self.on_duration_changed)
        duration_layout.addWidget(self.duration_spinbox)
        
        # 时长（秒）显示
        self.duration_seconds_label = QLabel("(0.5秒)")
        duration_layout.addWidget(self.duration_seconds_label)
        duration_layout.addStretch()
        properties_layout.addLayout(duration_layout)
        
        # 力度
        velocity_layout = QHBoxLayout()
        velocity_layout.addWidget(QLabel("力度:"))
        self.velocity_slider = QSlider(Qt.Horizontal)
        self.velocity_slider.setRange(0, 127)
        self.velocity_slider.setValue(127)
        self.velocity_slider.valueChanged.connect(self.on_velocity_changed)
        velocity_layout.addWidget(self.velocity_slider)
        
        self.velocity_label = QLabel("127")
        self.velocity_label.setMinimumWidth(40)
        velocity_layout.addWidget(self.velocity_label)
        properties_layout.addLayout(velocity_layout)
        
        # 波形
        waveform_layout = QHBoxLayout()
        waveform_layout.addWidget(QLabel("波形:"))
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["方波", "三角波", "锯齿波", "正弦波", "噪声"])
        self.waveform_combo.currentIndexChanged.connect(self.on_waveform_changed)
        waveform_layout.addWidget(self.waveform_combo)
        waveform_layout.addStretch()
        properties_layout.addLayout(waveform_layout)
        
        # ADSR参数
        adsr_group = QGroupBox("ADSR包络")
        adsr_layout = QVBoxLayout()
        adsr_group.setLayout(adsr_layout)
        properties_layout.addWidget(adsr_group)
        
        # Attack
        attack_layout = QHBoxLayout()
        attack_layout.addWidget(QLabel("起音 (Attack):"))
        self.attack_spinbox = QDoubleSpinBox()
        self.attack_spinbox.setRange(0.0, 1.0)
        self.attack_spinbox.setSingleStep(0.01)
        self.attack_spinbox.setDecimals(3)
        self.attack_spinbox.setValue(0.001)
        self.attack_spinbox.valueChanged.connect(self.on_adsr_changed)
        attack_layout.addWidget(self.attack_spinbox)
        attack_layout.addWidget(QLabel("秒"))
        attack_layout.addStretch()
        adsr_layout.addLayout(attack_layout)
        
        # Decay
        decay_layout = QHBoxLayout()
        decay_layout.addWidget(QLabel("衰减 (Decay):"))
        self.decay_spinbox = QDoubleSpinBox()
        self.decay_spinbox.setRange(0.0, 1.0)
        self.decay_spinbox.setSingleStep(0.01)
        self.decay_spinbox.setDecimals(3)
        self.decay_spinbox.setValue(0.05)
        self.decay_spinbox.valueChanged.connect(self.on_adsr_changed)
        decay_layout.addWidget(self.decay_spinbox)
        decay_layout.addWidget(QLabel("秒"))
        decay_layout.addStretch()
        adsr_layout.addLayout(decay_layout)
        
        # Sustain
        sustain_layout = QHBoxLayout()
        sustain_layout.addWidget(QLabel("延音 (Sustain):"))
        self.sustain_spinbox = QDoubleSpinBox()
        self.sustain_spinbox.setRange(0.0, 1.0)
        self.sustain_spinbox.setSingleStep(0.01)
        self.sustain_spinbox.setDecimals(2)
        self.sustain_spinbox.setValue(0.8)
        self.sustain_spinbox.valueChanged.connect(self.on_adsr_changed)
        sustain_layout.addWidget(self.sustain_spinbox)
        sustain_layout.addWidget(QLabel("(0-1)"))
        sustain_layout.addStretch()
        adsr_layout.addLayout(sustain_layout)
        
        # Release
        release_layout = QHBoxLayout()
        release_layout.addWidget(QLabel("释音 (Release):"))
        self.release_spinbox = QDoubleSpinBox()
        self.release_spinbox.setRange(0.0, 1.0)
        self.release_spinbox.setSingleStep(0.01)
        self.release_spinbox.setDecimals(3)
        self.release_spinbox.setValue(0.1)
        self.release_spinbox.valueChanged.connect(self.on_adsr_changed)
        release_layout.addWidget(self.release_spinbox)
        release_layout.addWidget(QLabel("秒"))
        release_layout.addStretch()
        adsr_layout.addLayout(release_layout)
        
        # 移除应用按钮，属性改变立即生效
        # 保留重置按钮
        button_layout = QHBoxLayout()
        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self.reset_changes)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        
        properties_layout.addLayout(button_layout)
        
        # ========== 单个音符效果编辑区域 ==========
        self.note_effects_group = QGroupBox("音符效果")
        note_effects_layout = QVBoxLayout()
        self.note_effects_group.setLayout(note_effects_layout)
        self.note_effects_group.setVisible(False)
        layout.addWidget(self.note_effects_group)
        
        # 音符颤音（音高调制）
        note_vibrato_group = QGroupBox("颤音 (Vibrato)")
        note_vibrato_layout = QVBoxLayout()
        note_vibrato_group.setLayout(note_vibrato_layout)
        
        # 启用复选框
        self.note_vibrato_enabled_checkbox = QCheckBox("启用颤音")
        self.note_vibrato_enabled_checkbox.toggled.connect(self.on_note_vibrato_enabled_changed)
        note_vibrato_layout.addWidget(self.note_vibrato_enabled_checkbox)
        
        # 速度
        note_vibrato_rate_layout = QHBoxLayout()
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
        effects_layout = QVBoxLayout()
        self.effects_group.setLayout(effects_layout)
        layout.addWidget(self.effects_group)
        
        # 滤波器
        filter_group = QGroupBox("滤波器")
        filter_layout = QVBoxLayout()
        filter_group.setLayout(filter_layout)
        
        # 启用复选框
        self.filter_enabled_checkbox = QCheckBox("启用滤波器")
        self.filter_enabled_checkbox.toggled.connect(self.on_filter_enabled_changed)
        filter_layout.addWidget(self.filter_enabled_checkbox)
        
        # 滤波器类型
        filter_type_layout = QHBoxLayout()
        filter_type_layout.addWidget(QLabel("类型:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["低通", "高通", "带通"])
        self.filter_type_combo.currentIndexChanged.connect(self.on_filter_type_changed)
        filter_type_layout.addWidget(self.filter_type_combo)
        filter_type_layout.addStretch()
        filter_layout.addLayout(filter_type_layout)
        
        # 截止频率
        cutoff_layout = QHBoxLayout()
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
        delay_layout = QVBoxLayout()
        delay_group.setLayout(delay_layout)
        
        # 启用复选框
        self.delay_enabled_checkbox = QCheckBox("启用延迟")
        self.delay_enabled_checkbox.toggled.connect(self.on_delay_enabled_changed)
        delay_layout.addWidget(self.delay_enabled_checkbox)
        
        # 延迟时间
        delay_time_layout = QHBoxLayout()
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
        tremolo_layout = QVBoxLayout()
        tremolo_group.setLayout(tremolo_layout)
        
        # 启用复选框
        self.tremolo_enabled_checkbox = QCheckBox("启用颤音")
        self.tremolo_enabled_checkbox.toggled.connect(self.on_tremolo_enabled_changed)
        tremolo_layout.addWidget(self.tremolo_enabled_checkbox)
        
        # 速度
        tremolo_rate_layout = QHBoxLayout()
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
        
        layout.addStretch()
    
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
            
            # 根据音轨类型设置类型选择框
            # 在设置索引前先阻塞信号，避免触发on_track_type_changed
            self.track_type_combo.blockSignals(True)
            if track.track_type == TrackType.DRUM_TRACK:
                self.track_type_combo.setCurrentIndex(2)  # 打击乐
            else:
                # 音符音轨，根据名称判断（可选）
                if track.name == "主旋律":
                    self.track_type_combo.setCurrentIndex(0)
                elif track.name == "低音":
                    self.track_type_combo.setCurrentIndex(1)
                else:
                    self.track_type_combo.setCurrentIndex(0)  # 默认主旋律
            self.track_type_combo.blockSignals(False)
    
    def update_ui(self):
        """更新UI显示"""
        if self.current_note is None:
            return
        
        note = self.current_note
        track = self.current_track
        
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
        duration_beats = note.duration * self.bpm / 60.0
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
        duration_seconds = duration_beats * 60.0 / self.bpm
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
            # 根据设置决定是否对齐
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            
            new_start_time = value
            if settings_manager.is_snap_to_beat_enabled():
                # 对齐到最近的1/4拍
                beats_per_second = self.bpm / 60.0
                start_beats = new_start_time * beats_per_second
                start_beats = round(start_beats * 4) / 4
                new_start_time = start_beats / beats_per_second
                # 更新显示
                self.start_time_spinbox.blockSignals(True)
                self.start_time_spinbox.setValue(new_start_time)
                self.start_time_spinbox.blockSignals(False)
            
            # 计算新的时长（保持结束时间不变）
            old_start_time = self.current_note.start_time
            old_end_time = old_start_time + self.current_note.duration
            new_duration = old_end_time - new_start_time
            
            # 确保时长大于0
            if new_duration > 0:
                self.current_note.start_time = new_start_time
                self.current_note.duration = new_duration
                
                # 更新UI显示
                duration_beats = new_duration * self.bpm / 60.0
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
            # 根据设置决定是否对齐
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            
            new_end_time = value
            if settings_manager.is_snap_to_beat_enabled():
                # 对齐到最近的1/4拍
                beats_per_second = self.bpm / 60.0
                end_beats = new_end_time * beats_per_second
                end_beats = round(end_beats * 4) / 4
                new_end_time = end_beats / beats_per_second
                # 更新显示
                self.end_time_spinbox.blockSignals(True)
                self.end_time_spinbox.setValue(new_end_time)
                self.end_time_spinbox.blockSignals(False)
            
            # 计算新的时长
            start_time = self.current_note.start_time
            new_duration = new_end_time - start_time
            
            # 确保时长大于0且结束时间大于开始时间
            if new_duration > 0 and new_end_time > start_time:
                self.current_note.duration = new_duration
                
                # 更新UI显示
                duration_beats = new_duration * self.bpm / 60.0
                self.duration_spinbox.blockSignals(True)
                self.duration_spinbox.setValue(duration_beats)
                self.duration_spinbox.blockSignals(False)
                self.update_duration_seconds()
                
            self.property_changed.emit(self.current_note, self.current_track)
    
    def on_duration_changed(self, value: float):
        """时长改变（value是节拍数）"""
        # 将节拍数转换为秒数
        duration_seconds = value * 60.0 / self.bpm
        self.update_duration_seconds()
        if self.current_note and self.current_track:
            # 根据设置决定是否对齐
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            
            if settings_manager.is_snap_to_beat_enabled():
                # 对齐时长到最近的1/4拍
                duration_beats = duration_seconds * self.bpm / 60.0
                duration_beats = round(duration_beats * 4) / 4
                duration_seconds = duration_beats * 60.0 / self.bpm
                # 更新显示
                self.duration_spinbox.blockSignals(True)
                self.duration_spinbox.setValue(duration_beats)
                self.duration_spinbox.blockSignals(False)
                self.update_duration_seconds()
            
            old_duration = self.current_note.duration
            new_duration = duration_seconds
            duration_delta = new_duration - old_duration
            
            # 更新当前音符的时长
            self.current_note.duration = new_duration
            
            # 更新结束时间显示
            new_end_time = self.current_note.start_time + new_duration
            self.end_time_spinbox.blockSignals(True)
            self.end_time_spinbox.setValue(new_end_time)
            self.end_time_spinbox.blockSignals(False)
            
            # 如果时长改变，需要调整后续音符的位置
            if abs(duration_delta) > 0.001:  # 如果时长有变化
                adjusted_notes = self.adjust_following_notes(duration_delta)
                # 如果有后续音符被调整，需要立即刷新UI
                if adjusted_notes:
                    # 发出信号通知UI刷新（使用QTimer确保在下一个事件循环中刷新）
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.property_changed.emit(self.current_note, self.current_track))
                    return
            
            self.property_changed.emit(self.current_note, self.current_track)
    
    def adjust_following_notes(self, duration_delta: float):
        """调整后续音符的位置，使它们保持连续
        
        Returns:
            被调整的音符列表
        """
        if not self.current_note or not self.current_track:
            return []
        
        # 计算当前音符的新结束时间
        current_note_end = self.current_note.start_time + self.current_note.duration
        
        # 获取同一轨道上所有音符，按开始时间排序
        # 注意：需要先按旧的start_time排序，因为我们要基于旧位置判断
        all_notes = sorted(self.current_track.notes, key=lambda n: n.start_time)
        
        # 找到当前音符在列表中的位置
        current_index = -1
        for i, note in enumerate(all_notes):
            if note == self.current_note:
                current_index = i
                break
        
        if current_index == -1:
            return []
        
        # 获取当前音符之后的所有音符
        following_notes = all_notes[current_index + 1:]
        
        if not following_notes:
            return []
        
        # 计算旧结束时间（用于判断哪些音符需要调整）
        old_end_time = self.current_note.start_time + (self.current_note.duration - duration_delta)
        
        # 记录哪些音符被调整了
        adjusted_notes = []
        
        # 调整后续音符的位置
        # 如果第一个后续音符紧接在当前音符之后（没有间隙或间隙很小），则调整它
        first_following = following_notes[0]
        if first_following.start_time <= old_end_time + 0.01:  # 允许很小的误差
            # 这个音符紧接在当前音符之后，调整它的位置
            first_following.start_time = current_note_end
            adjusted_notes.append(first_following)
            current_note_end = first_following.start_time + first_following.duration
            
            # 继续调整后续的音符，使它们保持连续
            for i in range(1, len(following_notes)):
                note = following_notes[i]
                # 如果这个音符紧接在前一个音符之后，调整它
                prev_note = following_notes[i-1]
                # 使用更新后的位置计算前一个音符的结束时间
                prev_end = prev_note.start_time + prev_note.duration
                if note.start_time <= prev_end + 0.01:  # 紧接在前一个之后
                    note.start_time = prev_end
                    adjusted_notes.append(note)
                    current_note_end = note.start_time + note.duration
                else:
                    # 如果有间隙，停止调整
                    break
        
        # 返回被调整的音符列表
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
            duration_beats = self.current_note.duration * self.bpm / 60.0
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
            self.track_property_changed.emit(track)
    
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
            self.track_property_changed.emit(track)
    
    def on_filter_params_changed(self):
        """滤波器参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.filter_params:
            track.filter_params.cutoff_frequency = self.cutoff_spinbox.value()
            track.filter_params.resonance = self.resonance_spinbox.value()
            self.track_property_changed.emit(track)
    
    def on_delay_enabled_changed(self, enabled: bool):
        """延迟启用状态改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.delay_params:
            track.delay_params.enabled = enabled
            self.track_property_changed.emit(track)
    
    def on_delay_params_changed(self):
        """延迟参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.delay_params:
            track.delay_params.delay_time = self.delay_time_spinbox.value()
            track.delay_params.feedback = self.feedback_spinbox.value()
            track.delay_params.mix = self.mix_spinbox.value()
            self.track_property_changed.emit(track)
    
    def on_tremolo_enabled_changed(self, enabled: bool):
        """颤音启用状态改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.tremolo_params:
            track.tremolo_params.enabled = enabled
            self.track_property_changed.emit(track)
    
    def on_batch_waveform_changed(self, index: int):
        """批量波形改变（立即生效）"""
        if not self.current_notes:
            return
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_batch_velocity_changed(self):
        """批量力度改变（立即生效）"""
        if not self.current_notes:
            return
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_batch_duty_changed(self):
        """批量占空比改变（立即生效）"""
        if not self.current_notes:
            return
        # 发送批量修改信号（立即生效）
        self.batch_property_changed.emit(self.current_notes)
    
    def on_track_type_changed(self, index: int):
        """音轨类型改变"""
        if not self.current_track_for_edit:
            return
        
        # 音轨类型改变时，更新音轨的track_type
        from core.models import TrackType
        type_map = {
            0: TrackType.NOTE_TRACK,  # 主旋律
            1: TrackType.NOTE_TRACK,  # 低音
            2: TrackType.DRUM_TRACK   # 打击乐
        }
        new_track_type = type_map.get(index, TrackType.NOTE_TRACK)
        
        # 更新音轨类型
        self.current_track_for_edit.track_type = new_track_type
        
        # 发送音轨属性改变信号（这会触发UI刷新）
        self.track_property_changed.emit(self.current_track_for_edit)
    
    def on_track_name_changed(self):
        """音轨名称改变"""
        if not self.current_track_for_edit:
            return
        
        new_name = self.track_name_edit.text().strip()
        if new_name:
            self.current_track_for_edit.name = new_name
            # 发送音轨属性改变信号
            self.track_property_changed.emit(self.current_track_for_edit)
    
    # 音轨不再有默认波形，波形是音符的属性
    # on_track_waveform_changed 方法已移除
    
    def on_tremolo_params_changed(self):
        """颤音参数改变"""
        track = self.current_track_for_edit if self.current_track_for_edit else self.current_track
        if track and track.tremolo_params:
            track.tremolo_params.rate = self.tremolo_rate_spinbox.value()
            track.tremolo_params.depth = self.tremolo_depth_spinbox.value()
            self.track_property_changed.emit(track)
    
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

