"""
Seed 风格参数面板。
"""

import json
import sys

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import ADSRParams, Project, WaveformType
from core.seed_style_catalog import (
    SeedMusicStyle,
    StyleParams,
    get_style_meta,
    get_style_params,
    get_style_variants,
    set_style_runtime_override,
)
from ui.error_utils import show_error_with_console


class StyleParamsWidget(QWidget):
    """
    右侧 Dock 中用于展示和调整当前 Seed 风格参数的面板。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.settings = QSettings("8bit", "MusicMaker")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        self.summary_label = QLabel("尚未使用 Seed 生成项目。")
        self.summary_label.setWordWrap(True)
        font = self.summary_label.font()
        font.setPointSize(max(9, font.pointSize() - 1))
        self.summary_label.setFont(font)
        main_layout.addWidget(self.summary_label)

        preset_layout = QVBoxLayout()
        preset_layout.setContentsMargins(0, 4, 0, 4)

        preset_row_top = QHBoxLayout()
        preset_label = QLabel("预设：")
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(160)
        preset_row_top.addWidget(preset_label)
        preset_row_top.addWidget(self.preset_combo, 1)
        preset_layout.addLayout(preset_row_top)

        preset_row_bottom = QHBoxLayout()
        self.load_preset_button = QPushButton("加载预设")
        self.save_preset_button = QPushButton("保存为预设")
        preset_row_bottom.addStretch(1)
        preset_row_bottom.addWidget(self.load_preset_button)
        preset_row_bottom.addWidget(self.save_preset_button)
        preset_layout.addLayout(preset_row_bottom)

        main_layout.addLayout(preset_layout)

        self._current_style = None
        self._current_variant = None
        self._current_presets = {}

        self.melody_wave_combo = QComboBox()
        self.melody_duty_spin = QDoubleSpinBox()
        self.melody_duty_spin.setRange(0.05, 0.95)
        self.melody_duty_spin.setSingleStep(0.05)
        self.melody_duty_spin.setDecimals(2)
        self.melody_a_spin = QDoubleSpinBox()
        self.melody_d_spin = QDoubleSpinBox()
        self.melody_s_spin = QDoubleSpinBox()
        self.melody_r_spin = QDoubleSpinBox()

        self._init_adsr_spin(self.melody_a_spin, 0.0, 0.2, 0.001)
        self._init_adsr_spin(self.melody_d_spin, 0.0, 0.5, 0.01)
        self._init_adsr_spin(self.melody_s_spin, 0.0, 1.0, 0.05)
        self._init_adsr_spin(self.melody_r_spin, 0.0, 0.8, 0.01)
        self._init_wave_combo(self.melody_wave_combo)

        main_layout.addWidget(
            self._build_group(
                "主旋律",
                self.melody_wave_combo,
                self.melody_duty_spin,
                self.melody_a_spin,
                self.melody_d_spin,
                self.melody_s_spin,
                self.melody_r_spin,
            )
        )

        self.bass_wave_combo = QComboBox()
        self.bass_duty_spin = QDoubleSpinBox()
        self.bass_duty_spin.setRange(0.05, 0.95)
        self.bass_duty_spin.setSingleStep(0.05)
        self.bass_duty_spin.setDecimals(2)
        self.bass_a_spin = QDoubleSpinBox()
        self.bass_d_spin = QDoubleSpinBox()
        self.bass_s_spin = QDoubleSpinBox()
        self.bass_r_spin = QDoubleSpinBox()

        self._init_adsr_spin(self.bass_a_spin, 0.0, 0.2, 0.001)
        self._init_adsr_spin(self.bass_d_spin, 0.0, 0.5, 0.01)
        self._init_adsr_spin(self.bass_s_spin, 0.0, 1.0, 0.05)
        self._init_adsr_spin(self.bass_r_spin, 0.0, 0.8, 0.01)
        self._init_wave_combo(self.bass_wave_combo)

        main_layout.addWidget(
            self._build_group(
                "低音",
                self.bass_wave_combo,
                self.bass_duty_spin,
                self.bass_a_spin,
                self.bass_d_spin,
                self.bass_s_spin,
                self.bass_r_spin,
            )
        )

        self.harmony_wave_combo = QComboBox()
        self.harmony_duty_spin = QDoubleSpinBox()
        self.harmony_duty_spin.setRange(0.05, 0.95)
        self.harmony_duty_spin.setSingleStep(0.05)
        self.harmony_duty_spin.setDecimals(2)
        self.harmony_a_spin = QDoubleSpinBox()
        self.harmony_d_spin = QDoubleSpinBox()
        self.harmony_s_spin = QDoubleSpinBox()
        self.harmony_r_spin = QDoubleSpinBox()

        self._init_adsr_spin(self.harmony_a_spin, 0.0, 0.3, 0.001)
        self._init_adsr_spin(self.harmony_d_spin, 0.0, 0.6, 0.01)
        self._init_adsr_spin(self.harmony_s_spin, 0.0, 1.0, 0.05)
        self._init_adsr_spin(self.harmony_r_spin, 0.0, 1.0, 0.01)
        self._init_wave_combo(self.harmony_wave_combo)

        main_layout.addWidget(
            self._build_group(
                "和声",
                self.harmony_wave_combo,
                self.harmony_duty_spin,
                self.harmony_a_spin,
                self.harmony_d_spin,
                self.harmony_s_spin,
                self.harmony_r_spin,
            )
        )

        self.drum_scale_spin = QDoubleSpinBox()
        self.drum_scale_spin.setRange(0.3, 1.7)
        self.drum_scale_spin.setSingleStep(0.05)
        self.drum_scale_spin.setDecimals(2)
        drum_group = QGroupBox("鼓点整体")
        drum_layout = QFormLayout(drum_group)
        drum_layout.setContentsMargins(6, 4, 6, 4)
        self.drum_scale_label = QLabel("整体力度缩放：")
        drum_layout.addRow(self.drum_scale_label, self.drum_scale_spin)
        main_layout.addWidget(drum_group)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 4, 0, 0)
        self.apply_button = QPushButton("应用到当前风格")
        btn_row.addWidget(self.apply_button)
        btn_row.addStretch(1)
        main_layout.addLayout(btn_row)

        main_layout.addStretch(1)

        self._style_name_map = {
            SeedMusicStyle.CLASSIC_8BIT: "经典 8bit",
            SeedMusicStyle.LOFI: "Lofi",
            SeedMusicStyle.BATTLE: "战斗 / 紧张",
            SeedMusicStyle.SUSPENSE: "悬疑 / 惊悚",
            SeedMusicStyle.DANCE: "慢摇 / 舞曲",
            SeedMusicStyle.CALM: "舒缓 / 美好",
            SeedMusicStyle.ROCK: "重金属 / 摇滚",
            SeedMusicStyle.WORKSHOP: "工作坊 / 专注",
        }

        app = QApplication.instance()
        if app is not None:
            base_font = app.font()
            for widget in (
                self.load_preset_button,
                self.save_preset_button,
                self.apply_button,
                self.preset_combo,
                self.melody_wave_combo,
                self.bass_wave_combo,
                self.harmony_wave_combo,
            ):
                widget.setFont(base_font)

        self.apply_button.clicked.connect(self.apply_to_current_style)
        self.save_preset_button.clicked.connect(self.save_current_as_preset)
        self.load_preset_button.clicked.connect(self.load_selected_preset)

    def _init_wave_combo(self, combo: QComboBox):
        combo.clear()
        combo.addItem("方波", WaveformType.SQUARE)
        combo.addItem("三角波", WaveformType.TRIANGLE)
        combo.addItem("锯齿波", WaveformType.SAWTOOTH)
        if hasattr(WaveformType, "SINE"):
            combo.addItem("正弦波", WaveformType.SINE)
        combo.addItem("噪声", WaveformType.NOISE)

    def _init_adsr_spin(self, spin: QDoubleSpinBox, minimum: float, maximum: float, step: float):
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(3)

    def _build_group(
        self,
        title: str,
        wave_combo: QComboBox,
        duty_spin: QDoubleSpinBox,
        a_spin: QDoubleSpinBox,
        d_spin: QDoubleSpinBox,
        s_spin: QDoubleSpinBox,
        r_spin: QDoubleSpinBox,
    ) -> QGroupBox:
        box = QGroupBox(title)
        layout = QFormLayout(box)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.addRow(QLabel("波形："), wave_combo)
        layout.addRow(QLabel("占空比："), duty_spin)
        layout.addRow(QLabel("Attack："), a_spin)
        layout.addRow(QLabel("Decay："), d_spin)
        layout.addRow(QLabel("Sustain："), s_spin)
        layout.addRow(QLabel("Release："), r_spin)
        return box

    def _waveform_to_text(self, waveform: WaveformType) -> str:
        name = getattr(waveform, "name", str(waveform))
        mapping = {
            "SQUARE": "方波",
            "TRIANGLE": "三角波",
            "SAWTOOTH": "锯齿波",
            "SINE": "正弦波",
            "NOISE": "噪声",
        }
        return mapping.get(name, name)

    def _adsr_to_text(self, adsr) -> str:
        return (
            f"A={adsr.attack:.3f}, D={adsr.decay:.3f}, "
            f"S={adsr.sustain:.2f}, R={adsr.release:.3f}"
        )

    def set_style(self, style: SeedMusicStyle, variant_id: str, project: Project):
        """
        根据当前 Seed 生成结果更新显示。
        """
        self._current_style = style
        self._current_variant = variant_id

        if style is None:
            self.summary_label.setText("当前项目不是通过 Seed 生成，暂无风格参数可展示。")
            for spin in (
                self.melody_duty_spin,
                self.melody_a_spin,
                self.melody_d_spin,
                self.melody_s_spin,
                self.melody_r_spin,
                self.bass_duty_spin,
                self.bass_a_spin,
                self.bass_d_spin,
                self.bass_s_spin,
                self.bass_r_spin,
                self.harmony_duty_spin,
                self.harmony_a_spin,
                self.harmony_d_spin,
                self.harmony_s_spin,
                self.harmony_r_spin,
                self.drum_scale_spin,
            ):
                spin.setValue(0.0)
            return

        meta = get_style_meta(style)
        params = get_style_params(style)
        style_name = self._style_name_map.get(style, style.name)

        variant_name = ""
        variant_desc = ""
        try:
            variants = get_style_variants(style)
            for variant in variants:
                if variant.get("id") == variant_id:
                    variant_name = variant.get("name", "")
                    variant_desc = variant.get("desc", "")
                    break
        except Exception:
            pass

        bpm = getattr(project, "bpm", meta.get("default_bpm", ""))
        mood = meta.get("mood", "")
        desc = meta.get("short_desc", "")

        lines = [f"风格：{style_name}"]
        if variant_name:
            lines.append(f"变体：{variant_name}")
        if bpm:
            lines.append(f"BPM：{int(bpm)}")
        if mood:
            lines.append(f"情绪：{mood}")
        if desc:
            lines.append(f"说明：{desc}")
        if variant_desc:
            lines.append(f"变体说明：{variant_desc}")

        self.summary_label.setText("\n".join(lines))
        self._load_presets_for_style(style)
        self._apply_params_to_controls(params)

    def _set_waveform_combo(self, combo: QComboBox, waveform: WaveformType):
        for index in range(combo.count()):
            if combo.itemData(index) == waveform:
                combo.setCurrentIndex(index)
                return

    def _apply_params_to_controls(self, params: StyleParams):
        self._set_waveform_combo(self.melody_wave_combo, params.melody_waveform)
        self.melody_duty_spin.setValue(float(params.melody_duty))
        self.melody_a_spin.setValue(float(params.melody_adsr.attack))
        self.melody_d_spin.setValue(float(params.melody_adsr.decay))
        self.melody_s_spin.setValue(float(params.melody_adsr.sustain))
        self.melody_r_spin.setValue(float(params.melody_adsr.release))

        self._set_waveform_combo(self.bass_wave_combo, params.bass_waveform)
        self.bass_duty_spin.setValue(float(params.bass_duty))
        self.bass_a_spin.setValue(float(params.bass_adsr.attack))
        self.bass_d_spin.setValue(float(params.bass_adsr.decay))
        self.bass_s_spin.setValue(float(params.bass_adsr.sustain))
        self.bass_r_spin.setValue(float(params.bass_adsr.release))

        self._set_waveform_combo(self.harmony_wave_combo, params.harmony_waveform)
        self.harmony_duty_spin.setValue(float(params.harmony_duty))
        self.harmony_a_spin.setValue(float(params.harmony_adsr.attack))
        self.harmony_d_spin.setValue(float(params.harmony_adsr.decay))
        self.harmony_s_spin.setValue(float(params.harmony_adsr.sustain))
        self.harmony_r_spin.setValue(float(params.harmony_adsr.release))

        self.drum_scale_spin.setValue(float(params.drum_velocity_scale))

    def _collect_params(self) -> StyleParams:
        melody_adsr = ADSRParams(
            attack=float(self.melody_a_spin.value()),
            decay=float(self.melody_d_spin.value()),
            sustain=float(self.melody_s_spin.value()),
            release=float(self.melody_r_spin.value()),
        )
        bass_adsr = ADSRParams(
            attack=float(self.bass_a_spin.value()),
            decay=float(self.bass_d_spin.value()),
            sustain=float(self.bass_s_spin.value()),
            release=float(self.bass_r_spin.value()),
        )
        harmony_adsr = ADSRParams(
            attack=float(self.harmony_a_spin.value()),
            decay=float(self.harmony_d_spin.value()),
            sustain=float(self.harmony_s_spin.value()),
            release=float(self.harmony_r_spin.value()),
        )

        return StyleParams(
            melody_waveform=self.melody_wave_combo.currentData(),
            melody_duty=float(self.melody_duty_spin.value()),
            melody_adsr=melody_adsr,
            bass_waveform=self.bass_wave_combo.currentData(),
            bass_duty=float(self.bass_duty_spin.value()),
            bass_adsr=bass_adsr,
            harmony_waveform=self.harmony_wave_combo.currentData(),
            harmony_duty=float(self.harmony_duty_spin.value()),
            harmony_adsr=harmony_adsr,
            drum_velocity_scale=float(self.drum_scale_spin.value()),
        )

    def apply_to_current_style(self):
        """
        将当前面板上的参数应用到当前 Seed 风格。
        """
        if self._current_style is None:
            QMessageBox.information(self, "提示", "请先使用 Seed 生成一段音乐，再调整风格参数。")
            return

        params = self._collect_params()
        try:
            set_style_runtime_override(self._current_style, params)
        except Exception as exc:
            error_msg = f"应用风格参数时出错：{exc}"
            show_error_with_console(self, "应用失败", error_msg, "critical", exc_info=sys.exc_info())
            return

        QMessageBox.information(
            self,
            "已应用",
            "已将当前参数应用到该风格。之后的 Seed 生成将使用这些参数。",
        )

    def _preset_settings_key(self, style: SeedMusicStyle) -> str:
        return f"seed_style_presets/{style.value}"

    def _load_presets_for_style(self, style: SeedMusicStyle):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self._current_presets = {}
        if style is None:
            self.preset_combo.addItem("（无风格）", None)
            self.preset_combo.blockSignals(False)
            return

        raw = self.settings.value(self._preset_settings_key(style), "", type=str)
        if raw:
            try:
                self._current_presets = json.loads(raw)
            except Exception:
                self._current_presets = {}

        self.preset_combo.addItem("（当前默认参数）", None)
        for name in self._current_presets.keys():
            self.preset_combo.addItem(name, name)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

    def _save_presets_for_style(self, style: SeedMusicStyle):
        if style is None:
            return

        try:
            raw = json.dumps(self._current_presets)
        except Exception:
            return

        self.settings.setValue(self._preset_settings_key(style), raw)

    def _params_to_dict(self, params: StyleParams) -> dict:
        return {
            "melody_waveform": getattr(params.melody_waveform, "name", str(params.melody_waveform)),
            "melody_duty": float(params.melody_duty),
            "melody_adsr": {
                "a": float(params.melody_adsr.attack),
                "d": float(params.melody_adsr.decay),
                "s": float(params.melody_adsr.sustain),
                "r": float(params.melody_adsr.release),
            },
            "bass_waveform": getattr(params.bass_waveform, "name", str(params.bass_waveform)),
            "bass_duty": float(params.bass_duty),
            "bass_adsr": {
                "a": float(params.bass_adsr.attack),
                "d": float(params.bass_adsr.decay),
                "s": float(params.bass_adsr.sustain),
                "r": float(params.bass_adsr.release),
            },
            "harmony_waveform": getattr(params.harmony_waveform, "name", str(params.harmony_waveform)),
            "harmony_duty": float(params.harmony_duty),
            "harmony_adsr": {
                "a": float(params.harmony_adsr.attack),
                "d": float(params.harmony_adsr.decay),
                "s": float(params.harmony_adsr.sustain),
                "r": float(params.harmony_adsr.release),
            },
            "drum_velocity_scale": float(params.drum_velocity_scale),
        }

    def _params_from_dict(self, data: dict) -> StyleParams:
        def waveform_from_name(name: str) -> WaveformType:
            if not name:
                return WaveformType.SQUARE
            return getattr(WaveformType, name, WaveformType.SQUARE)

        melody_adsr = ADSRParams(
            attack=float(data.get("melody_adsr", {}).get("a", 0.001)),
            decay=float(data.get("melody_adsr", {}).get("d", 0.05)),
            sustain=float(data.get("melody_adsr", {}).get("s", 0.8)),
            release=float(data.get("melody_adsr", {}).get("r", 0.1)),
        )
        bass_adsr = ADSRParams(
            attack=float(data.get("bass_adsr", {}).get("a", 0.001)),
            decay=float(data.get("bass_adsr", {}).get("d", 0.08)),
            sustain=float(data.get("bass_adsr", {}).get("s", 0.3)),
            release=float(data.get("bass_adsr", {}).get("r", 0.1)),
        )
        harmony_adsr = ADSRParams(
            attack=float(data.get("harmony_adsr", {}).get("a", 0.01)),
            decay=float(data.get("harmony_adsr", {}).get("d", 0.15)),
            sustain=float(data.get("harmony_adsr", {}).get("s", 0.8)),
            release=float(data.get("harmony_adsr", {}).get("r", 0.25)),
        )

        return StyleParams(
            melody_waveform=waveform_from_name(data.get("melody_waveform")),
            melody_duty=float(data.get("melody_duty", 0.5)),
            melody_adsr=melody_adsr,
            bass_waveform=waveform_from_name(data.get("bass_waveform")),
            bass_duty=float(data.get("bass_duty", 0.5)),
            bass_adsr=bass_adsr,
            harmony_waveform=waveform_from_name(data.get("harmony_waveform")),
            harmony_duty=float(data.get("harmony_duty", 0.5)),
            harmony_adsr=harmony_adsr,
            drum_velocity_scale=float(data.get("drum_velocity_scale", 1.0)),
        )

    def save_current_as_preset(self):
        """将当前控件参数保存为当前风格的一个预设。"""
        if self._current_style is None:
            QMessageBox.information(self, "提示", "请先使用 Seed 生成一段音乐，再保存预设。")
            return

        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：")
        if not ok or not name.strip():
            return

        name = name.strip()
        params = self._collect_params()
        self._current_presets[name] = self._params_to_dict(params)
        self._save_presets_for_style(self._current_style)
        self._load_presets_for_style(self._current_style)

        index = self.preset_combo.findData(name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

        QMessageBox.information(self, "已保存", f"已保存预设「{name}」。")

    def load_selected_preset(self):
        """从下拉列表中加载选中的预设到控件。"""
        if self._current_style is None:
            QMessageBox.information(self, "提示", "当前没有可用的 Seed 风格。")
            return

        data_key = self.preset_combo.currentData()
        if data_key is None:
            params = get_style_params(self._current_style)
            self._apply_params_to_controls(params)
            return

        preset_data = self._current_presets.get(data_key)
        if not preset_data:
            QMessageBox.warning(self, "提示", "未找到该预设的数据，可能设置已损坏。")
            return

        try:
            params = self._params_from_dict(preset_data)
        except Exception as exc:
            error_msg = f"解析预设时出错：\n{exc}"
            show_error_with_console(self, "加载失败", error_msg, "critical", exc_info=sys.exc_info())
            return

        self._apply_params_to_controls(params)
