"""
示波器可视化模块

实现类似示波器的波形可视化，将不同音轨显示为不同通道的波形。
波形从左侧生成，向右移动到蜂鸣器，到达蜂鸣器时才播放。
"""

import numpy as np
from typing import List, Optional, Tuple
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QFont

from core.models import Track, TrackType, Note
from core.audio_engine import AudioEngine
from ui.theme import theme_manager


class OscilloscopeWidget(QWidget):
    """示波器可视化组件"""
    
    def __init__(self, audio_engine: AudioEngine, bpm: float = 120.0, parent=None):
        """
        初始化示波器组件
        
        Args:
            audio_engine: 音频引擎实例
            bpm: 当前BPM
            parent: 父组件
        """
        super().__init__(parent)
        
        self.audio_engine = audio_engine
        self.bpm = bpm
        self.tracks: List[Track] = []
        
        # 可视化参数
        self.channel_height = 80  # 每个通道的高度（像素）
        self.min_channel_height = 60  # 每个通道的最小高度（像素），确保波形可见
        self.channel_spacing = 10  # 通道之间的间距（像素）
        self.buzzer_x_offset = 80  # 蜂鸣器距离右侧的距离（像素）
        self.waveform_start_x = 200  # 波形起始位置（左侧留出空间给代码显示）
        
        # 波形移动速度（像素/秒）
        # 这个速度决定了波形从左侧移动到蜂鸣器需要多长时间
        # 速度应该与播放速度同步，根据BPM计算
        # 降低速度可以让波形更拉伸，不那么密集
        self.waveform_speed = 200.0  # 像素/秒，提高速度让波形运动更快
        
        # 波形预览时间（秒）- 显示未来多少秒的音符
        self.preview_time = 5.0  # 显示未来5秒的音符，确保有足够的时间让波形移动到蜂鸣器
        
        # 渲染设置
        self.max_notes_to_render = 10  # 最多渲染多少个音符的波形
        self.pre_render_notes = 3  # 预渲染几个音符（防止空白）
        
        # 代码显示设置
        self.code_language = "pseudocode"  # 代码语言：pseudocode, micropython, assembly
        self.code_templates = {
            "pseudocode": "play_note(frequency={frequency}, duration={duration}, waveform={waveform})",
            "micropython": "buzzer.freq({frequency})\nbuzzer.duty({duty})\ntime.sleep({duration})",
            "assembly": "MOV A, #{frequency}\nOUT PORT_B, A\nCALL DELAY_{duration}ms"
        }
        
        # 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_waveforms)
        self.update_timer.setInterval(16)  # 每16ms更新一次（约60fps），确保平滑动画
        
        # 静态更新定时器（即使不播放也定期更新）
        self.static_update_timer = QTimer()
        self.static_update_timer.timeout.connect(self.update_waveforms)
        self.static_update_timer.setInterval(200)  # 每200ms更新一次
        self.static_update_timer.start()  # 始终运行
        
        # 当前播放时间（由外部设置）
        self.current_time = 0.0
        # 内部时间（用于动画），后面会简化为直接使用current_time，避免双重时间轴导致抖动
        self.internal_time = 0.0
        self.is_playing = False
        # 固定采样网格配置，用于稳定波形采样，避免每帧抖动
        self.visible_window = 5.0  # 可见时间窗口（秒）
        self.num_samples = 1000    # 每个通道的采样点数（固定），与时间窗口一起决定time_step
        self.time_step = self.visible_window / self.num_samples
        
        # 通道颜色（为每个通道分配不同颜色）
        self.channel_colors = [
            QColor(255, 100, 100),  # 红色
            QColor(100, 255, 100),  # 绿色
            QColor(100, 100, 255),  # 蓝色
            QColor(255, 255, 100),  # 黄色
            QColor(255, 100, 255),  # 洋红
            QColor(100, 255, 255),  # 青色
            QColor(255, 200, 100),  # 橙色
            QColor(200, 100, 255),  # 紫色
        ]
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 不使用布局，直接在paintEvent中绘制所有内容
        
        # 应用主题
        self.apply_theme()
        
        # 设置最小尺寸
        self.setMinimumHeight(400)
        
        # 初始化音轨颜色映射（用于固定每个音轨的颜色）
        self.track_colors = {}
        
        # 波形缓存（避免每次重绘都重新生成）
        self.waveform_cache = {}  # key: (track_id, note_id), value: waveform_data
    
    def apply_theme(self):
        """应用主题样式"""
        theme = theme_manager.current_theme
        bg_color = theme.get_color("background")
        self.setStyleSheet(f"background-color: {bg_color};")
    
    def set_tracks(self, tracks: List[Track], selected_track: Track = None):
        """设置音轨列表
        
        Args:
            tracks: 所有音轨列表
            selected_track: 选中的音轨（如果提供，只渲染选中的音轨）
        """
        # 去重：使用track的id确保每个音轨只出现一次
        seen_track_ids = set()
        unique_tracks = []
        for track in tracks:
            if track.enabled:
                track_id = id(track)
                if track_id not in seen_track_ids:
                    seen_track_ids.add(track_id)
                    unique_tracks.append(track)
        
        # 如果用户之前选择了要渲染的音轨，优先使用用户选择的音轨
        if hasattr(self, '_selected_tracks_for_render') and self._selected_tracks_for_render:
            # 只使用用户选择的音轨中在当前unique_tracks中的（确保音轨是启用的）
            user_selected = [t for t in self._selected_tracks_for_render if t in unique_tracks]
            if user_selected:
                unique_tracks = user_selected
            # 如果用户选择的音轨都不在传入的tracks中，但用户确实选择了，则使用用户选择的音轨
            elif self._selected_tracks_for_render:
                # 检查用户选择的音轨是否在项目中的所有音轨中
                unique_tracks = self._selected_tracks_for_render
        # 如果指定了选中的音轨，只使用选中的音轨（优先级低于用户选择的音轨）
        elif selected_track is not None and selected_track in unique_tracks:
            unique_tracks = [selected_track]
        
        # 检查音轨列表是否发生变化
        old_track_ids = {id(track) for track in self.tracks} if hasattr(self, 'tracks') and self.tracks else set()
        new_track_ids = {id(track) for track in unique_tracks}
        
        # 如果音轨列表发生变化，清除所有缓存和颜色映射（确保完全刷新）
        if old_track_ids != new_track_ids:
            # 音轨列表变化，清除所有缓存和颜色
            if hasattr(self, 'waveform_cache'):
                self.waveform_cache.clear()
            # 清除所有颜色映射，重新分配
            self.track_colors.clear()
        
        self.tracks = unique_tracks
        self.selected_track = selected_track  # 保存选中的音轨
        if not hasattr(self, '_selected_tracks_for_render'):
            self._selected_tracks_for_render = None  # 用户选择的要渲染的音轨列表
        
        # 为每个音轨分配固定的颜色（基于音轨索引，而不是通道索引）
        # 这样即使音轨顺序变化，每个音轨的颜色也是固定的
        for i, track in enumerate(self.tracks):
            track_key = id(track)
            if track_key not in self.track_colors:
                self.track_colors[track_key] = self.channel_colors[i % len(self.channel_colors)]
        
        # 清除不再使用的音轨的颜色（只保留当前音轨）
        current_track_ids = {id(track) for track in self.tracks}
        self.track_colors = {k: v for k, v in self.track_colors.items() if k in current_track_ids}
        
        # 清除不再使用的波形缓存
        if hasattr(self, 'waveform_cache'):
            self.waveform_cache = {k: v for k, v in self.waveform_cache.items() if k[0] in current_track_ids}
        
        # 重置内部时间，确保刷新
        if hasattr(self, 'internal_time'):
            self.internal_time = 0.0
        if hasattr(self, 'current_time'):
            self.current_time = 0.0
        
        self.update()
    
    def set_selected_tracks(self, selected_tracks: List[Track]):
        """设置要渲染的选中音轨列表（最多3个）
        
        Args:
            selected_tracks: 选中的音轨列表（最多3个）
        """
        if len(selected_tracks) > 3:
            selected_tracks = selected_tracks[:3]
        
        # 保存用户选择的音轨
        self._selected_tracks_for_render = selected_tracks
        
        # 使用set_tracks来确保所有逻辑都正确执行（包括颜色分配、缓存清除等）
        # 传入所有启用的音轨，set_tracks会根据_selected_tracks_for_render自动筛选
        # 但这里我们需要直接设置，所以先保存，然后调用set_tracks
        # 实际上，我们应该直接设置tracks并触发更新
        self.tracks = selected_tracks
        
        # 清除缓存
        if hasattr(self, 'waveform_cache'):
            self.waveform_cache.clear()
        self.track_colors.clear()
        
        # 重新分配颜色
        for i, track in enumerate(self.tracks):
            track_key = id(track)
            if track_key not in self.track_colors:
                self.track_colors[track_key] = self.channel_colors[i % len(self.channel_colors)]
        
        # 重置内部时间
        if hasattr(self, 'internal_time'):
            self.internal_time = 0.0
        if hasattr(self, 'current_time'):
            self.current_time = 0.0
        
        # 触发重绘
        self.update()
        for i, track in enumerate(self.tracks):
            track_key = id(track)
            self.track_colors[track_key] = self.channel_colors[i % len(self.channel_colors)]
        
        self.update()
    
    def set_bpm(self, bpm: float):
        """设置BPM"""
        self.bpm = bpm
    
    def set_current_time(self, current_time: float):
        """设置当前播放时间"""
        # 简化为直接使用当前时间，避免双重时间轴导致的视觉抖动
        self.current_time = current_time
        self.internal_time = current_time
    
    def set_playing(self, is_playing: bool):
        """设置播放状态"""
        self.is_playing = is_playing
        if is_playing:
            if not self.update_timer.isActive():
                self.update_timer.start()
        else:
            if self.update_timer.isActive():
                self.update_timer.stop()
        # 即使不播放也触发一次重绘，显示当前状态
        self.update()
    
    def generate_code_for_note(self, note: Note, track: Track) -> str:
        """
        为音符生成代码文本（只显示频率）
        
        Args:
            note: 音符对象
            track: 音轨对象
        
        Returns:
            代码文本字符串（只包含频率）
        """
        if note is None:
            return track.name[:10]
        
        # 计算频率
        frequency = self.audio_engine.waveform_generator.midi_to_frequency(note.pitch)
        frequency_int = int(frequency)
        
        return f"{frequency_int}Hz"
    
    def get_notes_in_range(self, track: Track, start_time: float, end_time: float) -> List[Note]:
        """
        获取时间范围内的音符
        
        Args:
            track: 音轨
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
        Returns:
            音符列表
        """
        if track.track_type != TrackType.NOTE_TRACK:
            return []
        
        notes = []
        for note in track.notes:
            note_end_time = note.start_time + note.duration
            # 如果音符与时间范围有重叠
            if note.start_time < end_time and note_end_time > start_time:
                notes.append(note)
        
        return notes
    
    def generate_pwm_waveform(self, note: Note, duration: float, num_samples: int) -> np.ndarray:
        """
        生成PWM波形用于显示
        
        Args:
            note: 音符对象
            duration: 显示时长（秒）
            num_samples: 采样点数（像素数）
        
        Returns:
            波形数据数组（归一化到-1到1）
        """
        if note.pitch <= 0:
            return np.zeros(num_samples, dtype=np.float32)
        
        # 计算频率
        frequency = self.audio_engine.waveform_generator.midi_to_frequency(note.pitch)
        
        # 生成基础波形（使用足够的采样率以确保频率特征可见）
        # 确保每个周期有足够的采样点来显示波形特征
        # 使用原始采样率生成，然后下采样到显示需要的点数
        waveform = self.audio_engine.waveform_generator.generate_waveform(
            waveform_type=note.waveform,
            frequency=frequency,
            duration=duration,
            amplitude=1.0,  # 归一化振幅
            duty_cycle=note.duty_cycle
        )
        
        # 在每个音符前后各添加约3%的0电平，用于视觉上分隔音符（仅影响示波器显示，不影响真实音频）
        try:
            pad_samples = max(1, int(len(waveform) * 0.03))
            zero_pad = np.zeros(pad_samples, dtype=np.float32)
            waveform = np.concatenate([zero_pad, waveform, zero_pad])
        except Exception:
            # 任何异常都回退到原始波形，避免崩溃
            pass
        
        # 对波形进行采样以适应显示
        # 使用更智能的采样方法，保持频率特征
        if len(waveform) > num_samples:
            # 下采样：使用平均或选择关键点，而不是简单跳跃
            # 为了保持频率特征，使用线性插值而不是简单跳跃
            indices = np.linspace(0, len(waveform) - 1, num_samples)
            sampled = np.interp(indices, np.arange(len(waveform)), waveform)
        elif len(waveform) < num_samples:
            # 上采样：线性插值
            indices = np.linspace(0, len(waveform) - 1, num_samples)
            sampled = np.interp(indices, np.arange(len(waveform)), waveform)
        else:
            sampled = waveform
        
        return sampled.astype(np.float32)
    
    def calculate_note_position(self, note: Note, current_time: float, waveform_area_width: float) -> Tuple[float, float, float]:
        """
        计算音符波形在屏幕上的位置
        
        所有波形都从固定位置（最左边）开始生成，向右移动到蜂鸣器。
        当波形到达蜂鸣器时，该音符开始播放。
        
        Args:
            note: 音符对象
            current_time: 当前播放时间（秒）
            waveform_area_width: 波形显示区域宽度（像素，从起始位置到蜂鸣器）
        
        Returns:
            (x_start, x_end, display_start_offset) 
            - x_start: 波形起始x坐标（相对于波形区域起始位置，0表示在蜂鸣器位置）
            - x_end: 波形结束x坐标
            - display_start_offset: 如果波形部分在可见区域外，这个值表示需要跳过的部分（0-1）
        """
        # 计算音符相对于当前时间的偏移
        # time_offset > 0: 音符还未播放（未来）
        # time_offset < 0: 音符已经开始播放（过去）
        time_offset = note.start_time - current_time
        
        # 计算波形从左侧移动到蜂鸣器需要的时间
        # 蜂鸣器在波形区域的右侧（waveform_area_width 位置）
        time_to_buzzer = waveform_area_width / self.waveform_speed
        
        # 所有波形都从位置0（最左边）开始生成
        # 波形的起始位置：从0开始，向右移动
        # 当 time_offset = time_to_buzzer 时，波形到达蜂鸣器（x_start = 0）
        # 公式：x_start = waveform_area_width - time_offset * self.waveform_speed
        # 当 time_offset = time_to_buzzer 时，x_start = waveform_area_width - waveform_area_width = 0（到达蜂鸣器）
        # 当 time_offset > time_to_buzzer 时，x_start < 0（还在左侧，未到达）
        # 当 time_offset < time_to_buzzer 时，x_start > waveform_area_width（已经超过蜂鸣器）
        
        x_start = waveform_area_width - time_offset * self.waveform_speed
        
        # 计算波形的宽度（根据音符持续时间）
        waveform_width = note.duration * self.waveform_speed
        x_end = x_start + waveform_width
        
        # 计算显示起始偏移（如果波形部分在可见区域外）
        display_start_offset = 0.0
        if x_start < 0:
            # 波形部分在左侧不可见区域，需要跳过这部分
            display_start_offset = -x_start / waveform_width if waveform_width > 0 else 0
            x_start = 0
        
        return (x_start, x_end, display_start_offset)
    
    def update_waveforms(self):
        """更新波形显示"""
        # 直接根据当前时间重绘，时间推进统一由current_time控制，避免抖动
        self.update()
    
    def paintEvent(self, event):
        """绘制示波器"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 获取主题颜色
        theme = theme_manager.current_theme
        bg_color = QColor(theme.get_color("background"))
        grid_color = QColor(theme.get_color("border"))
        text_color = QColor(theme.get_color("text_primary"))
        
        # 绘制背景
        painter.fillRect(0, 0, width, height, bg_color)
        
        # 绘制标题和提示文字
        title_y = 30
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(10, title_y, "示波器视图")
        
        # 绘制提示文字
        painter.setFont(QFont("Arial", 10))
        painter.drawText(10, title_y + 20, "波形从左侧生成，向右移动到蜂鸣器。设置可在菜单中找到。")
        
        if len(self.tracks) == 0:
            # 没有音轨时显示提示
            painter.setPen(QPen(text_color))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(
                width // 2 - 100,
                height // 2,
                "暂无音轨数据，请先添加音轨"
            )
            # 绘制一些示例网格线，让界面不那么空
            painter.setPen(QPen(grid_color, 1, Qt.DashLine))
            for i in range(3):
                y = 100 + i * 100
                painter.drawLine(50, y, width - 50, y)
            return
        
        # 计算通道区域
        start_y = title_y + 35  # 从标题和提示文字下方开始
        available_height = height - start_y - 50  # 底部留出空间
        
        # 如果通道太多，只显示音符最多的几个音轨
        tracks_to_display = self.tracks
        if len(self.tracks) > 0:
            # 计算每个音轨的音符数量
            track_note_counts = []
            for track in self.tracks:
                if track.track_type == TrackType.NOTE_TRACK:
                    note_count = len(track.notes)
                else:
                    note_count = len(track.drum_events) if hasattr(track, 'drum_events') else 0
                track_note_counts.append((track, note_count))
            
            # 按音符数量排序（降序）
            track_note_counts.sort(key=lambda x: x[1], reverse=True)
            
            # 计算最多能显示多少个音轨（确保每个音轨至少有最小高度）
            max_tracks = 0
            for i in range(1, len(track_note_counts) + 1):
                test_height = i * (self.min_channel_height + self.channel_spacing) - self.channel_spacing
                if test_height <= available_height:
                    max_tracks = i
                else:
                    break
            
            # 只显示音符最多的几个音轨
            if max_tracks > 0 and max_tracks < len(track_note_counts):
                tracks_to_display = [t[0] for t in track_note_counts[:max_tracks]]
            else:
                tracks_to_display = self.tracks
        
        # 计算通道总高度
        total_channel_height = len(tracks_to_display) * (self.channel_height + self.channel_spacing) - self.channel_spacing
        
        # 如果通道总高度超过可用高度，调整通道高度（但不少于最小高度）
        if total_channel_height > available_height:
            calculated_height = (available_height - (len(tracks_to_display) - 1) * self.channel_spacing) // len(tracks_to_display)
            self.channel_height = max(self.min_channel_height, calculated_height)
            total_channel_height = len(tracks_to_display) * (self.channel_height + self.channel_spacing) - self.channel_spacing
        
        # 计算垂直居中
        y_offset = start_y + (available_height - total_channel_height) // 2
        
        # 计算波形显示区域（从最左边到蜂鸣器）
        waveform_start_x = self.waveform_start_x  # 左侧留出空间给标签
        buzzer_x = width - self.buzzer_x_offset  # 蜂鸣器位置
        waveform_area_width = buzzer_x - waveform_start_x  # 波形显示区域宽度（从起始位置到蜂鸣器）
        
        # 绘制蜂鸣器（在右侧）
        buzzer_y = height // 2
        buzzer_radius = 20
        
        # 蜂鸣器背景
        buzzer_bg = QColor(100, 100, 100)
        painter.setBrush(buzzer_bg)
        painter.setPen(QPen(QColor(200, 200, 200), 2))
        painter.drawEllipse(
            buzzer_x - buzzer_radius,
            buzzer_y - buzzer_radius,
            buzzer_radius * 2,
            buzzer_radius * 2
        )
        
        # 蜂鸣器标签
        painter.setPen(QPen(text_color))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(
            buzzer_x - 15,
            buzzer_y + 5,
            "输出"
        )
        
        # 绘制蜂鸣器垂直线（表示播放位置）
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawLine(
            buzzer_x,
            y_offset,
            buzzer_x,
            y_offset + total_channel_height
        )
        
        # 绘制每个通道（使用筛选后的音轨列表）
        # 使用track id去重
        seen_track_ids = set()
        unique_tracks_to_draw = []
        for track in tracks_to_display:
            track_id = id(track)
            if track_id not in seen_track_ids:
                seen_track_ids.add(track_id)
                unique_tracks_to_draw.append(track)
        
        for i, track in enumerate(unique_tracks_to_draw):
            # 计算通道位置
            channel_y = y_offset + i * (self.channel_height + self.channel_spacing)
            channel_center_y = channel_y + self.channel_height // 2
            
            # 绘制通道背景（从最左边到蜂鸣器）
            channel_bg = QColor(bg_color)
            channel_bg.setAlpha(30)
            painter.fillRect(
                waveform_start_x,
                channel_y,
                waveform_area_width,
                self.channel_height,
                channel_bg
            )
            
            # 绘制代码显示（左侧）
            # 找到即将播放的音符（最接近蜂鸣器的音符）
            animation_time = self.internal_time if hasattr(self, 'internal_time') else self.current_time
            upcoming_note = None
            if track.track_type == TrackType.NOTE_TRACK:
                # 找到最接近蜂鸣器位置（即将播放）的音符
                time_to_buzzer = waveform_area_width / self.waveform_speed
                target_time = animation_time + time_to_buzzer
                
                # 查找在目标时间附近的音符
                for note in track.notes:
                    note_end_time = note.start_time + note.duration
                    # 如果音符的开始时间在目标时间附近（前后0.5秒内）
                    if abs(note.start_time - target_time) < 0.5 or (note.start_time <= target_time <= note_end_time):
                        if upcoming_note is None or abs(note.start_time - target_time) < abs(upcoming_note.start_time - target_time):
                            upcoming_note = note
                        break
            
            # 生成并显示代码（只显示频率）
            code_text = self.generate_code_for_note(upcoming_note, track) if upcoming_note else track.name[:10]
            
            # 绘制代码文本（使用等宽字体，更适合代码显示）
            painter.setPen(QPen(text_color))
            painter.setFont(QFont("Consolas", 9))  # 等宽字体
            painter.drawText(
                10,
                channel_center_y + 5,
                code_text[:25]  # 限制长度
            )
            
            # 绘制通道网格线（水平中心线，从最左边到蜂鸣器）
            painter.setPen(QPen(grid_color, 1, Qt.DotLine))
            painter.drawLine(
                waveform_start_x,
                channel_center_y,
                waveform_start_x + waveform_area_width,
                channel_center_y
            )
            
            # 生成连续波形（过去一段时间到当前播放时刻）
            if track.track_type == TrackType.NOTE_TRACK:
                # 使用内部时间（平滑后的时间）计算位置，确保动画平滑
                animation_time = self.internal_time if hasattr(self, 'internal_time') else self.current_time
                
                # 使用固定时间窗口，保证“当前时间”准确落在蜂鸣器所在的红线上
                # 可见时间范围：从 (current_time - visible_window) 到 current_time
                time_range_for_area = self.visible_window
                num_samples = self.num_samples
                # 这里用 (num_samples - 1) 确保最后一个采样点严格对应当前时间
                time_step = time_range_for_area / max(1, (num_samples - 1))
                
                visible_end_time = max(0.0, animation_time)
                visible_start_time = max(0.0, visible_end_time - time_range_for_area)
                
                # 获取这个时间范围内的所有音符（稍微扩大范围以确保覆盖）
                all_notes = self.get_notes_in_range(track, visible_start_time - 0.5, visible_end_time + 0.5)
                
                # 如果窗口内没有音符，跳过该通道
                if not all_notes:
                    continue
                
                # 初始化波形数组（全0，表示没有音符的地方）
                continuous_waveform = np.zeros(num_samples, dtype=np.float32)
                
                # 获取音轨的固定颜色
                track_key = id(track)
                if track_key not in self.track_colors:
                    self.track_colors[track_key] = self.channel_colors[len(self.track_colors) % len(self.channel_colors)]
                color = self.track_colors[track_key]
                
                # 为窗口内所有音符预生成或获取完整波形（缓存）
                # 使用id(note)作为键的一部分，避免Note不可哈希的问题
                note_waveforms = {}
                for note in all_notes:
                    note_id = id(note)
                    note_key = (track_key, note_id, note.start_time, note.duration, note.pitch, note.waveform.value, note.duty_cycle)
                    if note_key not in self.waveform_cache:
                        frequency = self.audio_engine.waveform_generator.midi_to_frequency(note.pitch)
                        samples_per_cycle = self.audio_engine.sample_rate / frequency if frequency > 0 else 100
                        min_samples_per_cycle = 20  # 每个周期至少20个采样点，确保波形细节可见
                        if samples_per_cycle < min_samples_per_cycle:
                            display_sample_rate = frequency * min_samples_per_cycle
                        else:
                            display_sample_rate = self.audio_engine.sample_rate
                        full_samples = max(500, int(note.duration * display_sample_rate))
                        self.waveform_cache[note_key] = self.generate_pwm_waveform(note, note.duration, full_samples)
                    note_waveforms[note_id] = self.waveform_cache[note_key]
                
                # 为每个采样点选择一个“当前音符”：
                # 规则：在该时间范围内所有覆盖此时刻的音符中，
                # 1) 优先选择 start_time 最大（靠后开始的），
                # 2) 如果 start_time 相同，则选择 pitch 较高的。
                eps = 1e-4
                for i in range(num_samples):
                    sample_time = visible_start_time + i * time_step
                    winner = None
                    for note in all_notes:
                        note_start = note.start_time
                        note_end = note.start_time + note.duration
                        if note_start <= sample_time < note_end:
                            if winner is None:
                                winner = note
                            else:
                                if (note_start > winner.start_time + eps or
                                    (abs(note_start - winner.start_time) <= eps and note.pitch > winner.pitch)):
                                    winner = note
                    if winner is None:
                        continue
                    full_waveform = note_waveforms.get(id(winner))
                    if full_waveform is None or len(full_waveform) == 0:
                        continue
                    note_duration = winner.duration
                    if note_duration <= 0:
                        continue
                    local_pos = (sample_time - winner.start_time) / note_duration
                    local_pos = max(0.0, min(1.0, local_pos))
                    wf_idx = local_pos * (len(full_waveform) - 1)
                    left = int(np.floor(wf_idx))
                    right = min(len(full_waveform) - 1, left + 1)
                    frac = wf_idx - left
                    value = (1.0 - frac) * full_waveform[left] + frac * full_waveform[right]
                    continuous_waveform[i] = value
                
                # 可选：按当前窗口内的最大幅度归一化，使波形尽量“撑满”通道高度
                max_amp = np.max(np.abs(continuous_waveform))
                if max_amp > 0:
                    continuous_waveform = continuous_waveform / max_amp
                
                # 现在计算每个采样点在屏幕上的x位置
                # 将整个可见时间窗口线性映射到完整的波形区域宽度：
                # - 最左边对应 visible_start_time（过去）
                # - 最右边（蜂鸣器位置）对应 visible_end_time == current_time
                points = []
                for i in range(num_samples):
                    # 线性插值到 [0, waveform_area_width]（时间从左到右推进）
                    if num_samples > 1:
                        x_norm = i / (num_samples - 1)
                    else:
                        x_norm = 0.0
                    x = x_norm * waveform_area_width
                    screen_x = waveform_start_x + x
                    # 使用接近整个通道高度的比例，使波形更“饱满”
                    screen_y = channel_center_y - continuous_waveform[i] * self.channel_height * 0.45
                    points.append((screen_x, screen_y))
                
                # 绘制连续波形线
                if len(points) > 1:
                    painter.setPen(QPen(color, 2))
                    for j in range(len(points) - 1):
                        painter.drawLine(
                            int(points[j][0]),
                            int(points[j][1]),
                            int(points[j + 1][0]),
                            int(points[j + 1][1])
                        )
        
        # 如果正在播放，绘制连接线（从波形到蜂鸣器）
        if self.is_playing and len(self.tracks) > 0:
            painter.setPen(QPen(QColor(255, 200, 0), 2, Qt.DashLine))
            for i, track in enumerate(self.tracks):
                if track.track_type != TrackType.NOTE_TRACK:
                    continue
                
                channel_y = y_offset + i * (self.channel_height + self.channel_spacing)
                channel_center_y = channel_y + self.channel_height // 2
                
                # 找到当前正在播放的音符（到达蜂鸣器的音符）
                notes = self.get_notes_in_range(
                    track,
                    self.current_time - 0.1,  # 稍微提前一点
                    self.current_time + 0.1
                )
                
                for note in notes:
                    # 检查音符是否到达蜂鸣器
                    time_offset = note.start_time - self.current_time
                    if abs(time_offset) < 0.1:  # 在蜂鸣器附近
                        # 绘制连接线
                        line_start_x = buzzer_x - buzzer_radius
                        painter.drawLine(
                            line_start_x,
                            channel_center_y,
                            buzzer_x - buzzer_radius,
                            channel_center_y
                        )
