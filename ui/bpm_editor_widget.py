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

from core.models import Project
from core.musical_time import TempoEvent


class BPMEditorWidget(QWidget):
    """BPM编辑器组件"""

    tempo_events_changed = pyqtSignal(list)  # 新的TempoEvent列表
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
        title = QLabel("Tempo / BPM 编辑")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # 说明文字
        info_label = QLabel(
            "内部以 beat / tick 锚定 tempo event，秒仅作为派生显示。\n"
            "导入 MIDI 文件时会自动提取 tempo map 信息。"
        )
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

        # Tempo 事件表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["开始拍 (Beat)", "开始 Tick", "BPM", "操作"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        if self.project.tempo_events:
            current_bpm = self.project.tempo_events[0].bpm
            self.current_bpm_label.setText(f"{int(current_bpm)}")
        else:
            self.current_bpm_label.setText(f"{int(self.project.bpm)}")

        # 更新表格
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        if self.project.tempo_events:
            for i, tempo_event in enumerate(self.project.tempo_events):
                self.table.insertRow(i)

                start_beat = self.project.ticks_to_beats(tempo_event.tick)
                beat_item = QTableWidgetItem(f"{start_beat:.3f}")
                beat_item.setData(Qt.UserRole, tempo_event)
                self.table.setItem(i, 0, beat_item)

                tick_item = QTableWidgetItem(str(tempo_event.tick))
                tick_item.setData(Qt.UserRole, tempo_event)
                self.table.setItem(i, 1, tick_item)

                # BPM
                bpm_item = QTableWidgetItem(f"{int(tempo_event.bpm)}")
                bpm_item.setData(Qt.UserRole, tempo_event)
                self.table.setItem(i, 2, bpm_item)

                # 操作按钮
                button_widget = QWidget()
                button_layout = QHBoxLayout()
                button_layout.setContentsMargins(2, 2, 2, 2)
                button_widget.setLayout(button_layout)

                edit_button = QPushButton("编辑")
                edit_button.clicked.connect(
                    lambda checked, event=tempo_event: self.edit_segment(event)
                )
                button_layout.addWidget(edit_button)

                self.table.setCellWidget(i, 3, button_widget)

        self.table.blockSignals(False)

    def add_segment(self):
        """添加Tempo事件"""
        if not self.project:
            return

        last_event = self.project.tempo_events[-1]
        new_tick = last_event.tick + self.project.beats_to_ticks(4.0)
        self.project.add_tempo_event(new_tick, last_event.bpm)
        self.refresh()
        self.emit_tempo_changed()

    def remove_selected_segment(self):
        """删除选中的Tempo事件"""
        if not self.project:
            return

        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "警告", "请先选择一个 Tempo 事件")
            return

        if len(self.project.tempo_events) <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个 Tempo 事件")
            return

        rows_to_remove = sorted([row.row() for row in selected_rows], reverse=True)
        tempo_events = list(self.project.tempo_events)
        for row in rows_to_remove:
            if row < len(tempo_events):
                self.project.remove_tempo_event(tempo_events[row])

        self.refresh()
        self.emit_tempo_changed()

    def edit_segment(self, tempo_event: TempoEvent):
        """编辑Tempo事件"""
        if not self.project:
            return

        # 创建编辑对话框
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("编辑 Tempo 事件")
        dialog.setMinimumWidth(300)

        layout = QFormLayout()
        dialog.setLayout(layout)

        start_beat = self.project.ticks_to_beats(tempo_event.tick)
        start_beat_spin = QDoubleSpinBox()
        start_beat_spin.setRange(0.0, 10000.0)
        start_beat_spin.setDecimals(3)
        start_beat_spin.setSingleStep(0.25)
        start_beat_spin.setValue(start_beat)
        if tempo_event.tick == 0:
            start_beat_spin.setEnabled(False)
        layout.addRow("开始拍 (Beat):", start_beat_spin)

        tick_label = QLabel(str(tempo_event.tick))
        tick_label.setStyleSheet("color: gray;")
        layout.addRow("开始 Tick:", tick_label)

        second_label = QLabel(f"{self.project.ticks_to_seconds(tempo_event.tick):.3f} 秒")
        second_label.setStyleSheet("color: gray;")
        layout.addRow("派生时间:", second_label)

        # BPM
        bpm_spin = QSpinBox()
        bpm_spin.setRange(30, 300)
        bpm_spin.setValue(int(tempo_event.bpm))
        layout.addRow("BPM:", bpm_spin)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            updated_events = list(self.project.tempo_events)
            event_index = updated_events.index(tempo_event)
            new_tick = (
                0
                if tempo_event.tick == 0
                else self.project.beats_to_ticks(start_beat_spin.value())
            )
            updated_events[event_index] = TempoEvent(new_tick, float(bpm_spin.value()))
            self.project.replace_tempo_events(updated_events)
            self.refresh()
            self.emit_tempo_changed()

    def reset_to_fixed_bpm(self):
        """重置为固定BPM"""
        if not self.project:
            return

        reply = QMessageBox.question(
            self,
            "确认",
            "确定要重置为固定 BPM 吗？这将删除所有 tempo event，只保留起点事件。",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.project.tempo_events:
                default_bpm = self.project.tempo_events[0].bpm
            else:
                default_bpm = self.project.bpm

            self.project.replace_tempo_events([TempoEvent(0, default_bpm)])
            self.refresh()
            self.emit_tempo_changed()

    def on_item_changed(self, item: QTableWidgetItem):
        """表格项改变"""
        # 这里可以添加实时编辑功能
        pass

    def emit_tempo_changed(self):
        """发出Tempo改变信号。"""
        if self.project:
            self.tempo_events_changed.emit(self.project.tempo_events.copy())
            self.bpm_segments_changed.emit(self.project.bpm_segments.copy())
