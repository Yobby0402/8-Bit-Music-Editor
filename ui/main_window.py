"""
主窗口模块

应用程序的主窗口界面。
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QAction,
    QMessageBox, QFileDialog, QSplitter, QDialog,
    QDockWidget, QSlider, QDialogButtonBox, QLabel, QComboBox, QApplication, QDesktopWidget,
    QProgressDialog, QFormLayout, QGroupBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer, QSettings, QEvent
import json
from PyQt5.QtGui import QIcon, QKeySequence, QKeyEvent, QFont, QBrush, QColor
import os

from core.sequencer import Sequencer
from core.models import Project, WaveformType, Track, Note, TrackType, ADSRParams
from core.midi_io import MidiIO
from core.track_events import DrumType, DrumEvent

from ui.unified_editor_widget import UnifiedEditorWidget
from ui.grid_sequence_widget import GridSequenceWidget
from ui.timeline_widget import TimelineWidget
from ui.property_panel_widget import PropertyPanelWidget
from ui.score_library_widget import ScoreLibraryWidget
from ui.metronome_widget import MetronomeWidget
from ui.oscilloscope_widget import OscilloscopeWidget
from ui.theme import theme_manager
from ui.shortcut_manager import get_shortcut_manager
from ui.shortcut_config_dialog import ShortcutConfigDialog
from PyQt5.QtWidgets import QStackedWidget, QTabWidget, QPushButton, QButtonGroup, QSpinBox, QCheckBox
from ui.settings_manager import get_settings_manager
from core.score_library import ScoreLibrary
from core.seed_music_generator import (
    generate_simple_project_from_seed,
    SeedMusicStyle,
    get_style_meta,
    get_style_variants,
    get_style_params,
    StyleParams,
    set_style_runtime_override,
)


class StyleParamsWidget(QWidget):
    """
    右侧 Dock 中用于展示 & 调整当前 Seed 风格参数的面板。
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

        # 预设选择与管理（拆成上下两行，避免在窄窗口中挤在一行重叠）
        preset_layout = QVBoxLayout()
        preset_layout.setContentsMargins(0, 4, 0, 4)

        # 第一行：标签 + 下拉框
        preset_row_top = QHBoxLayout()
        preset_label = QLabel("预设：")
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(160)
        preset_row_top.addWidget(preset_label)
        preset_row_top.addWidget(self.preset_combo, 1)
        preset_layout.addLayout(preset_row_top)

        # 第二行：按钮
        preset_row_bottom = QHBoxLayout()
        self.load_preset_button = QPushButton("加载预设")
        self.save_preset_button = QPushButton("保存为预设")
        preset_row_bottom.addStretch(1)
        preset_row_bottom.addWidget(self.load_preset_button)
        preset_row_bottom.addWidget(self.save_preset_button)
        preset_layout.addLayout(preset_row_bottom)

        main_layout.addLayout(preset_layout)

        # 主旋律 / 低音 / 和声 / 鼓点 四个分组（改为可编辑控件）
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

        # 鼓点：只有一个整体缩放
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

        # 操作按钮（这里先预留位置，后续可扩展为“保存预设”等）
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
            SeedMusicStyle.CALM: "舒缓 / 美好",
        }

        # 统一按钮/下拉字体，使用当前应用全局字体，避免与其它区域不一致
        app = QApplication.instance()
        if app is not None:
            base_font = app.font()
            for w in (
                self.load_preset_button,
                self.save_preset_button,
                self.apply_button,
                self.preset_combo,
                self.melody_wave_combo,
                self.bass_wave_combo,
                self.harmony_wave_combo,
            ):
                w.setFont(base_font)

        # 点击“应用到当前风格”时，将当前控件值写回运行时覆盖
        self.apply_button.clicked.connect(self.apply_to_current_style)
        self.save_preset_button.clicked.connect(self.save_current_as_preset)
        self.load_preset_button.clicked.connect(self.load_selected_preset)

    def _init_wave_combo(self, combo: QComboBox):
        combo.clear()
        combo.addItem("方波", WaveformType.SQUARE)
        combo.addItem("三角波", WaveformType.TRIANGLE)
        combo.addItem("锯齿波", WaveformType.SAWTOOTH)
        # 一些环境风格可能会用到正弦波/噪声
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

    def _waveform_to_text(self, wf: WaveformType) -> str:
        name = getattr(wf, "name", str(wf))
        mapping = {
            "SQUARE": "方波",
            "TRIANGLE": "三角波",
            "SAWTOOTH": "锯齿波",
            "SINE": "正弦波",
            "NOISE": "噪声",
        }
        return mapping.get(name, name)

    def _adsr_to_text(self, adsr) -> str:
        return f"A={adsr.attack:.3f}, D={adsr.decay:.3f}, S={adsr.sustain:.2f}, R={adsr.release:.3f}"

    def set_style(self, style: SeedMusicStyle, variant_id: str, project: Project):
        """
        根据当前 Seed 生成结果更新显示（仅展示参数，不修改任何逻辑）。
        """
        self._current_style = style
        self._current_variant = variant_id

        if style is None:
            self.summary_label.setText("当前项目不是通过 Seed 生成，暂无风格参数可展示。")
            # 清空控件显示
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

        # 变体名称/说明
        variant_name = ""
        variant_desc = ""
        try:
            variants = get_style_variants(style)
            for v in variants:
                if v.get("id") == variant_id:
                    variant_name = v.get("name", "")
                    variant_desc = v.get("desc", "")
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

        # 刷新当前风格下的预设列表
        self._load_presets_for_style(style)

        self._apply_params_to_controls(params)

    def _set_waveform_combo(self, combo: QComboBox, wf: WaveformType):
        for i in range(combo.count()):
            if combo.itemData(i) == wf:
                combo.setCurrentIndex(i)
                return

    def _apply_params_to_controls(self, params: StyleParams):
        # 主旋律控件
        self._set_waveform_combo(self.melody_wave_combo, params.melody_waveform)
        self.melody_duty_spin.setValue(float(params.melody_duty))
        self.melody_a_spin.setValue(float(params.melody_adsr.attack))
        self.melody_d_spin.setValue(float(params.melody_adsr.decay))
        self.melody_s_spin.setValue(float(params.melody_adsr.sustain))
        self.melody_r_spin.setValue(float(params.melody_adsr.release))

        # 低音控件
        self._set_waveform_combo(self.bass_wave_combo, params.bass_waveform)
        self.bass_duty_spin.setValue(float(params.bass_duty))
        self.bass_a_spin.setValue(float(params.bass_adsr.attack))
        self.bass_d_spin.setValue(float(params.bass_adsr.decay))
        self.bass_s_spin.setValue(float(params.bass_adsr.sustain))
        self.bass_r_spin.setValue(float(params.bass_adsr.release))

        # 和声控件
        self._set_waveform_combo(self.harmony_wave_combo, params.harmony_waveform)
        self.harmony_duty_spin.setValue(float(params.harmony_duty))
        self.harmony_a_spin.setValue(float(params.harmony_adsr.attack))
        self.harmony_d_spin.setValue(float(params.harmony_adsr.decay))
        self.harmony_s_spin.setValue(float(params.harmony_adsr.sustain))
        self.harmony_r_spin.setValue(float(params.harmony_adsr.release))

        # 鼓点整体
        self.drum_scale_spin.setValue(float(params.drum_velocity_scale))

    def _collect_params(self) -> StyleParams:
        """
        从当前控件中采集出一份 StyleParams，用于覆盖当前风格。
        """
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

        params = StyleParams(
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
        return params

    def apply_to_current_style(self):
        """
        将当前面板上的参数应用到当前 Seed 风格：
        - 通过 set_style_runtime_override 覆盖运行时参数；
        - 之后再生成 Seed 音乐时，会按照新的音色/ADSR/鼓力度生成。
        """
        if self._current_style is None:
            QMessageBox.information(self, "提示", "请先使用 Seed 生成一段音乐，再调整风格参数。")
            return
        params = self._collect_params()
        try:
            set_style_runtime_override(self._current_style, params)
        except Exception as e:
            QMessageBox.critical(self, "应用失败", f"应用风格参数时出错：{e}")
            return
        QMessageBox.information(self, "已应用", "已将当前参数应用到该风格。之后的 Seed 生成将使用这些参数。")

    # ---- 预设相关 ----

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
        def wf(name: str) -> WaveformType:
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
            melody_waveform=wf(data.get("melody_waveform")),
            melody_duty=float(data.get("melody_duty", 0.5)),
            melody_adsr=melody_adsr,
            bass_waveform=wf(data.get("bass_waveform")),
            bass_duty=float(data.get("bass_duty", 0.5)),
            bass_adsr=bass_adsr,
            harmony_waveform=wf(data.get("harmony_waveform")),
            harmony_duty=float(data.get("harmony_duty", 0.5)),
            harmony_adsr=harmony_adsr,
            drum_velocity_scale=float(data.get("drum_velocity_scale", 1.0)),
        )

    def save_current_as_preset(self):
        """将当前控件参数保存为当前风格的一个预设（持久化到 QSettings）"""
        if self._current_style is None:
            QMessageBox.information(self, "提示", "请先使用 Seed 生成一段音乐，再保存预设。")
            return
        from PyQt5.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "保存预设", "预设名称：")
        if not ok or not name.strip():
            return
        name = name.strip()
        params = self._collect_params()
        self._current_presets[name] = self._params_to_dict(params)
        self._save_presets_for_style(self._current_style)
        # 刷新下拉列表并选中新预设
        self._load_presets_for_style(self._current_style)
        index = self.preset_combo.findData(name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

        QMessageBox.information(self, "已保存", f"已保存预设「{name}」。")

    def load_selected_preset(self):
        """从下拉列表中加载选中的预设到控件（不自动应用到运行时覆盖）"""
        if self._current_style is None:
            QMessageBox.information(self, "提示", "当前没有可用的 Seed 风格。")
            return
        data_key = self.preset_combo.currentData()
        if data_key is None:
            # 选中的是“当前默认参数”占位项，则回到默认 StyleParams
            params = get_style_params(self._current_style)
            self._apply_params_to_controls(params)
            return
        preset_data = self._current_presets.get(data_key)
        if not preset_data:
            QMessageBox.warning(self, "提示", "未找到该预设的数据，可能设置已损坏。")
            return
        try:
            params = self._params_from_dict(preset_data)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"解析预设时出错：\n{e}")
            return
        self._apply_params_to_controls(params)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        self.sequencer = Sequencer()
        self.current_file_path = None  # 当前打开的文件路径
        self.current_midi_file_path = None  # 当前导入的MIDI文件路径
        # 当前 Seed 生成的风格及变体（用于风格参数面板）
        self.current_seed_style = None
        self.current_seed_variant = None
        
        # 初始化设置管理器（用于保存/读取设置）
        self.settings = QSettings("8bit", "MusicMaker")
        
        # 初始化快捷键管理器
        self.shortcut_manager = get_shortcut_manager()
        # 设置管理器
        self.settings_manager = get_settings_manager()
        # 乐谱片段库
        self.score_library = ScoreLibrary()
        
        # 右侧 Dock 面板当前锁定宽度（属性 / 乐谱），在 init_ui 中初始化
        self._right_dock_width = None
        
        self.init_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_shortcuts()
        
        # 定时器用于更新播放状态和播放头（刷新间隔从设置中读取）
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_playback_status)
        # 使用已经初始化好的 settings_manager，避免重复导入和局部变量遮蔽
        self.update_timer.start(self.settings_manager.get_playhead_refresh_interval())
        
        # 播放开始时间（用于计算播放位置）
        self.playback_start_time = None
        self.playback_start_offset = 0.0  # 播放开始时的偏移时间
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("8bit音乐制作器")
        # 使用屏幕尺寸的80%作为默认窗口大小，确保在不同分辨率下都能正常显示
        desktop = QApplication.desktop()
        screen = desktop.screenGeometry()
        default_width = int(screen.width() * 0.8)
        default_height = int(screen.height() * 0.8)
        self.setGeometry(
            int(screen.width() * 0.1),
            int(screen.height() * 0.1),
            default_width,
            default_height
        )
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局（垂直，分为上下两部分）
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)
        
        # ========== 上方：统一编辑器（整合所有功能）==========
        note_selection_area = QWidget()
        # 移除固定高度限制，使用拉伸因子确保各占一半
        note_selection_layout = QHBoxLayout()
        note_selection_layout.setContentsMargins(0, 0, 0, 0)
        note_selection_area.setLayout(note_selection_layout)
        
        # 设置大小策略，确保高度固定
        from PyQt5.QtWidgets import QSizePolicy
        note_selection_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 统一编辑器（包含波形、音轨类型、钢琴键盘、打击乐、拍数）
        self.unified_editor = UnifiedEditorWidget(self.sequencer.get_bpm())
        # 将sequencer的audio_engine传递给预览组件，以便应用主音量
        self.unified_editor.audio_engine = self.sequencer.audio_engine
        if hasattr(self.unified_editor, 'piano_keyboard'):
            self.unified_editor.piano_keyboard.audio_engine = self.sequencer.audio_engine
        note_selection_layout.addWidget(self.unified_editor)
        
        main_layout.addWidget(note_selection_area, 1)  # 拉伸因子1，占一半
        
        # ========== 下方：音轨区域 ==========
        track_area = QWidget()
        track_area_layout = QVBoxLayout()
        track_area_layout.setContentsMargins(0, 0, 0, 0)
        track_area.setLayout(track_area_layout)
        
        # 设置大小策略，确保高度固定
        track_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 上方：播放控制区域
        playback_control_area = QWidget()
        playback_control_layout = QHBoxLayout()
        playback_control_layout.setContentsMargins(8, 6, 8, 6)
        playback_control_layout.setSpacing(8)
        playback_control_area.setLayout(playback_control_layout)
        
        # ========== 左侧：播放控制按钮 ==========
        # 播放按钮组（使用图标，互斥逻辑）
        # 创建按钮组，实现互斥（类似老式录音机）
        self.playback_button_group = QButtonGroup()
        self.playback_button_group.setExclusive(True)  # 互斥模式
        
        # 播放/停止按钮（合并播放和暂停）
        self.play_stop_button = QPushButton("▶")  # 播放图标
        self.play_stop_button.setToolTip("播放/停止")
        self.play_stop_button.setCheckable(False)  # 不可选中（不是切换按钮）
        self.play_stop_button.clicked.connect(self.toggle_play_stop)
        playback_control_layout.addWidget(self.play_stop_button)
        
        self.stop_button = QPushButton("⏹")  # 停止图标
        self.stop_button.setToolTip("停止")
        self.stop_button.setCheckable(False)
        self.stop_button.clicked.connect(self.stop)
        playback_control_layout.addWidget(self.stop_button)
        
        playback_control_layout.addSpacing(16)
        
        # ========== 中间：节拍器和BPM ==========
        # 节拍器
        self.metronome_widget = MetronomeWidget()
        self.metronome_widget.set_bpm(self.sequencer.get_bpm())
        playback_control_layout.addWidget(self.metronome_widget)
        
        playback_control_layout.addSpacing(8)
        
        # BPM控制
        bpm_label = QLabel("BPM:")
        playback_control_layout.addWidget(bpm_label)
        self.bpm_spinbox = QSpinBox()
        self.bpm_spinbox.setRange(30, 300)
        self.bpm_spinbox.setValue(120)
        self.bpm_spinbox.setMinimumWidth(60)
        self.bpm_spinbox.valueChanged.connect(self.on_bpm_changed)
        playback_control_layout.addWidget(self.bpm_spinbox)
        
        # 文件名显示（BPM右侧）
        self.file_name_label = QLabel("")
        self.file_name_label.setMinimumWidth(150)
        self.file_name_label.setMaximumWidth(300)
        self.file_name_label.setToolTip("当前打开的文件")
        playback_control_layout.addWidget(self.file_name_label)
        
        playback_control_layout.addStretch()
        
        # ========== 右侧：视图切换和音量控制 ==========
        # 视图切换（拨动开关样式）
        view_label = QLabel("视图:")
        playback_control_layout.addWidget(view_label)
        
        # 创建拨动开关组件
        from ui.toggle_switch_widget import ToggleSwitchWidget
        self.view_toggle_switch = ToggleSwitchWidget()
        self.view_toggle_switch.setToolTip("切换视图：左侧=序列，右侧=示波器")
        # 连接位置变化信号
        self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
        playback_control_layout.addWidget(self.view_toggle_switch)
        
        playback_control_layout.addSpacing(16)
        
        # 播放音量控制
        volume_label = QLabel("音量:")
        playback_control_layout.addWidget(volume_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        # 实时更新音量（拖动时立即生效）
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_slider.setMinimumWidth(120)
        self.volume_slider.setMaximumWidth(150)
        playback_control_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(40)
        playback_control_layout.addWidget(self.volume_label)
        
        track_area_layout.addWidget(playback_control_area)
        
        # 下方：使用堆叠界面切换视图
        self.view_stack = QStackedWidget()
        
        # 序列编辑器视图
        self.sequence_widget = GridSequenceWidget(self.sequencer.get_bpm())
        self.view_stack.addWidget(self.sequence_widget)
        
        # 示波器视图
        self.oscilloscope_widget = OscilloscopeWidget(
            self.sequencer.audio_engine,
            self.sequencer.get_bpm()
        )
        self.view_stack.addWidget(self.oscilloscope_widget)
        
        # 默认显示序列视图
        self.view_stack.setCurrentIndex(0)
        
        track_area_layout.addWidget(self.view_stack, 1)  # 可拉伸
        
        # 连接序列编辑器中的添加音轨按钮
        self.sequence_widget.add_track_button.clicked.connect(self.on_add_track_clicked)
        
        main_layout.addWidget(track_area, 1)  # 拉伸因子1，占一半
        
        # ========== 属性 / 乐谱 / 风格参数面板：使用浮动窗口（DockWidget）==========
        self.property_dock = QDockWidget("属性面板", self)
        self.property_panel = PropertyPanelWidget()
        self.property_dock.setWidget(self.property_panel)
        self.property_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_dock)
        # 为了避免属性面板从“空状态”到“有控件”时宽度猛然变化，固定一个较为合适的最小宽度，
        # 并默认显示一个空状态文本，这样音轨区域的宽度在使用过程中保持稳定，不会因为选中/取消选中而抖动。
        from PyQt5.QtWidgets import QSizePolicy
        self.property_dock.setMinimumWidth(320)
        # 允许用户手动调整到更宽，但不要因为内容变化自动变窄
        self.property_dock.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        # 默认显示（显示的是“未选中音符”的空状态），避免第一次选中音符时界面突然被挤压
        self.property_dock.setVisible(True)
        # 允许关闭，但可以通过菜单重新打开
        self.property_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)

        # 乐谱面板（乐谱片段库）
        self.score_dock = QDockWidget("乐谱面板", self)
        self.score_panel = ScoreLibraryWidget(self.score_library)
        self.score_dock.setWidget(self.score_panel)
        self.score_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.score_dock)
        # 使乐谱面板与属性面板使用相同的宽度策略，避免在切换 Tab 时右侧区域宽度发生跳变
        self.score_dock.setMinimumWidth(self.property_dock.minimumWidth())
        self.score_dock.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        # 默认不显示，需要时通过菜单显示
        self.score_dock.setVisible(False)
        self.score_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)

        # 风格参数面板（Seed 风格参数预览）
        self.style_dock = QDockWidget("风格参数", self)
        self.style_params_panel = StyleParamsWidget()
        self.style_dock.setWidget(self.style_params_panel)
        self.style_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.style_dock)
        self.style_dock.setMinimumWidth(self.property_dock.minimumWidth())
        self.style_dock.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.style_dock.setVisible(False)
        self.style_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)

        # 将三个面板在右侧堆叠（类似 Altium 的属性面板/其它面板堆叠效果）
        self.tabifyDockWidget(self.property_dock, self.score_dock)
        self.tabifyDockWidget(self.property_dock, self.style_dock)

        # 记录并锁定当前右侧面板宽度，避免在属性/乐谱面板之间切换时自动调整宽度。
        # 注意：这里在 dock 叠放之后再读取宽度，确保是分隔条最终布局后的宽度。
        self._right_dock_width = self.property_dock.width()
        if self._right_dock_width <= 0:
            self._right_dock_width = self.property_dock.minimumWidth()
        self.property_dock.setMinimumWidth(self._right_dock_width)
        self.property_dock.setMaximumWidth(self._right_dock_width)
        self.score_dock.setMinimumWidth(self._right_dock_width)
        self.score_dock.setMaximumWidth(self._right_dock_width)
        self.style_dock.setMinimumWidth(self._right_dock_width)
        self.style_dock.setMaximumWidth(self._right_dock_width)

        # 监听两个 dock 的尺寸变化：当用户手动调整右侧区域宽度时，同步更新锁定宽度，
        # 使属性/乐谱面板在 Tab 之间切换时宽度保持不变，只在用户拖动时才整体改变。
        self.property_dock.installEventFilter(self)
        self.score_dock.installEventFilter(self)
        self.style_dock.installEventFilter(self)

        
        # 连接信号
        self.connect_signals()
        
        # 应用主题
        self.apply_theme()
        
        # 应用显示相关设置（背景/前景色等）
        self.apply_display_settings_from_settings(central_widget, note_selection_area, track_area, playback_control_area)
        
        # 不再自动创建默认音轨（用户需要手动创建）
        # self.init_default_tracks()
        
        # 初始化显示
        self.refresh_ui()

    def eventFilter(self, obj, event):
        """
        统一处理右侧 Dock（属性面板 / 乐谱面板）的宽度锁定逻辑：
        - 用户拖动右侧分隔条时，Dock 会收到 Resize 事件；
        - 这里捕获新的宽度，并同步更新两个 Dock 的 min/maxWidth，
          这样在 Tab 之间切换时就不会自动重新计算大小，右侧区域宽度保持稳定。
        """
        tracked_docks = {getattr(self, "property_dock", None), getattr(self, "score_dock", None), getattr(self, "style_dock", None)}
        if event.type() == QEvent.Resize and obj in tracked_docks:
            new_width = obj.width()
            if new_width > 0 and new_width != self._right_dock_width:
                self._right_dock_width = new_width
                # 同步锁定右侧所有 Dock 的宽度
                for dock in tracked_docks:
                    if dock is not None:
                        dock.setMinimumWidth(new_width)
                        dock.setMaximumWidth(new_width)
        return super().eventFilter(obj, event)
    
    def apply_theme(self):
        """应用主题到所有UI组件"""
        # 使用统一主题应用方法，将所有样式（包括按钮/标签/菜单等）一次性应用到主窗口，
        # 确保按钮字体和风格全局统一。
        theme_manager.apply_to_widget(self)
        
        # 个别子组件仍有自定义逻辑（如示波器需要额外应用主题）
        if hasattr(self, 'oscilloscope_widget'):
            self.oscilloscope_widget.apply_theme()
    
    def apply_display_settings_from_settings(self, central_widget=None, note_selection_area=None,
                                             track_area=None, playback_control_area=None):
        """根据设置管理器应用显示相关设置（背景色/前景色/字体大小）"""
        bg_color = self.settings_manager.get_ui_background_color()
        fg_color = self.settings_manager.get_ui_foreground_color()
        try:
            gradient_enabled = self.settings_manager.is_background_gradient_enabled()
            grad_color2 = self.settings_manager.get_background_gradient_color2()
            grad_mode = self.settings_manager.get_background_gradient_mode()
        except Exception:
            gradient_enabled = False
            grad_color2 = bg_color
            grad_mode = "none"
        
        # 全局字体大小（通过QApplication设置，保证大部分控件生效）
        try:
            app = QApplication.instance()
            if app is not None:
                font = app.font()
                font.setPointSize(self.settings_manager.get_ui_font_size())
                app.setFont(font)
        except Exception as e:
            # 显式打印异常，避免静默失败影响后续布局 / 绘制但又没有任何提示
            import traceback
            print("应用全局字体设置时出错：", e)
            traceback.print_exc()
        
        # 背景色应用到主要区域
        if central_widget is None:
            central_widget = self.centralWidget()
        if central_widget is not None:
            if gradient_enabled and grad_mode != "none":
                # 根据模式构建渐变样式，直接作用在中央部件上，确保肉眼可见
                if grad_mode == "center":
                    bg_image = f"background-image: qradialgradient(cx:0.5, cy:0.5, radius:1, fx:0.5, fy:0.5, stop:0 {bg_color}, stop:1 {grad_color2});"
                elif grad_mode == "top_bottom":
                    bg_image = f"background-image: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bg_color}, stop:1 {grad_color2});"
                elif grad_mode == "bottom_top":
                    bg_image = f"background-image: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 {bg_color}, stop:1 {grad_color2});"
                elif grad_mode == "left_right":
                    bg_image = f"background-image: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {bg_color}, stop:1 {grad_color2});"
                elif grad_mode == "right_left":
                    bg_image = f"background-image: qlineargradient(x1:1, y1:0, x2:0, y2:0, stop:0 {bg_color}, stop:1 {grad_color2});"
                elif grad_mode == "diagonal":
                    bg_image = f"background-image: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {bg_color}, stop:1 {grad_color2});"
                else:
                    bg_image = ""
                if bg_image:
                    central_widget.setStyleSheet(f"background-color: {bg_color}; {bg_image}")
                else:
                    central_widget.setStyleSheet(f"background-color: {bg_color};")
            else:
                # 未启用渐变时使用纯色背景
                central_widget.setStyleSheet(f"background-color: {bg_color};")

        # 子区域采用透明样式，继承中央部件的背景（包括渐变）
        for area in (note_selection_area, track_area, playback_control_area):
            if area is not None:
                area.setStyleSheet("background: transparent;")
        
        # 状态栏前景色
        if self.statusBar() is not None:
            self.statusBar().setStyleSheet(f"color: {fg_color};")

    def refresh_theme_from_settings(self):
        """
        从当前设置重新应用主题和样式。
        点击设置对话框中的“应用/确定”后调用，确保无需重启即可看到效果。
        """
        # 重新应用主窗口主题（菜单栏/工具栏/状态栏/按钮等）
        self.apply_theme()
        # 重新应用背景/前景色、字体等
        self.apply_display_settings_from_settings()

        # 根据设置刷新播放线刷新率（应用后立即生效）
        try:
            from ui.settings_manager import get_settings_manager
            settings_manager = get_settings_manager()
            if hasattr(self, "update_timer") and self.update_timer is not None:
                interval = settings_manager.get_playhead_refresh_interval()
                self.update_timer.setInterval(interval)
        except Exception:
            # 安全兜底：不要因为刷新失败导致设置对话框崩溃
            pass

        theme = theme_manager.current_theme

        # 更新序列编辑器背景、网格和按钮样式
        if hasattr(self, "sequence_widget"):
            bg = QColor(theme.get_color("background"))
            if hasattr(self.sequence_widget, "view"):
                self.sequence_widget.view.setBackgroundBrush(QBrush(bg))
            if hasattr(self.sequence_widget, "draw_grid"):
                self.sequence_widget.draw_grid()
            # 统一小按钮风格（添加/删除音轨、渲染按钮等）
            button_small_style = theme.get_style("button_small")
            for btn_name in ("add_track_button", "delete_track_button", "render_waveform_button"):
                if hasattr(self.sequence_widget, btn_name):
                    btn = getattr(self.sequence_widget, btn_name)
                    if btn is not None:
                        btn.setStyleSheet(button_small_style)
            # 进度条主题
            if hasattr(self.sequence_widget, "progress_bar"):
                try:
                    self.sequence_widget.progress_bar.apply_theme()
                except Exception:
                    pass

        # 更新统一编辑器背景和按钮样式（钢琴区域 / 波形按钮 / 节拍长度等）
        if hasattr(self, "unified_editor"):
            try:
                bg = theme.get_color("background")
                self.unified_editor.setStyleSheet(f"background-color: {bg};")
                if hasattr(self.unified_editor, "apply_theme_to_buttons"):
                    self.unified_editor.apply_theme_to_buttons()
            except Exception:
                pass

        # 更新示波器等子组件的主题
        if hasattr(self, "oscilloscope_widget"):
            try:
                self.oscilloscope_widget.apply_theme()
            except Exception:
                pass

        # 刷新主界面数据和重绘
        if hasattr(self, "refresh_ui"):
            # 保留选择并强制全量刷新，使颜色/字体在所有区域立即生效
            self.refresh_ui(preserve_selection=True, force_full_refresh=True)

        # 最后强制重绘窗口
        self.repaint()
    
    
    def init_default_tracks(self):
        """初始化默认轨道（可选，现在不自动创建）"""
        # 不再自动创建默认音轨，让用户手动创建
        # 如果需要默认音轨，可以取消下面的注释
        pass
        
        # 如果需要默认音轨，使用以下代码：
        # from core.models import WaveformType, TrackType
        # 
        # # 主旋律
        # melody_track = self.sequencer.add_track(
        #     name="主旋律",
        #     waveform=WaveformType.SQUARE,
        #     track_type=TrackType.NOTE_TRACK
        # )
        # 
        # # 低音
        # bass_track = self.sequencer.add_track(
        #     name="低音",
        #     waveform=WaveformType.TRIANGLE,
        #     track_type=TrackType.NOTE_TRACK
        # )
        # 
        # # 打击乐
        # drum_track = self.sequencer.add_track(
        #     name="打击乐",
        #     track_type=TrackType.DRUM_TRACK
        # )
    
    def connect_signals(self):
        """连接信号"""
        # 统一编辑器信号
        self.unified_editor.add_melody_note.connect(self.on_add_melody_note)
        self.unified_editor.add_bass_event.connect(self.on_add_bass_event)
        self.unified_editor.add_drum_event.connect(self.on_add_drum_event)
        
        # 序列编辑器信号
        self.sequence_widget.note_clicked.connect(self.on_note_selected)
        self.sequence_widget.note_position_changed.connect(self.on_note_position_changed)
        self.sequence_widget.note_deleted.connect(self.on_note_deleted)
        self.sequence_widget.notes_deleted.connect(self.on_notes_deleted)
        
        # 属性面板信号
        self.property_panel.property_changed.connect(self.on_property_changed)
        self.property_panel.property_update_requested.connect(self.on_property_update_requested)
        self.property_panel.batch_property_changed.connect(self.on_batch_property_changed)
        self.property_panel.track_property_changed.connect(self.on_track_property_changed)

        # 乐谱面板信号
        if hasattr(self, "score_panel"):
            self.score_panel.request_create_from_selection.connect(self.on_score_create_from_selection)
            self.score_panel.snippet_apply_requested.connect(self.on_score_apply_snippet)
            self.score_panel.snippet_delete_requested.connect(self.on_score_delete_snippet)
            self.score_panel.snippet_preview_requested.connect(self.on_score_preview_snippet)
        
        # 序列编辑器选择变化信号
        self.sequence_widget.selection_changed.connect(self.on_selection_changed)
        self.sequence_widget.track_clicked.connect(self.on_track_clicked)
        self.sequence_widget.track_enabled_changed.connect(self.on_track_enabled_changed)
        self.sequence_widget.playhead_time_changed.connect(self.on_playhead_time_changed)
        
        # 音轨删除信号
        self.sequence_widget.track_deleted.connect(self.on_track_deleted)
        
        # 渲染波形请求信号
        self.sequence_widget.render_waveform_requested.connect(self.on_render_waveform_requested)
    
    def on_playhead_time_changed(self, time: float):
        """播放线时间改变（用户拖动进度条时）"""
        # 如果正在播放，停止播放
        if self.sequencer.playback_state.is_playing:
            self.sequencer.stop()
            self.metronome_widget.set_playing(False)
            self.statusBar().showMessage("已停止播放")
        
        # 更新播放头位置
        self.sequence_widget.set_playhead_time(time)
        
        # 更新播放开始偏移（用于下次播放时从正确位置开始）
        self.playback_start_offset = time
    
    def refresh_ui(self, preserve_selection: bool = False, force_full_refresh: bool = False):
        """刷新UI显示
        
        Args:
            preserve_selection: 是否保持选中状态（用于属性面板更新时）
            force_full_refresh: 是否强制全量刷新（用于音轨删除等操作）
        """
        # 更新序列编辑器（强制全量刷新以确保删除的音轨和音符被清除）
        self.sequence_widget.set_tracks(self.sequencer.project.tracks, preserve_selection=preserve_selection)
        self.sequence_widget.set_bpm(self.sequencer.get_bpm())
        
        # 如果强制全量刷新，调用序列编辑器的全量刷新
        if force_full_refresh:
            self.sequence_widget.refresh(force_full_refresh=True)
        
        # 更新进度条的总时长
        if hasattr(self.sequence_widget, 'progress_bar'):
            total_duration = self.sequencer.project.get_total_duration()
            self.sequence_widget.progress_bar.set_total_time(total_duration)
        
        # 更新统一编辑器BPM
        self.unified_editor.set_bpm(self.sequencer.get_bpm())
        
        # 更新示波器（只有在当前视图是示波器视图时才更新）
        if hasattr(self, 'oscilloscope_widget') and hasattr(self, 'view_stack'):
            # 如果当前不在示波器视图，不更新示波器（避免覆盖用户选择）
            if self.view_stack.currentIndex() != 1:
                # 不在示波器视图，只更新BPM
                self.oscilloscope_widget.set_bpm(self.sequencer.get_bpm())
            else:
                # 在示波器视图，才更新音轨
                # 优先检查用户是否选择了要渲染的音轨
                if hasattr(self.oscilloscope_widget, '_selected_tracks_for_render') and \
                   self.oscilloscope_widget._selected_tracks_for_render:
                    # 用户已经选择了要渲染的音轨，直接使用，不覆盖
                    enabled_tracks = [t for t in self.sequencer.project.tracks if t.enabled]
                    user_selected = [t for t in self.oscilloscope_widget._selected_tracks_for_render if t in enabled_tracks]
                    if user_selected:
                        # 只更新BPM，不更新音轨（保持用户选择）
                        self.oscilloscope_widget.set_bpm(self.sequencer.get_bpm())
                    else:
                        # 用户选择的音轨都不在启用的音轨中，清空
                        self.oscilloscope_widget.set_tracks([])
                        self.oscilloscope_widget.set_bpm(self.sequencer.get_bpm())
                else:
                    # 没有用户选择，使用默认逻辑
                    # 获取选中的音轨（使用统一方法）
                    selected_track = self._get_selected_track()
                    
                    # 获取所有启用的音轨
                    enabled_tracks = [t for t in self.sequencer.project.tracks if t.enabled]
                    
                    # 如果有选中的音轨，只渲染选中的
                    if selected_track and selected_track in enabled_tracks:
                        self.oscilloscope_widget.set_tracks(enabled_tracks, selected_track=selected_track)
                    elif len(enabled_tracks) <= 3:
                        # 不超过3个，自动渲染所有音轨
                        self.oscilloscope_widget.set_tracks(enabled_tracks)
                    else:
                        # 超过3个音轨，但没有用户选择，默认渲染前3个
                        self.oscilloscope_widget.set_selected_tracks(enabled_tracks[:3])
                        self.oscilloscope_widget.set_tracks(enabled_tracks[:3])
                    self.oscilloscope_widget.set_bpm(self.sequencer.get_bpm())
    
    def on_add_melody_note(self, pitch: int, duration_beats: float, waveform, target_track=None, insert_mode="sequential"):
        """添加主旋律音符"""
        # 确定目标音轨
        if target_track is not None and target_track.track_type == TrackType.NOTE_TRACK:
            melody_track = target_track
        else:
            # 如果没有指定音轨，找到第一个音符音轨
            melody_track = None
            for track in self.sequencer.project.tracks:
                if track.track_type == TrackType.NOTE_TRACK:
                    melody_track = track
                    break
            
            if not melody_track:
                # 如果没有音符音轨，创建一个
                melody_track = self.sequencer.add_track(
                    name="音轨 1",
                    track_type=TrackType.NOTE_TRACK
                )
                self.refresh_ui()
        
        # 计算开始时间
        duration = duration_beats * 60.0 / self.sequencer.get_bpm()
        
        if insert_mode == "playhead":
            # 播放线插入模式：使用播放线位置
            start_time = self.sequence_widget.playhead_time
        else:
            # 顺序插入模式：序列末尾
            if melody_track.notes:
                last_end_time = max(note.end_time for note in melody_track.notes)
                start_time = last_end_time
            else:
                start_time = 0.0
        
        # 检查是否与现有音符重叠（如果重叠，移动到下一个位置）
        for existing_note in melody_track.notes:
            if (start_time < existing_note.end_time and 
                start_time + duration > existing_note.start_time):
                start_time = existing_note.end_time
                break
        
        # 添加音符
        note = self.sequencer.add_note(
            melody_track,
            pitch,
            start_time,
            duration
        )
        note.waveform = waveform
        
        # 高亮显示目标音轨
        self.sequence_widget.set_highlighted_track(melody_track)
        
        self.refresh_ui()
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        self.statusBar().showMessage(f"已添加音符: {note_name}{octave} ({duration_beats}拍)")
    
    
    def on_add_bass_event(self, pitch: int, duration_beats: float, waveform, target_track=None, insert_mode="sequential"):
        """添加低音事件"""
        # 确定目标音轨
        if target_track is not None and target_track.track_type == TrackType.NOTE_TRACK:
            bass_track = target_track
        else:
            # 如果没有指定音轨，找到第一个音符音轨
            bass_track = None
            for track in self.sequencer.project.tracks:
                if track.track_type == TrackType.NOTE_TRACK:
                    bass_track = track
                    break
            
            if not bass_track:
                # 如果没有音符音轨，创建一个
                bass_track = self.sequencer.add_track(
                    name="音轨 1",
                    track_type=TrackType.NOTE_TRACK
                )
                self.refresh_ui()
        
        # 计算开始时间
        duration = duration_beats * 60.0 / self.sequencer.get_bpm()
        
        if insert_mode == "playhead":
            # 播放线插入模式：使用播放线位置
            start_time = self.sequence_widget.playhead_time
        else:
            # 顺序插入模式：序列末尾
            if bass_track.notes:
                last_end_time = max(note.end_time for note in bass_track.notes)
                start_time = last_end_time
            else:
                start_time = 0.0
        
        # 检查重叠（如果重叠，移动到下一个位置）
        for existing_note in bass_track.notes:
            if (start_time < existing_note.end_time and 
                start_time + duration > existing_note.start_time):
                start_time = existing_note.end_time
                break
        
        # 添加音符
        note = self.sequencer.add_note(
            bass_track,
            pitch,
            start_time,
            duration
        )
        note.waveform = waveform
        
        # 高亮显示目标音轨
        self.sequence_widget.set_highlighted_track(bass_track)
        
        self.refresh_ui()
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = pitch // 12 - 1
        note_name = note_names[pitch % 12]
        self.statusBar().showMessage(f"已添加音符: {note_name}{octave} ({duration_beats}拍)")
    
    def on_add_drum_event(self, drum_type, duration_beats: float, target_track=None, insert_mode="sequential"):
        """添加打击乐事件"""
        # 确定目标音轨
        if target_track is not None and target_track.track_type == TrackType.DRUM_TRACK:
            drum_track = target_track
        else:
            # 如果没有指定音轨，找到第一个打击乐音轨
            drum_track = None
            for track in self.sequencer.project.tracks:
                if track.track_type == TrackType.DRUM_TRACK:
                    drum_track = track
                    break
            
            if not drum_track:
                # 如果没有打击乐轨道，创建一个
                drum_track = self.sequencer.add_track(name="打击乐", track_type=TrackType.DRUM_TRACK)
                self.refresh_ui()
        
        # 计算开始节拍位置
        if insert_mode == "playhead":
            # 播放线插入模式：使用播放线位置
            start_beat = self.sequence_widget.playhead_time * self.sequencer.get_bpm() / 60.0
        else:
            # 顺序插入模式：序列末尾
            if drum_track.drum_events:
                last_end_beat = max(event.end_beat for event in drum_track.drum_events)
                start_beat = last_end_beat
            else:
                start_beat = 0.0
        
        # 检查重叠（如果重叠，移动到下一个位置）
        for existing_event in drum_track.drum_events:
            if (start_beat < existing_event.end_beat and 
                start_beat + duration_beats > existing_event.start_beat):
                start_beat = existing_event.end_beat
                break
        
        # 添加打击乐事件
        drum_event = self.sequencer.add_drum_event(
            drum_track,
            drum_type,
            start_beat,
            duration_beats
        )
        
        # 高亮显示目标音轨
        self.sequence_widget.set_highlighted_track(drum_track)
        
        self.refresh_ui()
        drum_names = {
            DrumType.KICK: "底鼓",
            DrumType.SNARE: "军鼓",
            DrumType.HIHAT: "踩镲",
            DrumType.CRASH: "吊镲"
        }
        self.statusBar().showMessage(f"已添加打击乐: {drum_names.get(drum_type, '打击')} ({duration_beats}拍)")
    
    def on_note_selected(self, note, track):
        """音符选中"""
        self.selected_note = note
        self.selected_track = track
        
        # 更新属性面板
        self.property_panel.set_note(note, track)
        
        # 根据对象类型更新状态栏信息
        if isinstance(note, DrumEvent):
            drum_names = {
                DrumType.KICK: "底鼓",
                DrumType.SNARE: "军鼓",
                DrumType.HIHAT: "踩镲",
                DrumType.CRASH: "吊镲",
            }
            self.statusBar().showMessage(
                f"已选中打击乐: {drum_names.get(note.drum_type, '打击')} (按Delete键删除)"
            )
        else:
            note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            octave = note.pitch // 12 - 1
            note_name = note_names[note.pitch % 12]
            self.statusBar().showMessage(f"已选中音符: {note_name}{octave} (按Delete键删除)")
            # 自动聚焦属性面板（如果当前显示的是乐谱面板，则切换回属性面板）
            self._focus_property_panel()
    
    def on_note_deleted(self, note, track):
        """音符被删除（单个，通过命令系统）"""
        # 检查音符是否还在轨道中（可能已经被widget删除了）
        if note in track.notes:
            # 通过命令系统删除音符（支持撤销/重做）
            self.sequencer.remove_note(track, note, use_command=True)
        
        self.refresh_ui()
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = note.pitch // 12 - 1
        note_name = note_names[note.pitch % 12]
        self.statusBar().showMessage(f"已删除音符: {note_name}{octave}")
    
    def on_notes_deleted(self, notes_and_tracks):
        """批量删除音符（通过命令系统）"""
        from core.command import BatchCommand, DeleteNoteCommand
        from PyQt5.QtCore import QTimer
        
        if not notes_and_tracks:
            return
        
        # 创建批量删除命令
        commands = []
        for note, track in notes_and_tracks:
            # 检查音符是否还在轨道中
            if note in track.notes:
                command = DeleteNoteCommand(self.sequencer, track, note)
                commands.append(command)
        
        if commands:
            # 执行批量命令
            batch_command = BatchCommand(commands, f"批量删除 {len(commands)} 个音符")
            self.sequencer.command_history.execute_command(batch_command)
            
            # 延迟刷新，确保所有删除操作完成，避免在删除过程中访问已删除的对象
            QTimer.singleShot(50, lambda: self.refresh_ui())
            self.statusBar().showMessage(f"已删除 {len(commands)} 个音符")
    
    def on_note_position_changed(self, note, track, old_start_time, new_start_time):
        """音符位置改变"""
        # 通过命令系统移动音符（支持撤销/重做）
        # 注意：note.start_time已经在grid_sequence_widget中更新了
        # 但我们需要通过命令系统来记录这个操作
        if abs(old_start_time - new_start_time) > 0.001:
            # 先恢复旧位置（因为widget已经更新了，需要恢复）
            note.start_time = old_start_time
            # 通过命令系统移动
            self.sequencer.move_note(track, note, new_start_time)
        
        self.statusBar().showMessage(f"音符已移动到: {new_start_time:.2f}s")
        self.refresh_ui()
    
    def on_property_changed(self, note: Note, track: Track):
        """属性面板属性改变"""
        # 通过命令系统修改音符属性（支持撤销/重做）
        # 获取当前属性值
        kwargs = {}
        if hasattr(self.property_panel, 'pitch_spinbox'):
            new_pitch = self.property_panel.pitch_spinbox.value()
            if new_pitch != note.pitch:
                kwargs['pitch'] = new_pitch
        
        if hasattr(self.property_panel, 'duration_spinbox'):
            duration_beats = self.property_panel.duration_spinbox.value()
            duration_seconds = duration_beats * 60.0 / self.sequencer.get_bpm()
            if abs(duration_seconds - note.duration) > 0.001:
                kwargs['duration'] = duration_seconds
        
        if hasattr(self.property_panel, 'velocity_slider'):
            new_velocity = self.property_panel.velocity_slider.value()
            if new_velocity != note.velocity:
                kwargs['velocity'] = new_velocity
        
        if hasattr(self.property_panel, 'waveform_combo'):
            waveform_map = {
                0: WaveformType.SQUARE,
                1: WaveformType.TRIANGLE,
                2: WaveformType.SAWTOOTH,
                3: WaveformType.SINE,
                4: WaveformType.NOISE
            }
            new_waveform = waveform_map.get(self.property_panel.waveform_combo.currentIndex(), WaveformType.SQUARE)
            if new_waveform != note.waveform:
                kwargs['waveform'] = new_waveform
        
        if hasattr(self.property_panel, 'attack_spinbox') and note.adsr:
            adsr_changed = False
            adsr_dict = {}
            if abs(self.property_panel.attack_spinbox.value() - note.adsr.attack) > 0.001:
                adsr_dict['attack'] = self.property_panel.attack_spinbox.value()
                adsr_changed = True
            if abs(self.property_panel.decay_spinbox.value() - note.adsr.decay) > 0.001:
                adsr_dict['decay'] = self.property_panel.decay_spinbox.value()
                adsr_changed = True
            if abs(self.property_panel.sustain_spinbox.value() - note.adsr.sustain) > 0.001:
                adsr_dict['sustain'] = self.property_panel.sustain_spinbox.value()
                adsr_changed = True
            if abs(self.property_panel.release_spinbox.value() - note.adsr.release) > 0.001:
                adsr_dict['release'] = self.property_panel.release_spinbox.value()
                adsr_changed = True
            if adsr_changed:
                kwargs['adsr'] = adsr_dict
        
        # 如果有属性改变，通过命令系统修改
        if kwargs:
            # 处理时长改变时的后续音符调整
            if 'duration' in kwargs:
                old_duration = note.duration
                new_duration = kwargs['duration']
                duration_delta = new_duration - old_duration
                
                # 先通过命令修改当前音符
                self.sequencer.modify_note(track, note, **kwargs)
                
                # 然后调整后续音符（也需要通过命令，但为了简化，这里直接调整）
                # 注意：后续音符的调整应该也通过命令，但为了简化，这里先直接调整
                if abs(duration_delta) > 0.001:
                    adjusted_notes = self.property_panel.adjust_following_notes(duration_delta)
                    # TODO: 后续音符的调整也应该通过命令系统
            else:
                self.sequencer.modify_note(track, note, **kwargs)
        
        # 刷新显示（属性改变需要刷新以反映变化）
        self.refresh_ui(preserve_selection=True)
        
        # 更新属性面板显示（以防有变化）
        if self.property_panel.current_note == note:
            self.property_panel.update_ui()
    
    def on_property_update_requested(self, note: Note, track: Track):
        """属性面板请求更新UI"""
        self.refresh_ui()
    
    def on_selection_changed(self):
        """序列编辑器选择变化"""
        selected_blocks = [item for item in self.sequence_widget.scene.selectedItems() 
                          if hasattr(item, 'item') and hasattr(item, 'track')]
        
        # 如果当前正在编辑音轨（current_track_for_edit不为None）
        if self.property_panel.current_track_for_edit is not None:
            # 检查选中的音符是否都在当前编辑的音轨上
            current_track = self.property_panel.current_track_for_edit
            all_in_current_track = True
            if selected_blocks:
                for block in selected_blocks:
                    if id(block.track) != id(current_track):
                        all_in_current_track = False
                        break
            
            # 如果所有选中的音符都在当前音轨上，只更新current_notes，不改变显示模式
            if all_in_current_track:
                if selected_blocks:
                    notes_and_tracks = [(block.item, block.track) for block in selected_blocks]
                    # 只更新current_notes，不改变显示
                    self.property_panel.current_notes = notes_and_tracks
                    # 更新多选标签
                    if self.property_panel.multi_select_label.isVisible():
                        track = self.property_panel.current_track_for_edit
                        if track.track_type == TrackType.DRUM_TRACK:
                            self.property_panel.multi_select_label.setText(
                                f"音轨: {track.name}\n已选中 {len(notes_and_tracks)} 个打击乐事件\n（打击乐事件暂不支持批量编辑）"
                            )
                        else:
                            self.property_panel.multi_select_label.setText(
                                f"音轨: {track.name}\n已选中 {len(notes_and_tracks)} 个音符\n可以统一编辑共有属性"
                            )
                return
            else:
                # 选中了其他音轨的音符，退出音轨编辑模式
                self.property_panel.current_track_for_edit = None
        
        # 不在音轨编辑模式，正常处理选择变化
        if len(selected_blocks) == 0:
            # 没有选中，清空属性面板
            self.property_panel.set_note(None, None)
        elif len(selected_blocks) == 1:
            # 单个选中，显示单个音符编辑
            block = selected_blocks[0]
            self.property_panel.set_note(block.item, block.track)
        else:
            # 多选，显示批量编辑
            notes_and_tracks = [(block.item, block.track) for block in selected_blocks]
            self.property_panel.set_notes(notes_and_tracks)
            # 多选时同样自动聚焦属性面板，方便立即批量调整
            self._focus_property_panel()
    
    def on_batch_property_changed(self, notes_and_tracks: list):
        """批量属性改变"""
        if not notes_and_tracks:
            return
        
        # 获取要修改的属性
        kwargs = {}
        
        # 波形（仅当用户在批量区域实际修改了波形时才应用）
        if hasattr(self.property_panel, 'batch_waveform_combo') and getattr(self.property_panel, "_batch_waveform_dirty", False):
            waveform_map = {
                0: WaveformType.SQUARE,
                1: WaveformType.TRIANGLE,
                2: WaveformType.SAWTOOTH,
                3: WaveformType.SINE,
                4: WaveformType.NOISE
            }
            selected_waveform = waveform_map.get(self.property_panel.batch_waveform_combo.currentIndex())
            if selected_waveform:
                kwargs['waveform'] = selected_waveform
        
        # 力度（仅当用户在批量区域实际拖动过力度滑块时才应用）
        if hasattr(self.property_panel, 'batch_velocity_slider') and getattr(self.property_panel, "_batch_velocity_dirty", False):
            velocity = self.property_panel.batch_velocity_slider.value()
            kwargs['velocity'] = velocity
        
        # 占空比（仅当用户在批量区域实际修改过占空比时才应用）
        if hasattr(self.property_panel, 'batch_duty_spinbox') and getattr(self.property_panel, "_batch_duty_dirty", False):
            duty_cycle = self.property_panel.batch_duty_spinbox.value()
            kwargs['duty_cycle'] = duty_cycle
        
        # 通过命令系统批量修改
        if kwargs:
            self.sequencer.batch_modify_notes(notes_and_tracks, **kwargs)
            # 刷新显示（批量修改需要刷新以反映变化）
            self.refresh_ui(preserve_selection=True)

            # 由于刷新过程中会重建部分 UI，原先的多选高亮可能丢失，
            # 这里根据 notes_and_tracks 重新恢复选中状态，保持用户的多选不变。
            try:
                selected_blocks = []
                for note, track in notes_and_tracks:
                    block = self.sequence_widget.note_blocks.get((id(note), id(track)))
                    if block:
                        block.setSelected(True)
                        selected_blocks.append(block)
                # 同步更新 GridSequenceWidget 内部的 selected_items 状态
                if selected_blocks and hasattr(self.sequence_widget, "_update_selection_from_blocks"):
                    self.sequence_widget._update_selection_from_blocks(selected_blocks)
            except Exception:
                pass

            self.statusBar().showMessage(f"已批量修改 {len(notes_and_tracks)} 个音符的属性")
    
    def on_track_clicked(self, track: Track):
        """音轨被点击"""
        # 先设置属性面板为音轨编辑模式（这会显示音轨效果和批量编辑）
        self.property_panel.set_track(track)
        
        # 选中该轨道上的所有音符（这可能会触发on_selection_changed，但set_track已经设置了正确的显示）
        self.sequence_widget.select_track_notes(track)
        
        # 设置统一编辑器的目标音轨
        self.unified_editor.set_selected_track(track)
        
        # 高亮显示目标音轨
        self.sequence_widget.set_highlighted_track(track)
        
        # 确保属性面板保持音轨编辑模式（防止on_selection_changed覆盖），并切换到属性面板标签
        self.property_panel.set_track(track)
        self._focus_property_panel()
        
        note_count = len(track.notes) if track.track_type == TrackType.NOTE_TRACK else len(track.drum_events)
        self.statusBar().showMessage(f"已选中音轨: {track.name} ({note_count} 个音符/事件)")
    
    def on_track_property_changed(self, track: Track):
        """音轨属性改变"""
        # 刷新UI以反映音轨属性的变化（如名称、类型等）
        self.refresh_ui(preserve_selection=True)
        self.statusBar().showMessage(f"已更新音轨: {track.name}")
    
    def on_track_deleted(self, track: Track):
        """音轨被删除"""
        from core.command import DeleteTrackCommand
        from PyQt5.QtWidgets import QMessageBox
        
        # 检查音轨是否还在项目中（可能已经被删除）
        if track not in self.sequencer.project.tracks:
            # 音轨已经被删除，直接刷新UI
            self.refresh_ui()
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除音轨 \"{track.name}\" 吗？\n此操作将删除该音轨上的所有音符。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 使用命令系统删除音轨（支持撤销/重做）
            command = DeleteTrackCommand(self.sequencer, track)
            self.sequencer.command_history.execute_command(command)
            
            # 强制全量刷新UI（确保删除的音轨和所有音符都被清除）
            self.refresh_ui(force_full_refresh=True)
            
            # 清除选中状态
            self.selected_note = None
            self.selected_track = None
            if hasattr(self, 'unified_editor'):
                self.unified_editor.set_selected_track(None)
            
            self.statusBar().showMessage(f"已删除音轨: {track.name}")
    
    def clear_all_tracks(self):
        """清空所有音轨"""
        from PyQt5.QtWidgets import QMessageBox
        from core.command import BatchCommand, DeleteTrackCommand
        
        if not self.sequencer.project.tracks:
            self.statusBar().showMessage("没有可清空的音轨")
            return
        
        # 确认清空
        reply = QMessageBox.question(
            self, "确认清空", 
            f"确定要清空所有 {len(self.sequencer.project.tracks)} 个音轨吗？\n此操作将删除所有音轨及其上的所有音符，且无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 创建批量删除命令
            commands = []
            tracks_to_delete = list(self.sequencer.project.tracks)  # 复制列表，避免在迭代时修改
            
            for track in tracks_to_delete:
                command = DeleteTrackCommand(self.sequencer, track)
                commands.append(command)
            
            if commands:
                # 执行批量命令
                batch_command = BatchCommand(commands, f"清空所有音轨 ({len(commands)} 个)")
                self.sequencer.command_history.execute_command(batch_command)
                
                # 刷新UI
                self.refresh_ui()
                
                # 清除选中状态
                self.selected_note = None
                self.selected_track = None
                if hasattr(self, 'unified_editor'):
                    self.unified_editor.set_selected_track(None)
                
                self.statusBar().showMessage(f"已清空所有音轨 ({len(commands)} 个)")
    
    def on_track_enabled_changed(self, track: Track, enabled: bool):
        """音轨启用状态改变"""
        # 防止在刷新过程中触发（避免循环刷新）
        if not hasattr(self.sequencer, 'project') or not self.sequencer.project:
            return
        
        track.enabled = enabled
        # 使用延迟刷新，让当前事件处理完成，避免访问已删除的对象
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, self.sequence_widget.refresh)
        status = "启用" if enabled else "禁用"
        self.statusBar().showMessage(f"已{status}音轨: {track.name}")
    
    def on_metronome_toggled(self, enabled: bool):
        """节拍器开关"""
        # 如果正在播放，同步节拍器状态
        if enabled and self.sequencer.playback_state.is_playing:
            self.metronome_widget.set_playing(True)
        elif not enabled:
            self.metronome_widget.set_playing(False)
    
    def toggle_play_stop(self):
        """切换播放/停止状态（合并播放和暂停）"""
        if self.sequencer.playback_state.is_playing:
            # 正在播放，点击停止
            self.stop()
        else:
            # 未播放，点击播放
            self.play()
    
    def toggle_play_pause(self):
        """切换播放/暂停"""
        if self.sequencer.playback_state.is_playing:
            # 播放中按空格应为“暂停”，保留当前位置，方便继续播放
            self.pause()
        else:
            self.play()
    
    def select_all_notes(self):
        """全选音符"""
        # 触发序列编辑器的全选
        if hasattr(self.sequence_widget, 'view'):
            from PyQt5.QtGui import QKeyEvent
            fake_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.ControlModifier)
            self.sequence_widget.on_key_press(fake_event)
    
    def on_note_added(self, note, track):
        """音符添加"""
        self.statusBar().showMessage(f"已添加音符: MIDI {note.pitch}")
    
    def on_note_removed(self, note, track):
        """音符删除"""
        self.statusBar().showMessage(f"已删除音符")
    
    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        new_action = QAction("新建(&N)", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_project)
        file_menu.addAction(new_action)
        
        # 合并打开和导入：根据文件类型自动调用相应函数
        open_action = QAction("打开/导入(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_or_import_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        # 合并"另存为"和"导出"为一个统一的导出功能
        export_action = QAction("导出(&E)...", self)
        export_action.setShortcut(QKeySequence.SaveAs)
        export_action.triggered.connect(self.export_file)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        
        # 显示/隐藏属性面板
        self.toggle_property_action = QAction("属性面板(&P)", self)
        self.toggle_property_action.setCheckable(True)
        self.toggle_property_action.setChecked(False)  # 默认不显示
        self.toggle_property_action.triggered.connect(self.toggle_property_panel)
        view_menu.addAction(self.toggle_property_action)

        # 显示/隐藏乐谱面板
        self.toggle_score_action = QAction("乐谱面板(&L)", self)
        self.toggle_score_action.setCheckable(True)
        self.toggle_score_action.setChecked(False)
        self.toggle_score_action.triggered.connect(self.toggle_score_panel)
        view_menu.addAction(self.toggle_score_action)

        # 显示/隐藏风格参数面板
        self.toggle_style_params_action = QAction("风格参数(&S)", self)
        self.toggle_style_params_action.setCheckable(True)
        self.toggle_style_params_action.setChecked(False)
        self.toggle_style_params_action.triggered.connect(self.toggle_style_params_panel)
        view_menu.addAction(self.toggle_style_params_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        
        # 撤销
        self.undo_action = QAction("撤销(&U)", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)
        
        # 重做
        self.redo_action = QAction("重做(&R)", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)
        
        # 定时更新撤销/重做按钮状态
        self.update_undo_redo_timer = QTimer()
        self.update_undo_redo_timer.timeout.connect(self.update_undo_redo_state)
        self.update_undo_redo_timer.start(100)  # 每100ms更新一次
        
        edit_menu.addSeparator()
        
        # 全选
        select_all_action = QAction("全选(&A)", self)
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.triggered.connect(self.select_all_notes)
        edit_menu.addAction(select_all_action)
        
        # 播放菜单
        play_menu = menubar.addMenu("播放(&P)")
        
        play_pause_action = QAction("播放/暂停", self)
        play_pause_action.setShortcut(Qt.Key_Space)
        play_pause_action.triggered.connect(self.toggle_play_pause)
        play_menu.addAction(play_pause_action)
        
        stop_action = QAction("停止(&S)", self)
        stop_action.setShortcut("Ctrl+.")
        stop_action.triggered.connect(self.stop)
        play_menu.addAction(stop_action)
        
        # 生成菜单（用于 V3：Seed 生成音乐等功能）
        generate_menu = menubar.addMenu("生成(&G)")

        generate_seed_action = QAction("从 Seed 生成音乐(&M)...", self)
        generate_seed_action.triggered.connect(self.generate_music_from_seed)
        generate_menu.addAction(generate_seed_action)

        # 设置菜单（统一入口）
        settings_menu = menubar.addMenu("设置(&S)")
        
        # 统一设置窗口：包括显示设置 / 示波器设置 / 快捷键设置等所有配置
        settings_action = QAction("设置(&S)...", self)
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        """设置工具栏（已移到右侧面板，这里保留空实现）"""
        # 播放控制已移到右侧面板
        pass
    
    def setup_statusbar(self):
        """设置状态栏"""
        self.statusBar().showMessage("就绪")
    
    def new_project(self):
        """新建项目"""
        if self.check_unsaved_changes():
            # 创建新的序列器（这会创建新的项目）
            self.sequencer = Sequencer()
            self.current_file_path = None
            self.current_midi_file_path = None
            self.setWindowTitle("8bit音乐制作器 - 新建项目")
            # 更新文件名显示
            self._update_file_name_display()
            
            # 停止播放
            self.stop()
            
            # 强制刷新UI（确保所有组件都清空）
            self.refresh_ui()
            
            # 清除选中状态
            self.selected_note = None
            self.selected_track = None
            if hasattr(self, 'unified_editor'):
                self.unified_editor.set_selected_track(None)
            
            self.statusBar().showMessage("已创建新项目")

    def generate_music_from_seed(self):
        """
        使用 Seed 生成一段简单的 8bit 音乐（V3 的第一版实现）。

        - 弹出对话框输入 Seed（字符串或数字均可）和大致小节数；
        - 调用核心的 generate_simple_project_from_seed 生成 Project；
        - 直接用 Sequencer 加载，并刷新当前 UI。
        """
        from PyQt5.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QComboBox, QDialogButtonBox

        if not self.check_unsaved_changes():
            return

        # 自定义对话框：选择风格 + 输入 Seed + 小节数
        class SeedGenerateDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("从 Seed 生成音乐")
                layout = QVBoxLayout(self)

                # 种子（放在最上面）
                seed_row = QHBoxLayout()
                seed_label = QLabel("种子：")
                self.seed_edit = QLineEdit()
                self.seed_edit.setText("minecraft")
                seed_row.addWidget(seed_label)
                seed_row.addWidget(self.seed_edit)
                layout.addLayout(seed_row)

                # 生成模式（旋律 / 整曲）
                mode_row = QHBoxLayout()
                mode_label = QLabel("生成模式：")
                self.mode_combo = QComboBox()
                self.mode_combo.addItem("生成旋律", "melody")
                self.mode_combo.addItem("整曲（含前奏结构）", "full_song")
                mode_row.addWidget(mode_label)
                mode_row.addWidget(self.mode_combo)
                layout.addLayout(mode_row)

                # 小节数
                bars_row = QHBoxLayout()
                bars_label = QLabel("小节数（4/4 拍）：")
                from PyQt5.QtWidgets import QSpinBox
                self.bars_spin = QSpinBox()
                self.bars_spin.setRange(4, 64)
                self.bars_spin.setValue(8)
                bars_row.addWidget(bars_label)
                bars_row.addWidget(self.bars_spin)
                layout.addLayout(bars_row)

                # 轨道内容选择：是否生成和声 / 鼓点
                track_row = QHBoxLayout()
                track_label = QLabel("轨道：")
                self.harmony_checkbox = QCheckBox("和声")
                self.harmony_checkbox.setChecked(True)
                self.drum_checkbox = QCheckBox("鼓点")
                self.drum_checkbox.setChecked(True)
                track_row.addWidget(track_label)
                track_row.addWidget(self.harmony_checkbox)
                track_row.addWidget(self.drum_checkbox)
                track_row.addStretch(1)
                layout.addLayout(track_row)

                # 风格选择
                style_row = QHBoxLayout()
                style_label = QLabel("风格：")
                self.style_combo = QComboBox()
                # 这里的顺序和 SeedMusicStyle 保持一一对应，便于后面映射
                self.style_combo.addItem("经典 8bit", SeedMusicStyle.CLASSIC_8BIT)
                self.style_combo.addItem("Lofi", SeedMusicStyle.LOFI)
                self.style_combo.addItem("战斗 / 紧张", SeedMusicStyle.BATTLE)
                self.style_combo.addItem("悬疑 / 惊悚", SeedMusicStyle.SUSPENSE)
                self.style_combo.addItem("舒缓 / 美好", SeedMusicStyle.CALM)
                style_row.addWidget(style_label)
                style_row.addWidget(self.style_combo)
                layout.addLayout(style_row)

                # 风格变体选择（例如：战斗-默认 / 偏旋律 / 偏鼓点；悬疑-默认 / 更紧张 / 更空灵）
                variant_row = QHBoxLayout()
                variant_label = QLabel("风格变体：")
                self.variant_combo = QComboBox()
                variant_row.addWidget(variant_label)
                variant_row.addWidget(self.variant_combo)
                layout.addLayout(variant_row)

                # 结构：Intro / 主循环占比（仅在整曲模式下生效）
                self.structure_group = QWidget()
                structure_layout = QVBoxLayout(self.structure_group)
                structure_layout.setContentsMargins(0, 0, 0, 0)

                intro_row = QHBoxLayout()
                self.intro_label = QLabel("结构：默认整段主循环")
                structure_layout.addWidget(self.intro_label)

                slider_row = QHBoxLayout()
                slider_caption = QLabel("前奏 Intro 占总长度的比例：")
                self.intro_ratio_slider = QSlider(Qt.Horizontal)
                self.intro_ratio_slider.setRange(0, 50)  # 0% ~ 50%
                self.intro_ratio_slider.setValue(25)
                slider_row.addWidget(slider_caption)
                slider_row.addWidget(self.intro_ratio_slider)
                structure_layout.addLayout(slider_row)

                layout.addWidget(self.structure_group)

                # 风格说明（只读），帮助用户快速理解当前风格的大致参数和情绪（放在最下面）
                self.style_info_label = QLabel()
                self.style_info_label.setWordWrap(True)
                # 稍微减小一点字体，使说明文字不会抢占主 UI 视觉
                font = self.style_info_label.font()
                font.setPointSize(max(9, font.pointSize() - 1))
                self.style_info_label.setFont(font)
                layout.addWidget(self.style_info_label)

                # 按钮
                button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                button_box.accepted.connect(self.accept)
                button_box.rejected.connect(self.reject)
                layout.addWidget(button_box)
                # 修改标准按钮文本为“生成 / 取消”，与当前业务更贴合
                ok_button = button_box.button(QDialogButtonBox.Ok)
                cancel_button = button_box.button(QDialogButtonBox.Cancel)
                if ok_button is not None:
                    ok_button.setText("生成")
                if cancel_button is not None:
                    cancel_button.setText("取消")

                # 绑定风格变化事件，实时刷新说明
                self.style_combo.currentIndexChanged.connect(self._on_style_changed)
                # 绑定结构相关事件
                self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
                self.intro_ratio_slider.valueChanged.connect(self._update_intro_label)
                self.bars_spin.valueChanged.connect(self._update_intro_label)
                # 初始化一次展示
                self._on_style_changed(self.style_combo.currentIndex())
                self._on_mode_changed(self.mode_combo.currentIndex())
                self._update_intro_label()

            def _on_style_changed(self, index: int):
                style = self.style_combo.itemData(index)
                if style is None:
                    self.style_info_label.setText("")
                    self.variant_combo.clear()
                    return
                try:
                    meta = get_style_meta(style)
                except Exception:
                    self.style_info_label.setText("")
                    self.variant_combo.clear()
                    return

                bpm = meta.get("default_bpm", "")
                mood = meta.get("mood", "")
                desc = meta.get("short_desc", "")
                lines = []
                if bpm:
                    lines.append(f"默认 BPM：{bpm}")
                if mood:
                    lines.append(f"情绪：{mood}")
                if desc:
                    lines.append(f"说明：{desc}")
                self.style_info_label.setText("\n".join(lines))

                # 根据当前风格刷新变体下拉框
                self.variant_combo.blockSignals(True)
                self.variant_combo.clear()
                try:
                    variants = get_style_variants(style)
                except Exception:
                    variants = [{"id": "default", "name": "默认", "desc": ""}]

                for var in variants:
                    name = var.get("name", "默认")
                    vid = var.get("id", "default")
                    vdesc = var.get("desc", "")
                    # 文本中附带一点简短说明，帮助区分
                    if vdesc:
                        text = f"{name} - {vdesc}"
                    else:
                        text = name
                    self.variant_combo.addItem(text, vid)
                self.variant_combo.blockSignals(False)

            def get_values(self):
                style = self.style_combo.currentData()
                seed = self.seed_edit.text().strip()
                bars = self.bars_spin.value()
                variant_id = self.variant_combo.currentData()
                mode = self.mode_combo.currentData()
                intro_ratio = self.intro_ratio_slider.value() / 100.0
                use_harmony = self.harmony_checkbox.isChecked()
                use_drums = self.drum_checkbox.isChecked()
                return style, variant_id, seed, bars, mode, intro_ratio, use_harmony, use_drums

            def _on_mode_changed(self, index: int):
                mode = self.mode_combo.itemData(index)
                # 只有整曲模式下才需要显示结构设置
                self.structure_group.setVisible(mode == "full_song")
                self._update_intro_label()

            def _update_intro_label(self, *args):
                total_bars = max(1, self.bars_spin.value())
                ratio = self.intro_ratio_slider.value() / 100.0
                if ratio <= 0.0:
                    self.intro_label.setText("结构：无前奏，全部为主循环")
                    return
                # 最少保证 1 小节前奏，且前奏不超过一半
                intro_bars = max(1, int(total_bars * ratio))
                intro_bars = min(intro_bars, total_bars // 2 if total_bars >= 2 else 1)
                main_bars = max(0, total_bars - intro_bars)
                self.intro_label.setText(f"结构：前奏 {intro_bars} 小节 + 主循环 {main_bars} 小节")

        dlg = SeedGenerateDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        style, variant_id, seed, length_bars, mode, intro_ratio, use_harmony, use_drums = dlg.get_values()
        if not seed:
            return

        # 3. 生成项目
        try:
            project = generate_simple_project_from_seed(
                seed,
                length_bars=length_bars,
                style=style,
                variant_id=variant_id or "default",
                intro_ratio=intro_ratio if mode == "full_song" else 0.0,
                enable_bass=(mode == "full_song"),
                enable_harmony=use_harmony,
                enable_drums=use_drums,
            )
        except Exception as e:
            QMessageBox.critical(self, "生成失败", f"基于 Seed 生成音乐时出错：{e}")
            return

        # 4. 应用到当前 Sequencer
        self.sequencer.set_project(project)
        self.current_file_path = None
        self.current_midi_file_path = None
        self.setWindowTitle(f"8bit音乐制作器 - Seed: {seed}")
        self._update_file_name_display()

        # 同步 UI 中的 BPM（旋钮 / 节拍器 / 网格等）到生成工程的 BPM
        bpm = float(project.bpm)
        # 更新 sequencer 与各子组件
        self.sequencer.set_bpm(bpm)
        # 更新 BPM 控件的显示，但避免触发 on_bpm_changed 里的逻辑
        self.bpm_spinbox.blockSignals(True)
        self.bpm_spinbox.setValue(int(bpm))
        self.bpm_spinbox.blockSignals(False)
        self.sequence_widget.set_bpm(bpm)
        self.unified_editor.set_bpm(bpm)
        self.property_panel.set_bpm(bpm)
        self.metronome_widget.set_bpm(bpm)
        if hasattr(self, 'oscilloscope_widget'):
            self.oscilloscope_widget.set_bpm(bpm)

        # 停止可能的播放
        self.stop()

        # 清除属性面板与选中状态
        self.property_panel.set_track(None)
        self.property_panel.set_note(None, None)
        self.property_panel.set_notes([])
        self.selected_note = None
        self.selected_track = None
        if hasattr(self, 'unified_editor'):
            self.unified_editor.set_selected_track(None)

        # 更新风格参数面板（仅更新内容，不再自动改变窗口布局/大小）
        self.current_seed_style = style
        self.current_seed_variant = variant_id or "default"
        if hasattr(self, "style_params_panel"):
            self.style_params_panel.set_style(style, self.current_seed_variant, project)

        # 刷新 UI 显示新生成的项目
        self.sequence_widget.refresh(force_full_refresh=True)
        self.refresh_ui()
        self.statusBar().showMessage(f"已基于 Seed “{seed}” 生成一个新的项目")
    
    def open_or_import_file(self):
        """打开或导入文件（根据文件类型自动判断）"""
        if not self.check_unsaved_changes():
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开/导入文件", "", 
            "所有支持的文件 (*.json *.mid *.midi);;JSON文件 (*.json);;MIDI文件 (*.mid *.midi);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        # 根据文件扩展名自动判断调用哪个函数
        file_ext = file_path.lower()
        if file_ext.endswith('.json'):
            self.open_project_file(file_path)
        elif file_ext.endswith('.mid') or file_ext.endswith('.midi'):
            self.import_midi_file(file_path)
        else:
            QMessageBox.warning(self, "警告", f"不支持的文件类型: {file_path}")
    
    def open_project_file(self, file_path: str):
        """打开项目文件"""
        try:
            # 创建加载进度对话框
            progress = QProgressDialog("正在加载项目...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)  # 立即显示
            progress.setValue(0)
            QApplication.processEvents()  # 处理事件，确保对话框显示
            
            import json
            progress.setLabelText("正在读取文件...")
            progress.setValue(10)
            QApplication.processEvents()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            progress.setLabelText("正在解析项目数据...")
            progress.setValue(30)
            QApplication.processEvents()
            
            # 清除属性面板的状态（清除旧的音轨信息）
            self.property_panel.set_track(None)
            self.property_panel.set_note(None, None)
            self.property_panel.set_notes([])
            
            progress.setLabelText("正在加载项目...")
            progress.setValue(50)
            QApplication.processEvents()
            
            project = Project.from_dict(data)
            self.sequencer.set_project(project)
            self.current_file_path = file_path
            self.setWindowTitle(f"8bit音乐制作器 - {project.name}")
            
            progress.setLabelText("正在更新界面...")
            progress.setValue(70)
            QApplication.processEvents()
            
            # 清除选中状态
            self.selected_note = None
            self.selected_track = None
            if hasattr(self, 'unified_editor'):
                self.unified_editor.set_selected_track(None)
            
            progress.setLabelText("正在刷新显示...")
            progress.setValue(90)
            QApplication.processEvents()
            
            # 强制全量刷新UI（清除所有旧的UI元素，确保track引用正确）
            self.sequence_widget.refresh(force_full_refresh=True)
            self.refresh_ui()
            
            progress.setValue(100)
            progress.close()
            
            # 保存项目文件路径
            self.current_file_path = file_path
            # 清除MIDI文件路径（因为打开了项目文件）
            self.current_midi_file_path = None
            # 更新文件名显示
            self._update_file_name_display()
            self.statusBar().showMessage(f"已打开项目: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开项目失败:\n{str(e)}")
    
    def open_project(self):
        """打开项目（保留以兼容旧代码）"""
        if not self.check_unsaved_changes():
            return
        
        # 获取上次打开的目录
        last_dir = self.settings.value("last_open_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", last_dir, "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        # 保存当前打开的目录
        if file_path:
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_open_directory", directory)
        
        if file_path:
            self.open_project_file(file_path)
    
    def save_project(self):
        """保存项目"""
        if self.current_file_path:
            self.save_project_to_file(self.current_file_path)
        else:
            # 如果没有保存路径，调用导出功能
            self.export_file()
    
    def export_file(self):
        """导出文件（统一处理项目保存和音频导出）"""
        # 获取上次保存的目录
        last_dir = self.settings.value("last_save_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""
        
        # 文件格式选择对话框
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出文件", last_dir,
            "JSON项目文件 (*.json);;"
            "MIDI文件 (*.mid);;"
            "WAV音频文件 (*.wav);;"
            "MP3音频文件 (*.mp3);;"
            "OGG音频文件 (*.ogg);;"
            "所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        # 保存当前保存的目录
        directory = os.path.dirname(file_path)
        self.settings.setValue("last_save_directory", directory)
        
        # 根据选择的过滤器确定文件格式
        if "JSON" in selected_filter:
            # 保存为JSON项目文件
            if not file_path.endswith('.json'):
                file_path += '.json'
            self.save_project_to_file(file_path)
            self.current_file_path = file_path
        elif "MIDI" in selected_filter:
            # 导出为MIDI文件
            if not file_path.lower().endswith('.mid'):
                file_path += '.mid'
            self.export_midi_to_file(file_path)
        elif "WAV" in selected_filter:
            # 导出为WAV音频文件
            if not file_path.endswith('.wav'):
                file_path += '.wav'
            self.export_audio_to_file(file_path, format="wav")
        elif "MP3" in selected_filter:
            # 导出为MP3音频文件
            if not file_path.endswith('.mp3'):
                file_path += '.mp3'
            self.export_audio_to_file(file_path, format="mp3")
        elif "OGG" in selected_filter:
            # 导出为OGG音频文件
            if not file_path.endswith('.ogg'):
                file_path += '.ogg'
            self.export_audio_to_file(file_path, format="ogg")
        else:
            # 根据文件扩展名自动判断
            ext = file_path.lower()
            if ext.endswith('.json'):
                if not file_path.endswith('.json'):
                    file_path += '.json'
                self.save_project_to_file(file_path)
                self.current_file_path = file_path
            elif ext.endswith('.mid') or ext.endswith('.midi'):
                if not file_path.lower().endswith('.mid'):
                    file_path += '.mid'
                self.export_midi_to_file(file_path)
            elif ext.endswith('.wav'):
                if not file_path.endswith('.wav'):
                    file_path += '.wav'
                self.export_audio_to_file(file_path, format="wav")
            elif ext.endswith('.mp3'):
                if not file_path.endswith('.mp3'):
                    file_path += '.mp3'
                self.export_audio_to_file(file_path, format="mp3")
            elif ext.endswith('.ogg') or ext.endswith('.oga'):
                if not file_path.endswith('.ogg'):
                    file_path += '.ogg'
                self.export_audio_to_file(file_path, format="ogg")
            else:
                # 默认保存为JSON项目文件
                if not file_path.endswith('.json'):
                    file_path += '.json'
                self.save_project_to_file(file_path)
                self.current_file_path = file_path
    
    def save_project_to_file(self, file_path: str):
        """保存项目到文件"""
        try:
            import json
            data = self.sequencer.project.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.setWindowTitle(f"8bit音乐制作器 - {self.sequencer.project.name}")
            self.statusBar().showMessage(f"项目已保存: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存项目失败:\n{str(e)}")
    
    def export_midi_to_file(self, file_path: str):
        """导出MIDI文件"""
        try:
            from core.midi_io import MidiIO
            MidiIO.export_midi(self.sequencer.project, file_path)
            self.statusBar().showMessage(f"已导出MIDI: {file_path}")
            QMessageBox.information(self, "成功", f"MIDI文件已导出:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出MIDI失败:\n{str(e)}")
    
    def export_audio_to_file(self, file_path: str, format: str = "wav"):
        """导出音频文件"""
        try:
            from core.audio_export import AudioExporter
            
            # 生成音频
            audio = self.sequencer.audio_engine.generate_project_audio(
                self.sequencer.project
            )
            
            if len(audio) == 0:
                QMessageBox.warning(self, "警告", "项目中没有音频数据")
                return
            
            # 导出音频文件
            sample_rate = self.sequencer.audio_engine.sample_rate
            AudioExporter.export_audio(audio, file_path, sample_rate, format=format)
            
            self.statusBar().showMessage(f"已导出{format.upper()}: {file_path}")
            QMessageBox.information(self, "成功", f"{format.upper()}文件已导出:\n{file_path}")
        except ImportError as e:
            error_msg = str(e)
            if "mp3" in format.lower() or "pydub" in error_msg or "ffmpeg" in error_msg or "moviepy" in error_msg:
                QMessageBox.warning(
                    self, "缺少依赖",
                    "导出MP3需要安装以下库之一：\n\n"
                    "方法1（推荐）：安装moviepy（会自动下载内置ffmpeg）\n"
                    "  pip install moviepy\n\n"
                    "方法2：安装pydub并手动安装ffmpeg\n"
                    "  pip install pydub\n"
                    "  然后从 https://ffmpeg.org/ 下载安装ffmpeg\n\n"
                    "或者，您可以使用OGG格式（无需额外依赖）"
                )
            elif "soundfile" in error_msg:
                QMessageBox.warning(
                    self, "缺少依赖",
                    "导出OGG需要安装soundfile库。\n\n"
                    "请运行以下命令安装：\n"
                    "pip install soundfile"
                )
            else:
                QMessageBox.critical(self, "错误", f"导出失败:\n{error_msg}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出{format.upper()}失败:\n{str(e)}")
    
    def import_midi_file(self, file_path: str):
        """导入MIDI文件"""
        try:
            # 检查是否有未保存的更改
            if not self.check_unsaved_changes():
                return
            
            # 创建加载进度对话框
            progress = QProgressDialog("正在导入MIDI文件...", "取消", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)  # 立即显示
            progress.setValue(0)
            QApplication.processEvents()  # 处理事件，确保对话框显示
            
            progress.setLabelText("正在读取MIDI文件...")
            progress.setValue(10)
            QApplication.processEvents()
            
            # 清除属性面板的状态（清除旧的音轨信息）
            self.property_panel.set_track(None)
            self.property_panel.set_note(None, None)
            self.property_panel.set_notes([])
            
            progress.setLabelText("正在解析MIDI数据...")
            progress.setValue(20)
            QApplication.processEvents()
            
            # 获取当前选择的默认波形（从统一编辑器）
            default_waveform = self.unified_editor.selected_waveform
            
            progress.setLabelText("正在导入MIDI文件...")
            progress.setValue(40)
            QApplication.processEvents()
            
            # 导入MIDI文件：为保证忠实还原原始MIDI，这里强制关闭吸附并允许重叠，
            # 避免在导入阶段移动音符位置或修改节奏结构。
            project = MidiIO.import_midi(
                file_path,
                default_waveform=default_waveform,
                snap_to_beat=False,   # 不在导入时对齐到拍
                allow_overlap=True    # 允许音符重叠（保持和声/和弦结构）
            )
            
            progress.setLabelText("正在设置项目...")
            progress.setValue(60)
            QApplication.processEvents()
            
            # 设置项目
            self.sequencer.set_project(project)
            self.current_file_path = None  # MIDI导入后，项目文件路径为空
            # 保存MIDI文件路径
            self.current_midi_file_path = file_path
            
            progress.setLabelText("正在更新界面...")
            progress.setValue(70)
            QApplication.processEvents()
            
            # 清除选中状态
            self.selected_note = None
            self.selected_track = None
            if hasattr(self, 'unified_editor'):
                self.unified_editor.set_selected_track(None)
            
            progress.setLabelText("正在刷新显示...")
            progress.setValue(80)
            QApplication.processEvents()
            
            # 先更新tracks，然后强制全量刷新UI（清除所有旧的UI元素，确保track引用正确）
            self.sequence_widget.set_tracks(project.tracks, preserve_selection=False)
            self.sequence_widget.refresh(force_full_refresh=True)
            self.refresh_ui()
            
            progress.setLabelText("正在完成导入...")
            progress.setValue(90)
            QApplication.processEvents()
            
            # 更新BPM显示
            self.bpm_spinbox.setValue(int(project.bpm))
            
            progress.setValue(100)
            progress.close()
            
            # 更新文件名显示
            self._update_file_name_display()
            self.statusBar().showMessage(f"已导入MIDI: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入MIDI失败:\n{str(e)}")
    
    def import_midi(self):
        """导入MIDI文件（保留以兼容旧代码）"""
        # 获取上次打开的目录
        last_dir = self.settings.value("last_open_directory", "")
        if not last_dir or not os.path.exists(last_dir):
            last_dir = ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入MIDI", last_dir, "MIDI文件 (*.mid *.midi);;所有文件 (*.*)"
        )
        
        # 保存当前打开的目录
        if file_path:
            directory = os.path.dirname(file_path)
            self.settings.setValue("last_open_directory", directory)
            self.import_midi_file(file_path)
    
    
    def play(self):
        """播放"""
        # 如果已经在播放，不重复播放
        if self.sequencer.playback_state.is_playing:
            return
        
        # 获取当前播放头位置
        current_time = self.sequence_widget.playhead_time
        
        # 禁用所有预览功能（钢琴键盘、打击乐等）
        self.unified_editor.set_preview_enabled(False)
        
        self.sequencer.play(start_time=current_time)
        self.statusBar().showMessage("播放中...")
        
        # 记录播放开始时间
        import time
        self.playback_start_time = time.time()
        self.playback_start_offset = current_time
        
        # 更新按钮状态和文本
        if hasattr(self, 'play_stop_button'):
            self.play_stop_button.setText("⏸")  # 暂停图标
            self.play_stop_button.setToolTip("暂停")
        
        # 同步节拍器
        if self.metronome_widget.is_enabled:
            self.metronome_widget.set_playing(True)
        
        # 更新示波器播放状态
        if hasattr(self, 'oscilloscope_widget'):
            self.oscilloscope_widget.set_playing(True)
    
    def pause(self):
        """暂停"""
        # 如果已经在暂停状态，不重复暂停
        if not self.sequencer.playback_state.is_playing:
            return
        
        if self.sequencer.playback_state.is_playing:
            self.sequencer.stop()
            self.statusBar().showMessage("已暂停")
            # 不重置播放头位置，保持当前位置
            # 不启用预览功能，保持暂停状态
            # 同步节拍器
            self.metronome_widget.set_playing(False)
        
        # 更新示波器播放状态
        if hasattr(self, 'oscilloscope_widget'):
            self.oscilloscope_widget.set_playing(False)
        
        # 更新按钮状态和文本
        if hasattr(self, 'play_stop_button'):
            self.play_stop_button.setText("▶")  # 播放图标
            self.play_stop_button.setToolTip("播放")
    
    def stop(self):
        """停止"""
        self.sequencer.stop()
        self.statusBar().showMessage("已停止")
        
        # 重置播放头到开始位置
        self.sequence_widget.set_playhead_time(0.0)
        self.playback_start_time = None
        
        # 启用所有预览功能（钢琴键盘、打击乐等）
        self.unified_editor.set_preview_enabled(True)
        
        # 同步节拍器
        self.metronome_widget.set_playing(False)
        
        # 更新按钮状态和文本
        if hasattr(self, 'play_stop_button'):
            self.play_stop_button.setText("▶")  # 播放图标
            self.play_stop_button.setToolTip("播放")
    
    def switch_view(self, index: int):
        """切换视图
        
        Args:
            index: 视图索引（0=序列视图，1=示波器视图）
        """
        # 如果切换到示波器视图，检查是否有选中的音轨
        if index == 1:  # 示波器视图
            # 优先检查用户是否选择了要渲染的音轨
            if hasattr(self.oscilloscope_widget, '_selected_tracks_for_render') and \
               self.oscilloscope_widget._selected_tracks_for_render:
                # 用户已经选择了要渲染的音轨，直接使用，不覆盖
                enabled_tracks = [t for t in self.sequencer.project.tracks if t.enabled]
                user_selected = [t for t in self.oscilloscope_widget._selected_tracks_for_render if t in enabled_tracks]
                if user_selected:
                    # 用户选择的音轨存在且启用，使用它们
                    self.oscilloscope_widget.set_tracks(user_selected)
                else:
                    # 用户选择的音轨都不在启用的音轨中，显示提示
                    self.oscilloscope_widget.set_tracks([])
                    self.statusBar().showMessage("选择的音轨未启用，请先启用音轨")
            else:
                # 没有用户选择的音轨，检查是否有选中的音轨
                selected_track = self._get_selected_track()
                
                if selected_track is None:
                    # 没有选中音轨，显示提示
                    self.view_stack.setCurrentIndex(index)
                    if hasattr(self, 'oscilloscope_widget'):
                        self.oscilloscope_widget.set_tracks([])  # 清空音轨，显示提示
                    self.statusBar().showMessage("请先选择一个音轨")
                    # 更新拨动开关位置（即使没有选中音轨也切换到示波器视图）
                    if hasattr(self, 'view_toggle_switch'):
                        # 临时断开信号，避免循环调用
                        self.view_toggle_switch.position_changed.disconnect()
                        self.view_toggle_switch.animate_to(index)
                        # 重新连接信号
                        self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
                    return
                else:
                    # 有选中的音轨，更新示波器
                    enabled_tracks = [t for t in self.sequencer.project.tracks if t.enabled]
                    if selected_track in enabled_tracks:
                        self.oscilloscope_widget.set_tracks(enabled_tracks, selected_track=selected_track)
        
        if hasattr(self, 'view_stack'):
            self.view_stack.setCurrentIndex(index)
            # 更新拨动开关位置（不触发信号，避免循环调用）
            if hasattr(self, 'view_toggle_switch'):
                # 临时断开信号，避免循环调用
                self.view_toggle_switch.position_changed.disconnect()
                self.view_toggle_switch.animate_to(index)
                # 重新连接信号
                self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
    
    def _get_selected_track(self):
        """获取当前选中的音轨（从多个可能的来源）"""
        # 1. 检查 sequence_widget 的 highlighted_track
        if hasattr(self, 'sequence_widget') and hasattr(self.sequence_widget, 'highlighted_track'):
            if self.sequence_widget.highlighted_track:
                return self.sequence_widget.highlighted_track
        
        # 2. 检查 main_window 的 selected_track
        if hasattr(self, 'selected_track') and self.selected_track:
            return self.selected_track
        
        # 3. 检查 unified_editor 的 selected_track
        if hasattr(self, 'unified_editor') and hasattr(self.unified_editor, 'selected_track'):
            if self.unified_editor.selected_track:
                return self.unified_editor.selected_track
        
        return None
    
    def on_view_switch_changed(self, position: int):
        """视图拨动开关位置改变"""
        self.switch_view(position)
    
    def on_render_waveform_requested(self, track):
        """渲染音轨选择请求"""
        # 获取所有启用的音轨
        enabled_tracks = [t for t in self.sequencer.project.tracks if t.enabled]
        
        if not enabled_tracks:
            # 没有启用的音轨
            self.statusBar().showMessage("没有启用的音轨，请先启用音轨")
            return
        
        # 如果不超过3个音轨，自动选择所有音轨渲染
        if len(enabled_tracks) <= 3:
            # 自动选择所有音轨
            self.oscilloscope_widget.set_selected_tracks(enabled_tracks)
            # 切换到示波器视图
            self.view_stack.setCurrentIndex(1)
            if hasattr(self, 'view_toggle_switch'):
                self.view_toggle_switch.position_changed.disconnect()
                self.view_toggle_switch.animate_to(1)
                self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
            # 渲染所有音轨
            self.oscilloscope_widget.set_tracks(enabled_tracks)
            self.statusBar().showMessage(f"正在渲染 {len(enabled_tracks)} 个音轨的波形")
        else:
            # 超过3个音轨，弹出选择对话框
            self.show_track_selection_dialog(enabled_tracks)
    
    def _update_file_name_display(self):
        """更新文件名显示"""
        if hasattr(self, 'file_name_label'):
            if self.current_midi_file_path:
                # 显示MIDI文件名
                file_name = os.path.basename(self.current_midi_file_path)
                self.file_name_label.setText(f"文件: {file_name}")
            elif self.current_file_path:
                # 显示项目文件名
                file_name = os.path.basename(self.current_file_path)
                self.file_name_label.setText(f"文件: {file_name}")
            else:
                # 没有打开文件
                self.file_name_label.setText("")
    
    def on_bpm_changed(self, value: int):
        """BPM改变"""
        # 播放期间禁止调整BPM
        if self.sequencer.playback_state.is_playing:
            # 恢复原来的BPM值
            current_bpm = int(self.sequencer.get_bpm())
            self.bpm_spinbox.blockSignals(True)  # 临时阻止信号，避免循环
            self.bpm_spinbox.setValue(current_bpm)
            self.bpm_spinbox.blockSignals(False)
            self.statusBar().showMessage("播放期间不能调整BPM，请先停止播放")
            return
        
        bpm = float(value)
        old_bpm = self.sequencer.get_bpm()
        self.sequencer.set_bpm(bpm)
        self.sequence_widget.set_bpm(bpm)
        self.unified_editor.set_bpm(bpm)
        self.property_panel.set_bpm(bpm)
        self.metronome_widget.set_bpm(bpm)
        # 更新示波器BPM
        if hasattr(self, 'oscilloscope_widget'):
            self.oscilloscope_widget.set_bpm(bpm)
        
        # 如果正在播放，需要重新计算播放位置（基于新的BPM）
        if self.sequencer.playback_state.is_playing and self.playback_start_time:
            import time
            # 计算当前播放时间（基于旧BPM）
            elapsed_time = time.time() - self.playback_start_time
            current_time_old_bpm = self.playback_start_offset + elapsed_time
            
            # 将时间转换为节拍数（基于旧BPM）
            beats_old = current_time_old_bpm * old_bpm / 60.0
            
            # 将节拍数转换回时间（基于新BPM）
            current_time_new_bpm = beats_old * 60.0 / bpm
            
            # 更新播放起始偏移，确保播放线位置正确
            self.playback_start_offset = current_time_new_bpm
            self.playback_start_time = time.time()
        
        self.refresh_ui()
    
    def on_volume_changed(self, value: int):
        """音量改变（实时更新）"""
        volume = value / 100.0  # 转换为0.0-1.0
        self.sequencer.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{value}%")
    
    def on_volume_slider_released(self):
        """播放音量改变（实时更新，不需要重新播放）"""
        value = self.volume_slider.value()
        volume = value / 100.0  # 转换为0.0-1.0
        self.sequencer.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{value}%")
        # 音量改变实时生效，不需要重新播放
    
    def update_playback_status(self):
        """更新播放状态和播放头"""
        if self.sequencer.playback_state.is_playing and self.playback_start_time:
            import time
            # 计算当前播放时间
            elapsed_time = time.time() - self.playback_start_time
            current_time = self.playback_start_offset + elapsed_time
            
            # 只有在进度条不在拖动状态时才更新播放头（避免与用户拖动冲突）
            if hasattr(self.sequence_widget, 'progress_bar'):
                if not self.sequence_widget.progress_bar.is_dragging:
                    # 更新播放头
                    self.sequence_widget.set_playhead_time(current_time)
                    # 更新进度条的当前时间
                    self.sequence_widget.progress_bar.set_current_time(current_time)
            
            # 更新示波器
            if hasattr(self, 'oscilloscope_widget'):
                self.oscilloscope_widget.set_current_time(current_time)
            
            # 确保预览被禁用（防止播放过程中被启用）
            if self.unified_editor.preview_enabled:
                self.unified_editor.set_preview_enabled(False)
            
            # 检查是否播放完毕（简化：如果播放头超过项目总时长，停止）
            # 优先使用音频真实结束时间（适配导入MIDI时BPM变化的情况）
            total_duration = self.sequencer.playback_state.end_time or self.sequencer.project.get_total_duration()
            if current_time >= total_duration:
                self.stop()
        elif not self.sequencer.playback_state.is_playing:
            # 播放停止时，节拍器也停止，并启用预览
            self.metronome_widget.set_playing(False)
            # 如果预览被禁用，重新启用
            if not self.unified_editor.preview_enabled:
                self.unified_editor.set_preview_enabled(True)
    
    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改（简化实现）"""
        # 这里可以添加检查逻辑
        return True
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于",
            "8bit音乐制作器 v0.1.0\n\n"
            "一个功能完备的8bit音乐和音效制作器。\n\n"
            "使用PyQt5开发。"
        )
    
    def setup_shortcuts(self):
        """设置快捷键"""
        # 八度增减快捷键
        octave_up_seq = self.shortcut_manager.get_key_sequence("octave_up")
        if octave_up_seq:
            octave_up_action = QAction(self)
            octave_up_action.setShortcut(octave_up_seq)
            octave_up_action.triggered.connect(self.octave_up)
            self.addAction(octave_up_action)
        
        octave_down_seq = self.shortcut_manager.get_key_sequence("octave_down")
        if octave_down_seq:
            octave_down_action = QAction(self)
            octave_down_action.setShortcut(octave_down_seq)
            octave_down_action.triggered.connect(self.octave_down)
            self.addAction(octave_down_action)
        
        # 删除最后一个音符快捷键
        delete_last_note_seq = self.shortcut_manager.get_key_sequence("delete_last_note")
        if delete_last_note_seq:
            delete_last_note_action = QAction(self)
            delete_last_note_action.setShortcut(delete_last_note_seq)
            delete_last_note_action.triggered.connect(self.delete_last_note)
            self.addAction(delete_last_note_action)
        
        # 将快捷键管理器传递给子组件
        if hasattr(self, 'unified_editor'):
            self.unified_editor.setup_shortcuts(self.shortcut_manager)
            # 更新钢琴键盘按钮文本显示快捷键
            if hasattr(self.unified_editor, 'piano_keyboard'):
                self.unified_editor.piano_keyboard.update_button_texts()
    
    def octave_up(self):
        """增加一度（八度）"""
        if hasattr(self, 'unified_editor') and hasattr(self.unified_editor, 'piano_keyboard'):
            current_octave = self.unified_editor.piano_keyboard.current_octave
            if current_octave < 8:
                self.unified_editor.piano_keyboard.on_octave_changed(current_octave + 1)
    
    def octave_down(self):
        """减少一度（八度）"""
        if hasattr(self, 'unified_editor') and hasattr(self.unified_editor, 'piano_keyboard'):
            current_octave = self.unified_editor.piano_keyboard.current_octave
            if current_octave > 0:
                self.unified_editor.piano_keyboard.on_octave_changed(current_octave - 1)
    
    def delete_last_note(self):
        """删除当前音轨上的最后一个音符"""
        from core.models import TrackType
        
        # 确定目标音轨
        target_track = None
        
        # 优先使用统一编辑器选中的音轨
        if hasattr(self, 'unified_editor') and hasattr(self.unified_editor, 'selected_track'):
            if self.unified_editor.selected_track and self.unified_editor.selected_track.track_type == TrackType.NOTE_TRACK:
                target_track = self.unified_editor.selected_track
        
        # 如果没有选中的音轨，使用第一个音符音轨
        if target_track is None:
            for track in self.sequencer.project.tracks:
                if track.track_type == TrackType.NOTE_TRACK and track.notes:
                    target_track = track
                    break
        
        # 如果没有找到音轨或音轨没有音符
        if target_track is None or not target_track.notes:
            self.statusBar().showMessage("没有可删除的音符")
            return
        
        # 找到最后一个音符（end_time最大的，如果有多个，选择start_time最大的）
        last_note = None
        max_end_time = -1
        max_start_time = -1
        
        for note in target_track.notes:
            end_time = note.end_time
            if end_time > max_end_time or (end_time == max_end_time and note.start_time > max_start_time):
                max_end_time = end_time
                max_start_time = note.start_time
                last_note = note
        
        if last_note:
            # 使用命令系统删除音符（支持撤销/重做）
            self.sequencer.remove_note(target_track, last_note, use_command=True)
            self.refresh_ui()
            
            # 显示提示信息
            note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            octave = last_note.pitch // 12 - 1
            note_name = note_names[last_note.pitch % 12]
            self.statusBar().showMessage(f"已删除最后一个音符: {note_name}{octave} (音轨: {target_track.name})")
        else:
            self.statusBar().showMessage("没有找到可删除的音符")
    
    def show_settings(self):
        """显示设置对话框"""
        from ui.settings_dialog import SettingsDialog
        # 将示波器widget传给设置对话框，便于直接调整相关参数
        osc_widget = getattr(self, "oscilloscope_widget", None)
        dialog = SettingsDialog(self, oscilloscope_widget=osc_widget)
        if dialog.exec_() == QDialog.Accepted:
            # 设置已应用，在此基础上强制对序列编辑器做一次全量刷新，
            # 确保任何显示相关的变更（包括播放线刷新间隔引发的重绘）
            # 都不会留下“音符临时不显示”的状态。
            if hasattr(self, "sequence_widget") and hasattr(self.sequencer, "project"):
                try:
                    # 先同步轨道引用，再做全量刷新
                    self.sequence_widget.set_tracks(self.sequencer.project.tracks, preserve_selection=True)
                    self.sequence_widget.refresh(force_full_refresh=True)
                except Exception:
                    # 出现异常时避免影响主流程，仅在状态栏提示
                    pass
            self.statusBar().showMessage("设置已更新")
    
    def show_shortcut_config(self):
        """显示快捷键配置对话框"""
        # 现在在统一的设置对话框中进行快捷键配置，并自动切换到“快捷键”标签页
        from ui.settings_dialog import SettingsDialog
        osc_widget = getattr(self, "oscilloscope_widget", None)
        dialog = SettingsDialog(self, oscilloscope_widget=osc_widget)
        # 切换到“快捷键”分类
        for i in range(dialog.category_list.count()):
            item = dialog.category_list.item(i)
            if item and item.text() == "快捷键":
                dialog.category_list.setCurrentRow(i)
                break
        if dialog.exec_() == QDialog.Accepted:
            # 重新设置快捷键
            self.setup_shortcuts()
            if hasattr(self, 'unified_editor'):
                self.unified_editor.setup_shortcuts(self.shortcut_manager)
                # 更新钢琴键盘按钮文本
                if hasattr(self.unified_editor, 'piano_keyboard'):
                    self.unified_editor.piano_keyboard.update_button_texts()
            self.statusBar().showMessage("快捷键配置已更新")
    
    def keyPressEvent(self, event):
        """全局键盘事件"""
        # 空格键：播放/暂停（除非焦点在输入框中）
        if event.key() == Qt.Key_Space:
            focus_widget = self.focusWidget()
            # 如果焦点在输入框、SpinBox等可编辑控件上，不处理空格键
            if not isinstance(focus_widget, (QSpinBox,)):
                self.toggle_play_pause()
                event.accept()
                return
        
        # 其他按键传递给默认处理
        super().keyPressEvent(event)
    
    def toggle_property_panel(self, visible: bool):
        """切换属性面板的显示/隐藏"""
        self.property_dock.setVisible(visible)
        # 确保乐谱面板状态按钮与实际一致（互斥显示更符合直觉）
        if visible and hasattr(self, "toggle_score_action"):
            self.toggle_score_action.setChecked(self.score_dock.isVisible())

    def _focus_property_panel(self):
        """确保属性面板可见并置于属性/乐谱堆叠的最前面"""
        if not hasattr(self, "property_dock"):
            return
        self.property_dock.setVisible(True)
        if hasattr(self, "toggle_property_action"):
            self.toggle_property_action.setChecked(True)
        try:
            # 如果属性面板与乐谱面板堆叠在一起，这里确保切换到“属性面板”这一页
            self.property_dock.raise_()
        except Exception:
            pass

    def toggle_score_panel(self, visible: bool):
        """切换乐谱面板的显示/隐藏"""
        if not hasattr(self, "score_dock"):
            return
        self.score_dock.setVisible(visible)
        # 可根据需要选择互斥：这里不强制关闭属性面板，只是跟随更新菜单状态
        if hasattr(self, "toggle_property_action"):
            self.toggle_property_action.setChecked(self.property_dock.isVisible())

    def toggle_style_params_panel(self, visible: bool):
        """切换风格参数面板的显示/隐藏"""
        if not hasattr(self, "style_dock"):
            return
        self.style_dock.setVisible(visible)

    # ---- 乐谱面板相关逻辑 ----

    def on_score_create_from_selection(self):
        """从当前选中的音符/鼓点创建乐谱片段"""
        if not hasattr(self.sequence_widget, "selected_items"):
            return

        selected = list(self.sequence_widget.selected_items)
        if not selected:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先在音轨区域选择一个或多个音符/鼓点。")
            return

        # 要求所有选中的项在同一个音轨上
        first_track = selected[0][1]
        from core.track_events import DrumEvent
        is_drum_track = first_track.track_type == TrackType.DRUM_TRACK
        for item, track in selected:
            if track is not first_track:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "提示", "当前仅支持从单个音轨的选择创建片段，请不要跨多个音轨选择。")
                return
            # 简单校验类型一致
            if is_drum_track and not isinstance(item, DrumEvent):
                QMessageBox.warning(self, "提示", "鼓点乐谱片段仅支持来自打击乐音轨的事件。")
                return

        # 计算相对时间/节拍，起点归一到 0
        if is_drum_track:
            # 使用节拍
            all_beats = [ev.start_beat for ev, _t in selected]
            base_beat = min(all_beats)
            drums = []
            for ev, _t in selected:
                drums.append(
                    {
                        "offset_beats": ev.start_beat - base_beat,
                        "duration_beats": ev.duration_beats,
                        "drum_type": ev.drum_type.name,
                        "velocity": getattr(ev, "velocity", 100),
                    }
                )
            snippet_type = "drum"
            data = {"drums": drums}
        else:
            # 普通音符使用秒
            all_times = [n.start_time for n, _t in selected]
            base_time = min(all_times)
            notes = []
            for n, _t in selected:
                notes.append(
                    {
                        "offset": n.start_time - base_time,
                        "duration": n.duration,
                        "pitch": n.pitch,
                        "velocity": getattr(n, "velocity", 100),
                        "waveform": getattr(getattr(n, "waveform", None), "name", ""),
                        "duty_cycle": getattr(n, "duty_cycle", 0.5),
                    }
                )
            snippet_type = "note"
            data = {"notes": notes}

        # 让用户输入名称和分组
        from PyQt5.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "乐谱片段名称", "请输入片段名称：")
        if not ok or not name.strip():
            return
        name = name.strip()

        group, ok = QInputDialog.getText(self, "乐谱片段分组", "可选：输入分组名称（例如：常用鼓点 / 和弦进行）：")
        if not ok:
            group = ""
        group = group.strip()

        # 添加到库
        snippet_id = self.score_library.add_snippet(
            name=name,
            group=group,
            snippet_type=snippet_type,
            track_name=first_track.name,
            data=data,
        )

        # 刷新 UI
        if hasattr(self, "score_panel"):
            self.score_panel.refresh()

        self.statusBar().showMessage(f"已保存乐谱片段：{name}（{snippet_id[:8]}）")

    def on_score_apply_snippet(self, snippet_id: str):
        """在当前选中音轨应用指定乐谱片段"""
        snippet = self.score_library.get_snippet(snippet_id)
        if not snippet:
            return

        snippet_type = snippet.get("type")
        data = snippet.get("data") or {}

        # 选择目标音轨：优先使用当前选中/高亮的音轨
        target_track = self._get_selected_track()
        if target_track is None:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先在音轨区域选择一个目标音轨。")
            return

        if snippet_type == "drum" and target_track.track_type != TrackType.DRUM_TRACK:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "鼓点乐谱片段只能应用到打击乐音轨。")
            return
        if snippet_type == "note" and target_track.track_type != TrackType.NOTE_TRACK:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "音符乐谱片段只能应用到音符音轨（主旋律/低音等）。")
            return

        # 读取统一编辑器当前的插入模式和波形设置
        insert_mode = getattr(self.unified_editor, "insert_mode", "playhead")
        selected_waveform = getattr(self.unified_editor, "selected_waveform", None)

        # 计算插入起点（顺序插入 / 播放线插入）
        bpm = self.sequencer.get_bpm()
        if insert_mode == "sequential":
            # 顺序插入：从当前音轨末尾开始
            if snippet_type == "drum":
                if target_track.drum_events:
                    last_end_beat = max(ev.end_beat for ev in target_track.drum_events)
                else:
                    last_end_beat = 0.0
                base_beat = last_end_beat
                base_time = base_beat * 60.0 / bpm
            else:
                if target_track.notes:
                    last_end_time = max(n.end_time for n in target_track.notes)
                else:
                    last_end_time = 0.0
                base_time = last_end_time
                base_beat = base_time * bpm / 60.0
        else:
            # 播放线插入：使用当前播放线位置
            base_time = float(self.sequence_widget.playhead_time)
            base_beat = base_time * bpm / 60.0

        from core.track_events import DrumType
        from core.models import WaveformType

        if snippet_type == "drum":
            drums = data.get("drums") or []
            for info in drums:
                offset_beats = float(info.get("offset_beats", 0.0))
                duration_beats = float(info.get("duration_beats", 1.0))
                drum_name = info.get("drum_type", "KICK")
                try:
                    drum_type = getattr(DrumType, drum_name)
                except AttributeError:
                    drum_type = DrumType.KICK
                velocity = int(info.get("velocity", 100))
                start_beat = base_beat + offset_beats
                self.sequencer.add_drum_event(
                    target_track,
                    drum_type,
                    start_beat,
                    duration_beats,
                    velocity=velocity,
                )
        else:
            notes = data.get("notes") or []
            for info in notes:
                offset = float(info.get("offset", 0.0))
                duration = float(info.get("duration", 0.25))
                pitch = int(info.get("pitch", 60))
                velocity = int(info.get("velocity", 100))
                # 波形优先采用统一编辑器右侧当前选择，其次退回片段中保存的波形信息
                waveform_name = info.get("waveform", "") or "SQUARE"
                duty_cycle = float(info.get("duty_cycle", 0.5))

                start_time = base_time + offset
                note = self.sequencer.add_note(
                    target_track,
                    pitch,
                    start_time,
                    duration,
                    velocity=velocity,
                )
                # 恢复/覆盖波形：优先使用统一编辑器当前选择的波形
                try:
                    if selected_waveform is not None:
                        note.waveform = selected_waveform
                    else:
                        note.waveform = getattr(WaveformType, waveform_name)
                except AttributeError:
                    pass
                if hasattr(note, "duty_cycle"):
                    note.duty_cycle = duty_cycle

        # 应用后刷新 UI
        self.refresh_ui(preserve_selection=False)
        self.statusBar().showMessage(f"已将乐谱片段“{snippet.get('name', '')}”应用到音轨：{target_track.name}")

    def on_score_preview_snippet(self, snippet_id: str):
        """试听指定乐谱片段（不改动工程，只播放一次）"""
        snippet = self.score_library.get_snippet(snippet_id)
        if not snippet:
            return

        snippet_type = snippet.get("type")
        data = snippet.get("data") or {}

        # 暂时停掉当前播放，避免和预览混在一起
        if self.sequencer.playback_state.is_playing:
            self.stop()

        bpm = self.sequencer.get_bpm()

        from core.models import Track, TrackType, WaveformType, Note, ADSRParams
        from core.track_events import DrumType, DrumEvent

        # 构造一个临时轨道，仅用于生成预览音频
        # Track 数据模型当前没有 waveform 字段，波形是 Note 级别的属性，这里只需要一个 NOTE_TRACK 轨道容器即可。
        preview_track = Track(name="预览", track_type=TrackType.NOTE_TRACK)

        if snippet_type == "drum":
            # 将鼓点片段转换为一个临时鼓轨道
            preview_track.track_type = TrackType.DRUM_TRACK
            drums = data.get("drums") or []
            for info in drums:
                start_beat = float(info.get("offset_beats", 0.0))
                duration_beats = float(info.get("duration_beats", 1.0))
                drum_name = info.get("drum_type", "KICK")
                try:
                    drum_type = getattr(DrumType, drum_name)
                except AttributeError:
                    drum_type = DrumType.KICK
                velocity = int(info.get("velocity", 100))
                event = DrumEvent(
                    drum_type=drum_type,
                    start_beat=start_beat,
                    duration_beats=duration_beats,
                    velocity=velocity,
                )
                preview_track.drum_events.append(event)
        else:
            # 普通音符片段：构造若干 Note
            notes = data.get("notes") or []
            for info in notes:
                offset = float(info.get("offset", 0.0))
                duration = float(info.get("duration", 0.5))
                pitch = int(info.get("pitch", 60))
                velocity = int(info.get("velocity", 100))
                waveform_name = info.get("waveform", "SQUARE")
                try:
                    waveform = getattr(WaveformType, waveform_name)
                except AttributeError:
                    waveform = WaveformType.SQUARE
                duty = float(info.get("duty_cycle", 0.5))
                note = Note(
                    start_time=offset,
                    duration=duration,
                    pitch=pitch,
                    velocity=velocity,
                    waveform=waveform,
                    duty_cycle=duty,
                    adsr=ADSRParams(),
                )
                preview_track.notes.append(note)

        # 使用音频引擎直接为单轨道生成音频并播放
        try:
            audio = self.sequencer.audio_engine.generate_track_audio(
                preview_track,
                start_time=0.0,
                end_time=None,
                bpm=bpm,
                original_bpm=bpm,
            )
            self.sequencer.audio_engine.play_audio(audio, loop=False)
            self.statusBar().showMessage("正在试听乐谱片段")
        except Exception:
            # 预览失败不影响主流程
            pass

    def on_score_delete_snippet(self, snippet_id: str):
        """删除指定乐谱片段"""
        self.score_library.delete_snippet(snippet_id)
        if hasattr(self, "score_panel"):
            self.score_panel.refresh()
        self.statusBar().showMessage("已删除乐谱片段")
    
    def undo(self):
        """撤销操作"""
        description = self.sequencer.undo()
        if description:
            self.statusBar().showMessage(f"已撤销: {description}")
            self.refresh_ui()
        else:
            self.statusBar().showMessage("无法撤销")
    
    def redo(self):
        """重做操作"""
        description = self.sequencer.redo()
        if description:
            self.statusBar().showMessage(f"已重做: {description}")
            self.refresh_ui()
        else:
            self.statusBar().showMessage("无法重做")
    
    def update_undo_redo_state(self):
        """更新撤销/重做按钮状态"""
        self.undo_action.setEnabled(self.sequencer.can_undo())
        self.redo_action.setEnabled(self.sequencer.can_redo())
    
    def on_add_track_clicked(self):
        """添加音轨按钮点击"""
        from core.models import WaveformType
        from PyQt5.QtWidgets import QLineEdit
        
        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("添加音轨")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        # 音轨名称输入
        layout.addWidget(QLabel("音轨名称:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("请输入音轨名称")
        name_input.setText(f"音轨 {len(self.sequencer.project.tracks) + 1}")
        layout.addWidget(name_input)
        
        # 音轨类型选择
        layout.addWidget(QLabel("音轨类型:"))
        track_type_combo = QComboBox()
        track_type_combo.addItems(["音符音轨", "打击乐音轨"])
        layout.addWidget(track_type_combo)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            track_name = name_input.text().strip()
            if not track_name:
                track_name = f"音轨 {len(self.sequencer.project.tracks) + 1}"
            
            track_type = TrackType.NOTE_TRACK if track_type_combo.currentIndex() == 0 else TrackType.DRUM_TRACK
            
            track = self.sequencer.add_track(
                name=track_name,
                track_type=track_type
            )
            
            self.refresh_ui()
            self.statusBar().showMessage(f"已添加音轨: {track.name}")
    
    def show_oscilloscope_render_count_dialog(self):
        """显示示波器渲染音符数设置对话框"""
        if hasattr(self, 'oscilloscope_widget'):
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox
            theme = theme_manager.current_theme
            
            dialog = QDialog(self)
            dialog.setWindowTitle("示波器设置")
            dialog.setStyleSheet(theme.get_style("dialog"))
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            label = QLabel("渲染音符数 (1-50):")
            label.setStyleSheet(theme.get_style("label"))
            layout.addWidget(label)
            
            spinbox = QSpinBox()
            spinbox.setRange(1, 50)
            spinbox.setValue(self.oscilloscope_widget.max_notes_to_render)
            spinbox.setStyleSheet(theme.get_style("line_edit"))
            layout.addWidget(spinbox)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.setStyleSheet(theme.get_style("button"))
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            if dialog.exec_() == QDialog.Accepted:
                self.oscilloscope_widget.max_notes_to_render = spinbox.value()
                # 清除波形缓存，强制重新生成
                if hasattr(self.oscilloscope_widget, 'waveform_cache'):
                    self.oscilloscope_widget.waveform_cache.clear()
                self.oscilloscope_widget.update()
    
    def show_oscilloscope_pre_render_dialog(self):
        """显示示波器预渲染音符数设置对话框"""
        if hasattr(self, 'oscilloscope_widget'):
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QDialogButtonBox
            theme = theme_manager.current_theme
            
            dialog = QDialog(self)
            dialog.setWindowTitle("示波器设置")
            dialog.setStyleSheet(theme.get_style("dialog"))
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            label = QLabel("预渲染音符数 (0-10):")
            label.setStyleSheet(theme.get_style("label"))
            layout.addWidget(label)
            
            spinbox = QSpinBox()
            spinbox.setRange(0, 10)
            spinbox.setValue(self.oscilloscope_widget.pre_render_notes)
            spinbox.setStyleSheet(theme.get_style("line_edit"))
            layout.addWidget(spinbox)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.setStyleSheet(theme.get_style("button"))
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            if dialog.exec_() == QDialog.Accepted:
                self.oscilloscope_widget.pre_render_notes = spinbox.value()
                self.oscilloscope_widget.update()
    
    def show_oscilloscope_code_language_dialog(self):
        """显示示波器代码语言设置对话框"""
        if hasattr(self, 'oscilloscope_widget'):
            from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QTextEdit
            theme = theme_manager.current_theme
            
            dialog = QDialog(self)
            dialog.setWindowTitle("示波器代码语言设置")
            dialog.setStyleSheet(theme.get_style("dialog"))
            dialog.resize(500, 400)
            
            layout = QVBoxLayout()
            dialog.setLayout(layout)
            
            # 语言选择
            label = QLabel("代码语言:")
            label.setStyleSheet(theme.get_style("label"))
            layout.addWidget(label)
            
            language_combo = QComboBox()
            language_combo.addItems(["伪代码 (Pseudocode)", "MicroPython (ESP32)", "汇编 (Assembly)"])
            language_map = {"伪代码 (Pseudocode)": "pseudocode", "MicroPython (ESP32)": "micropython", "汇编 (Assembly)": "assembly"}
            reverse_map = {"pseudocode": 0, "micropython": 1, "assembly": 2}
            language_combo.setCurrentIndex(reverse_map.get(self.oscilloscope_widget.code_language, 0))
            language_combo.setStyleSheet(theme.get_style("line_edit"))
            layout.addWidget(language_combo)
            
            # 代码模板编辑
            template_label = QLabel("代码模板 (可使用变量: {frequency}, {duration}, {duration_ms}, {waveform}, {duty}, {duty_cycle}, {pitch}):")
            template_label.setStyleSheet(theme.get_style("label"))
            layout.addWidget(template_label)
            
            template_edit = QTextEdit()
            current_lang = self.oscilloscope_widget.code_language
            template_edit.setPlainText(self.oscilloscope_widget.code_templates.get(current_lang, ""))
            template_edit.setStyleSheet(theme.get_style("line_edit"))
            template_edit.setFont(QFont("Consolas", 10))
            layout.addWidget(template_edit)
            
            # 语言切换时更新模板
            def on_language_changed(index):
                lang_key = language_map[language_combo.currentText()]
                template_edit.setPlainText(self.oscilloscope_widget.code_templates.get(lang_key, ""))
            language_combo.currentIndexChanged.connect(on_language_changed)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.setStyleSheet(theme.get_style("button"))
            button_box.accepted.connect(dialog.accept)
            button_box.rejected.connect(dialog.reject)
            layout.addWidget(button_box)
            
            if dialog.exec_() == QDialog.Accepted:
                selected_lang = language_map[language_combo.currentText()]
                self.oscilloscope_widget.code_language = selected_lang
                self.oscilloscope_widget.code_templates[selected_lang] = template_edit.toPlainText()
                self.oscilloscope_widget.update()
    
    def show_track_selection_dialog(self, enabled_tracks):
        """显示音轨选择对话框（当启用的音轨超过3个时）
        
        Args:
            enabled_tracks: 所有启用的音轨列表
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox, QScrollArea, QWidget, QMessageBox
        theme = theme_manager.current_theme
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择要渲染的音轨（最多3个）")
        dialog.setStyleSheet(theme.get_style("dialog"))
        dialog.resize(400, 300)
        
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        
        label = QLabel("请选择要渲染的音轨（最多选择3个）:")
        label.setStyleSheet(theme.get_style("label"))
        layout.addWidget(label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        
        checkboxes = []
        # 如果已经有用户选择的音轨，默认选中它们
        default_selected = []
        if hasattr(self.oscilloscope_widget, '_selected_tracks_for_render') and \
           self.oscilloscope_widget._selected_tracks_for_render:
            default_selected = self.oscilloscope_widget._selected_tracks_for_render
        else:
            # 如果没有用户选择，默认选择前3个
            default_selected = enabled_tracks[:3]
        
        for track in enabled_tracks:
            checkbox = QCheckBox(track.name)
            checkbox.setStyleSheet(theme.get_style("label"))
            # 如果音轨在默认选中列表中，设置为选中
            if track in default_selected:
                checkbox.setChecked(True)
            checkboxes.append((checkbox, track))
            scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.setStyleSheet(theme.get_style("button"))
        
        def on_ok():
            selected = [track for checkbox, track in checkboxes if checkbox.isChecked()]
            if len(selected) > 3:
                QMessageBox.warning(dialog, "警告", "最多只能选择3个音轨！")
                return
            if len(selected) == 0:
                QMessageBox.warning(dialog, "警告", "请至少选择1个音轨！")
                return
            
            # 保存用户选择的音轨
            self.oscilloscope_widget.set_selected_tracks(selected)
            
            # 直接使用用户选择的音轨设置示波器（在切换视图之前）
            # 这样即使后续有refresh_ui调用，也会保留用户的选择
            self.oscilloscope_widget.set_tracks(selected)
            
            # 切换到示波器视图
            self.view_stack.setCurrentIndex(1)
            if hasattr(self, 'view_toggle_switch'):
                self.view_toggle_switch.position_changed.disconnect()
                self.view_toggle_switch.animate_to(1)
                self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
            
            # 确保触发重绘
            self.oscilloscope_widget.update()
            self.statusBar().showMessage(f"正在渲染 {len(selected)} 个音轨的波形")
            
            dialog.accept()
        
        button_box.accepted.connect(on_ok)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.exec_()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.check_unsaved_changes():
            self.sequencer.cleanup()
            event.accept()
        else:
            event.ignore()

