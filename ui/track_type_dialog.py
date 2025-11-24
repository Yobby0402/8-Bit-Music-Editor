"""
轨道类型选择对话框

选择要创建的轨道类型。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt

from core.models import WaveformType


class TrackTypeDialog(QDialog):
    """轨道类型选择对话框"""
    
    TRACK_TYPES = [
        ("主旋律", WaveformType.SQUARE, "用于主旋律，使用方波"),
        ("低音", WaveformType.TRIANGLE, "用于低音线，使用三角波"),
        ("打击乐", WaveformType.NOISE, "用于打击乐，使用噪声"),
        ("和声", WaveformType.SQUARE, "用于和声，使用方波"),
        ("效果", WaveformType.SAWTOOTH, "用于特殊效果，使用锯齿波"),
    ]
    
    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)
        self.setWindowTitle("选择轨道类型")
        self.setModal(True)
        self.selected_type = None
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        layout.addWidget(QLabel("请选择轨道类型："))
        
        # 类型列表
        self.type_list = QListWidget()
        for name, waveform, desc in self.TRACK_TYPES:
            item = QListWidgetItem(f"{name} - {desc}")
            item.setData(Qt.UserRole, (name, waveform))
            self.type_list.addItem(item)
        
        self.type_list.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.type_list)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept_selection)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
    
    def accept_selection(self):
        """接受选择"""
        current_item = self.type_list.currentItem()
        if current_item:
            self.selected_type = current_item.data(Qt.UserRole)
            self.accept()
    
    def get_selected_type(self):
        """获取选中的类型"""
        return self.selected_type

