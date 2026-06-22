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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.models import ADSRParams, WaveformType
from core.sfx_generator import (
    SFX_PRESET_LABELS,
    SfxNoteSpec,
    SfxSpec,
    build_sfx_spec,
)

NOTE_COLUMNS = [
    "pitch",
    "start",
    "duration",
    "velocity",
    "waveform",
    "duty",
    "attack",
    "decay",
    "sustain",
    "release",
]


def _number_item(value: float | int) -> QTableWidgetItem:
    item = QTableWidgetItem(str(value))
    item.setTextAlignment(Qt.AlignCenter)
    return item


class SfxEditorDialog(QDialog):
    """Collect and edit an SFX spec before insertion."""

    def __init__(self, parent=None, *, start_beat: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("SFX editor")
        self.setMinimumWidth(860)
        self._spec = build_sfx_spec("coin")
        self._ai_thread = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.preset_combo = QComboBox()
        for kind, label in SFX_PRESET_LABELS.items():
            self.preset_combo.addItem(label, kind)
        self.preset_combo.currentIndexChanged.connect(self._load_selected_preset)
        form.addRow("Preset", self.preset_combo)

        self.label_edit = QLineEdit()
        form.addRow("Label", self.label_edit)

        self.start_beat_spin = QDoubleSpinBox()
        self.start_beat_spin.setRange(0.0, 9999.0)
        self.start_beat_spin.setDecimals(3)
        self.start_beat_spin.setSingleStep(0.25)
        self.start_beat_spin.setValue(max(0.0, float(start_beat)))
        form.addRow("Start beat", self.start_beat_spin)

        self.auto_preview_checkbox = QCheckBox("Auto preview")
        self.auto_preview_checkbox.setChecked(True)
        form.addRow("", self.auto_preview_checkbox)

        self.ai_prompt_edit = QPlainTextEdit()
        self.ai_prompt_edit.setFixedHeight(64)
        self.ai_prompt_edit.setPlaceholderText("coin pickup, laser zap, door open...")
        form.addRow("AI prompt", self.ai_prompt_edit)

        ai_row = QHBoxLayout()
        self.ai_generate_button = QPushButton("AI generate")
        self.ai_generate_button.clicked.connect(self.request_ai_generation)
        self.ai_status_label = QLabel("")
        ai_row.addWidget(self.ai_generate_button)
        ai_row.addWidget(self.ai_status_label, 1)
        form.addRow("", ai_row)

        self.note_table = QTableWidget(0, len(NOTE_COLUMNS))
        self.note_table.setHorizontalHeaderLabels(NOTE_COLUMNS)
        self.note_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.note_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.note_table, 1)

        note_buttons = QHBoxLayout()
        add_button = QPushButton("Add note")
        remove_button = QPushButton("Remove note")
        add_button.clicked.connect(self.add_note_row)
        remove_button.clicked.connect(self.remove_selected_note_rows)
        note_buttons.addWidget(add_button)
        note_buttons.addWidget(remove_button)
        note_buttons.addStretch()
        layout.addLayout(note_buttons)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._load_spec(self._spec)

    def _load_selected_preset(self, *_args) -> None:
        self._load_spec(build_sfx_spec(str(self.preset_combo.currentData())))

    def _load_spec(self, spec: SfxSpec) -> None:
        self._spec = spec
        self.label_edit.setText(spec.label)
        self.note_table.setRowCount(0)
        for note in spec.notes:
            self.add_note_row(note)

    def add_note_row(self, note: SfxNoteSpec | None = None) -> None:
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

    def remove_selected_note_rows(self) -> None:
        rows = sorted({index.row() for index in self.note_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.note_table.removeRow(row)

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
            raise ValueError("SFX needs at least one note")
        label = self.label_edit.text().strip() or "Custom SFX"
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
        self.ai_status_label.setText("AI generation is handled by the main window")

    def ai_prompt(self) -> str:
        return self.ai_prompt_edit.toPlainText().strip()

    def show_ai_error(self, message: str) -> None:
        self.ai_status_label.setText("")
        self.ai_generate_button.setEnabled(True)
        QMessageBox.warning(self, "SFX AI", message)

    def set_ai_busy(self, busy: bool) -> None:
        self.ai_generate_button.setEnabled(not busy)
        self.ai_status_label.setText("Generating..." if busy else "")

    def _note_from_row(self, row: int) -> SfxNoteSpec:
        def text(column: int) -> str:
            item = self.note_table.item(row, column)
            return item.text().strip() if item else ""

        waveform = WaveformType(text(4) or WaveformType.SQUARE.value)
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


__all__ = ["SfxEditorDialog"]
