"""
设置对话框模块

提供统一的设置界面，左侧显示设置分类，右侧显示对应的设置项。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QLabel, QSpinBox, QDialogButtonBox,
    QTextEdit, QComboBox, QPushButton, QColorDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFontComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ui.theme import theme_manager
from ui.oscilloscope_widget import OscilloscopeWidget
from ui.settings_manager import get_settings_manager
from ui.shortcut_manager import get_shortcut_manager
from core.models import WaveformType


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None, oscilloscope_widget=None):
        """初始化设置对话框
        
        Args:
            parent: 父窗口
            oscilloscope_widget: 示波器widget（用于获取和设置示波器相关设置）
        """
        super().__init__(parent)
        self.oscilloscope_widget = oscilloscope_widget
        self.settings_manager = get_settings_manager()
        self.shortcut_manager = get_shortcut_manager()
        self.editing_shortcut_item = None
        self.setWindowTitle("设置")
        self.resize(700, 500)
        
        self.init_ui()
        self.apply_theme()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局（垂直）
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # 内容布局（水平）
        content_layout = QHBoxLayout()
        
        # 左侧：设置分类列表
        self.category_list = QListWidget()
        self.category_list.setMaximumWidth(150)
        self.category_list.setMinimumWidth(150)
        self.category_list.currentRowChanged.connect(self.on_category_changed)
        content_layout.addWidget(self.category_list)
        
        # 右侧：设置内容堆叠窗口
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget, 1)  # 拉伸因子1
        
        # 添加设置分类
        self.add_category("显示设置", self.create_display_settings())
        self.add_category("编辑设置", self.create_edit_settings())
        self.add_category("示波器设置", self.create_oscilloscope_settings())
        self.add_category("快捷键", self.create_shortcut_settings())
        self.add_category("其他设置", self.create_other_settings())
        
        # 默认选择第一个分类
        self.category_list.setCurrentRow(0)
        
        # 将内容布局添加到主布局
        main_layout.addLayout(content_layout, 1)  # 拉伸因子1，占满空间
        
        # 添加按钮栏（应用、取消、确定）
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 恢复默认按钮（重置所有设置与快捷键）
        self.reset_button = QPushButton("恢复默认")
        self.reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.reset_button)
        
        self.apply_button = QPushButton("应用")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        # 将按钮栏添加到主布局
        main_layout.addLayout(button_layout)
    
    def add_category(self, name: str, widget: QWidget):
        """添加设置分类
        
        Args:
            name: 分类名称
            widget: 对应的设置widget
        """
        item = QListWidgetItem(name)
        self.category_list.addItem(item)
        self.stacked_widget.addWidget(widget)
    
    def on_category_changed(self, index: int):
        """分类切换事件"""
        if index >= 0:
            self.stacked_widget.setCurrentIndex(index)
    
    def create_oscilloscope_settings(self) -> QWidget:
        """创建示波器设置页面"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 渲染音符数设置
        render_layout = QHBoxLayout()
        render_label = QLabel("渲染音符数 (1-50):")
        render_label.setMinimumWidth(150)
        render_layout.addWidget(render_label)
        
        self.render_count_spinbox = QSpinBox()
        self.render_count_spinbox.setRange(1, 50)
        if self.oscilloscope_widget:
            self.render_count_spinbox.setValue(self.oscilloscope_widget.max_notes_to_render)
        render_layout.addWidget(self.render_count_spinbox)
        render_layout.addStretch()
        layout.addLayout(render_layout)
        
        # 预渲染音符数设置
        pre_render_layout = QHBoxLayout()
        pre_render_label = QLabel("预渲染音符数 (0-10):")
        pre_render_label.setMinimumWidth(150)
        pre_render_layout.addWidget(pre_render_label)
        
        self.pre_render_spinbox = QSpinBox()
        self.pre_render_spinbox.setRange(0, 10)
        if self.oscilloscope_widget:
            self.pre_render_spinbox.setValue(self.oscilloscope_widget.pre_render_notes)
        pre_render_layout.addWidget(self.pre_render_spinbox)
        pre_render_layout.addStretch()
        layout.addLayout(pre_render_layout)
        
        # 代码语言设置
        code_lang_layout = QHBoxLayout()
        code_lang_label = QLabel("代码语言:")
        code_lang_label.setMinimumWidth(150)
        code_lang_layout.addWidget(code_lang_label)
        
        self.code_language_combo = QComboBox()
        self.code_language_combo.addItems(["伪代码 (Pseudocode)", "MicroPython (ESP32)", "汇编 (Assembly)"])
        language_map = {"伪代码 (Pseudocode)": "pseudocode", "MicroPython (ESP32)": "micropython", "汇编 (Assembly)": "assembly"}
        reverse_map = {"pseudocode": 0, "micropython": 1, "assembly": 2}
        if self.oscilloscope_widget:
            self.code_language_combo.setCurrentIndex(reverse_map.get(self.oscilloscope_widget.code_language, 0))
        code_lang_layout.addWidget(self.code_language_combo)
        code_lang_layout.addStretch()
        layout.addLayout(code_lang_layout)
        
        # 代码模板编辑
        template_label = QLabel("代码模板 (可使用变量: {frequency}, {duration}, {duration_ms}, {waveform}, {duty}, {duty_cycle}, {pitch}):")
        layout.addWidget(template_label)
        
        self.template_edit = QTextEdit()
        if self.oscilloscope_widget:
            current_lang = self.oscilloscope_widget.code_language
            self.template_edit.setPlainText(self.oscilloscope_widget.code_templates.get(current_lang, ""))
        self.template_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.template_edit)
        
        # 语言切换时更新模板
        def on_language_changed(index):
            if self.oscilloscope_widget:
                lang_key = language_map[self.code_language_combo.currentText()]
                self.template_edit.setPlainText(self.oscilloscope_widget.code_templates.get(lang_key, ""))
        self.code_language_combo.currentIndexChanged.connect(on_language_changed)
        
        layout.addStretch()
        
        return widget
    
    def _create_color_button(self, initial_color: str) -> QPushButton:
        """创建一个用于选择颜色的按钮"""
        btn = QPushButton()
        btn.setFixedWidth(60)
        btn.setText("")
        btn.setProperty("color", initial_color)
        btn.setStyleSheet(f"background-color: {initial_color}; border: 1px solid #666;")
        
        def on_click():
            current = QColor(btn.property("color"))
            color = QColorDialog.getColor(current, self, "选择颜色")
            if color.isValid():
                hex_color = color.name()
                btn.setProperty("color", hex_color)
                btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #666;")
        btn.clicked.connect(on_click)
        return btn
    
    def create_display_settings(self) -> QWidget:
        """创建显示设置页面（背景/前景色、字体大小、波形主题色）"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 全局背景色
        bg_layout = QHBoxLayout()
        bg_label = QLabel("整体背景色:")
        bg_label.setMinimumWidth(100)
        bg_layout.addWidget(bg_label)
        bg_color = self.settings_manager.get_ui_background_color()
        self.bg_color_button = self._create_color_button(bg_color)
        bg_layout.addWidget(self.bg_color_button)
        
        # 背景渐变开关
        from PyQt5.QtWidgets import QCheckBox
        self.bg_gradient_check = QCheckBox("启用渐变")
        self.bg_gradient_check.setChecked(self.settings_manager.is_background_gradient_enabled())
        bg_layout.addWidget(self.bg_gradient_check)
        
        bg_layout.addStretch()
        layout.addLayout(bg_layout)

        # 渐变第二颜色 + 模式
        gradient_layout = QHBoxLayout()
        gradient_label = QLabel("渐变第二颜色:")
        gradient_label.setMinimumWidth(100)
        gradient_layout.addWidget(gradient_label)
        bg_color2 = self.settings_manager.get_background_gradient_color2()
        self.bg_color2_button = self._create_color_button(bg_color2)
        gradient_layout.addWidget(self.bg_color2_button)
        
        mode_label = QLabel("渐变方式:")
        gradient_layout.addWidget(mode_label)
        self.bg_gradient_mode_combo = QComboBox()
        # 模式：中心向四周、上->下、下->上、左->右、右->左、对角线
        self.bg_gradient_mode_combo.addItems([
            "无渐变",
            "中心向四周",
            "上到下",
            "下到上",
            "左到右",
            "右到左",
            "对角线"
        ])
        mode_map = {
            "none": 0,
            "center": 1,
            "top_bottom": 2,
            "bottom_top": 3,
            "left_right": 4,
            "right_left": 5,
            "diagonal": 6,
        }
        current_mode = self.settings_manager.get_background_gradient_mode()
        self.bg_gradient_mode_combo.setCurrentIndex(mode_map.get(current_mode, 0))
        gradient_layout.addWidget(self.bg_gradient_mode_combo)
        gradient_layout.addStretch()
        layout.addLayout(gradient_layout)
        
        # 全局前景/文字颜色
        fg_layout = QHBoxLayout()
        fg_label = QLabel("整体前景色:")
        fg_label.setMinimumWidth(120)
        fg_layout.addWidget(fg_label)
        fg_color = self.settings_manager.get_ui_foreground_color()
        self.fg_color_button = self._create_color_button(fg_color)
        fg_layout.addWidget(self.fg_color_button)
        fg_layout.addStretch()
        layout.addLayout(fg_layout)
        
        # 全局字体设置（字体族 + 大小）
        font_layout = QHBoxLayout()
        font_label = QLabel("软件字体:")
        font_label.setMinimumWidth(120)
        font_layout.addWidget(font_label)
        # 字体族选择
        self.font_family_combo = QFontComboBox()
        current_family = self.settings_manager.get_ui_font_family()
        if current_family:
            self.font_family_combo.setCurrentFont(QFont(current_family))
        font_layout.addWidget(self.font_family_combo, 1)
        # 字体大小
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 32)
        self.font_size_spinbox.setValue(self.settings_manager.get_ui_font_size())
        self.font_size_spinbox.setMinimumWidth(60)
        font_layout.addWidget(self.font_size_spinbox)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        # 按钮字体（独立设置）
        button_font_layout = QHBoxLayout()
        button_font_label = QLabel("按钮字体:")
        button_font_label.setMinimumWidth(120)
        button_font_layout.addWidget(button_font_label)
        self.button_font_family_combo = QFontComboBox()
        btn_family = self.settings_manager.get_button_font_family()
        if btn_family:
            self.button_font_family_combo.setCurrentFont(QFont(btn_family))
        button_font_layout.addWidget(self.button_font_family_combo, 1)
        self.button_font_size_spinbox = QSpinBox()
        self.button_font_size_spinbox.setRange(8, 32)
        self.button_font_size_spinbox.setValue(self.settings_manager.get_button_font_size())
        self.button_font_size_spinbox.setMinimumWidth(60)
        button_font_layout.addWidget(self.button_font_size_spinbox)
        button_font_layout.addStretch()
        layout.addLayout(button_font_layout)
        
        # 波形主题色设置
        layout.addSpacing(10)
        waveform_title = QLabel("波形主题色:")
        layout.addWidget(waveform_title)
        
        self.waveform_color_buttons = {}
        waveform_items = [
            ("方波", "waveform_color_square", WaveformType.SQUARE),
            ("三角波", "waveform_color_triangle", WaveformType.TRIANGLE),
            ("锯齿波", "waveform_color_sawtooth", WaveformType.SAWTOOTH),
            ("正弦波", "waveform_color_sine", WaveformType.SINE),
            ("噪声", "waveform_color_noise", WaveformType.NOISE),
        ]
        for label_text, key, wf_type in waveform_items:
            wf_layout = QHBoxLayout()
            lbl = QLabel(label_text + ":")
            lbl.setMinimumWidth(120)
            wf_layout.addWidget(lbl)
            color_str = self.settings_manager.get_waveform_color(key)
            btn = self._create_color_button(color_str)
            wf_layout.addWidget(btn)
            wf_layout.addStretch()
            layout.addLayout(wf_layout)
            self.waveform_color_buttons[key] = btn
        
        layout.addStretch()
        return widget
    
    def create_edit_settings(self) -> QWidget:
        """创建编辑行为相关设置页面（吸附到网格、是否允许重叠、播放线刷新率等）"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        from PyQt5.QtWidgets import QCheckBox
        # 吸附到节拍网格
        self.snap_to_beat_checkbox = QCheckBox("编辑时吸附到节拍网格（1/4 拍）")
        self.snap_to_beat_checkbox.setChecked(self.settings_manager.is_snap_to_beat_enabled())
        layout.addWidget(self.snap_to_beat_checkbox)
        
        # 是否允许音符重叠
        self.allow_overlap_checkbox = QCheckBox("允许音符重叠（关闭时拖动/编辑会自动避免重叠）")
        self.allow_overlap_checkbox.setChecked(self.settings_manager.is_overlap_allowed())
        layout.addWidget(self.allow_overlap_checkbox)

        # 重叠音符的显示方式：蜘蛛纸牌式垂直摞起
        self.stack_overlapped_checkbox = QCheckBox("重叠音符堆叠显示（类似蜘蛛纸牌，从上到下错位，而不是完全重叠）")
        self.stack_overlapped_checkbox.setChecked(self.settings_manager.is_stack_overlapped_notes_enabled())
        layout.addWidget(self.stack_overlapped_checkbox)

        # 播放线刷新率（毫秒）
        refresh_layout = QHBoxLayout()
        refresh_label = QLabel("播放线刷新间隔 (毫秒，数值越小越流畅、但更耗性能):")
        refresh_layout.addWidget(refresh_label)
        self.playhead_refresh_spinbox = QSpinBox()
        self.playhead_refresh_spinbox.setRange(10, 200)
        self.playhead_refresh_spinbox.setSingleStep(5)
        self.playhead_refresh_spinbox.setValue(self.settings_manager.get_playhead_refresh_interval())
        refresh_layout.addWidget(self.playhead_refresh_spinbox)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # 说明文字
        info_label = QLabel(
            "说明：\n"
            " - 吸附到节拍网格：在拖动音符、移动播放线等操作时，对齐到最近的 1/4 拍位置。\n"
            " - 允许重叠：关闭时，在网格中拖动或导入时将尽量避免音符交叠；开启则保留叠音和和弦结构。\n"
            " - 重叠音符堆叠显示：仅影响显示方式，开启后相同位置的音符会在垂直方向上错位摞起，方便查看。"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        return widget
    
    def create_shortcut_settings(self) -> QWidget:
        """创建快捷键设置页面（内嵌原快捷键配置对话框的功能）"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        info_label = QLabel("双击快捷键列可以编辑快捷键。按 ESC 取消编辑。")
        layout.addWidget(info_label)
        
        # 表格
        self.shortcut_table = QTableWidget()
        self.shortcut_table.setColumnCount(2)
        self.shortcut_table.setHorizontalHeaderLabels(["功能", "快捷键"])
        self.shortcut_table.horizontalHeader().setStretchLastSection(True)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.shortcut_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.shortcut_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.shortcut_table.itemDoubleClicked.connect(self.on_shortcut_item_double_clicked)
        layout.addWidget(self.shortcut_table)
        
        # 底部按钮栏（重置）
        btn_layout = QHBoxLayout()
        reset_button = QPushButton("重置为默认")
        reset_button.clicked.connect(self.reset_shortcuts_to_defaults)
        btn_layout.addWidget(reset_button)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.load_shortcuts_to_table()
        return widget
    
    def create_other_settings(self) -> QWidget:
        """创建其他设置页面"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # 占位文本
        placeholder = QLabel("其他设置项将在此处显示")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)
        
        layout.addStretch()
        
        return widget
    
    def apply_theme(self):
        """应用主题"""
        theme = theme_manager.current_theme
        self.setStyleSheet(theme.get_style("dialog"))
        
        # 应用主题到子控件
        for i in range(self.stacked_widget.count()):
            widget = self.stacked_widget.widget(i)
            if widget:
                for child in widget.findChildren(QLabel):
                    child.setStyleSheet(theme.get_style("label"))
                for child in widget.findChildren(QSpinBox):
                    child.setStyleSheet(theme.get_style("line_edit"))
                for child in widget.findChildren(QComboBox):
                    child.setStyleSheet(theme.get_style("line_edit"))
                for child in widget.findChildren(QTextEdit):
                    child.setStyleSheet(theme.get_style("line_edit"))
                for child in widget.findChildren(QTableWidget):
                    child.setStyleSheet(theme.get_style("line_edit"))

    def reset_to_defaults(self):
        """恢复所有设置为默认值（包括显示/渐变/波形颜色和快捷键）"""
        # 重置设置管理器
        self.settings_manager.reset_to_defaults()
        # 重置快捷键
        self.shortcut_manager.reset_to_defaults()
        self.shortcut_manager.save_shortcuts()

        # 重新加载“显示设置”控件的值
        if hasattr(self, "bg_color_button"):
            bg = self.settings_manager.get_ui_background_color()
            self.bg_color_button.setProperty("color", bg)
            self.bg_color_button.setStyleSheet(f"background-color: {bg}; border: 1px solid #666;")
        if hasattr(self, "fg_color_button"):
            fg = self.settings_manager.get_ui_foreground_color()
            self.fg_color_button.setProperty("color", fg)
            self.fg_color_button.setStyleSheet(f"background-color: {fg}; border: 1px solid #666;")
        if hasattr(self, "bg_gradient_check"):
            self.bg_gradient_check.setChecked(self.settings_manager.is_background_gradient_enabled())
        if hasattr(self, "bg_color2_button"):
            bg2 = self.settings_manager.get_background_gradient_color2()
            self.bg_color2_button.setProperty("color", bg2)
            self.bg_color2_button.setStyleSheet(f"background-color: {bg2}; border: 1px solid #666;")
        if hasattr(self, "bg_gradient_mode_combo"):
            mode = self.settings_manager.get_background_gradient_mode()
            mode_map = {
                "none": 0,
                "center": 1,
                "top_bottom": 2,
                "bottom_top": 3,
                "left_right": 4,
                "right_left": 5,
                "diagonal": 6,
            }
            self.bg_gradient_mode_combo.setCurrentIndex(mode_map.get(mode, 0))
        if hasattr(self, "font_size_spinbox"):
            self.font_size_spinbox.setValue(self.settings_manager.get_ui_font_size())
        if hasattr(self, "font_family_combo"):
            fam = self.settings_manager.get_ui_font_family()
            if fam:
                self.font_family_combo.setCurrentFont(QFont(fam))
        if hasattr(self, "button_font_size_spinbox"):
            self.button_font_size_spinbox.setValue(self.settings_manager.get_button_font_size())
        if hasattr(self, "button_font_family_combo"):
            bfam = self.settings_manager.get_button_font_family()
            if bfam:
                self.button_font_family_combo.setCurrentFont(QFont(bfam))

        # 重新加载“编辑设置”控件的值（吸附、重叠、播放线刷新率）
        if hasattr(self, "snap_to_beat_checkbox"):
            self.snap_to_beat_checkbox.setChecked(self.settings_manager.is_snap_to_beat_enabled())
        if hasattr(self, "allow_overlap_checkbox"):
            self.allow_overlap_checkbox.setChecked(self.settings_manager.is_overlap_allowed())
        if hasattr(self, "playhead_refresh_spinbox"):
            self.playhead_refresh_spinbox.setValue(self.settings_manager.get_playhead_refresh_interval())

        # 重新加载快捷键表
        self.load_shortcuts_to_table()

        # 应用一次，立即让主界面恢复默认外观与快捷键
        self.apply_settings()

    # ===== 快捷键相关逻辑 =====
    def load_shortcuts_to_table(self):
        """将快捷键信息加载到表格"""
        if not hasattr(self, "shortcut_table"):
            return
        shortcuts = self.shortcut_manager.get_all_shortcuts()
        # 类似原快捷键对话框的分组
        categories = [
            ("钢琴键盘 - 白键", ["piano_c", "piano_d", "piano_e", "piano_f", "piano_g", "piano_a", "piano_b"]),
            ("钢琴键盘 - 黑键", ["piano_c_sharp", "piano_d_sharp", "piano_f_sharp", "piano_g_sharp", "piano_a_sharp"]),
            ("波形选择", ["waveform_square", "waveform_triangle", "waveform_sawtooth", "waveform_sine"]),
            ("节拍长度", ["duration_quarter", "duration_half", "duration_whole", "duration_double", "duration_quad"]),
            ("打击乐", ["drum_kick", "drum_snare", "drum_hihat", "drum_crash"]),
            ("八度控制", ["octave_up", "octave_down"]),
            ("其他", ["rest", "delete_last_note"]),
        ]
        # 针对表格，我们只展示具体条目，不展示分类行
        total_rows = sum(len(keys) for _, keys in categories)
        self.shortcut_table.setRowCount(total_rows)
        from ui.shortcut_config_dialog import ShortcutConfigDialog
        row = 0
        for _, keys in categories:
            for key in keys:
                if key in shortcuts:
                    name = ShortcutConfigDialog.SHORTCUT_NAMES.get(key, key)
                    name_item = QTableWidgetItem(name)
                    name_item.setData(Qt.UserRole, key)
                    self.shortcut_table.setItem(row, 0, name_item)
                    shortcut_item = QTableWidgetItem(shortcuts[key])
                    shortcut_item.setData(Qt.UserRole, key)
                    self.shortcut_table.setItem(row, 1, shortcut_item)
                    row += 1

    def on_shortcut_item_double_clicked(self, item: QTableWidgetItem):
        """双击快捷键单元格开始编辑"""
        if item.column() == 1:
            self.editing_shortcut_item = item
            self.shortcut_table.editItem(item)

    def keyPressEvent(self, event):
        """处理按键事件（用于编辑快捷键）"""
        if self.editing_shortcut_item and self.shortcut_table.currentItem() == self.editing_shortcut_item:
            # 组合修饰键
            modifiers = []
            if event.modifiers() & Qt.ControlModifier:
                modifiers.append("Ctrl")
            if event.modifiers() & Qt.AltModifier:
                modifiers.append("Alt")
            if event.modifiers() & Qt.ShiftModifier:
                modifiers.append("Shift")
            if event.modifiers() & Qt.MetaModifier:
                modifiers.append("Meta")

            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
                return

            from PyQt5.QtGui import QKeySequence
            try:
                key_seq = QKeySequence(key)
                key_name = key_seq.toString()
            except Exception as e:
                # 理论上这里不会抛异常，但若发生了，直接打印出来方便调试
                import traceback
                print("解析快捷键按键时出错：", e)
                traceback.print_exc()
                key_name = ""
            if not key_name:
                return

            if modifiers:
                shortcut_str = "+".join(modifiers) + "+" + key_name
            else:
                shortcut_str = key_name

            # 冲突检查
            current_key = self.editing_shortcut_item.data(Qt.UserRole)
            if self.check_shortcut_conflict(shortcut_str, current_key):
                QMessageBox.warning(self, "冲突", f"快捷键 {shortcut_str} 已被其他功能使用！")
                return

            self.editing_shortcut_item.setText(shortcut_str)
            self.editing_shortcut_item = None
            event.accept()
            return

        # ESC 取消编辑
        if event.key() == Qt.Key_Escape and self.editing_shortcut_item:
            self.editing_shortcut_item = None
            event.accept()
            return

        super().keyPressEvent(event)

    def check_shortcut_conflict(self, shortcut_str: str, current_key: str) -> bool:
        """检查快捷键是否与其他功能冲突"""
        shortcuts = self.shortcut_manager.get_all_shortcuts()
        for key, value in shortcuts.items():
            if key != current_key and value == shortcut_str:
                return True
        return False

    def reset_shortcuts_to_defaults(self):
        """重置所有快捷键为默认"""
        reply = QMessageBox.question(
            self, "确认", "确定要重置所有快捷键为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.shortcut_manager.reset_to_defaults()
            self.shortcut_manager.save_shortcuts()
            self.load_shortcuts_to_table()
    
    def apply_settings(self):
        """应用设置（不关闭对话框）"""
        # 显示设置
        if hasattr(self, "bg_color_button"):
            bg_color = self.bg_color_button.property("color")
            if isinstance(bg_color, str):
                self.settings_manager.set_ui_background_color(bg_color)
        if hasattr(self, "fg_color_button"):
            fg_color = self.fg_color_button.property("color")
            if isinstance(fg_color, str):
                self.settings_manager.set_ui_foreground_color(fg_color)
        if hasattr(self, "font_size_spinbox"):
            self.settings_manager.set_ui_font_size(self.font_size_spinbox.value())
        if hasattr(self, "font_family_combo"):
            font = self.font_family_combo.currentFont()
            self.settings_manager.set_ui_font_family(font.family())
        # 按钮字体
        if hasattr(self, "button_font_size_spinbox"):
            self.settings_manager.set_button_font_size(self.button_font_size_spinbox.value())
        if hasattr(self, "button_font_family_combo"):
            btn_font = self.button_font_family_combo.currentFont()
            self.settings_manager.set_button_font_family(btn_font.family())
        
        # 波形主题色
        if hasattr(self, "waveform_color_buttons"):
            for key, btn in self.waveform_color_buttons.items():
                color = btn.property("color")
                if isinstance(color, str):
                    self.settings_manager.set_waveform_color(key, color)

        # 背景渐变
        if hasattr(self, "bg_gradient_check"):
            self.settings_manager.set_background_gradient_enabled(self.bg_gradient_check.isChecked())
        if hasattr(self, "bg_color2_button"):
            color2 = self.bg_color2_button.property("color")
            if isinstance(color2, str):
                self.settings_manager.set_background_gradient_color2(color2)
        if hasattr(self, "bg_gradient_mode_combo"):
            idx = self.bg_gradient_mode_combo.currentIndex()
            idx_to_mode = {
                0: "none",
                1: "center",
                2: "top_bottom",
                3: "bottom_top",
                4: "left_right",
                5: "right_left",
                6: "diagonal",
            }
            self.settings_manager.set_background_gradient_mode(idx_to_mode.get(idx, "none"))

        # 编辑行为设置（吸附/重叠/堆叠显示/播放线刷新率）
        if hasattr(self, "snap_to_beat_checkbox"):
            self.settings_manager.set_snap_to_beat(self.snap_to_beat_checkbox.isChecked())
        if hasattr(self, "allow_overlap_checkbox"):
            self.settings_manager.set_allow_overlap(self.allow_overlap_checkbox.isChecked())
        if hasattr(self, "stack_overlapped_checkbox"):
            self.settings_manager.set_stack_overlapped_notes(self.stack_overlapped_checkbox.isChecked())
        if hasattr(self, "playhead_refresh_spinbox"):
            self.settings_manager.set_playhead_refresh_interval(self.playhead_refresh_spinbox.value())
        
        # 立即应用字体（字体族 + 大小，全局），并统一全局调色板背景
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtGui import QPalette, QColor
            app = QApplication.instance()
            if app is not None:
                font = app.font()
                family = self.settings_manager.get_ui_font_family()
                if family:
                    font.setFamily(family)
                font.setPointSize(self.settings_manager.get_ui_font_size())
                app.setFont(font)
                
                # 全局背景色：让所有未单独设置背景的区域使用相同的颜色，而不是默认纯白
                bg_color_str = self.settings_manager.get_ui_background_color()
                if bg_color_str:
                    palette = app.palette()
                    bg_qcolor = QColor(bg_color_str)
                    palette.setColor(QPalette.Window, bg_qcolor)
                    palette.setColor(QPalette.Base, bg_qcolor)
                    palette.setColor(QPalette.AlternateBase, bg_qcolor)
                    app.setPalette(palette)
        except Exception:
            pass
        
        # 通知主窗口刷新显示（背景/前景色、网格等）
        parent = self.parent()
        if parent is not None:
            # 优先使用统一的刷新入口
            if hasattr(parent, "refresh_theme_from_settings"):
                parent.refresh_theme_from_settings()
            else:
                # 兼容旧逻辑
                if hasattr(parent, "apply_theme"):
                    parent.apply_theme()
                if hasattr(parent, "apply_display_settings_from_settings"):
                    parent.apply_display_settings_from_settings()
                if hasattr(parent, "refresh_ui"):
                    parent.refresh_ui(preserve_selection=True, force_full_refresh=True)
        
        # 示波器设置
        if self.oscilloscope_widget:
            # 更新示波器设置
            self.oscilloscope_widget.max_notes_to_render = self.render_count_spinbox.value()
            self.oscilloscope_widget.pre_render_notes = self.pre_render_spinbox.value()
            
            # 更新代码语言和模板
            language_map = {"伪代码 (Pseudocode)": "pseudocode", "MicroPython (ESP32)": "micropython", "汇编 (Assembly)": "assembly"}
            selected_lang = language_map[self.code_language_combo.currentText()]
            self.oscilloscope_widget.code_language = selected_lang
            self.oscilloscope_widget.code_templates[selected_lang] = self.template_edit.toPlainText()
            
            # 清除波形缓存，强制重新生成
            if hasattr(self.oscilloscope_widget, 'waveform_cache'):
                self.oscilloscope_widget.waveform_cache.clear()
            self.oscilloscope_widget.update()
        
        # 快捷键设置（保存到 shortcut_manager）
        if hasattr(self, "shortcut_table"):
            for row in range(self.shortcut_table.rowCount()):
                name_item = self.shortcut_table.item(row, 0)
                shortcut_item = self.shortcut_table.item(row, 1)
                if name_item and shortcut_item:
                    key = name_item.data(Qt.UserRole)
                    shortcut = shortcut_item.text()
                    if key:
                        self.shortcut_manager.set_shortcut(key, shortcut)
    
    def accept(self):
        """确认设置"""
        self.apply_settings()
        super().accept()
