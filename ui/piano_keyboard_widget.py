"""
钢琴键盘音高选择器

使用八度+音符按钮的方式选择音高。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QButtonGroup, QSizePolicy, QGridLayout, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject, QEvent, QRect
from PyQt5.QtGui import QColor, QResizeEvent

from ui.multiline_button import MultilineButton
from core.waveform_generator import WaveformGenerator
from core.audio_engine import AudioEngine
from core.models import Note, WaveformType


class PianoKeysContainer(QWidget):
    """钢琴键盘容器，黑白键分别布局，各自居中且宽度一致"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.white_keys = []
        self.black_keys = []
        # 使用垂直布局，黑键在上，白键在下，各自居中
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)  # 增加间距，确保黑白键不重叠
        main_layout.setContentsMargins(0, 5, 0, 5)  # 上下留出边距，避免被裁剪
        self.setLayout(main_layout)
        
        # 黑键容器（第一行，居中）
        self.black_keys_container = QWidget()
        self.black_keys_container.setMinimumHeight(50)  # 确保黑键容器有足够高度
        self.black_keys_container.setMaximumHeight(50)  # 限制最大高度，避免被裁剪
        self.black_keys_layout = QHBoxLayout()
        self.black_keys_layout.setContentsMargins(0, 0, 0, 0)
        self.black_keys_layout.addStretch()  # 左侧弹性空间
        self.black_keys_container.setLayout(self.black_keys_layout)
        main_layout.addWidget(self.black_keys_container)
        
        # 白键容器（第二行，居中）
        self.white_keys_container = QWidget()
        self.white_keys_container.setMinimumHeight(100)  # 确保白键容器有足够高度（2:1比例）
        self.white_keys_container.setMaximumHeight(100)  # 限制最大高度，避免被裁剪
        self.white_keys_layout = QHBoxLayout()
        self.white_keys_layout.setContentsMargins(0, 0, 0, 0)
        self.white_keys_layout.addStretch()  # 左侧弹性空间
        self.white_keys_container.setLayout(self.white_keys_layout)
        main_layout.addWidget(self.white_keys_container)
    
    def add_white_key(self, button: QPushButton, col: int):
        """添加白键到白键容器（居中布局）"""
        self.white_keys.append(button)
        button.setParent(self.white_keys_container)
        self.white_keys_layout.addWidget(button)
        # 在最后添加弹性空间（如果这是最后一个白键）
        if len(self.white_keys) == 7:  # 总共7个白键
            self.white_keys_layout.addStretch()
    
    def add_black_key(self, button: QPushButton, col: int):
        """添加黑键到黑键容器（居中布局）"""
        self.black_keys.append(button)
        button.setParent(self.black_keys_container)
        self.black_keys_layout.addWidget(button)
        # 在最后添加弹性空间（如果这是最后一个黑键）
        if len(self.black_keys) == 5:  # 总共5个黑键
            self.black_keys_layout.addStretch()


class PianoKeyboardWidget(QWidget):
    """钢琴键盘音高选择器"""
    
    pitch_changed = pyqtSignal(int)
    note_clicked = pyqtSignal(int)  # 点击音符时发送音高
    
    def __init__(self, parent=None):
        """初始化钢琴键盘"""
        super().__init__(parent)
        
        self.current_pitch = 60  # 默认C4
        self.current_octave = 4  # 当前八度（C4所在的八度）
        self.audio_engine = AudioEngine()
        self.waveform_gen = WaveformGenerator()
        self.preview_sound = None
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.play_preview)
        self.preview_enabled = True  # 是否启用预览（播放时禁用）
        
        # 预览参数（可以从外部设置）
        self.preview_waveform = WaveformType.SQUARE  # 默认方波
        self.preview_duration = 0.2  # 默认0.2秒（用于预览）
        self.preview_duration_beats = 1.0  # 默认1拍（实际时长）
        self.bpm = 120.0  # 默认BPM
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI - 只显示八度选择和钢琴键盘（所有键按顺序排列）"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 设置统一背景色
        from ui.theme import theme_manager
        theme = theme_manager.current_theme
        bg_color = theme.get_color('background')
        self.setStyleSheet(f"background-color: {bg_color};")
        
        # 八度选择（上方，居中）
        octave_wrapper = QWidget()
        octave_wrapper_layout = QHBoxLayout()
        octave_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        
        octave_layout = QHBoxLayout()
        self.octave_buttons = []
        self.octave_group = QButtonGroup()
        
        # 获取主题（在创建按钮之前）
        from ui.theme import theme_manager
        theme = theme_manager.current_theme
        
        # 显示0-8八度（更宽范围）
        for octave in range(0, 9):
            btn = QPushButton(f"C{octave}")
            btn.setCheckable(True)
            btn.setMinimumWidth(40)
            btn.setMaximumWidth(50)
            btn.setMinimumHeight(30)
            # 应用主题样式，使其与其他按键统一
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('text_primary')};
                    border: 2px solid {theme.get_color('border')};
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('primary_light')};
                    border-color: {theme.get_color('accent')};
                }}
                QPushButton:checked {{
                    background-color: {theme.get_color('accent')};
                    color: {theme.get_color('text_primary')};
                    border-color: {theme.get_color('accent_dark')};
                    border-width: 3px;
                }}
                QPushButton:pressed {{
                    background-color: {theme.get_color('accent_dark')};
                }}
            """)
            if octave == 4:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, o=octave: self.on_octave_changed(o))
            self.octave_buttons.append(btn)
            self.octave_group.addButton(btn, octave)
            octave_layout.addWidget(btn)
        
        # 八度按钮居中
        octave_wrapper_layout.addStretch()
        octave_wrapper_layout.addLayout(octave_layout)
        octave_wrapper_layout.addStretch()
        octave_wrapper.setLayout(octave_wrapper_layout)
        layout.addWidget(octave_wrapper)
        
        # 八度滑块区域（在八度按钮下方）
        octave_slider_wrapper = QWidget()
        octave_slider_layout = QHBoxLayout()
        octave_slider_layout.setContentsMargins(20, 5, 20, 5)
        
        # 创建滑块
        self.octave_slider = QSlider(Qt.Horizontal)
        self.octave_slider.setMinimum(0)
        self.octave_slider.setMaximum(8)
        self.octave_slider.setValue(4)  # 默认C4
        self.octave_slider.setTickPosition(QSlider.TicksBelow)
        self.octave_slider.setTickInterval(1)
        self.octave_slider.setSingleStep(1)
        self.octave_slider.setPageStep(1)
        
        # 应用主题样式到滑块
        self.octave_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                border: 1px solid {theme.get_color('border')};
                height: 6px;
                background: {theme.get_color('primary')};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {theme.get_color('accent')};
                border: 2px solid {theme.get_color('accent_dark')};
                width: 18px;
                height: 18px;
                border-radius: 9px;
                margin: -6px 0;
            }}
            QSlider::handle:horizontal:hover {{
                background: {theme.get_color('accent_light')};
            }}
            QSlider::handle:horizontal:pressed {{
                background: {theme.get_color('accent_dark')};
            }}
            QSlider::sub-page:horizontal {{
                background: {theme.get_color('accent')};
                border-radius: 3px;
            }}
        """)
        
        # 连接滑块值改变信号
        self.octave_slider.valueChanged.connect(self.on_slider_value_changed)
        
        octave_slider_layout.addWidget(self.octave_slider)
        octave_slider_wrapper.setLayout(octave_slider_layout)
        octave_slider_wrapper.setMaximumHeight(40)
        layout.addWidget(octave_slider_wrapper)
        
        # 钢琴键盘区域（黑白键分别布局，各自居中）
        self.keys_container = PianoKeysContainer(self)
        # 白键和黑键高度比为2:1，确保白键显示完整
        # 白键100px + 黑键50px + 间距10px = 160px，但为了确保不被裁剪，设置为170px
        self.keys_container.setMinimumHeight(170)  # 确保黑白键完全显示，不被裁剪
        self.keys_container.setMaximumHeight(170)  # 限制最大高度
        # 不设置背景色，使用父容器的背景色（与其他部分一致）
        self.keys_container.setStyleSheet("")  # 透明背景，继承父容器
        # 确保内容不会被裁剪
        self.keys_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # 创建白键和黑键
        self.white_buttons = []
        self.black_buttons = []
        self.white_group = QButtonGroup()
        self.black_group = QButtonGroup()
        
        white_notes = ["C", "D", "E", "F", "G", "A", "B"]
        
        # 创建白键（居中布局，所有白键宽度一致）
        # 白键高度设为100px，与黑键50px形成2:1的比例
        for col, note_name in enumerate(white_notes):
            btn = MultilineButton(note_name)
            btn.setCheckable(True)
            btn.setMinimumHeight(100)  # 白键高度100px（与黑键50px形成2:1比例）
            btn.setMaximumHeight(100)  # 限制最大高度
            btn.setFixedWidth(60)  # 固定宽度，确保所有白键宽度完全一致
            # 使用Fixed策略
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # 应用主题样式
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: white;
                    border: 1px solid {theme.get_color('border')};
                    font-size: 11px;
                    padding: 2px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('hover')};
                }}
                QPushButton:checked {{
                    background-color: {theme.get_color('accent_light')};
                    border: 2px solid {theme.get_color('accent')};
                }}
            """)
            btn._note_name = note_name
            btn._is_sharp = False
            btn.installEventFilter(self)
            btn.clicked.connect(lambda checked, n=note_name: self.on_note_clicked(n, False))
            self.white_buttons.append(btn)
            self.white_group.addButton(btn)
            self.keys_container.add_white_key(btn, col)
        
        # 创建黑键（放在两个白键之间）
        black_positions = [
            (0, "C#"),   # 在C和D之间（第0列）
            (1, "D#"),   # 在D和E之间（第1列）
            (3, "F#"),   # 在F和G之间（第3列）
            (4, "G#"),   # 在G和A之间（第4列）
            (5, "A#"),   # 在A和B之间（第5列）
        ]
        
        for col, note_name in black_positions:
            btn = MultilineButton(note_name)
            btn.setCheckable(True)
            btn.setMinimumHeight(50)  # 黑键高度
            btn.setMaximumHeight(50)  # 限制最大高度
            btn.setFixedWidth(40)  # 固定宽度，确保所有黑键宽度完全一致
            # 使用Fixed策略
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # 应用主题样式（theme已在上面定义）
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('text_primary')};
                    color: white;
                    border: 1px solid {theme.get_color('border_dark')};
                    font-size: 10px;
                    padding: 2px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('accent_dark')};
                }}
                QPushButton:checked {{
                    background-color: {theme.get_color('accent')};
                    border: 2px solid {theme.get_color('accent_light')};
                }}
            """)
            btn._note_name = note_name
            btn._is_sharp = True
            btn.installEventFilter(self)
            btn.clicked.connect(lambda checked, n=note_name: self.on_note_clicked(n, True))
            self.black_buttons.append(btn)
            self.black_group.addButton(btn)
            # 添加黑键到容器（第一行，在两个白键中间）
            self.keys_container.add_black_key(btn, col)
        
        # 居中显示
        container_wrapper = QWidget()
        wrapper_layout = QHBoxLayout()
        wrapper_layout.addStretch()
        wrapper_layout.addWidget(self.keys_container)
        wrapper_layout.addStretch()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        container_wrapper.setLayout(wrapper_layout)
        # 确保wrapper不会裁剪内容，高度与keys_container一致
        container_wrapper.setMinimumHeight(170)
        container_wrapper.setMaximumHeight(170)
        
        layout.addWidget(container_wrapper)
        
        # 休止符按钮区域（在钢琴键盘下方）
        self.rest_button_container = QWidget()
        rest_button_layout = QHBoxLayout()
        rest_button_layout.setContentsMargins(0, 5, 0, 5)
        rest_button_layout.addStretch()
        
        # 休止符按钮（由外部设置）
        self.rest_button = None
        
        rest_button_layout.addStretch()
        self.rest_button_container.setLayout(rest_button_layout)
        self.rest_button_container.setMaximumHeight(50)
        layout.addWidget(self.rest_button_container)
        
        # 确保布局不会裁剪内容
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 更新显示（包括按钮文本）
        self.update_button_texts()
        self.update_pitch_display()
    
    def set_rest_button(self, button):
        """设置休止符按钮（由外部调用）"""
        if self.rest_button:
            # 移除旧的按钮
            self.rest_button_container.layout().removeWidget(self.rest_button)
            self.rest_button.setParent(None)
        
        self.rest_button = button
        if button:
            # 添加到布局中间
            layout = self.rest_button_container.layout()
            # 在addStretch之前插入
            layout.insertWidget(1, button)
    
    def eventFilter(self, obj, event):
        """事件过滤器，用于处理鼠标悬停"""
        if event.type() == QEvent.Enter:
            if hasattr(obj, '_note_name'):
                self.on_note_hover(obj._note_name, obj._is_sharp)
        return super().eventFilter(obj, event)
    
    def on_octave_changed(self, octave: int):
        """八度改变（由按钮触发）"""
        self.current_octave = octave
        # 更新滑块（避免循环触发）
        if self.octave_slider.value() != octave:
            self.octave_slider.blockSignals(True)
            self.octave_slider.setValue(octave)
            self.octave_slider.blockSignals(False)
        # 更新按钮文本显示真实音符名称
        self.update_button_texts()
        self.update_pitch()
    
    def on_slider_value_changed(self, value: int):
        """滑块值改变（由滑块触发）"""
        self.current_octave = value
        # 更新按钮（避免循环触发）
        if 0 <= value < len(self.octave_buttons):
            self.octave_buttons[value].blockSignals(True)
            self.octave_buttons[value].setChecked(True)
            self.octave_buttons[value].blockSignals(False)
        # 更新按钮文本显示真实音符名称
        self.update_button_texts()
        self.update_pitch()
    
    def on_note_hover(self, note_name: str, is_sharp: bool):
        """音符悬停（播放预览）"""
        # 如果预览被禁用，不播放
        if not self.preview_enabled:
            return
        
        # 计算MIDI音高
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_index = note_names.index(note_name)
        pitch = (self.current_octave + 1) * 12 + note_index
        
        # 临时设置音高并播放预览
        temp_pitch = self.current_pitch
        self.current_pitch = pitch
        self.play_preview()
        self.current_pitch = temp_pitch
    
    def on_note_clicked(self, note_name: str, is_sharp: bool):
        """音符点击（直接添加）"""
        # 计算MIDI音高
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_index = note_names.index(note_name)
        
        # MIDI音高 = (八度 + 1) * 12 + 音符索引
        pitch = (self.current_octave + 1) * 12 + note_index
        
        self.current_pitch = pitch
        self.update_pitch()
        
        # 更新按钮选中状态
        self.update_button_states()
        
        # 发送点击信号（用于直接添加）
        self.note_clicked.emit(pitch)
    
    def update_button_texts(self):
        """更新按钮文本显示真实音符名称（根据当前八度）和快捷键"""
        # 获取快捷键管理器（如果存在）
        shortcut_manager = None
        if hasattr(self.parent(), 'shortcut_manager'):
            shortcut_manager = self.parent().shortcut_manager
        elif hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), 'shortcut_manager'):
            shortcut_manager = self.parent().parent().shortcut_manager
        
        # 钢琴键盘快捷键映射
        piano_shortcuts = {
            "C": "piano_c",
            "D": "piano_d",
            "E": "piano_e",
            "F": "piano_f",
            "G": "piano_g",
            "A": "piano_a",
            "B": "piano_b",
            "C#": "piano_c_sharp",
            "D#": "piano_d_sharp",
            "F#": "piano_f_sharp",
            "G#": "piano_g_sharp",
            "A#": "piano_a_sharp",
        }
        
        # 更新所有按钮文本
        all_buttons = self.white_buttons + self.black_buttons
        for btn in all_buttons:
            note_name = btn._note_name
            full_name = f"{note_name}{self.current_octave}"
            
            # 如果有快捷键管理器，显示快捷键
            if shortcut_manager:
                shortcut_key = piano_shortcuts.get(note_name)
                if shortcut_key:
                    shortcut = shortcut_manager.get_shortcut(shortcut_key)
                    if shortcut:
                        btn.setText(f"{full_name}\n{shortcut}")
                    else:
                        btn.setText(full_name)
                else:
                    btn.setText(full_name)
            else:
                btn.setText(full_name)
    
    def update_button_states(self):
        """更新按钮选中状态"""
        # 清除所有按钮选中
        all_buttons = self.white_buttons + self.black_buttons
        for btn in all_buttons:
            btn.setChecked(False)
        
        # 选中当前音符对应的按钮
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        current_note_name = note_names[self.current_pitch % 12]
        
        # 查找对应的按钮（比较基础音符名，不比较八度）
        for btn in all_buttons:
            btn_base_name = btn._note_name
            if btn_base_name == current_note_name:
                btn.setChecked(True)
                break
    
    def update_pitch(self):
        """更新音高"""
        self.update_pitch_display()
        self.pitch_changed.emit(self.current_pitch)
    
    def update_pitch_display(self):
        """更新音高显示（现在由外部显示，这里只发送信号）"""
        # 音高显示已移到编辑器上方，这里只发送信号
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = self.current_pitch // 12 - 1
        note_name = note_names[self.current_pitch % 12]
        # 发送信号通知外部更新显示
        self.pitch_changed.emit(self.current_pitch)
    
    def set_preview_params(self, waveform: WaveformType, duration_beats: float, bpm: float = 120.0):
        """设置预览参数（波形、时长（拍数）、BPM）"""
        self.preview_waveform = waveform
        self.preview_duration_beats = duration_beats
        self.bpm = bpm
        # 将拍数转换为秒（用于预览，但使用实际时长）
        self.preview_duration = duration_beats * 60.0 / bpm
    
    def play_preview(self):
        """播放预览（使用设置的参数）"""
        # 如果预览被禁用（播放时），不播放预览
        if not self.preview_enabled:
            return
        
        # 停止之前的预览
        if self.preview_sound:
            self.audio_engine.stop_all()
        
        # 使用设置的参数生成预览音频
        note = Note(
            pitch=self.current_pitch,
            start_time=0.0,
            duration=self.preview_duration,  # 使用实际时长
            waveform=self.preview_waveform  # 使用选择的波形
        )
        
        audio = self.audio_engine.generate_note_audio(note)
        self.preview_sound = self.audio_engine.play_audio(audio, loop=False)
    
    def set_preview_enabled(self, enabled: bool):
        """设置预览是否启用"""
        self.preview_enabled = enabled
        if not enabled:
            # 禁用时停止当前预览
            if self.preview_sound:
                self.audio_engine.stop_all()
                self.preview_sound = None
    
    def get_pitch(self) -> int:
        """获取当前音高"""
        return self.current_pitch
    
    def set_pitch(self, pitch: int):
        """设置音高"""
        pitch = max(0, min(127, pitch))
        self.current_pitch = pitch
        
        # 更新八度
        octave = pitch // 12 - 1
        if 0 <= octave <= 8:
            self.current_octave = octave
            # 更新八度按钮
            if 0 <= octave < len(self.octave_buttons):
                self.octave_buttons[octave].blockSignals(True)
                self.octave_buttons[octave].setChecked(True)
                self.octave_buttons[octave].blockSignals(False)
            # 更新滑块
            if self.octave_slider.value() != octave:
                self.octave_slider.blockSignals(True)
                self.octave_slider.setValue(octave)
                self.octave_slider.blockSignals(False)
        
        self.update_pitch_display()
        self.update_button_texts()
        self.update_button_states()
