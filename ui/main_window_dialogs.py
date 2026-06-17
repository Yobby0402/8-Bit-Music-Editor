"""
主窗口相关的独立对话框辅助函数。
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.llm_seed_prompts import build_seed_suggest_messages
from core.models import Track, TrackRole, TrackType
from core.seed_style_catalog import SeedMusicStyle, get_style_meta, get_style_variants
from core.variation_spec import parse_ai_seed_response
from ui.background_tasks import LlmHttpThread
from ui.qt_thread_debug import thread_log
from ui.settings_manager import get_settings_manager


@dataclass(frozen=True)
class SeedGenerationSelection:
    """Seed 生成对话框返回的用户选择。"""

    style: SeedMusicStyle
    variant_id: str
    seed: str
    length_bars: int
    use_harmony: bool
    use_drums: bool
    length_index: int
    style_index: int
    variant_index: int
    music_description: str = ""
    ai_knobs: Tuple[int, int, int, int] | None = None
    free_form_layout: bool = False


@dataclass(frozen=True)
class NewTrackSelection:
    """添加音轨对话框返回的用户选择。"""

    name: str
    track_type: TrackType
    role: TrackRole | None = None


NEW_TRACK_ROLE_OPTIONS: tuple[tuple[str, TrackRole], ...] = (
    ("主旋律", TrackRole.MELODY),
    ("低音", TrackRole.BASS),
    ("和声", TrackRole.HARMONY),
    ("效果", TrackRole.EFFECT),
)


def build_new_track_default_name(track_count: int, track_type: TrackType) -> str:
    """构建添加音轨对话框中的默认名称。"""
    if track_type == TrackType.DRUM_TRACK:
        return "打击乐"
    return f"音轨 {track_count + 1}"


def resolve_new_track_role_from_editor_index(index: int) -> TrackRole:
    """将角色下拉框索引转换为 TrackRole。"""
    if 0 <= index < len(NEW_TRACK_ROLE_OPTIONS):
        return NEW_TRACK_ROLE_OPTIONS[index][1]
    return TrackRole.MELODY


class _SeedGenerateDialog(QDialog):
    """从 Seed 生成音乐的参数对话框。"""

    def __init__(self, parent=None, last_settings=None):
        super().__init__(parent)
        self.setWindowTitle("从 Seed 生成音乐")
        layout = QVBoxLayout(self)

        last_seed = last_settings.get("seed", "minecraft") if last_settings else "minecraft"
        last_length_index = last_settings.get("length_index", 0) if last_settings else 0
        last_style_index = last_settings.get("style_index", 5) if last_settings else 5
        last_variant_index = last_settings.get("variant_index", 0) if last_settings else 0
        last_harmony = last_settings.get("harmony", True) if last_settings else True
        last_drums = last_settings.get("drums", True) if last_settings else True
        last_desc = (last_settings.get("music_description", "") if last_settings else "") or ""
        kn_last = last_settings.get("ai_knobs") if last_settings else None
        last_free_form = bool(last_settings.get("free_form_layout", False)) if last_settings else False
        self._ai_knobs: Tuple[int, int, int, int] | None = None
        if isinstance(kn_last, (list, tuple)) and len(kn_last) == 4:
            try:
                self._ai_knobs = (int(kn_last[0]), int(kn_last[1]), int(kn_last[2]), int(kn_last[3]))
            except (TypeError, ValueError):
                self._ai_knobs = None
        self._llm_thread: LlmHttpThread | None = None

        seed_row = QHBoxLayout()
        seed_label = QLabel("种子：")
        self.seed_edit = QLineEdit()
        self.seed_edit.setText(last_seed)
        seed_row.addWidget(seed_label)
        seed_row.addWidget(self.seed_edit)
        layout.addLayout(seed_row)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("大致描述（可选）："))
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText(
            "例如：深夜森林、略带忧伤的关底… 会基于描述增加变化（无需 AI 也会用哈希盐）"
        )
        self.desc_edit.setText(last_desc)
        desc_row.addWidget(self.desc_edit, 1)
        layout.addLayout(desc_row)

        ai_row = QHBoxLayout()
        self.ai_suggest_button = QPushButton("用本地 AI 建议种子…")
        self.ai_suggest_button.clicked.connect(self._on_ai_suggest_seed)
        ai_row.addWidget(self.ai_suggest_button)
        ai_row.addStretch(1)
        layout.addLayout(ai_row)

        length_row = QHBoxLayout()
        length_label = QLabel("音乐长度：")
        self.length_preset_combo = QComboBox()
        self.length_preset_combo.addItem("16 小节（4 乐句：起-承-转-合）", 16)
        self.length_preset_combo.addItem("24 小节（6 乐句：扩展段落）", 24)
        self.length_preset_combo.addItem("32 小节（8 乐句：完整段落）", 32)
        self.length_preset_combo.addItem("48 小节（短曲：Intro-Verse-Chorus）", 48)
        self.length_preset_combo.addItem("64 小节（中曲：Intro-Verse-Chorus-Verse-Chorus）", 64)
        self.length_preset_combo.addItem("80 小节（长曲：Intro-Verse-Chorus-Verse-Chorus-Bridge）", 80)
        self.length_preset_combo.addItem("96 小节（完整曲：Intro-Verse-Chorus-Verse-Chorus-Bridge-Chorus）", 96)
        self.length_preset_combo.addItem(
            "112 小节（扩展曲：Intro-Verse-Chorus-Verse-Chorus-Bridge-Chorus-Outro）",
            112,
        )
        self.length_preset_combo.addItem("128 小节（完整作品：包含所有部分）", 128)
        if 0 <= last_length_index < self.length_preset_combo.count():
            self.length_preset_combo.setCurrentIndex(last_length_index)
        else:
            self.length_preset_combo.setCurrentIndex(0)
        length_row.addWidget(length_label)
        length_row.addWidget(self.length_preset_combo)
        layout.addLayout(length_row)

        self.structure_info_label = QLabel("结构：4 个乐句，每个 4 小节（起-承-转-合结构）")
        self.structure_info_label.setWordWrap(True)
        font = self.structure_info_label.font()
        font.setPointSize(max(9, font.pointSize() - 1))
        self.structure_info_label.setFont(font)
        layout.addWidget(self.structure_info_label)

        self.free_form_checkbox = QCheckBox("自由编排（弱化固定乐句/和声循环，变化更大）")
        self.free_form_checkbox.setChecked(last_free_form)
        self.free_form_checkbox.stateChanged.connect(self._on_length_preset_changed)
        layout.addWidget(self.free_form_checkbox)

        track_row = QHBoxLayout()
        track_label = QLabel("轨道：")
        self.harmony_checkbox = QCheckBox("和声")
        self.harmony_checkbox.setChecked(last_harmony)
        self.drum_checkbox = QCheckBox("鼓点")
        self.drum_checkbox.setChecked(last_drums)
        track_row.addWidget(track_label)
        track_row.addWidget(self.harmony_checkbox)
        track_row.addWidget(self.drum_checkbox)
        track_row.addStretch(1)
        layout.addLayout(track_row)

        style_row = QHBoxLayout()
        style_label = QLabel("风格：")
        self.style_combo = QComboBox()
        self.style_combo.addItem("经典 8bit", SeedMusicStyle.CLASSIC_8BIT)
        self.style_combo.addItem("Lofi", SeedMusicStyle.LOFI)
        self.style_combo.addItem("战斗 / 紧张", SeedMusicStyle.BATTLE)
        self.style_combo.addItem("悬疑 / 惊悚", SeedMusicStyle.SUSPENSE)
        self.style_combo.addItem("舒缓 / 美好", SeedMusicStyle.CALM)
        self.style_combo.addItem("重金属 / 摇滚", SeedMusicStyle.ROCK)
        self.style_combo.addItem("慢摇 / 舞曲", SeedMusicStyle.DANCE)
        self.style_combo.addItem("工作坊 / 专注", SeedMusicStyle.WORKSHOP)
        self.style_combo.setCurrentIndex(last_style_index)
        style_row.addWidget(style_label)
        style_row.addWidget(self.style_combo)
        layout.addLayout(style_row)

        variant_row = QHBoxLayout()
        variant_label = QLabel("风格变体：")
        self.variant_combo = QComboBox()
        variant_row.addWidget(variant_label)
        variant_row.addWidget(self.variant_combo)
        layout.addLayout(variant_row)

        self.style_info_label = QLabel()
        self.style_info_label.setWordWrap(True)
        font = self.style_info_label.font()
        font.setPointSize(max(9, font.pointSize() - 1))
        self.style_info_label.setFont(font)
        layout.addWidget(self.style_info_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        ok_button = button_box.button(QDialogButtonBox.Ok)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText("生成")
        if cancel_button is not None:
            cancel_button.setText("取消")

        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        self.length_preset_combo.currentIndexChanged.connect(self._on_length_preset_changed)
        self._on_style_changed(self.style_combo.currentIndex())
        self._on_length_preset_changed()

        if last_variant_index < self.variant_combo.count():
            self.variant_combo.setCurrentIndex(last_variant_index)

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

        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()
        try:
            variants = get_style_variants(style)
        except Exception:
            variants = [{"id": "default", "name": "默认", "desc": ""}]

        for variant in variants:
            name = variant.get("name", "默认")
            variant_id = variant.get("id", "default")
            variant_desc = variant.get("desc", "")
            text = f"{name} - {variant_desc}" if variant_desc else name
            self.variant_combo.addItem(text, variant_id)
        self.variant_combo.blockSignals(False)

    def _on_length_preset_changed(self, *_args):
        """根据选择的长度预设更新结构说明。"""
        bars = self.length_preset_combo.currentData()
        structure_descriptions = {
            16: "结构：4 个乐句，每个 4 小节（起-承-转-合结构）",
            24: "结构：6 个乐句，每个 4 小节（扩展段落结构）",
            32: "结构：8 个乐句，每个 4 小节（完整段落结构）",
            48: "结构：12 个乐句，每个 4 小节（短曲：Intro + Verse + Chorus）",
            64: "结构：16 个乐句，每个 4 小节（中曲：Intro + Verse + Chorus + Verse + Chorus）",
            80: "结构：20 个乐句，每个 4 小节（长曲：Intro + Verse + Chorus + Verse + Chorus + Bridge）",
            96: "结构：24 个乐句，每个 4 小节（完整曲：Intro + Verse + Chorus + Verse + Chorus + Bridge + Chorus）",
            112: "结构：28 个乐句，每个 4 小节（扩展曲：Intro + Verse + Chorus + Verse + Chorus + Bridge + Chorus + Outro）",
            128: "结构：32 个乐句，每个 4 小节（完整作品：包含所有部分，适合完整曲子）",
        }
        desc = structure_descriptions.get(bars, f"结构：{bars} 小节")
        if getattr(self, "free_form_checkbox", None) is not None and self.free_form_checkbox.isChecked():
            desc = (
                f"{desc}\n\n已启用自由编排：Intro 长度、乐句分段、和弦级数与动机池会更随机，"
                "不再严格按「起承转合」固定套路。"
            )
        self.structure_info_label.setText(desc)

    def get_selection(self) -> SeedGenerationSelection:
        """提取用户在对话框中的选择。"""
        return SeedGenerationSelection(
            style=self.style_combo.currentData(),
            variant_id=self.variant_combo.currentData() or "default",
            seed=self.seed_edit.text().strip(),
            length_bars=self.length_preset_combo.currentData(),
            use_harmony=self.harmony_checkbox.isChecked(),
            use_drums=self.drum_checkbox.isChecked(),
            length_index=self.length_preset_combo.currentIndex(),
            style_index=self.style_combo.currentIndex(),
            variant_index=self.variant_combo.currentIndex(),
            music_description=self.desc_edit.text().strip(),
            ai_knobs=self._ai_knobs,
            free_form_layout=self.free_form_checkbox.isChecked(),
        )

    def closeEvent(self, event):
        self._cleanup_llm_thread()
        super().closeEvent(event)

    def _cleanup_llm_thread(self) -> None:
        t = self._llm_thread
        if t is None:
            return
        thread_log(f"SeedDialog cleanup_llm_thread isRunning={t.isRunning()}")
        if t.isRunning():
            # LlmHttpThread.run() 内同步阻塞 httpx；无子线程事件循环，wait 直到请求结束或超时
            if not t.wait(120000):
                thread_log("SeedDialog cleanup_llm_thread wait(120s) returned False")
        self._llm_thread = None
        t.deleteLater()
        self.ai_suggest_button.setEnabled(True)

    def _on_ai_suggest_seed(self) -> None:
        sm = get_settings_manager()
        if not sm.is_ai_enabled():
            QMessageBox.information(
                self,
                "本地 AI",
                "请先在「设置 → 本地 AI (LM Studio)」中勾选「启用本地 AI 功能」。",
            )
            return
        model = sm.get_ai_model()
        if not model:
            QMessageBox.warning(self, "本地 AI", "请在设置中填写「模型 ID」（与 LM Studio 中一致）。")
            return

        style_label = self.style_combo.currentText()
        user_desc = self.desc_edit.text().strip()
        messages = build_seed_suggest_messages(style_label, user_desc)

        self._cleanup_llm_thread()
        self.ai_suggest_button.setEnabled(False)

        thread = LlmHttpThread(
            sm.get_ai_base_url(),
            model,
            messages,
            api_key=sm.get_ai_api_key(),
            timeout_sec=float(sm.get_ai_timeout_sec()),
            parent=None,
        )
        self._llm_thread = thread
        thread.success.connect(self._on_llm_http_success, type=Qt.QueuedConnection)
        thread.failed.connect(self._on_llm_http_failed, type=Qt.QueuedConnection)
        thread.finished.connect(self._on_llm_http_thread_finished, type=Qt.QueuedConnection)
        thread_log("LlmHttpThread.start()")
        thread.start()

    def _on_llm_http_thread_finished(self) -> None:
        thr = self._llm_thread
        thread_log(
            f"LlmHttpThread.finished thr_is_none={thr is None} "
            f"isFinished={thr.isFinished() if thr else 'n/a'}"
        )
        if thr is None:
            return
        self._llm_thread = None
        thr.deleteLater()

    def _on_llm_http_success(self, text: str) -> None:
        thread_log("LlmHttpThread.success")
        self.ai_suggest_button.setEnabled(True)
        self._on_ai_worker_finished(text)

    def _on_llm_http_failed(self, err: object) -> None:
        thread_log(f"LlmHttpThread.failed err={err!r}")
        self.ai_suggest_button.setEnabled(True)
        self._on_ai_worker_failed(err)

    def _on_ai_worker_finished(self, text: object) -> None:
        def apply_and_notify() -> None:
            try:
                raw = "" if text is None else str(text)
                seed_line, knobs = parse_ai_seed_response(raw)
                if seed_line:
                    self.seed_edit.setText(seed_line)
                if knobs is not None:
                    self._ai_knobs = knobs
                QMessageBox.information(
                    self,
                    "本地 AI",
                    "已根据模型输出更新种子文本"
                    + ("与旋钮参数。" if knobs is not None else "。"),
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "本地 AI",
                    f"处理模型返回时出错：{exc}",
                )

        QTimer.singleShot(0, apply_and_notify)

    def _on_ai_worker_failed(self, err: object) -> None:
        err_text = str(err) if err is not None else "未知错误"

        def notify() -> None:
            QMessageBox.warning(self, "本地 AI 请求失败", err_text)

        QTimer.singleShot(0, notify)


def prompt_new_track(parent, track_count: int) -> Optional[NewTrackSelection]:
    """弹出添加音轨对话框，返回用户输入的音轨信息。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("添加音轨")
    dialog.setMinimumWidth(300)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    layout.addWidget(QLabel("音轨名称:"))
    name_input = QLineEdit()
    name_input.setPlaceholderText("请输入音轨名称")
    current_default_name = build_new_track_default_name(track_count, TrackType.NOTE_TRACK)
    name_input.setText(current_default_name)
    layout.addWidget(name_input)

    layout.addWidget(QLabel("音轨类型:"))
    track_type_combo = QComboBox()
    track_type_combo.addItems(["音符音轨", "打击乐音轨"])
    layout.addWidget(track_type_combo)

    track_role_row = QWidget()
    track_role_layout = QHBoxLayout(track_role_row)
    track_role_layout.setContentsMargins(0, 0, 0, 0)
    track_role_layout.addWidget(QLabel("音轨角色:"))
    track_role_combo = QComboBox()
    track_role_combo.addItems([label for label, _ in NEW_TRACK_ROLE_OPTIONS])
    track_role_layout.addWidget(track_role_combo)
    layout.addWidget(track_role_row)

    def refresh_track_type_controls() -> None:
        nonlocal current_default_name
        current_track_type = (
            TrackType.NOTE_TRACK
            if track_type_combo.currentIndex() == 0
            else TrackType.DRUM_TRACK
        )
        track_role_row.setVisible(current_track_type == TrackType.NOTE_TRACK)
        next_default_name = build_new_track_default_name(track_count, current_track_type)
        current_name = name_input.text().strip()
        if not current_name or current_name == current_default_name:
            name_input.setText(next_default_name)
        current_default_name = next_default_name

    track_type_combo.currentIndexChanged.connect(lambda _index: refresh_track_type_controls())
    refresh_track_type_controls()

    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec_() != QDialog.Accepted:
        return None

    track_name = name_input.text().strip() or current_default_name
    track_type = TrackType.NOTE_TRACK if track_type_combo.currentIndex() == 0 else TrackType.DRUM_TRACK
    track_role = None
    if track_type == TrackType.NOTE_TRACK:
        track_role = resolve_new_track_role_from_editor_index(track_role_combo.currentIndex())
    return NewTrackSelection(track_name, track_type, track_role)


def prompt_oscilloscope_render_count(parent, theme, current_value: int) -> Optional[int]:
    """弹出示波器渲染音符数量设置对话框。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("示波器设置")
    dialog.setStyleSheet(theme.get_style("dialog"))

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    label = QLabel("渲染音符数 (1-50):")
    label.setStyleSheet(theme.get_style("label"))
    layout.addWidget(label)

    spinbox = QSpinBox()
    spinbox.setRange(1, 50)
    spinbox.setValue(current_value)
    spinbox.setStyleSheet(theme.get_style("line_edit"))
    layout.addWidget(spinbox)

    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.setStyleSheet(theme.get_style("button"))
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec_() != QDialog.Accepted:
        return None

    return spinbox.value()


def prompt_oscilloscope_pre_render_count(parent, theme, current_value: int) -> Optional[int]:
    """弹出示波器预渲染音符数量设置对话框。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("示波器设置")
    dialog.setStyleSheet(theme.get_style("dialog"))

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    label = QLabel("预渲染音符数 (0-10):")
    label.setStyleSheet(theme.get_style("label"))
    layout.addWidget(label)

    spinbox = QSpinBox()
    spinbox.setRange(0, 10)
    spinbox.setValue(current_value)
    spinbox.setStyleSheet(theme.get_style("line_edit"))
    layout.addWidget(spinbox)

    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.setStyleSheet(theme.get_style("button"))
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec_() != QDialog.Accepted:
        return None

    return spinbox.value()


def prompt_oscilloscope_code_language(
    parent,
    theme,
    current_language: str,
    code_templates: dict[str, str],
) -> Optional[tuple[str, str]]:
    """弹出示波器代码语言和模板设置对话框。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("示波器代码语言设置")
    dialog.setStyleSheet(theme.get_style("dialog"))
    dialog.resize(500, 400)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    label = QLabel("代码语言:")
    label.setStyleSheet(theme.get_style("label"))
    layout.addWidget(label)

    language_combo = QComboBox()
    language_combo.addItems(["伪代码 (Pseudocode)", "MicroPython (ESP32)", "汇编 (Assembly)"])
    language_map = {
        "伪代码 (Pseudocode)": "pseudocode",
        "MicroPython (ESP32)": "micropython",
        "汇编 (Assembly)": "assembly",
    }
    reverse_map = {"pseudocode": 0, "micropython": 1, "assembly": 2}
    language_combo.setCurrentIndex(reverse_map.get(current_language, 0))
    language_combo.setStyleSheet(theme.get_style("line_edit"))
    layout.addWidget(language_combo)

    template_label = QLabel(
        "代码模板 (可使用变量: {frequency}, {duration}, {duration_ms}, {waveform}, {duty}, "
        "{duty_cycle}, {pitch}):"
    )
    template_label.setStyleSheet(theme.get_style("label"))
    layout.addWidget(template_label)

    template_edit = QTextEdit()
    template_edit.setPlainText(code_templates.get(current_language, ""))
    template_edit.setStyleSheet(theme.get_style("line_edit"))
    template_edit.setFont(QFont("Consolas", 10))
    layout.addWidget(template_edit)

    def on_language_changed(_index):
        language_key = language_map[language_combo.currentText()]
        template_edit.setPlainText(code_templates.get(language_key, ""))

    language_combo.currentIndexChanged.connect(on_language_changed)

    button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    button_box.setStyleSheet(theme.get_style("button"))
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec_() != QDialog.Accepted:
        return None

    selected_language = language_map[language_combo.currentText()]
    return selected_language, template_edit.toPlainText()


def prompt_track_selection(
    parent,
    theme,
    enabled_tracks: Sequence[Track],
    default_selected: Sequence[Track],
) -> Optional[list[Track]]:
    """弹出示波器轨道选择对话框。"""
    dialog = QDialog(parent)
    dialog.setWindowTitle("选择要渲染的音轨（最多3个）")
    dialog.setStyleSheet(theme.get_style("dialog"))
    dialog.resize(400, 300)

    layout = QVBoxLayout()
    dialog.setLayout(layout)

    label = QLabel("请选择要渲染的音轨（最多选择3个）:")
    label.setStyleSheet(theme.get_style("label"))
    layout.addWidget(label)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_widget = QWidget()
    scroll_layout = QVBoxLayout()
    scroll_widget.setLayout(scroll_layout)

    checkboxes = []
    for track in enabled_tracks:
        checkbox = QCheckBox(track.name)
        checkbox.setStyleSheet(theme.get_style("label"))
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
        selected_tracks = [track for checkbox, track in checkboxes if checkbox.isChecked()]
        if len(selected_tracks) > 3:
            QMessageBox.warning(dialog, "警告", "最多只能选择3个音轨！")
            return
        if not selected_tracks:
            QMessageBox.warning(dialog, "警告", "请至少选择1个音轨！")
            return
        dialog.accept()

    button_box.accepted.connect(on_ok)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)

    if dialog.exec_() != QDialog.Accepted:
        return None

    return [track for checkbox, track in checkboxes if checkbox.isChecked()]


def prompt_seed_generation(parent, last_settings=None) -> Optional[SeedGenerationSelection]:
    """弹出 Seed 生成对话框，返回用户选择。"""
    dialog = _SeedGenerateDialog(parent, last_settings=last_settings)
    if dialog.exec_() != QDialog.Accepted:
        return None
    return dialog.get_selection()
