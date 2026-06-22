"""SFX preset and note-parameter editor dialog."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import ADSRParams, WaveformType
from core.sfx_generator import (
    SFX_PRESET_LABELS,
    SfxNoteSpec,
    SfxSpec,
    build_sfx_spec,
)

NOTE_COLUMNS = [
    "音高",
    "起始",
    "时值",
    "力度",
    "波形",
    "占空比",
    "起音",
    "衰减",
    "保持",
    "释音",
]

SFX_PRESET_DISPLAY_LABELS = {
    "coin": "吃金币",
    "jump": "跳跃",
    "hit": "受击",
    "power_up": "强化",
    "laser": "激光",
    "explosion": "爆炸",
    "select": "菜单选择",
    "error": "错误提示",
    "door": "开门",
    "heal": "治疗",
}

WAVEFORM_DISPLAY_LABELS = {
    WaveformType.SQUARE: "方波",
    WaveformType.TRIANGLE: "三角波",
    WaveformType.SAWTOOTH: "锯齿波",
    WaveformType.SINE: "正弦波",
    WaveformType.NOISE: "噪声",
}


def _number_item(value: float | int | str) -> QTableWidgetItem:
    item = QTableWidgetItem(str(value))
    item.setTextAlignment(Qt.AlignCenter)
    return item


def _format_number(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


class SfxEditorWidget(QWidget):
    """Collect and edit an SFX spec before insertion."""

    def __init__(self, parent=None, *, start_beat: float = 0.0):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._spec = build_sfx_spec("coin")
        self._ai_thread = None
        self._updating_note_detail = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        layout.addLayout(form)

        self.preset_combo = QComboBox()
        for kind, label in SFX_PRESET_LABELS.items():
            self.preset_combo.addItem(SFX_PRESET_DISPLAY_LABELS.get(kind, label), kind)
        self.preset_combo.currentIndexChanged.connect(self._load_selected_preset)
        form.addRow("预设", self.preset_combo)

        self.label_edit = QLineEdit()
        form.addRow("名称", self.label_edit)

        self.start_beat_spin = QDoubleSpinBox()
        self.start_beat_spin.setRange(0.0, 9999.0)
        self.start_beat_spin.setDecimals(3)
        self.start_beat_spin.setSingleStep(0.25)
        self.start_beat_spin.setValue(max(0.0, float(start_beat)))
        form.addRow("插入拍点", self.start_beat_spin)

        self.auto_preview_checkbox = QCheckBox("插入后自动试听")
        self.auto_preview_checkbox.setChecked(True)
        form.addRow("", self.auto_preview_checkbox)

        self.ai_prompt_edit = QPlainTextEdit()
        self.ai_prompt_edit.setFixedHeight(64)
        self.ai_prompt_edit.setPlaceholderText("吃金币、激光、开门、受击...")
        form.addRow("AI 描述", self.ai_prompt_edit)

        ai_row = QHBoxLayout()
        self.ai_generate_button = QPushButton("AI 生成")
        self.ai_generate_button.setProperty("primaryAction", True)
        self.ai_generate_button.clicked.connect(self.request_ai_generation)
        self.ai_status_label = QLabel("")
        ai_row.addWidget(self.ai_generate_button)
        ai_row.addWidget(self.ai_status_label, 1)
        form.addRow("", ai_row)

        self.note_table = QTableWidget(0, len(NOTE_COLUMNS))
        self.note_table.setHorizontalHeaderLabels(NOTE_COLUMNS)
        self.note_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.note_table.setAlternatingRowColors(True)
        self.note_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.note_table.verticalHeader().setVisible(False)
        for column in range(4, len(NOTE_COLUMNS)):
            self.note_table.hideColumn(column)
        self.note_table.setMinimumHeight(120)
        self.note_table.itemSelectionChanged.connect(self._sync_detail_from_selected_row)
        self.note_table.itemChanged.connect(lambda _item: self._sync_detail_from_selected_row())
        layout.addWidget(self.note_table, 1)

        note_buttons = QHBoxLayout()
        add_button = QPushButton("添加音符")
        remove_button = QPushButton("移除音符")
        add_button.clicked.connect(self.add_note_row)
        remove_button.clicked.connect(self.remove_selected_note_rows)
        note_buttons.addWidget(add_button)
        note_buttons.addWidget(remove_button)
        note_buttons.addStretch()
        layout.addLayout(note_buttons)

        detail_title = QLabel("选中音符")
        layout.addWidget(detail_title)

        detail_grid = QGridLayout()
        self.note_detail_grid = detail_grid
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(6)
        layout.addLayout(detail_grid)

        self.pitch_spin = QSpinBox()
        self.pitch_spin.setRange(0, 127)
        detail_grid.addWidget(QLabel("音高"), 0, 0)
        detail_grid.addWidget(self.pitch_spin, 0, 1)

        self.note_start_spin = QDoubleSpinBox()
        self.note_start_spin.setRange(0.0, 9999.0)
        self.note_start_spin.setDecimals(3)
        self.note_start_spin.setSingleStep(0.05)
        detail_grid.addWidget(QLabel("起始"), 0, 2)
        detail_grid.addWidget(self.note_start_spin, 0, 3)

        self.note_duration_spin = QDoubleSpinBox()
        self.note_duration_spin.setRange(0.01, 64.0)
        self.note_duration_spin.setDecimals(3)
        self.note_duration_spin.setSingleStep(0.05)
        detail_grid.addWidget(QLabel("时值"), 1, 0)
        detail_grid.addWidget(self.note_duration_spin, 1, 1)

        self.velocity_spin = QSpinBox()
        self.velocity_spin.setRange(0, 127)
        detail_grid.addWidget(QLabel("力度"), 1, 2)
        detail_grid.addWidget(self.velocity_spin, 1, 3)

        self.waveform_combo = QComboBox()
        for waveform in WaveformType:
            self.waveform_combo.addItem(
                WAVEFORM_DISPLAY_LABELS.get(waveform, waveform.value),
                waveform.value,
            )
        detail_grid.addWidget(QLabel("波形"), 2, 0)
        detail_grid.addWidget(self.waveform_combo, 2, 1)

        self.duty_spin = QDoubleSpinBox()
        self.duty_spin.setRange(0.05, 0.95)
        self.duty_spin.setDecimals(2)
        self.duty_spin.setSingleStep(0.05)
        detail_grid.addWidget(QLabel("占空比"), 2, 2)
        detail_grid.addWidget(self.duty_spin, 2, 3)

        self.attack_spin = QDoubleSpinBox()
        self.attack_spin.setRange(0.0, 4.0)
        self.attack_spin.setDecimals(3)
        self.attack_spin.setSingleStep(0.005)
        detail_grid.addWidget(QLabel("起音"), 3, 0)
        detail_grid.addWidget(self.attack_spin, 3, 1)

        self.decay_spin = QDoubleSpinBox()
        self.decay_spin.setRange(0.0, 4.0)
        self.decay_spin.setDecimals(3)
        self.decay_spin.setSingleStep(0.005)
        detail_grid.addWidget(QLabel("衰减"), 3, 2)
        detail_grid.addWidget(self.decay_spin, 3, 3)

        self.sustain_spin = QDoubleSpinBox()
        self.sustain_spin.setRange(0.0, 1.0)
        self.sustain_spin.setDecimals(3)
        self.sustain_spin.setSingleStep(0.05)
        detail_grid.addWidget(QLabel("保持"), 4, 0)
        detail_grid.addWidget(self.sustain_spin, 4, 1)

        self.release_spin = QDoubleSpinBox()
        self.release_spin.setRange(0.0, 4.0)
        self.release_spin.setDecimals(3)
        self.release_spin.setSingleStep(0.005)
        detail_grid.addWidget(QLabel("释音"), 4, 2)
        detail_grid.addWidget(self.release_spin, 4, 3)
        detail_grid.setColumnStretch(1, 1)
        detail_grid.setColumnStretch(3, 1)

        self._detail_widgets = (
            self.pitch_spin,
            self.note_start_spin,
            self.note_duration_spin,
            self.velocity_spin,
            self.waveform_combo,
            self.duty_spin,
            self.attack_spin,
            self.decay_spin,
            self.sustain_spin,
            self.release_spin,
        )
        for widget in self._detail_widgets:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(
                    lambda _index: self._write_detail_to_selected_row()
                )
            else:
                widget.valueChanged.connect(lambda _value: self._write_detail_to_selected_row())

        self.insert_button = QPushButton("插入音效")
        self.insert_button.setProperty("primaryAction", True)
        layout.addWidget(self.insert_button)

        self._load_spec(self._spec)

    def _load_selected_preset(self, *_args) -> None:
        self._load_spec(build_sfx_spec(str(self.preset_combo.currentData())))

    def _load_spec(self, spec: SfxSpec) -> None:
        self._spec = spec
        self.label_edit.setText(spec.label)
        self._updating_note_detail = True
        self.note_table.setRowCount(0)
        for note in spec.notes:
            self.add_note_row(note, select=False)
        self._updating_note_detail = False
        if self.note_table.rowCount():
            self.note_table.selectRow(0)
        self._sync_detail_from_selected_row()

    def add_note_row(self, note: SfxNoteSpec | None = None, *, select: bool = True) -> None:
        if not isinstance(note, SfxNoteSpec):
            note = None
        note = note or SfxNoteSpec(84, 0.0, 0.1)
        row = self.note_table.rowCount()
        self.note_table.insertRow(row)
        values = [
            note.pitch,
            note.start_beat,
            note.duration_beats,
            note.velocity,
            note.waveform.value,
            note.duty_cycle,
            note.adsr.attack,
            note.adsr.decay,
            note.adsr.sustain,
            note.adsr.release,
        ]
        for column, value in enumerate(values):
            self.note_table.setItem(row, column, _number_item(value))
        if select:
            self.note_table.selectRow(row)
            self._sync_detail_from_selected_row()

    def remove_selected_note_rows(self) -> None:
        rows = sorted({index.row() for index in self.note_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.note_table.removeRow(row)
        if self.note_table.rowCount():
            self.note_table.selectRow(min(rows[-1] if rows else 0, self.note_table.rowCount() - 1))
        self._sync_detail_from_selected_row()

    def selected_kind(self) -> str:
        return str(self._spec.kind)

    def start_beat(self) -> float:
        return float(self.start_beat_spin.value())

    def auto_preview(self) -> bool:
        return bool(self.auto_preview_checkbox.isChecked())

    def spec(self) -> SfxSpec:
        notes = []
        for row in range(self.note_table.rowCount()):
            notes.append(self._note_from_row(row))
        if not notes:
            raise ValueError("音效至少需要一个音符")
        label = self.label_edit.text().strip() or "自定义音效"
        return SfxSpec(
            kind=self.selected_kind(),
            label=label,
            notes=tuple(notes),
            filter_params=self._spec.filter_params,
            delay_params=self._spec.delay_params,
            tremolo_params=self._spec.tremolo_params,
            vibrato_params=self._spec.vibrato_params,
        )

    def apply_ai_spec(self, spec: SfxSpec) -> None:
        self._load_spec(spec)
        index = self.preset_combo.findData(spec.kind)
        if index >= 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(index)
            self.preset_combo.blockSignals(False)

    def request_ai_generation(self) -> None:
        self.ai_status_label.setText("AI 生成由主窗口处理")

    def ai_prompt(self) -> str:
        return self.ai_prompt_edit.toPlainText().strip()

    def show_ai_error(self, message: str) -> None:
        self.ai_status_label.setText("")
        self.ai_generate_button.setEnabled(True)
        QMessageBox.warning(self, "SFX AI", message)

    def set_ai_busy(self, busy: bool) -> None:
        self.ai_generate_button.setEnabled(not busy)
        self.ai_status_label.setText("生成中..." if busy else "")

    def _note_from_row(self, row: int) -> SfxNoteSpec:
        def text(column: int) -> str:
            item = self.note_table.item(row, column)
            return item.text().strip() if item else ""

        try:
            waveform = WaveformType(text(4) or WaveformType.SQUARE.value)
        except ValueError:
            waveform = WaveformType.SQUARE
        return SfxNoteSpec(
            pitch=max(0, min(127, int(float(text(0) or 84)))),
            start_beat=max(0.0, float(text(1) or 0.0)),
            duration_beats=max(0.01, float(text(2) or 0.1)),
            velocity=max(0, min(127, int(float(text(3) or 110)))),
            waveform=waveform,
            duty_cycle=max(0.05, min(0.95, float(text(5) or 0.5))),
            adsr=ADSRParams(
                attack=max(0.0, float(text(6) or 0.002)),
                decay=max(0.0, float(text(7) or 0.04)),
                sustain=max(0.0, min(1.0, float(text(8) or 0.25))),
                release=max(0.0, float(text(9) or 0.03)),
            ),
        )

    def _sync_detail_from_selected_row(self) -> None:
        if self._updating_note_detail:
            return
        row = self.note_table.currentRow()
        enabled = row >= 0 and row < self.note_table.rowCount()
        for widget in getattr(self, "_detail_widgets", ()):
            widget.setEnabled(enabled)
        if not enabled:
            return

        note = self._note_from_row(row)
        self._updating_note_detail = True
        try:
            self.pitch_spin.setValue(note.pitch)
            self.note_start_spin.setValue(note.start_beat)
            self.note_duration_spin.setValue(note.duration_beats)
            self.velocity_spin.setValue(note.velocity)
            waveform_index = self.waveform_combo.findData(note.waveform.value)
            self.waveform_combo.setCurrentIndex(max(0, waveform_index))
            self.duty_spin.setValue(note.duty_cycle)
            self.attack_spin.setValue(note.adsr.attack)
            self.decay_spin.setValue(note.adsr.decay)
            self.sustain_spin.setValue(note.adsr.sustain)
            self.release_spin.setValue(note.adsr.release)
        finally:
            self._updating_note_detail = False

    def _write_detail_to_selected_row(self) -> None:
        if self._updating_note_detail:
            return
        row = self.note_table.currentRow()
        if row < 0 or row >= self.note_table.rowCount():
            return

        values = (
            self.pitch_spin.value(),
            self.note_start_spin.value(),
            self.note_duration_spin.value(),
            self.velocity_spin.value(),
            self.waveform_combo.currentData() or WaveformType.SQUARE.value,
            self.duty_spin.value(),
            self.attack_spin.value(),
            self.decay_spin.value(),
            self.sustain_spin.value(),
            self.release_spin.value(),
        )
        self._updating_note_detail = True
        try:
            for column, value in enumerate(values):
                item = self.note_table.item(row, column)
                if item is None:
                    self.note_table.setItem(row, column, _number_item(value))
                else:
                    item.setText(_format_number(value))
        finally:
            self._updating_note_detail = False


class SfxEditorDialog(QDialog):
    """Dialog wrapper kept for compatibility with older call sites."""

    def __init__(self, parent=None, *, start_beat: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("音效编辑器")
        self.setMinimumWidth(860)
        layout = QVBoxLayout(self)
        self.editor = SfxEditorWidget(self, start_beat=start_beat)
        layout.addWidget(self.editor)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.preset_combo = self.editor.preset_combo
        self.auto_preview_checkbox = self.editor.auto_preview_checkbox
        self.note_table = self.editor.note_table
        self.ai_generate_button = self.editor.ai_generate_button

    def __getattr__(self, name: str):
        editor = self.__dict__.get("editor")
        if editor is not None and hasattr(editor, name):
            return getattr(editor, name)
        raise AttributeError(name)


__all__ = ["SfxEditorDialog", "SfxEditorWidget"]
