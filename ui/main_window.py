"""
主窗口模块

应用程序的主窗口界面。
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QAction,
    QMessageBox, QFileDialog, QSplitter, QDialog,
    QDockWidget, QSlider, QDialogButtonBox, QLabel, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QKeySequence, QKeyEvent

from core.sequencer import Sequencer
from core.models import Project, WaveformType, Track, Note, TrackType
from core.midi_io import MidiIO
from core.track_events import DrumType

from ui.unified_editor_widget import UnifiedEditorWidget
from ui.grid_sequence_widget import GridSequenceWidget
from ui.timeline_widget import TimelineWidget
from ui.property_panel_widget import PropertyPanelWidget
from ui.metronome_widget import MetronomeWidget
from ui.theme import theme_manager
from PyQt5.QtWidgets import QStackedWidget, QTabWidget, QPushButton, QButtonGroup, QSpinBox


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        
        self.sequencer = Sequencer()
        self.current_file_path = None
        
        self.init_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # 定时器用于更新播放状态和播放头
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_playback_status)
        self.update_timer.start(50)  # 每50ms更新一次（更流畅）
        
        # 播放开始时间（用于计算播放位置）
        self.playback_start_time = None
        self.playback_start_offset = 0.0  # 播放开始时的偏移时间
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("8bit音乐制作器")
        self.setGeometry(100, 100, 1600, 1000)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局（垂直，分为上下两部分）
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # ========== 上方：统一编辑器（整合所有功能）==========
        note_selection_area = QWidget()
        note_selection_area.setMaximumHeight(350)  # 增加高度以容纳打击乐按钮
        note_selection_layout = QHBoxLayout()
        note_selection_area.setLayout(note_selection_layout)
        
        # 统一编辑器（包含波形、音轨类型、钢琴键盘、打击乐、拍数）
        self.unified_editor = UnifiedEditorWidget(self.sequencer.get_bpm())
        # 将sequencer的audio_engine传递给预览组件，以便应用主音量
        self.unified_editor.audio_engine = self.sequencer.audio_engine
        if hasattr(self.unified_editor, 'piano_keyboard'):
            self.unified_editor.piano_keyboard.audio_engine = self.sequencer.audio_engine
        note_selection_layout.addWidget(self.unified_editor)
        
        main_layout.addWidget(note_selection_area, 0)  # 不拉伸
        
        # ========== 下方：音轨区域 ==========
        track_area = QWidget()
        track_area_layout = QVBoxLayout()
        track_area_layout.setContentsMargins(0, 0, 0, 0)
        track_area.setLayout(track_area_layout)
        
        # 上方：播放控制区域
        playback_control_area = QWidget()
        playback_control_layout = QHBoxLayout()
        playback_control_layout.setContentsMargins(8, 6, 8, 6)
        playback_control_layout.setSpacing(8)
        playback_control_area.setLayout(playback_control_layout)
        
        # ========== 左侧：播放控制按钮 ==========
        # 播放按钮组
        self.play_button = QPushButton("播放")
        self.play_button.clicked.connect(self.play)
        playback_control_layout.addWidget(self.play_button)
        
        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.pause)
        playback_control_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("停止")
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
        
        playback_control_layout.addStretch()
        
        # ========== 右侧：音量控制 ==========
        # 播放音量控制
        volume_label = QLabel("音量:")
        playback_control_layout.addWidget(volume_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        # 使用sliderReleased信号避免拖动时频繁触发导致卡顿
        self.volume_slider.sliderReleased.connect(self.on_volume_slider_released)
        # 也监听valueChanged，但只在释放时更新（用于实时显示）
        self.volume_slider.valueChanged.connect(self.on_volume_label_changed)
        self.volume_slider.setMinimumWidth(120)
        self.volume_slider.setMaximumWidth(150)
        playback_control_layout.addWidget(self.volume_slider)
        
        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(40)
        playback_control_layout.addWidget(self.volume_label)
        
        track_area_layout.addWidget(playback_control_area)
        
        # 下方：音轨区域（序列编辑器）
        self.sequence_widget = GridSequenceWidget(self.sequencer.get_bpm())
        # 连接添加音轨按钮（从序列编辑器移到了主窗口的播放控制区域）
        # 现在需要连接到序列编辑器中的按钮
        track_area_layout.addWidget(self.sequence_widget, 1)  # 可拉伸
        
        # 连接序列编辑器中的添加音轨按钮
        self.sequence_widget.add_track_button.clicked.connect(self.on_add_track_clicked)
        
        main_layout.addWidget(track_area, 1)  # 可拉伸
        
        # ========== 属性面板：使用浮动窗口（DockWidget）==========
        self.property_dock = QDockWidget("属性面板", self)
        self.property_panel = PropertyPanelWidget()
        self.property_dock.setWidget(self.property_panel)
        self.property_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self.property_dock)
        # 默认不显示，需要时通过菜单显示
        self.property_dock.setVisible(False)
        # 允许关闭，但可以通过菜单重新打开
        self.property_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        
        # 连接信号
        self.connect_signals()
        
        # 应用主题
        self.apply_theme()
        
        # 设置中央部件和各个区域的背景色
        theme = theme_manager.current_theme
        bg_color = theme.get_color('background')
        central_widget.setStyleSheet(f"background-color: {bg_color};")
        note_selection_area.setStyleSheet(f"background-color: {bg_color};")
        track_area.setStyleSheet(f"background-color: {bg_color};")
        playback_control_area.setStyleSheet(f"background-color: {theme.get_color('primary_light')};")
        
        # 不再自动创建默认音轨（用户需要手动创建）
        # self.init_default_tracks()
        
        # 初始化显示
        self.refresh_ui()
    
    def apply_theme(self):
        """应用主题到所有UI组件"""
        theme = theme_manager.current_theme
        
        # 主窗口背景
        self.setStyleSheet(theme.get_style("main_window"))
        
        # 菜单栏
        if hasattr(self, 'menuBar'):
            self.menuBar().setStyleSheet(theme.get_style("menu_bar"))
        
        # 工具栏
        if hasattr(self, 'toolbar'):
            self.toolbar.setStyleSheet(theme.get_style("toolbar"))
        
        # 状态栏
        if hasattr(self, 'statusBar'):
            self.statusBar().setStyleSheet(theme.get_style("status_bar"))
        
        # 按钮样式
        button_style = theme.get_style("button")
        button_small_style = theme.get_style("button_small")
        
        # 播放控制按钮
        if hasattr(self, 'play_button'):
            self.play_button.setStyleSheet(button_style)
        if hasattr(self, 'pause_button'):
            self.pause_button.setStyleSheet(button_style)
        if hasattr(self, 'stop_button'):
            self.stop_button.setStyleSheet(button_style)
        # 添加音轨按钮现在在序列编辑器中
        if hasattr(self, 'sequence_widget') and hasattr(self.sequence_widget, 'add_track_button'):
            self.sequence_widget.add_track_button.setStyleSheet(button_small_style)
        
        # 标签样式
        label_style = theme.get_style("label")
        if hasattr(self, 'status_info_label'):
            self.status_info_label.setStyleSheet(label_style)
        if hasattr(self, 'volume_label'):
            self.volume_label.setStyleSheet(label_style)
        
        # 滑块样式
        if hasattr(self, 'volume_slider'):
            self.volume_slider.setStyleSheet(theme.get_style("slider"))
        
        # 输入框样式
        if hasattr(self, 'bpm_spinbox'):
            # SpinBox使用类似LineEdit的样式
            self.bpm_spinbox.setStyleSheet(theme.get_style("line_edit"))
        
        # 属性面板
        if hasattr(self, 'property_dock'):
            self.property_dock.setStyleSheet(theme.get_style("dialog"))
    
    
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
        
        # 序列编辑器选择变化信号
        self.sequence_widget.selection_changed.connect(self.on_selection_changed)
        self.sequence_widget.track_clicked.connect(self.on_track_clicked)
        self.sequence_widget.track_enabled_changed.connect(self.on_track_enabled_changed)
        self.sequence_widget.playhead_time_changed.connect(self.on_playhead_time_changed)
    
    def on_playhead_time_changed(self, time: float):
        """播放线时间改变"""
        # 更新统一编辑器的目标音轨（如果点击了音轨）
        # 这里暂时不处理，等实现点击音轨选择功能时再添加
        pass
    
    def refresh_ui(self, preserve_selection: bool = False):
        """刷新UI显示
        
        Args:
            preserve_selection: 是否保持选中状态（用于属性面板更新时）
        """
        # 更新序列编辑器
        self.sequence_widget.set_tracks(self.sequencer.project.tracks, preserve_selection=preserve_selection)
        self.sequence_widget.set_bpm(self.sequencer.get_bpm())
        
        # 更新统一编辑器BPM
        self.unified_editor.set_bpm(self.sequencer.get_bpm())
    
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
        
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = note.pitch // 12 - 1
        note_name = note_names[note.pitch % 12]
        self.statusBar().showMessage(f"已选中音符: {note_name}{octave} (按Delete键删除)")
    
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
        # 获取选中的音符列表
        selected_blocks = [item for item in self.sequence_widget.scene.selectedItems() 
                          if hasattr(item, 'item') and hasattr(item, 'track')]
        
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
    
    def on_batch_property_changed(self, notes_and_tracks: list):
        """批量属性改变"""
        if not notes_and_tracks:
            return
        
        # 获取要修改的属性
        kwargs = {}
        
        # 波形（从批量编辑获取）
        if hasattr(self.property_panel, 'batch_waveform_combo'):
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
        
        # 力度
        if hasattr(self.property_panel, 'batch_velocity_slider'):
            velocity = self.property_panel.batch_velocity_slider.value()
            kwargs['velocity'] = velocity
        
        # 占空比
        if hasattr(self.property_panel, 'batch_duty_spinbox'):
            duty_cycle = self.property_panel.batch_duty_spinbox.value()
            kwargs['duty_cycle'] = duty_cycle
        
        # 通过命令系统批量修改
        if kwargs:
            self.sequencer.batch_modify_notes(notes_and_tracks, **kwargs)
            # 刷新显示（批量修改需要刷新以反映变化）
            self.refresh_ui(preserve_selection=True)
            self.statusBar().showMessage(f"已批量修改 {len(notes_and_tracks)} 个音符的属性")
    
    def on_track_clicked(self, track: Track):
        """音轨被点击"""
        # 选中该轨道上的所有音符
        self.sequence_widget.select_track_notes(track)
        
        # 设置统一编辑器的目标音轨
        self.unified_editor.set_selected_track(track)
        
        # 高亮显示目标音轨
        self.sequence_widget.set_highlighted_track(track)
        
        # 在属性面板中显示音轨编辑界面（会同时显示音轨属性和多选音符属性）
        self.property_panel.set_track(track)
        note_count = len(track.notes) if track.track_type == TrackType.NOTE_TRACK else len(track.drum_events)
        self.statusBar().showMessage(f"已选中音轨: {track.name} ({note_count} 个音符/事件)")
    
    def on_track_property_changed(self, track: Track):
        """音轨属性改变"""
        # 刷新UI以反映音轨属性的变化（如名称、类型等）
        self.refresh_ui(preserve_selection=True)
        self.statusBar().showMessage(f"已更新音轨: {track.name}")
    
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
    
    def toggle_play_pause(self):
        """切换播放/暂停"""
        if self.sequencer.playback_state.is_playing:
            self.stop()
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
        
        open_action = QAction("打开(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)
        
        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("另存为(&A)...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # MIDI导入
        import_midi_action = QAction("导入MIDI(&I)...", self)
        import_midi_action.triggered.connect(self.import_midi)
        file_menu.addAction(import_midi_action)
        
        # MIDI导出
        export_midi_action = QAction("导出MIDI(&M)...", self)
        export_midi_action.triggered.connect(self.export_midi)
        file_menu.addAction(export_midi_action)
        
        file_menu.addSeparator()
        
        export_wav_action = QAction("导出WAV(&E)...", self)
        export_wav_action.triggered.connect(self.export_wav)
        file_menu.addAction(export_wav_action)
        
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
            self.sequencer = Sequencer()
            self.current_file_path = None
            self.setWindowTitle("8bit音乐制作器 - 新建项目")
            self.refresh_ui()
            self.statusBar().showMessage("已创建新项目")
    
    def open_project(self):
        """打开项目"""
        if not self.check_unsaved_changes():
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                project = Project.from_dict(data)
                self.sequencer.set_project(project)
                self.current_file_path = file_path
                self.setWindowTitle(f"8bit音乐制作器 - {project.name}")
                self.refresh_ui()
                self.statusBar().showMessage(f"已打开项目: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开项目失败:\n{str(e)}")
    
    def save_project(self):
        """保存项目"""
        if self.current_file_path:
            self.save_project_to_file(self.current_file_path)
        else:
            self.save_project_as()
    
    def save_project_as(self):
        """另存为"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
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
    
    def import_midi(self):
        """导入MIDI文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入MIDI", "", "MIDI文件 (*.mid *.midi);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # 检查是否有未保存的更改
            if not self.check_unsaved_changes():
                return
            
            # 导入MIDI文件
            project = MidiIO.import_midi(file_path)
            
            # 设置项目
            self.sequencer.set_project(project)
            self.current_file_path = None  # MIDI导入后，项目文件路径为空
            
            # 刷新UI
            self.refresh_ui()
            
            # 更新BPM显示
            self.bpm_spinbox.setValue(int(project.bpm))
            
            self.statusBar().showMessage(f"已导入MIDI: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入MIDI失败:\n{str(e)}")
    
    def export_midi(self):
        """导出MIDI文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出MIDI", "", "MIDI文件 (*.mid);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            # 确保文件扩展名是.mid
            if not file_path.lower().endswith('.mid'):
                file_path += '.mid'
            
            # 导出MIDI文件
            MidiIO.export_midi(self.sequencer.project, file_path)
            
            self.statusBar().showMessage(f"已导出MIDI: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出MIDI失败:\n{str(e)}")
    
    def export_wav(self):
        """导出WAV文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出WAV", "", "WAV文件 (*.wav);;所有文件 (*.*)"
        )
        
        if file_path:
            if not file_path.endswith('.wav'):
                file_path += '.wav'
            
            try:
                from scipy.io import wavfile
                import numpy as np
                
                # 生成音频
                audio = self.sequencer.audio_engine.generate_project_audio(
                    self.sequencer.project
                )
                
                if len(audio) == 0:
                    QMessageBox.warning(self, "警告", "项目中没有音频数据")
                    return
                
                # 转换为16位整数
                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                
                # 保存为WAV文件
                wavfile.write(file_path, self.sequencer.audio_engine.sample_rate, audio_int16)
                
                self.statusBar().showMessage(f"已导出WAV: {file_path}")
                QMessageBox.information(self, "成功", f"WAV文件已导出:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出WAV失败:\n{str(e)}")
    
    def play(self):
        """播放"""
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
        
        # 同步节拍器
        if self.metronome_widget.is_enabled:
            self.metronome_widget.set_playing(True)
    
    def pause(self):
        """暂停"""
        if self.sequencer.playback_state.is_playing:
            self.sequencer.stop()
            self.statusBar().showMessage("已暂停")
            # 不重置播放头位置，保持当前位置
            # 不启用预览功能，保持暂停状态
            # 同步节拍器
            self.metronome_widget.set_playing(False)
    
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
    
    def on_bpm_changed(self, value: int):
        """BPM改变"""
        bpm = float(value)
        self.sequencer.set_bpm(bpm)
        self.sequence_widget.set_bpm(bpm)
        self.unified_editor.set_bpm(bpm)
        self.property_panel.set_bpm(bpm)
        self.metronome_widget.set_bpm(bpm)
        self.refresh_ui()
    
    def on_volume_label_changed(self, value: int):
        """音量标签更新（实时显示，不触发音频更新）"""
        self.volume_label.setText(f"{value}%")
    
    def on_volume_slider_released(self):
        """播放音量改变（仅在释放滑块时触发）"""
        value = self.volume_slider.value()
        volume = value / 100.0  # 转换为0.0-1.0
        self.sequencer.audio_engine.set_master_volume(volume)
        self.volume_label.setText(f"{value}%")
        
        # 如果正在播放，需要重新播放以应用新音量
        if self.sequencer.playback_state.is_playing:
            current_time = self.sequence_widget.playhead_time
            self.stop()
            self.play()
            # 恢复播放位置（简化处理，实际应该保存并恢复）
    
    def update_playback_status(self):
        """更新播放状态和播放头"""
        if self.sequencer.playback_state.is_playing and self.playback_start_time:
            import time
            # 计算当前播放时间
            elapsed_time = time.time() - self.playback_start_time
            current_time = self.playback_start_offset + elapsed_time
            
            # 更新播放头
            self.sequence_widget.set_playhead_time(current_time)
            
            # 确保预览被禁用（防止播放过程中被启用）
            if self.unified_editor.preview_enabled:
                self.unified_editor.set_preview_enabled(False)
            
            # 检查是否播放完毕（简化：如果播放头超过项目总时长，停止）
            total_duration = self.sequencer.project.get_total_duration()
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
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.check_unsaved_changes():
            self.sequencer.cleanup()
            event.accept()
        else:
            event.ignore()

