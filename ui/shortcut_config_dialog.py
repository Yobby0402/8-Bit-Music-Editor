"""
快捷键配置对话框

允许用户自定义快捷键。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

from ui.shortcut_manager import get_shortcut_manager


class ShortcutConfigDialog(QDialog):
    """快捷键配置对话框"""
    
    # 快捷键显示名称映射
    SHORTCUT_NAMES = {
        # 钢琴键盘 - 白键
        "piano_c": "钢琴键 C",
        "piano_d": "钢琴键 D",
        "piano_e": "钢琴键 E",
        "piano_f": "钢琴键 F",
        "piano_g": "钢琴键 G",
        "piano_a": "钢琴键 A",
        "piano_b": "钢琴键 B",
        
        # 钢琴键盘 - 黑键
        "piano_c_sharp": "钢琴键 C#",
        "piano_d_sharp": "钢琴键 D#",
        "piano_f_sharp": "钢琴键 F#",
        "piano_g_sharp": "钢琴键 G#",
        "piano_a_sharp": "钢琴键 A#",
        
        # 波形选择
        "waveform_square": "波形：方波",
        "waveform_triangle": "波形：三角波",
        "waveform_sawtooth": "波形：锯齿波",
        "waveform_sine": "波形：正弦波",
        
        # 节拍长度
        "duration_quarter": "节拍：1/4拍",
        "duration_half": "节拍：1/2拍",
        "duration_whole": "节拍：1拍",
        "duration_double": "节拍：2拍",
        "duration_quad": "节拍：4拍",
        
        # 打击乐
        "drum_kick": "打击乐：底鼓",
        "drum_snare": "打击乐：军鼓",
        "drum_hihat": "打击乐：踩镲",
        "drum_crash": "打击乐：吊镲",
        
        # 八度控制
        "octave_up": "八度：增加一度",
        "octave_down": "八度：减少一度",
        
        # 休止符
        "rest": "休止符",
        
        # 删除最后一个音符
        "delete_last_note": "删除最后一个音符",
    }
    
    def __init__(self, parent=None):
        """初始化对话框"""
        super().__init__(parent)
        self.setWindowTitle("快捷键配置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.shortcut_manager = get_shortcut_manager()
        self.editing_item = None
        
        self.init_ui()
        self.load_shortcuts()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 说明标签
        info_label = QLabel("双击快捷键列可以编辑快捷键。按ESC取消编辑。")
        layout.addWidget(info_label)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["功能", "快捷键"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)
        
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
    
    def load_shortcuts(self):
        """加载快捷键到表格"""
        shortcuts = self.shortcut_manager.get_all_shortcuts()
        
        # 按类别分组显示
        categories = [
            ("钢琴键盘 - 白键", ["piano_c", "piano_d", "piano_e", "piano_f", "piano_g", "piano_a", "piano_b"]),
            ("钢琴键盘 - 黑键", ["piano_c_sharp", "piano_d_sharp", "piano_f_sharp", "piano_g_sharp", "piano_a_sharp"]),
            ("波形选择", ["waveform_square", "waveform_triangle", "waveform_sawtooth", "waveform_sine"]),
            ("节拍长度", ["duration_quarter", "duration_half", "duration_whole", "duration_double", "duration_quad"]),
            ("打击乐", ["drum_kick", "drum_snare", "drum_hihat", "drum_crash"]),
            ("八度控制", ["octave_up", "octave_down"]),
            ("其他", ["rest", "delete_last_note"]),
        ]
        
        self.table.setRowCount(sum(len(keys) for _, keys in categories))
        
        row = 0
        for category_name, keys in categories:
            for key in keys:
                if key in shortcuts:
                    # 功能名称
                    name_item = QTableWidgetItem(self.SHORTCUT_NAMES.get(key, key))
                    name_item.setData(Qt.UserRole, key)  # 存储key用于后续查找
                    self.table.setItem(row, 0, name_item)
                    
                    # 快捷键
                    shortcut_item = QTableWidgetItem(shortcuts[key])
                    shortcut_item.setData(Qt.UserRole, key)
                    self.table.setItem(row, 1, shortcut_item)
                    
                    row += 1
    
    def on_item_double_clicked(self, item: QTableWidgetItem):
        """双击项目时开始编辑"""
        if item.column() == 1:  # 只编辑快捷键列
            self.editing_item = item
            self.table.editItem(item)
    
    def keyPressEvent(self, event):
        """处理按键事件（用于编辑快捷键）"""
        if self.editing_item and self.table.currentItem() == self.editing_item:
            # 获取按键组合
            modifiers = []
            if event.modifiers() & Qt.ControlModifier:
                modifiers.append("Ctrl")
            if event.modifiers() & Qt.AltModifier:
                modifiers.append("Alt")
            if event.modifiers() & Qt.ShiftModifier:
                modifiers.append("Shift")
            if event.modifiers() & Qt.MetaModifier:
                modifiers.append("Meta")
            
            # 获取按键
            key = event.key()
            if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
                # 只是修饰键，不处理
                return
            
            # 构建快捷键字符串
            try:
                key_seq = QKeySequence(key)
                key_name = key_seq.toString()
                if not key_name:
                    # 如果无法转换为字符串，尝试使用key()方法
                    key_name = QKeySequence(key).toString()
            except:
                key_name = ""
            
            if not key_name:
                return
            
            if modifiers:
                shortcut_str = "+".join(modifiers) + "+" + key_name
            else:
                shortcut_str = key_name
            
            # 检查是否冲突
            if self.check_shortcut_conflict(shortcut_str, self.editing_item.data(Qt.UserRole)):
                QMessageBox.warning(self, "冲突", f"快捷键 {shortcut_str} 已被其他功能使用！")
                return
            
            # 设置快捷键
            self.editing_item.setText(shortcut_str)
            self.editing_item = None
            event.accept()
            return
        
        # ESC取消编辑
        if event.key() == Qt.Key_Escape and self.editing_item:
            self.editing_item = None
            event.accept()
            return
        
        super().keyPressEvent(event)
    
    def check_shortcut_conflict(self, shortcut_str: str, current_key: str) -> bool:
        """检查快捷键冲突"""
        shortcuts = self.shortcut_manager.get_all_shortcuts()
        for key, value in shortcuts.items():
            if key != current_key and value == shortcut_str:
                return True
        return False
    
    def reset_to_defaults(self):
        """重置为默认快捷键"""
        reply = QMessageBox.question(
            self, "确认", "确定要重置所有快捷键为默认值吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.shortcut_manager.reset_to_defaults()
            self.shortcut_manager.save_shortcuts()  # 保存重置后的默认值
            self.load_shortcuts()
    
    def accept(self):
        """保存快捷键配置"""
        # 从表格读取并保存
        for row in range(self.table.rowCount()):
            key_item = self.table.item(row, 0)
            shortcut_item = self.table.item(row, 1)
            if key_item and shortcut_item:
                key = key_item.data(Qt.UserRole)
                shortcut = shortcut_item.text()
                if key:
                    self.shortcut_manager.set_shortcut(key, shortcut)
        
        self.shortcut_manager.save_shortcuts()
        super().accept()

