"""
设置对话框模块

提供统一的设置界面，左侧显示设置分类，右侧显示对应的设置项。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QLabel, QSpinBox, QDialogButtonBox,
    QTextEdit, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.theme import theme_manager
from ui.oscilloscope_widget import OscilloscopeWidget


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
        self.add_category("示波器设置", self.create_oscilloscope_settings())
        self.add_category("其他设置", self.create_other_settings())
        
        # 默认选择第一个分类
        self.category_list.setCurrentRow(0)
        
        # 将内容布局添加到主布局
        main_layout.addLayout(content_layout, 1)  # 拉伸因子1，占满空间
        
        # 添加按钮栏（应用、取消、确定）
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
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
    
    def apply_settings(self):
        """应用设置（不关闭对话框）"""
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
    
    def accept(self):
        """确认设置"""
        self.apply_settings()
        super().accept()
