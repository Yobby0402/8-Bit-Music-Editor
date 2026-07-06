"""
主窗口中的壳层、布局装配与菜单搭建逻辑。
"""

from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QButtonGroup,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app_info import APP_NAME
from ui.bpm_editor_widget import BPMEditorWidget
from ui.grid_sequence_widget import GridSequenceWidget
from ui.oscilloscope_widget import OscilloscopeWidget
from ui.playback_settings_widget import PlaybackSettingsWidget
from ui.property_panel_widget import PropertyPanelWidget
from ui.right_panel_style import right_panel_stylesheet
from ui.score_library_widget import ScoreLibraryWidget
from ui.sfx_editor_dialog import SfxEditorWidget
from ui.style_params_widget import StyleParamsWidget
from ui.toggle_switch_widget import ToggleSwitchWidget
from ui.unified_editor_widget import UnifiedEditorWidget

RIGHT_PANEL_PAGES = (
    ("property", "属性"),
    ("score", "乐谱"),
    ("style", "风格"),
    ("playback", "播放"),
    ("bpm", "BPM"),
    ("sfx", "音效"),
)

RIGHT_PANEL_NAV_LABELS = {
    "property": "属性",
    "score": "乐谱",
    "style": "风格",
    "playback": "播放",
    "bpm": "BPM",
    "sfx": "音效",
}

RIGHT_PANEL_MIN_WIDTH = 560
MAIN_WINDOW_MIN_WIDTH = 1120
MAIN_WINDOW_MIN_HEIGHT = 650


def calculate_default_window_geometry(
    screen_width: int,
    screen_height: int,
) -> tuple[int, int, int, int]:
    """根据屏幕尺寸计算主窗口默认几何信息。"""
    default_width = int(screen_width * 0.8)
    default_height = int(screen_height * 0.8)
    return (
        int(screen_width * 0.1),
        int(screen_height * 0.1),
        default_width,
        default_height,
    )


def resolve_locked_dock_width(current_width: int, minimum_width: int) -> int:
    """解析右侧 Dock 需要锁定的宽度。"""
    return max(current_width, minimum_width) if current_width > 0 else minimum_width


def calculate_default_center_splitter_sizes(total_height: int) -> tuple[int, int]:
    """Return default sizes for the editor/track vertical splitter."""
    safe_total_height = max(400, int(total_height))
    editor_height = max(180, int(safe_total_height * 0.35))
    track_height = max(220, safe_total_height - editor_height)
    return editor_height, track_height


def configure_splitter_pane(widget: QWidget, *, vertical_policy) -> QWidget:
    """Make a splitter pane shrinkable enough for manual resizing."""
    widget.setMinimumHeight(0)
    policy = widget.sizePolicy()
    policy.setVerticalPolicy(vertical_policy)
    widget.setSizePolicy(policy)
    return widget


def build_right_panel_shell(parent, pages=RIGHT_PANEL_PAGES):
    """Build a single right-side stacked panel with compact top navigation."""
    container = QWidget(parent)
    container.setObjectName("rightPanelShell")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    nav = QWidget(container)
    nav.setObjectName("rightPanelNav")
    nav_layout = QHBoxLayout(nav)
    nav_layout.setContentsMargins(3, 3, 3, 3)
    nav_layout.setSpacing(3)
    button_group = QButtonGroup(container)
    button_group.setExclusive(True)
    buttons = {}
    for key, label in pages:
        button = QPushButton(RIGHT_PANEL_NAV_LABELS.get(key, label))
        button.setCheckable(True)
        button.setMinimumHeight(30)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setToolTip(label)
        button.setProperty("rightPanelNavButton", True)
        button_group.addButton(button)
        nav_layout.addWidget(button)
        buttons[key] = button
    layout.addWidget(nav)

    stack = QStackedWidget(container)
    stack.setObjectName("rightPanelStack")
    layout.addWidget(stack, 1)
    container.setStyleSheet(right_panel_stylesheet())
    return container, stack, buttons


def wrap_right_panel_page(widget: QWidget) -> QScrollArea:
    """Wrap a dock page so narrow right panels stay usable."""
    scroll_area = QScrollArea()
    scroll_area.setObjectName("rightPanelPageScroll")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll_area.setWidget(widget)
    return scroll_area


class MainWindowShellOpsMixin:
    """承载 MainWindow 的窗口壳层、布局与菜单逻辑。"""

    def show_right_panel_index(self, index: int) -> None:
        if not hasattr(self, "right_panel_stack"):
            return
        index = max(0, min(self.right_panel_stack.count() - 1, int(index)))
        self.right_panel_stack.setCurrentIndex(index)
        dock = getattr(self, "right_panel_dock", None)
        if dock is not None:
            dock.setVisible(True)
            dock.raise_()
        if hasattr(self, "right_panel_buttons"):
            for button_index, (key, _label) in enumerate(RIGHT_PANEL_PAGES):
                self.right_panel_buttons[key].setChecked(button_index == index)
        if hasattr(self, "toggle_property_action") and dock is not None:
            self.toggle_property_action.setChecked(dock.isVisible())
        action_map = {
            "property": "toggle_property_action",
            "score": "toggle_score_action",
            "style": "toggle_style_params_action",
            "playback": "toggle_playback_settings_action",
            "bpm": "toggle_bpm_editor_action",
            "sfx": "toggle_sfx_editor_action",
        }
        for button_index, (key, _label) in enumerate(RIGHT_PANEL_PAGES):
            action = getattr(self, action_map[key], None)
            if action is not None:
                action.setChecked(button_index == index and dock is not None and dock.isVisible())

    def show_right_panel_page(self, key: str) -> None:
        page_keys = [page_key for page_key, _label in RIGHT_PANEL_PAGES]
        if key not in page_keys:
            return
        self.show_right_panel_index(page_keys.index(key))

    def _build_editor_area(self) -> QWidget:
        """构建上方统一编辑器区域。"""
        note_selection_area = QWidget()
        note_selection_layout = QHBoxLayout()
        note_selection_layout.setContentsMargins(0, 0, 0, 0)
        note_selection_area.setLayout(note_selection_layout)
        configure_splitter_pane(
            note_selection_area,
            vertical_policy=QSizePolicy.Ignored,
        )

        self.unified_editor = UnifiedEditorWidget(self.sequencer.get_bpm())
        self.unified_editor.audio_engine = self.sequencer.audio_engine
        configure_splitter_pane(
            self.unified_editor,
            vertical_policy=QSizePolicy.Ignored,
        )
        if hasattr(self.unified_editor, "piano_keyboard"):
            self.unified_editor.piano_keyboard.audio_engine = self.sequencer.audio_engine
        note_selection_layout.addWidget(self.unified_editor)
        return note_selection_area

    def _build_playback_control_area(self) -> QWidget:
        """构建播放控制区域。"""
        playback_control_area = QWidget()
        playback_control_area.setFixedHeight(60)

        playback_control_layout = QHBoxLayout()
        playback_control_layout.setContentsMargins(8, 6, 8, 6)
        playback_control_layout.setSpacing(10)
        playback_control_area.setLayout(playback_control_layout)

        self.playback_button_group = QButtonGroup()
        self.playback_button_group.setExclusive(True)

        self.play_stop_button = QPushButton()
        self.play_stop_button.setToolTip("播放/暂停")
        self.play_stop_button.setCheckable(False)
        self.play_stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_stop_button.setIconSize(QSize(18, 18))
        self.play_stop_button.setFixedSize(44, 36)
        self.play_stop_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.play_stop_button.clicked.connect(self.toggle_play_pause)
        playback_control_layout.addWidget(self.play_stop_button)

        self.stop_button = QPushButton()
        self.stop_button.setToolTip("停止")
        self.stop_button.setCheckable(False)
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.setIconSize(QSize(18, 18))
        self.stop_button.setFixedSize(44, 36)
        self.stop_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.stop_button.clicked.connect(self.stop)
        playback_control_layout.addWidget(self.stop_button)

        self.hover_preview_enabled = bool(getattr(self, "hover_preview_enabled", True))
        self.hover_preview_button = QPushButton("悬停试听")
        self.hover_preview_button.setToolTip("开启后，鼠标滑过音符和鼓面板会播放预览音")
        self.hover_preview_button.setCheckable(True)
        self.hover_preview_button.setChecked(self.hover_preview_enabled)
        self.hover_preview_button.setFixedSize(84, 36)
        self.hover_preview_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hover_preview_button.toggled.connect(self.set_hover_preview_enabled)
        playback_control_layout.addWidget(self.hover_preview_button)

        playback_control_layout.addSpacing(12)

        bpm_label = QLabel("BPM:")
        bpm_label.setFixedWidth(35)
        bpm_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        playback_control_layout.addWidget(bpm_label)

        self.bpm_spinbox = QSpinBox()
        self.bpm_spinbox.setRange(30, 300)
        self.bpm_spinbox.setValue(120)
        self.bpm_spinbox.setFixedWidth(70)
        self.bpm_spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.bpm_spinbox.valueChanged.connect(self.on_bpm_changed)
        playback_control_layout.addWidget(self.bpm_spinbox)

        playback_control_layout.addSpacing(12)

        self.file_name_label = QLabel("")
        self.file_name_label.setMinimumWidth(100)
        self.file_name_label.setMaximumWidth(200)
        self.file_name_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.file_name_label.setToolTip("当前打开的文件")
        playback_control_layout.addWidget(self.file_name_label)

        playback_control_layout.addStretch()

        view_label = QLabel("视图:")
        view_label.setFixedWidth(35)
        view_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        playback_control_layout.addWidget(view_label)

        self.view_toggle_switch = ToggleSwitchWidget()
        self.view_toggle_switch.setToolTip("切换视图：左侧=序列，右侧=示波器")
        self.view_toggle_switch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)
        playback_control_layout.addWidget(self.view_toggle_switch)

        playback_control_layout.addSpacing(12)

        volume_label = QLabel("音量:")
        volume_label.setFixedWidth(35)
        volume_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        playback_control_layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        playback_control_layout.addWidget(self.volume_slider)

        self.volume_label = QLabel("100%")
        self.volume_label.setFixedWidth(40)
        self.volume_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        playback_control_layout.addWidget(self.volume_label)

        return playback_control_area

    def _build_track_area(self) -> tuple[QWidget, QWidget]:
        """构建下方音轨与视图区域。"""
        track_area = QWidget()
        track_area_layout = QVBoxLayout()
        track_area_layout.setContentsMargins(0, 0, 0, 0)
        track_area.setLayout(track_area_layout)
        configure_splitter_pane(
            track_area,
            vertical_policy=QSizePolicy.Expanding,
        )

        playback_control_area = self._build_playback_control_area()
        track_area_layout.addWidget(playback_control_area)

        self.view_stack = QStackedWidget()
        configure_splitter_pane(
            self.view_stack,
            vertical_policy=QSizePolicy.Expanding,
        )

        self.sequence_widget = GridSequenceWidget(self.sequencer.get_bpm())
        configure_splitter_pane(
            self.sequence_widget,
            vertical_policy=QSizePolicy.Ignored,
        )
        self.view_stack.addWidget(self.sequence_widget)

        self.oscilloscope_widget = OscilloscopeWidget(
            self.sequencer.audio_engine,
            self.sequencer.get_bpm(),
        )
        configure_splitter_pane(
            self.oscilloscope_widget,
            vertical_policy=QSizePolicy.Ignored,
        )
        self.view_stack.addWidget(self.oscilloscope_widget)
        self.view_stack.setCurrentIndex(0)

        track_area_layout.addWidget(self.view_stack, 1)
        self.sequence_widget.add_track_button.clicked.connect(self.on_add_track_clicked)
        return track_area, playback_control_area

    def _configure_dock_widget(
        self,
        dock: QDockWidget,
        *,
        minimum_width: int,
        visible: bool,
        maximum_height: int | None = None,
    ):
        """统一配置右侧 Dock 的宽度策略和可见性。"""
        dock.setMinimumWidth(minimum_width)
        dock.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        if maximum_height is not None:
            dock.setMaximumHeight(maximum_height)
        dock.setVisible(visible)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )

    def _build_side_docks(self):
        """构建右侧 Dock 面板。"""
        desktop = QApplication.desktop()
        screen = desktop.screenGeometry()
        max_height = int(screen.height() * 0.9)

        self.property_dock = QDockWidget("属性面板", self)
        self.property_panel = PropertyPanelWidget()
        self.property_dock.setWidget(self.property_panel)
        self.property_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_dock)
        self._configure_dock_widget(
            self.property_dock,
            minimum_width=320,
            visible=True,
            maximum_height=max_height,
        )

        self.score_dock = QDockWidget("乐谱面板", self)
        self.score_panel = ScoreLibraryWidget(self.score_library)
        self.score_dock.setWidget(self.score_panel)
        self.score_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.score_dock)
        self._configure_dock_widget(
            self.score_dock,
            minimum_width=self.property_dock.minimumWidth(),
            visible=False,
        )

        self.style_dock = QDockWidget("风格参数", self)
        self.style_params_panel = StyleParamsWidget()
        self.style_dock.setWidget(self.style_params_panel)
        self.style_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.style_dock)
        self._configure_dock_widget(
            self.style_dock,
            minimum_width=self.property_dock.minimumWidth(),
            visible=False,
        )

        self.playback_settings_dock = QDockWidget("播放设置", self)
        self.playback_settings_panel = PlaybackSettingsWidget()
        self.playback_settings_dock.setWidget(self.playback_settings_panel)
        self.playback_settings_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.playback_settings_dock)
        self._configure_dock_widget(
            self.playback_settings_dock,
            minimum_width=self.property_dock.minimumWidth(),
            visible=False,
        )
        self.playback_settings_panel.volume_ratios_changed.connect(
            self.on_playback_volume_ratios_changed
        )
        self.playback_settings_panel.track_selection_changed.connect(
            self.on_playback_track_selection_changed
        )

        self.bpm_editor_dock = QDockWidget("BPM编辑", self)
        self.bpm_editor_panel = BPMEditorWidget()
        self.bpm_editor_dock.setWidget(self.bpm_editor_panel)
        self.bpm_editor_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.bpm_editor_dock)
        self._configure_dock_widget(
            self.bpm_editor_dock,
            minimum_width=self.property_dock.minimumWidth(),
            visible=False,
        )
        self.bpm_editor_panel.tempo_events_changed.connect(self.on_tempo_events_changed)

        old_extra_docks = [
            self.score_dock,
            self.style_dock,
            self.playback_settings_dock,
            self.bpm_editor_dock,
        ]
        self.right_panel, self.right_panel_stack, self.right_panel_buttons = build_right_panel_shell(self)
        for panel in (
            self.property_panel,
            self.score_panel,
            self.style_params_panel,
            self.playback_settings_panel,
            self.bpm_editor_panel,
        ):
            self.right_panel_stack.addWidget(wrap_right_panel_page(panel))

        self.sfx_editor_panel = SfxEditorWidget(self)
        self.sfx_editor_panel.preview_button.clicked.connect(self.preview_sfx_from_panel)
        self.sfx_editor_panel.export_button.clicked.connect(self.export_sfx_from_panel)
        self.sfx_editor_panel.insert_button.clicked.connect(self.insert_sfx_from_panel)
        self.right_panel_stack.addWidget(wrap_right_panel_page(self.sfx_editor_panel))

        for index, (key, _label) in enumerate(RIGHT_PANEL_PAGES):
            button = self.right_panel_buttons[key]
            button.clicked.connect(
                lambda _checked=False, page_index=index: self.show_right_panel_index(page_index)
            )
        self.right_panel_buttons["property"].setChecked(True)
        self.right_panel_stack.setCurrentIndex(0)

        self.property_dock.setWindowTitle("右侧面板")
        self.property_dock.setWidget(self.right_panel)
        self.property_dock.setMinimumWidth(RIGHT_PANEL_MIN_WIDTH)
        self.property_dock.setVisible(True)
        for dock in old_extra_docks:
            self.removeDockWidget(dock)
            dock.setVisible(False)

        self.right_panel_dock = self.property_dock
        self.score_dock = self.right_panel_dock
        self.style_dock = self.right_panel_dock
        self.playback_settings_dock = self.right_panel_dock
        self.bpm_editor_dock = self.right_panel_dock

        self._right_dock_width = resolve_locked_dock_width(
            self.right_panel_dock.width(),
            self.right_panel_dock.minimumWidth(),
        )
        for dock in self._tracked_right_docks():
            if dock is not None:
                dock.setMinimumWidth(self._right_dock_width)
                dock.installEventFilter(self)

    def init_ui(self):
        """初始化 UI。"""
        self.setWindowTitle(APP_NAME)
        desktop = QApplication.desktop()
        screen = desktop.screenGeometry()
        geometry = calculate_default_window_geometry(screen.width(), screen.height())
        self.setGeometry(*geometry)

        self._initial_window_size = self.size()
        self.setMinimumSize(MAIN_WINDOW_MIN_WIDTH, MAIN_WINDOW_MIN_HEIGHT)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        central_widget.setLayout(main_layout)

        note_selection_area = self._build_editor_area()
        track_area, playback_control_area = self._build_track_area()

        self.center_splitter = QSplitter(Qt.Vertical)
        self.center_splitter.setChildrenCollapsible(False)
        self.center_splitter.addWidget(note_selection_area)
        self.center_splitter.addWidget(track_area)
        editor_height, track_height = calculate_default_center_splitter_sizes(
            geometry[3],
        )
        self.center_splitter.setSizes([editor_height, track_height])
        self.center_splitter.setStretchFactor(0, 0)
        self.center_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.center_splitter, 1)

        self._build_side_docks()
        self.connect_signals()
        self.apply_theme()
        self.apply_display_settings_from_settings(
            central_widget,
            note_selection_area,
            track_area,
            playback_control_area,
        )
        self.refresh_ui()

    def _add_action(
        self,
        target,
        text: str,
        handler,
        *,
        shortcut=None,
        checkable: bool = False,
        checked: bool | None = None,
    ):
        """创建并绑定一个 QAction。"""
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
        if checked is not None:
            action.setChecked(checked)
        action.triggered.connect(handler)
        target.addAction(action)
        return action

    def setup_menu(self):
        """设置菜单栏。"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        self._add_action(file_menu, "新建(&N)", self.new_project, shortcut=QKeySequence.New)
        self._add_action(
            file_menu,
            "打开/导入(&O)...",
            self.open_or_import_file,
            shortcut=QKeySequence.Open,
        )
        self._add_action(file_menu, "保存(&S)", self.save_project, shortcut=QKeySequence.Save)
        self._add_action(file_menu, "导出(&E)...", self.export_file, shortcut=QKeySequence.SaveAs)
        file_menu.addSeparator()
        self._add_action(file_menu, "退出(&X)", self.close, shortcut=QKeySequence.Quit)

        view_menu = menubar.addMenu("视图(&V)")
        self.toggle_property_action = self._add_action(
            view_menu,
            "属性面板(&P)",
            self.toggle_property_panel,
            checkable=True,
            checked=False,
        )
        self.toggle_score_action = self._add_action(
            view_menu,
            "乐谱面板(&L)",
            self.toggle_score_panel,
            checkable=True,
            checked=False,
        )
        self.toggle_style_params_action = self._add_action(
            view_menu,
            "风格参数(&S)",
            self.toggle_style_params_panel,
            checkable=True,
            checked=False,
        )
        self.toggle_playback_settings_action = self._add_action(
            view_menu,
            "播放设置(&B)",
            self.toggle_playback_settings_panel,
            checkable=True,
            checked=False,
        )
        self.toggle_bpm_editor_action = self._add_action(
            view_menu,
            "BPM编辑(&T)",
            self.toggle_bpm_editor_panel,
            checkable=True,
            checked=False,
        )
        self.toggle_sfx_editor_action = self._add_action(
            view_menu,
            "音效编辑器(&X)",
            lambda visible: self.show_right_panel_page("sfx")
            if visible
            else self.right_panel_dock.setVisible(False),
            checkable=True,
            checked=False,
        )

        edit_menu = menubar.addMenu("编辑(&E)")
        self.undo_action = self._add_action(
            edit_menu,
            "撤销(&U)",
            self.undo,
            shortcut=QKeySequence.Undo,
        )
        self.undo_action.setEnabled(False)
        self.redo_action = self._add_action(
            edit_menu,
            "重做(&R)",
            self.redo,
            shortcut=QKeySequence.Redo,
        )
        self.redo_action.setEnabled(False)

        self.update_undo_redo_timer = QTimer()
        self.update_undo_redo_timer.timeout.connect(self.update_undo_redo_state)
        self.update_undo_redo_timer.start(100)

        edit_menu.addSeparator()
        self._add_action(
            edit_menu,
            "全选(&A)",
            self.select_all_notes,
            shortcut=QKeySequence.SelectAll,
        )

        play_menu = menubar.addMenu("播放(&P)")
        self._add_action(play_menu, "播放/暂停", self.toggle_play_pause, shortcut=Qt.Key_Space)
        self._add_action(play_menu, "停止(&S)", self.stop, shortcut="Ctrl+.")
        self.hover_preview_action = self._add_action(
            play_menu,
            "悬停试听(&H)",
            self.set_hover_preview_enabled,
            checkable=True,
            checked=bool(getattr(self, "hover_preview_enabled", True)),
        )
        self._sync_hover_preview_controls()

        self._add_action(menubar, "生成(&G)", self.generate_music_from_seed)

        sfx_menu = menubar.addMenu("音效(&X)")
        self._add_action(sfx_menu, "打开音效面板", self.show_sfx_editor)
        sfx_menu.addSeparator()
        self._add_action(sfx_menu, "吃金币", self.insert_coin_sfx)
        self._add_action(sfx_menu, "跳跃", self.insert_jump_sfx)
        self._add_action(sfx_menu, "受击", self.insert_hit_sfx)
        self._add_action(sfx_menu, "强化", self.insert_power_up_sfx)
        self._add_action(sfx_menu, "激光", self.insert_laser_sfx)
        self._add_action(sfx_menu, "爆炸", self.insert_explosion_sfx)
        self._add_action(sfx_menu, "菜单选择", self.insert_select_sfx)
        self._add_action(sfx_menu, "错误提示", self.insert_error_sfx)
        self._add_action(sfx_menu, "开门", self.insert_door_sfx)
        self._add_action(sfx_menu, "治疗", self.insert_heal_sfx)

        self._add_action(menubar, "设置(&S)", self.show_settings)

        help_menu = menubar.addMenu("帮助(&H)")
        self._add_action(help_menu, "关于(&A)...", self.show_about)

    def setup_toolbar(self):
        """设置工具栏（已移到右侧面板，这里保留空实现）。"""
        pass

    def setup_statusbar(self):
        """设置状态栏。"""
        self.statusBar().showMessage("就绪")

    def check_unsaved_changes(self) -> bool:
        """检查未保存的更改（简化实现）。"""
        return True

    def closeEvent(self, event):
        """窗口关闭事件。"""
        if (
            getattr(self, "_midi_import_thread", None) is not None
            or getattr(self, "_playback_prepare_thread", None) is not None
        ):
            self.statusBar().showMessage("后台任务仍在运行，请稍后再关闭")
            event.ignore()
            return

        if self.check_unsaved_changes():
            service = getattr(self, "_app_control_service", None)
            if service is not None:
                service.stop()
                self._app_control_service = None
            self.sequencer.cleanup()
            event.accept()
        else:
            event.ignore()
