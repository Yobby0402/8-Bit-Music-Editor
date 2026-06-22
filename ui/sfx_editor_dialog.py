"""Small SFX preset parameter dialog."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
)

from core.sfx_generator import SFX_PRESET_LABELS


class SfxEditorDialog(QDialog):
    """Collect preset insertion options from the user."""

    def __init__(self, parent=None, *, start_beat: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("SFX editor")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.preset_combo = QComboBox()
        for kind, label in SFX_PRESET_LABELS.items():
            self.preset_combo.addItem(label, kind)
        form.addRow("Preset", self.preset_combo)

        self.start_beat_spin = QDoubleSpinBox()
        self.start_beat_spin.setRange(0.0, 9999.0)
        self.start_beat_spin.setDecimals(3)
        self.start_beat_spin.setSingleStep(0.25)
        self.start_beat_spin.setValue(max(0.0, float(start_beat)))
        form.addRow("Start beat", self.start_beat_spin)

        self.auto_preview_checkbox = QCheckBox("Auto preview")
        self.auto_preview_checkbox.setChecked(True)
        form.addRow("", self.auto_preview_checkbox)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def selected_kind(self) -> str:
        return str(self.preset_combo.currentData())

    def start_beat(self) -> float:
        return float(self.start_beat_spin.value())

    def auto_preview(self) -> bool:
        return bool(self.auto_preview_checkbox.isChecked())


__all__ = ["SfxEditorDialog"]
