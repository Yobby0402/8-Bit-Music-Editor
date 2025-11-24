"""
统一编辑器

整合主旋律、低音和打击乐的所有功能到一个界面。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QButtonGroup, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer

from ui.piano_keyboard_widget import PianoKeyboardWidget
from ui.theme import theme_manager
from core.models import WaveformType
from core.track_events import DrumType
from core.audio_engine import AudioEngine


class UnifiedEditorWidget(QWidget):
    """统一编辑器 - 整合所有音轨类型"""
    
    # 信号
    add_melody_note = pyqtSignal(int, float, WaveformType, object, str)  # pitch, duration_beats, waveform, target_track, insert_mode
    add_bass_event = pyqtSignal(int, float, WaveformType, object, str)  # pitch, duration_beats, waveform, target_track, insert_mode
    add_drum_event = pyqtSignal(DrumType, float, object, str)  # drum_type, duration_beats, target_track, insert_mode
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化统一编辑器"""
        super().__init__(parent)
        self.bpm = bpm
        
        # 默认值
        self.selected_waveform = WaveformType.SQUARE
        self.selected_duration = 1.0
        self.current_track_type = "melody"  # "melody" 或 "bass"
        self.insert_mode = "sequential"  # "sequential" 或 "playhead" - 插入模式
        self.selected_track = None  # 当前选中的目标音轨
        
        # 音频引擎（用于打击乐预览）
        self.audio_engine = AudioEngine()
        self.preview_sound = None
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.play_drum_preview)
        self.preview_enabled = True  # 是否启用预览（播放时禁用）
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)
        
        # ========== 左侧：钢琴键盘（60%宽度） ==========
        
        piano_container = QWidget()
        piano_container_layout = QVBoxLayout()
        piano_container.setLayout(piano_container_layout)
        piano_container_layout.setContentsMargins(0, 0, 0, 0)
        piano_container_layout.setSpacing(0)
        
        # 钢琴键盘
        self.piano_keyboard = PianoKeyboardWidget()
        self.piano_keyboard.note_clicked.connect(self.on_piano_note_clicked)
        self.piano_keyboard.pitch_changed.connect(self.on_pitch_changed)
        # 初始化预览参数（使用update_preview_params来设置正确的波形）
        self.update_preview_params()
        self.piano_keyboard.setMinimumHeight(220)
        
        # 创建休止符按钮
        self.rest_button = QPushButton("休止符")
        self.rest_button.setMinimumHeight(32)
        self.rest_button.setMaximumHeight(32)
        self.rest_button.setMinimumWidth(80)
        self.rest_button.clicked.connect(self.on_rest_clicked)
        self.piano_keyboard.set_rest_button(self.rest_button)
        
        piano_container_layout.addWidget(self.piano_keyboard, 1)
        
        # 下方：打击乐按钮
        drum_area = QWidget()
        drum_area.setMaximumHeight(70)
        drum_layout = QHBoxLayout()
        drum_layout.setContentsMargins(5, 5, 5, 5)
        drum_layout.setSpacing(6)
        drum_area.setLayout(drum_layout)
        
        # 左侧空白，用于居中
        drum_layout.addStretch()
        
        self.drum_buttons = []
        self.drum_group = QButtonGroup()
        
        drum_types = [
            ("底鼓", DrumType.KICK),
            ("军鼓", DrumType.SNARE),
            ("踩镲", DrumType.HIHAT),
            ("吊镲", DrumType.CRASH),
        ]
        
        for name, drum_type in drum_types:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(36)
            btn.setMaximumHeight(36)
            btn.setMinimumWidth(70)
            btn._drum_type = drum_type
            # 添加事件过滤器以实现悬停预览
            btn.installEventFilter(self)
            btn.clicked.connect(lambda checked, dt=drum_type: self.on_drum_clicked(dt))
            self.drum_buttons.append(btn)
            self.drum_group.addButton(btn)
            drum_layout.addWidget(btn)
        
        # 右侧空白，用于居中
        drum_layout.addStretch()
        piano_container_layout.addWidget(drum_area)
        
        main_layout.addWidget(piano_container, 7)  # 70%宽度
        
        # ========== 右侧：所有按钮（30%宽度，使用GridLayout） ==========
        right_area = QWidget()
        # 使用20列网格，方便均匀分布按钮
        right_layout = QGridLayout()
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_area.setLayout(right_layout)
        
        # 第一排：波形选择（4个按钮，每个占5列）
        waveform_row = 0
        max_cols = 20  # 总共20列
        
        self.waveform_buttons = []
        self.waveform_group = QButtonGroup()
        
        # 使用主题颜色，但保持波形特有的颜色区分
        waveform_colors = {
            WaveformType.SQUARE: "#FF6B6B",      # 红色
            WaveformType.TRIANGLE: "#4ECDC4",    # 青色
            WaveformType.SAWTOOTH: "#FFE66D",    # 黄色
            WaveformType.SINE: "#95E1D3",        # 浅青色
        }
        
        waveform_options = [
            ("方波", WaveformType.SQUARE),
            ("三角波", WaveformType.TRIANGLE),
            ("锯齿波", WaveformType.SAWTOOTH),
            ("正弦波", WaveformType.SINE)
        ]
        
        cols_per_waveform = max_cols // len(waveform_options)  # 每个按钮占5列
        
        for idx, (name, waveform_type) in enumerate(waveform_options):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 水平和垂直都扩展
            color = waveform_colors.get(waveform_type, "#CCCCCC")
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 11px;
                    background-color: {color};
                    color: white;
                    font-weight: 500;
                    border: 2px solid {color};
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background-color: {self._lighten_color(color)};
                    border-color: {self._lighten_color(color)};
                }}
                QPushButton:checked {{
                    border-color: #FFFFFF;
                    border-width: 3px;
                }}
                QPushButton:pressed {{
                    background-color: {self._darken_color(color)};
                }}
            """)
            if name == "方波":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, wt=waveform_type: self.on_waveform_selected(wt))
            self.waveform_buttons.append(btn)
            self.waveform_group.addButton(btn)
            col_start = idx * cols_per_waveform
            right_layout.addWidget(btn, waveform_row, col_start, 1, cols_per_waveform)
        
        # 第二排：插入模式选择（2个按钮，每个占10列）
        insert_mode_row = 1
        self.insert_mode_buttons = []
        self.insert_mode_group = QButtonGroup()
        
        insert_mode_options = [
            ("顺序插入", "sequential"),
            ("播放线插入", "playhead")
        ]
        
        theme = theme_manager.current_theme
        toggle_style = theme.get_style("button_toggle")
        
        cols_per_insert_mode = max_cols // len(insert_mode_options)  # 每个按钮占10列
        
        for idx, (name, mode) in enumerate(insert_mode_options):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 水平和垂直都扩展
            btn.setStyleSheet(toggle_style)
            if name == "顺序插入":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, m=mode: self.on_insert_mode_selected(m))
            self.insert_mode_buttons.append(btn)
            self.insert_mode_group.addButton(btn)
            col_start = idx * cols_per_insert_mode
            right_layout.addWidget(btn, insert_mode_row, col_start, 1, cols_per_insert_mode)
        
        # 第三排：节拍长度选择（5个按钮，每个占4列）
        duration_row = 2
        self.duration_buttons = []
        self.duration_group = QButtonGroup()
        
        duration_options = [
            ("1/4拍", 0.25), ("1/2拍", 0.5), ("1拍", 1.0),
            ("2拍", 2.0), ("4拍", 4.0)
        ]
        
        cols_per_duration = max_cols // len(duration_options)  # 每个按钮占4列
        
        for idx, (name, beats) in enumerate(duration_options):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 水平和垂直都扩展
            btn.setStyleSheet(toggle_style)
            if name == "1拍":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, b=beats: self.on_duration_selected(b))
            self.duration_buttons.append(btn)
            self.duration_group.addButton(btn)
            col_start = idx * cols_per_duration
            right_layout.addWidget(btn, duration_row, col_start, 1, cols_per_duration)
        main_layout.addWidget(right_area, 3)  # 30%宽度
        
        # 应用主题到打击乐按钮和休止符按钮
        self.apply_theme_to_buttons()
    
    def apply_theme_to_buttons(self):
        """应用主题到按钮"""
        theme = theme_manager.current_theme
        button_small_style = theme.get_style("button_small")
        
        # 休止符按钮
        if hasattr(self, 'rest_button'):
            self.rest_button.setStyleSheet(button_small_style)
        
        # 打击乐按钮 - 使用橙色主题但保持可识别
        drum_style = f"""
            QPushButton {{
                background-color: {theme.get_color('warning')};
                color: white;
                border: 2px solid {theme.darken_color(theme.get_color('warning'))};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 500;
                min-height: 36px;
                max-height: 36px;
            }}
            QPushButton:hover {{
                background-color: {theme.lighten_color(theme.get_color('warning'))};
                border-color: {theme.get_color('warning')};
            }}
            QPushButton:checked {{
                border-color: #FFFFFF;
                border-width: 3px;
            }}
            QPushButton:pressed {{
                background-color: {theme.darken_color(theme.get_color('warning'))};
            }}
        """
        for btn in self.drum_buttons:
            btn.setStyleSheet(drum_style)
    
    def _lighten_color(self, color_hex: str) -> str:
        """使颜色变亮"""
        return theme_manager.current_theme.lighten_color(color_hex)
    
    def _darken_color(self, color_hex: str) -> str:
        """使颜色变暗"""
        return theme_manager.current_theme.darken_color(color_hex)
    
    def on_waveform_selected(self, waveform: WaveformType):
        """波形选择"""
        self.selected_waveform = waveform
        self.update_preview_params()
    
    def on_track_type_selected(self, track_type: str):
        """音轨类型选择"""
        self.current_track_type = track_type
        # 当切换到低音时，使用三角波作为默认预览波形
        if track_type == "bass":
            # 如果当前波形不是三角波，可以选择自动切换，或者保持用户选择
            # 这里我们保持用户选择的波形，但更新预览参数
            self.update_preview_params()
        else:
            self.update_preview_params()
    
    def on_insert_mode_selected(self, mode: str):
        """插入模式选择"""
        self.insert_mode = mode
    
    def set_selected_track(self, track):
        """设置选中的目标音轨"""
        self.selected_track = track
    
    def update_preview_params(self):
        """更新预览参数（根据当前音轨类型）"""
        # 如果是低音，使用三角波作为预览（即使用户选择了其他波形，预览也用三角波）
        # 如果是主旋律，使用用户选择的波形
        preview_waveform = WaveformType.TRIANGLE if self.current_track_type == "bass" else self.selected_waveform
        self.piano_keyboard.set_preview_params(preview_waveform, self.selected_duration, self.bpm)
    
    def on_duration_selected(self, beats: float):
        """拍数选择"""
        self.selected_duration = beats
        self.update_preview_params()
    
    def on_pitch_changed(self, pitch: int):
        """音高改变（不再显示，保留方法以防其他地方调用）"""
        pass
    
    def on_piano_note_clicked(self, pitch: int):
        """钢琴键盘音符点击"""
        if self.current_track_type == "melody":
            self.add_melody_note.emit(pitch, self.selected_duration, self.selected_waveform, self.selected_track, self.insert_mode)
        else:  # bass
            self.add_bass_event.emit(pitch, self.selected_duration, self.selected_waveform, self.selected_track, self.insert_mode)
    
    def on_rest_clicked(self):
        """休止符点击"""
        if self.current_track_type == "melody":
            self.add_melody_note.emit(0, self.selected_duration, self.selected_waveform, self.selected_track, self.insert_mode)
        else:  # bass
            self.add_bass_event.emit(0, self.selected_duration, self.selected_waveform, self.selected_track, self.insert_mode)
    
    def on_drum_clicked(self, drum_type: DrumType):
        """打击乐点击"""
        self.add_drum_event.emit(drum_type, self.selected_duration, self.selected_track, self.insert_mode)
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于处理打击乐按钮悬停"""
        if event.type() == QEvent.Enter:
            if hasattr(obj, '_drum_type'):
                self.on_drum_hover(obj._drum_type)
        return super().eventFilter(obj, event)
    
    def on_drum_hover(self, drum_type: DrumType):
        """打击乐悬停（播放预览）"""
        # 如果预览被禁用，不播放
        if not self.preview_enabled:
            return
        
        # 延迟播放，避免快速移动鼠标时播放太多次
        self.hovered_drum_type = drum_type
        self.preview_timer.stop()
        self.preview_timer.start(100)  # 100ms延迟
    
    def play_drum_preview(self):
        """播放打击乐预览"""
        # 如果预览被禁用，不播放
        if not self.preview_enabled:
            return
        
        if not hasattr(self, 'hovered_drum_type'):
            return
        
        # 停止之前的预览
        if self.preview_sound:
            self.audio_engine.stop_all()
        
        # 将拍数转换为秒
        duration = self.selected_duration * 60.0 / self.bpm
        
        # 生成预览音频
        audio = self.audio_engine.generate_drum_audio(
            drum_type=self.hovered_drum_type,
            duration=duration,
            velocity=127
        )
        
        self.preview_sound = self.audio_engine.play_audio(audio, loop=False)
    
    def set_preview_enabled(self, enabled: bool):
        """设置预览是否启用（播放时禁用所有预览）"""
        self.preview_enabled = enabled
        # 同时设置钢琴键盘的预览状态
        if hasattr(self, 'piano_keyboard'):
            self.piano_keyboard.set_preview_enabled(enabled)
        
        # 禁用时停止当前预览
        if not enabled:
            if self.preview_sound:
                self.audio_engine.stop_all()
                self.preview_sound = None
            # 停止预览定时器
            self.preview_timer.stop()
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        self.update_preview_params()

