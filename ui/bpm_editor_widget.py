"""
BPM编辑器组件

用于显示和编辑BPM段，支持可变BPM。
"""

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import BPMSegment, Project


class BPMEditorWidget(QWidget):
    """BPM编辑器组件"""
    
    # 信号：BPM段改变
    bpm_segments_changed = pyqtSignal(list)  # 新的BPM段列表
    
    def __init__(self, parent=None):
        """初始化BPM编辑器"""
        super().__init__(parent)
        self.project: Optional[Project] = None
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.setLayout(layout)
        
        # 标题
        title = QLabel("BPM段编辑")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # 说明文字
        info_label = QLabel("可以添加多个BPM段，每个段定义从某个时间点开始的BPM值。\n"
                          "导入MIDI文件时会自动提取BPM段信息。")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(info_label)
        
        # 当前BPM显示
        current_bpm_layout = QHBoxLayout()
        current_bpm_layout.addWidget(QLabel("当前BPM:"))
        self.current_bpm_label = QLabel("120")
        self.current_bpm_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        current_bpm_layout.addWidget(self.current_bpm_label)
        current_bpm_layout.addStretch()
        layout.addLayout(current_bpm_layout)
        
        # BPM段表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["开始时间 (秒)", "BPM", "操作"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.table)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("添加段")
        self.add_button.clicked.connect(self.add_segment)
        button_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton("删除选中段")
        self.remove_button.clicked.connect(self.remove_selected_segment)
        button_layout.addWidget(self.remove_button)
        
        button_layout.addStretch()
        
        self.reset_button = QPushButton("重置为固定BPM")
        self.reset_button.clicked.connect(self.reset_to_fixed_bpm)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)
    
    def set_project(self, project: Project):
        """设置项目"""
        self.project = project
        self.refresh()
    
    def refresh(self):
        """刷新显示"""
        if not self.project:
            return
        
        # 更新当前BPM显示
        if self.project.bpm_segments:
            # 显示第一个段的BPM（或根据播放位置显示当前BPM）
            current_bpm = self.project.bpm_segments[0].bpm
            self.current_bpm_label.setText(f"{int(current_bpm)}")
        else:
            self.current_bpm_label.setText(f"{int(self.project.bpm)}")
        
        # 更新表格
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        if self.project.bpm_segments:
            for i, segment in enumerate(self.project.bpm_segments):
                self.table.insertRow(i)
                
                # 开始时间
                start_item = QTableWidgetItem(f"{segment.start_time:.3f}")
                start_item.setData(Qt.UserRole, segment)
                self.table.setItem(i, 0, start_item)
                
                # BPM
                bpm_item = QTableWidgetItem(f"{int(segment.bpm)}")
                bpm_item.setData(Qt.UserRole, segment)
                self.table.setItem(i, 1, bpm_item)
                
                # 操作按钮
                button_widget = QWidget()
                button_layout = QHBoxLayout()
                button_layout.setContentsMargins(2, 2, 2, 2)
                button_widget.setLayout(button_layout)
                
                edit_button = QPushButton("编辑")
                edit_button.clicked.connect(lambda checked, seg=segment: self.edit_segment(seg))
                button_layout.addWidget(edit_button)
                
                self.table.setCellWidget(i, 2, button_widget)
        
        self.table.blockSignals(False)
    
    def add_segment(self):
        """添加BPM段"""
        if not self.project:
            return
        
        # 获取项目总时长
        total_duration = self.project.get_total_duration()
        if total_duration == 0:
            total_duration = 10.0  # 默认10秒
        
        # 计算新的开始时间（在最后一个段之后，或项目结束时）
        if self.project.bpm_segments:
            last_segment = self.project.bpm_segments[-1]
            new_start_time = last_segment.start_time + 4.0  # 默认在最后一段后4秒
        else:
            new_start_time = 0.0
        
        # 使用最后一个段的BPM，或默认BPM
        if self.project.bpm_segments:
            new_bpm = self.project.bpm_segments[-1].bpm
        else:
            new_bpm = self.project.bpm
        
        # 添加段
        self.project.add_bpm_segment(new_start_time, new_bpm)
        self.refresh()
        self.emit_bpm_changed()
    
    def remove_selected_segment(self):
        """删除选中的BPM段"""
        if not self.project:
            return
        
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择一个BPM段")
            return
        
        # 如果只有一个段，不能删除
        if len(self.project.bpm_segments) <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个BPM段")
            return
        
        # 删除选中的段（从后往前删除，避免索引问题）
        rows_to_remove = sorted([row.row() for row in selected_rows], reverse=True)
        for row in rows_to_remove:
            if row < len(self.project.bpm_segments):
                segment = self.project.bpm_segments[row]
                self.project.remove_bpm_segment(segment)
        
        self.refresh()
        self.emit_bpm_changed()
    
    def edit_segment(self, segment: BPMSegment):
        """编辑BPM段"""
        if not self.project:
            return
        
        # 创建编辑对话框
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑BPM段")
        dialog.setMinimumWidth(300)
        
        layout = QFormLayout()
        dialog.setLayout(layout)
        
        # 开始时间
        start_time_spin = QDoubleSpinBox()
        start_time_spin.setRange(0.0, 1000.0)
        start_time_spin.setDecimals(3)
        start_time_spin.setSingleStep(0.1)
        start_time_spin.setValue(segment.start_time)
        layout.addRow("开始时间 (秒):", start_time_spin)
        
        # BPM
        bpm_spin = QSpinBox()
        bpm_spin.setRange(30, 300)
        bpm_spin.setValue(int(segment.bpm))
        layout.addRow("BPM:", bpm_spin)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            # 更新段
            segment.start_time = start_time_spin.value()
            segment.bpm = float(bpm_spin.value())
            self.project._update_segment_end_times()
            self.refresh()
            self.emit_bpm_changed()
    
    def reset_to_fixed_bpm(self):
        """重置为固定BPM"""
        if not self.project:
            return
        
        reply = QMessageBox.question(
            self, "确认", 
            "确定要重置为固定BPM吗？这将删除所有BPM段，只保留一个默认段。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 使用第一个段的BPM，或默认BPM
            if self.project.bpm_segments:
                default_bpm = self.project.bpm_segments[0].bpm
            else:
                default_bpm = self.project.bpm
            
            # 重置为单个段
            self.project.bpm_segments = [BPMSegment(start_time=0.0, bpm=default_bpm)]
            self.project.bpm = default_bpm
            self.refresh()
            self.emit_bpm_changed()
    
    def on_item_changed(self, item: QTableWidgetItem):
        """表格项改变"""
        # 这里可以添加实时编辑功能
        pass
    
    def emit_bpm_changed(self):
        """发出BPM改变信号"""
        if self.project:
            self.bpm_segments_changed.emit(self.project.bpm_segments.copy())


