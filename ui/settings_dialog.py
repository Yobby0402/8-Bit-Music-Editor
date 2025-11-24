"""
设置对话框

允许用户配置应用程序设置。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QGroupBox,
    QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt

from ui.settings_manager import get_settings_manager


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        self.settings_manager = get_settings_manager()
        
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 编辑选项组
        edit_group = QGroupBox("编辑选项")
        edit_layout = QVBoxLayout()
        edit_group.setLayout(edit_layout)
        
        # 吸附对齐到节拍
        self.snap_to_beat_checkbox = QCheckBox("吸附对齐到节拍")
        self.snap_to_beat_checkbox.setToolTip(
            "启用后，移动和添加音符时会自动对齐到节拍网格。\n"
            "禁用后，音符可以放置在任意位置。"
        )
        edit_layout.addWidget(self.snap_to_beat_checkbox)
        
        # 允许重叠
        self.allow_overlap_checkbox = QCheckBox("允许音符重叠")
        self.allow_overlap_checkbox.setToolTip(
            "启用后，允许同一音轨上的音符在时间上重叠。\n"
            "禁用后，如果音符重叠，会自动交换位置或阻止移动。"
        )
        edit_layout.addWidget(self.allow_overlap_checkbox)
        
        layout.addWidget(edit_group)
        
        layout.addStretch()
        
        # 按钮
        button_layout = QHBoxLayout()
        
        reset_button = QPushButton("重置为默认")
        reset_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_button)
        
        button_layout.addStretch()
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def load_settings(self):
        """加载设置到UI"""
        self.snap_to_beat_checkbox.setChecked(
            self.settings_manager.is_snap_to_beat_enabled()
        )
        self.allow_overlap_checkbox.setChecked(
            self.settings_manager.is_overlap_allowed()
        )
    
    def reset_to_defaults(self):
        """重置为默认值"""
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要重置所有设置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings_manager.reset_to_defaults()
            self.load_settings()
    
    def accept(self):
        """接受设置"""
        # 保存设置
        self.settings_manager.set_snap_to_beat(
            self.snap_to_beat_checkbox.isChecked()
        )
        self.settings_manager.set_allow_overlap(
            self.allow_overlap_checkbox.isChecked()
        )
        
        super().accept()

