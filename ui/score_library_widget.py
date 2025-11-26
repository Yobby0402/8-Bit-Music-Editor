"""
乐谱面板（Score Library）

用于展示和管理可复用的音符/鼓点片段。
"""

from typing import Dict, Any, List

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.theme import theme_manager


class ScoreLibraryWidget(QWidget):
    """
    乐谱面板 UI

    - 左侧树形列表：分组 -> 片段
    - 右侧按钮：从当前选择创建片段、应用到当前音轨、删除片段
    """

    # 请求从当前选择创建片段（交由 MainWindow 收集选中的音符/事件）
    request_create_from_selection = pyqtSignal()
    # 请求在当前音轨应用指定片段
    snippet_apply_requested = pyqtSignal(str)
    # 请求删除指定片段
    snippet_delete_requested = pyqtSignal(str)

    def __init__(self, score_library, parent=None):
        super().__init__(parent)
        self.score_library = score_library

        self._init_ui()
        self.refresh()

    # ---- UI ----

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.setLayout(layout)

        # 片段列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["名称", "类型", "分组", "轨道"])
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 60)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 80)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.btn_create = QPushButton("从当前选择创建片段")
        self.btn_create.clicked.connect(self.request_create_from_selection.emit)
        btn_layout.addWidget(self.btn_create)

        self.btn_apply = QPushButton("应用到当前音轨")
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        btn_layout.addWidget(self.btn_apply)

        self.btn_delete = QPushButton("删除片段")
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.btn_delete)

        self.btn_rename = QPushButton("重命名片段")
        self.btn_rename.clicked.connect(self._on_rename_snippet_clicked)
        btn_layout.addWidget(self.btn_rename)

        self.btn_rename_group = QPushButton("重命名分组")
        self.btn_rename_group.clicked.connect(self._on_rename_group_clicked)
        btn_layout.addWidget(self.btn_rename_group)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 应用主题样式
        theme = theme_manager.current_theme
        button_style = theme.get_style("button_small")
        for btn in (self.btn_create, self.btn_apply, self.btn_delete):
            btn.setStyleSheet(button_style)

    # ---- 列表刷新 ----

    def refresh(self):
        """从库中重新加载片段列表"""
        self.tree.clear()

        snippets = self.score_library.list_snippets()
        # 分组：group -> [snippets]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for s in snippets:
            group = s.get("group") or "未分组"
            groups.setdefault(group, []).append(s)

        for group_name, items in groups.items():
            group_item = QTreeWidgetItem(self.tree, [group_name])
            group_item.setFirstColumnSpanned(True)
            group_item.setFlags(Qt.ItemIsEnabled)

            for s in items:
                snippet_item = QTreeWidgetItem(group_item)
                snippet_item.setText(0, s.get("name", "未命名"))
                snippet_item.setText(1, "鼓点" if s.get("type") == "drum" else "音符")
                snippet_item.setText(2, group_name)
                snippet_item.setText(3, s.get("track_name", ""))
                snippet_item.setData(0, Qt.UserRole, s.get("id"))

        self.tree.expandAll()

    # ---- 事件处理 ----

    def _get_selected_snippet_id(self) -> str:
        item = self.tree.currentItem()
        if not item:
            return ""
        # 如果选中的是分组项，则没有 UserRole 数据
        snippet_id = item.data(0, Qt.UserRole)
        if isinstance(snippet_id, str):
            return snippet_id
        return ""

    def _get_selected_group_name(self) -> str:
        """根据当前选中项推断分组名"""
        item = self.tree.currentItem()
        if not item:
            return ""
        snippet_id = item.data(0, Qt.UserRole)
        if isinstance(snippet_id, str):
            # 选中的是片段行
            return item.text(2)
        # 选中的是分组行
        if item.parent() is None:
            return item.text(0)
        return ""

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        snippet_id = item.data(0, Qt.UserRole)
        if isinstance(snippet_id, str):
            self.snippet_apply_requested.emit(snippet_id)

    def _on_apply_clicked(self):
        snippet_id = self._get_selected_snippet_id()
        if not snippet_id:
            QMessageBox.information(self, "提示", "请选择一个乐谱片段后再应用。")
            return
        self.snippet_apply_requested.emit(snippet_id)

    def _on_delete_clicked(self):
        snippet_id = self._get_selected_snippet_id()
        if not snippet_id:
            QMessageBox.information(self, "提示", "请选择一个乐谱片段后再删除。")
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除选中的乐谱片段吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.snippet_delete_requested.emit(snippet_id)

    def _on_rename_snippet_clicked(self):
        """重命名当前选中的片段"""
        snippet_id = self._get_selected_snippet_id()
        if not snippet_id:
            QMessageBox.information(self, "提示", "请先选择一个乐谱片段。")
            return
        snippet = self.score_library.get_snippet(snippet_id)
        if not snippet:
            return
        current_name = snippet.get("name", "")
        new_name, ok = QInputDialog.getText(self, "重命名片段", "新的片段名称：", text=current_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == current_name:
            return
        self.score_library.rename_snippet(snippet_id, new_name)
        self.refresh()

    def _on_rename_group_clicked(self):
        """重命名当前分组（或选中片段所在分组）"""
        group_name = self._get_selected_group_name()
        if not group_name:
            QMessageBox.information(self, "提示", "请先选择一个分组或其中的片段。")
            return
        new_group, ok = QInputDialog.getText(self, "重命名分组", "新的分组名称：", text=group_name)
        if not ok:
            return
        new_group = new_group.strip()
        if not new_group or new_group == group_name:
            return
        self.score_library.rename_group(group_name, new_group)
        self.refresh()


