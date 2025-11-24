"""
主旋律编辑器

包含音高滑块、时长选择、波形选择、添加按钮。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.piano_keyboard_widget import PianoKeyboardWidget
from core.models import WaveformType


class MelodyEditorWidget(QWidget):
    """主旋律编辑器"""
    
    add_note_requested = pyqtSignal(int, float, WaveformType)  # pitch, duration_beats, waveform
    
    def __init__(self, bpm: float = 120.0, parent=None):
        """初始化主旋律编辑器"""
        super().__init__(parent)
        self.bpm = bpm
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI - 横向布局：波形选择 | 音符按钮 | 拍数选择"""
        # 先初始化默认值
        self.selected_duration = 1.0  # 默认1拍
        self.selected_waveform = WaveformType.SQUARE  # 默认方波
        
        # 主布局（水平）
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # 第二部分：波形选择（左侧）
        waveform_area = QWidget()
        waveform_area.setMaximumWidth(150)
        waveform_layout = QVBoxLayout()
        waveform_area.setLayout(waveform_layout)
        
        waveform_label = QLabel("波形")
        waveform_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        waveform_label.setAlignment(Qt.AlignCenter)
        waveform_layout.addWidget(waveform_label)
        
        waveform_buttons_layout = QVBoxLayout()
        self.waveform_buttons = []
        self.waveform_group = QButtonGroup()
        
        # 波形颜色映射
        waveform_colors = {
            WaveformType.SQUARE: "#FF6B6B",      # 红色
            WaveformType.TRIANGLE: "#4ECDC4",    # 青色
            WaveformType.SAWTOOTH: "#FFE66D",    # 黄色
            WaveformType.SINE: "#95E1D3",        # 浅绿色
        }
        
        waveform_options = [
            ("方波", WaveformType.SQUARE),
            ("三角波", WaveformType.TRIANGLE),
            ("锯齿波", WaveformType.SAWTOOTH),
            ("正弦波", WaveformType.SINE)
        ]
        
        for name, waveform_type in waveform_options:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            color = waveform_colors.get(waveform_type, "#CCCCCC")
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px;
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    border: 2px solid {color};
                    border-radius: 4px;
                    padding: 5px;
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
            if name == "方波":  # 默认选择方波
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, wt=waveform_type: self.on_waveform_selected(wt))
            self.waveform_buttons.append(btn)
            self.waveform_group.addButton(btn)
            waveform_buttons_layout.addWidget(btn)
        
        waveform_buttons_layout.addStretch()
        waveform_layout.addLayout(waveform_buttons_layout)
        
        main_layout.addWidget(waveform_area)
        main_layout.addSpacing(10)
        
        # 第三部分：音符按钮（钢琴键盘，中间，可拉伸）
        piano_container = QWidget()
        piano_container_layout = QVBoxLayout()
        piano_container.setLayout(piano_container_layout)
        
        # 上方：信息显示区域
        info_area = QWidget()
        info_area.setMaximumHeight(50)
        info_layout = QHBoxLayout()
        info_area.setLayout(info_layout)
        
        # 当前音高显示（从钢琴键盘获取）
        self.pitch_info_label = QLabel("C4 (MIDI 60)")
        self.pitch_info_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        self.pitch_info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.pitch_info_label)
        
        info_layout.addStretch()
        
        piano_container_layout.addWidget(info_area)
        
        # 钢琴键盘（中间）
        self.piano_keyboard = PianoKeyboardWidget()
        # 连接点击信号，直接添加音符
        self.piano_keyboard.note_clicked.connect(self.on_piano_note_clicked)
        # 连接音高变化信号，更新显示
        self.piano_keyboard.pitch_changed.connect(self.on_pitch_changed)
        # 初始化预览参数
        self.piano_keyboard.set_preview_params(self.selected_waveform, self.selected_duration, self.bpm)
        # 确保钢琴键盘有足够的高度，不会被裁剪
        self.piano_keyboard.setMinimumHeight(220)  # 八度选择30px + 键盘190px
        
        # 创建休止符按钮（统一风格）
        self.rest_button = QPushButton("休止符")
        self.rest_button.setMinimumHeight(40)
        self.rest_button.setMaximumHeight(40)
        self.rest_button.setMinimumWidth(100)
        self.rest_button.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: bold;
                background-color: #888888;
                color: white;
                border: 2px solid #666666;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #999999;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #777777;
            }
        """)
        self.rest_button.clicked.connect(self.on_rest_clicked)
        
        # 将休止符按钮添加到钢琴键盘底部
        self.piano_keyboard.set_rest_button(self.rest_button)
        
        piano_container_layout.addWidget(self.piano_keyboard, 1)
        # 确保布局不会裁剪内容
        piano_container_layout.setContentsMargins(0, 0, 0, 0)
        piano_container_layout.setSpacing(0)
        
        main_layout.addWidget(piano_container, 1)  # 可拉伸
        main_layout.addSpacing(10)
        
        # 第四部分：拍数选择（右侧）
        duration_area = QWidget()
        duration_area.setMaximumWidth(180)
        duration_layout = QVBoxLayout()
        duration_area.setLayout(duration_layout)
        
        duration_label = QLabel("拍数")
        duration_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        duration_label.setAlignment(Qt.AlignCenter)
        duration_layout.addWidget(duration_label)
        
        # 使用两列布局，更松散
        duration_buttons_wrapper = QWidget()
        duration_buttons_layout = QHBoxLayout()
        duration_buttons_wrapper.setLayout(duration_buttons_layout)
        
        # 左列
        left_column = QVBoxLayout()
        left_column.setSpacing(5)
        # 右列
        right_column = QVBoxLayout()
        right_column.setSpacing(5)
        
        self.duration_buttons = []
        self.duration_group = QButtonGroup()
        
        duration_options = [
            ("1/4拍", 0.25),
            ("1/2拍", 0.5),
            ("1拍", 1.0),
            ("2拍", 2.0),
            ("4拍", 4.0)
        ]
        
        for i, (name, beats) in enumerate(duration_options):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setMinimumHeight(35)
            btn.setMaximumHeight(35)
            btn.setStyleSheet("font-size: 11px; padding: 5px;")
            if name == "1拍":  # 默认选择1拍
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, b=beats: self.on_duration_selected(b))
            self.duration_buttons.append(btn)
            self.duration_group.addButton(btn)
            
            # 分配到左右两列
            if i < 3:  # 前3个在左列
                left_column.addWidget(btn)
            else:  # 后2个在右列
                right_column.addWidget(btn)
        
        left_column.addStretch()
        right_column.addStretch()
        
        duration_buttons_layout.addLayout(left_column)
        duration_buttons_layout.addSpacing(10)  # 列间距
        duration_buttons_layout.addLayout(right_column)
        
        duration_layout.addWidget(duration_buttons_wrapper)
        duration_layout.addStretch()
        
        main_layout.addWidget(duration_area)
    
    def on_pitch_changed(self, pitch: int):
        """音高改变时更新显示"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        if hasattr(self, 'pitch_info_label'):
            self.pitch_info_label.setText(f"{note_name}{octave} (MIDI {pitch})")
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
        # 更新预览参数
        self.piano_keyboard.set_preview_params(self.selected_waveform, self.selected_duration, self.bpm)
    
    def on_duration_selected(self, beats: float):
        """时长选择"""
        self.selected_duration = beats
        # 更新预览参数
        self.piano_keyboard.set_preview_params(self.selected_waveform, self.selected_duration, self.bpm)
    
    def on_waveform_selected(self, waveform: WaveformType):
        """波形选择"""
        self.selected_waveform = waveform
        # 更新预览参数
        self.piano_keyboard.set_preview_params(self.selected_waveform, self.selected_duration, self.bpm)
    
    def add_note(self):
        """添加音符（供外部调用）"""
        pitch = self.piano_keyboard.get_pitch()
        self.add_note_requested.emit(pitch, self.selected_duration, self.selected_waveform)
    
    def get_current_pitch(self) -> int:
        """获取当前音高"""
        return self.piano_keyboard.get_pitch()
    
    def get_selected_duration(self) -> float:
        """获取选中的时长"""
        return self.selected_duration
    
    def get_selected_waveform(self) -> WaveformType:
        """获取选中的波形"""
        return self.selected_waveform
    
    def on_piano_note_clicked(self, pitch: int):
        """钢琴键盘音符点击（直接添加）"""
        # 直接添加音符，使用当前选中的时长和波形
        self.add_note_requested.emit(pitch, self.selected_duration, self.selected_waveform)
    
    def _lighten_color(self, color_hex: str) -> str:
        """使颜色变亮"""
        # 移除#号
        color_hex = color_hex.lstrip('#')
        # 转换为RGB
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        # 增加亮度（最多到255）
        r = min(255, int(r * 1.2))
        g = min(255, int(g * 1.2))
        b = min(255, int(b * 1.2))
        return f"#{r:02X}{g:02X}{b:02X}"
    
    def _darken_color(self, color_hex: str) -> str:
        """使颜色变暗"""
        # 移除#号
        color_hex = color_hex.lstrip('#')
        # 转换为RGB
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        # 减少亮度
        r = max(0, int(r * 0.8))
        g = max(0, int(g * 0.8))
        b = max(0, int(b * 0.8))
        return f"#{r:02X}{g:02X}{b:02X}"
    
    def on_rest_clicked(self):
        """空白音符按钮点击"""
        # 添加空白音符（pitch=0）
        self.add_note_requested.emit(0, self.selected_duration, self.selected_waveform)

