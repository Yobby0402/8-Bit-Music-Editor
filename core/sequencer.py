"""
序列器模块

负责音乐序列的编辑、管理和播放控制。
"""

from typing import List, Optional
from dataclasses import dataclass, field
import numpy as np

from .models import Project, Track, Note, WaveformType, TrackType
from .audio_engine import AudioEngine
from .command import CommandHistory, Command, AddNoteCommand, DeleteNoteCommand, ModifyNoteCommand, MoveNoteCommand, BatchModifyNotesCommand
from .track_events import DrumEvent, DrumType


@dataclass
class PlaybackState:
    """播放状态"""
    is_playing: bool = False
    current_time: float = 0.0
    loop_start: float = 0.0
    loop_end: Optional[float] = None
    end_time: float = 0.0  # 实际音频结束时间（秒），用于精确控制播放线与停止时刻


class Sequencer:
    """序列器"""
    
    def __init__(self, project: Optional[Project] = None, sample_rate: int = 44100):
        """
        初始化序列器
        
        Args:
            project: 项目对象，None则创建新项目
            sample_rate: 采样率
        """
        if project is None:
            project = Project()
        
        self.project = project
        self.audio_engine = AudioEngine(sample_rate)
        self.playback_state = PlaybackState()
        self._current_sound = None
        
        # 命令历史管理器
        self.command_history = CommandHistory(max_history=100)
        
        # 播放时的音轨音量占比 {track_id: ratio (0-1)}，None表示使用track.volume
        self.playback_volume_ratios: dict = {}
        # 当前播放的音量缩放因子（用于防止多音轨混合时削波）
        self.current_volume_scale: float = 1.0
        # 播放时的音轨启用状态 {track_id: enabled (bool)}，None表示使用track.enabled
        self.playback_enabled_tracks: dict = {}
    
    def set_project(self, project: Project) -> None:
        """设置项目"""
        self.project = project
        self.stop()
        # 清空命令历史（新项目）
        self.command_history.clear()
    
    def add_track(self, name: str = None, track_type: TrackType = TrackType.NOTE_TRACK) -> Track:
        """
        添加新轨道
        
        Args:
            name: 轨道名称
            track_type: 音轨类型（NOTE_TRACK 或 DRUM_TRACK）
        
        Returns:
            新创建的轨道
        """
        if name is None:
            if track_type == TrackType.DRUM_TRACK:
                name = "打击乐"
            else:
                name = f"Track {len(self.project.tracks) + 1}"
        
        track = Track(name=name, track_type=track_type)
        self.project.add_track(track)
        return track
    
    def remove_track(self, track: Track) -> None:
        """删除轨道"""
        self.project.remove_track(track)
    
    def add_note(
        self,
        track: Track,
        pitch: int,
        start_time: float,
        duration: float,
        velocity: int = 127,
        use_command: bool = True
    ) -> Note:
        """
        添加音符
        
        Args:
            track: 目标轨道
            pitch: MIDI音高（0-127）
            start_time: 开始时间（秒）
            duration: 持续时间（秒）
            velocity: 力度（0-127）
            use_command: 是否使用命令（用于撤销/重做）
        
        Returns:
            新创建的音符
        """
        # 音符的波形由用户选择，不再使用音轨的默认波形
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            velocity=velocity,
            waveform=WaveformType.SQUARE  # 默认波形，用户可以在属性面板中修改
        )
        
        if use_command:
            # 使用命令模式
            command = AddNoteCommand(self, track, note)
            self.command_history.execute_command(command)
        else:
            # 直接添加（用于撤销/重做内部调用）
            track.add_note(note)
        
        return note
    
    def remove_note(self, track: Track, note: Note, use_command: bool = True) -> None:
        """
        删除音符
        
        Args:
            track: 目标轨道
            note: 要删除的音符
            use_command: 是否使用命令（用于撤销/重做）
        """
        if use_command:
            # 使用命令模式
            command = DeleteNoteCommand(self, track, note)
            self.command_history.execute_command(command)
        else:
            # 直接删除（用于撤销/重做内部调用）
            track.remove_note(note)
    
    def add_drum_event(
        self,
        track: Track,
        drum_type: DrumType,
        start_beat: float,
        duration_beats: float,
        velocity: int = 127,
        use_command: bool = True
    ) -> DrumEvent:
        """
        添加打击乐事件
        
        Args:
            track: 目标轨道（必须是打击乐音轨）
            drum_type: 打击乐类型
            start_beat: 开始节拍位置
            duration_beats: 持续节拍数
            velocity: 力度（0-127）
            use_command: 是否使用命令（用于撤销/重做）
        
        Returns:
            新创建的打击乐事件
        """
        if track.track_type != TrackType.DRUM_TRACK:
            raise ValueError(f"Track {track.name} is not a drum track")
        
        drum_event = DrumEvent(
            drum_type=drum_type,
            start_beat=start_beat,
            duration_beats=duration_beats,
            velocity=velocity
        )
        
        if use_command:
            # TODO: 实现 AddDrumEventCommand
            # 暂时直接添加
            track.add_drum_event(drum_event)
        else:
            # 直接添加（用于撤销/重做内部调用）
            track.add_drum_event(drum_event)
        
        return drum_event
    
    def remove_drum_event(self, track: Track, drum_event: DrumEvent, use_command: bool = True) -> None:
        """
        删除打击乐事件
        
        Args:
            track: 目标轨道
            drum_event: 要删除的打击乐事件
            use_command: 是否使用命令（用于撤销/重做）
        """
        if use_command:
            # TODO: 实现 DeleteDrumEventCommand
            # 暂时直接删除
            track.remove_drum_event(drum_event)
        else:
            # 直接删除（用于撤销/重做内部调用）
            track.remove_drum_event(drum_event)
    
    def get_notes_at_time(self, time: float) -> List[Note]:
        """
        获取指定时间点的所有音符
        
        Args:
            time: 时间（秒）
        
        Returns:
            音符列表
        """
        notes = []
        for track in self.project.tracks:
            notes.extend(track.get_notes_at_time(time))
        return notes
    
    def get_notes_in_range(self, start_time: float, end_time: float) -> List[Note]:
        """
        获取时间范围内的所有音符
        
        Args:
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
        Returns:
            音符列表
        """
        notes = []
        for track in self.project.tracks:
            notes.extend(track.get_notes_in_range(start_time, end_time))
        return notes
    
    def play(self, start_time: float = 0.0, loop: bool = False) -> None:
        """
        播放项目（使用每个音轨单独播放，支持实时音量控制）
        
        Args:
            start_time: 开始播放时间（秒）
            loop: 是否循环播放
        """
        self.stop()
        
        # 确定播放范围
        # 注意：如果JSON中存储的时间是基于不同BPM的，需要根据当前BPM重新计算
        # 但为了简化，我们假设JSON中的时间是基于项目BPM的
        end_time = self.project.get_total_duration()
        if self.playback_state.loop_end is not None:
            end_time = min(end_time, self.playback_state.loop_end)
        
        if end_time <= start_time:
            return
        
        # 设置播放启用状态
        if hasattr(self, 'playback_enabled_tracks') and self.playback_enabled_tracks:
            self.project._playback_enabled_tracks = self.playback_enabled_tracks
        else:
            self.project._playback_enabled_tracks = None
        
        # 为每个音轨生成单独的音频
        track_audio_list = self.audio_engine.generate_track_audio_list(
            self.project, start_time, end_time
        )
        
        if not track_audio_list:
            return
        
        # 计算总时长（使用最长的音轨）
        max_duration = 0.0
        for track, audio_data, track_id in track_audio_list:
            if len(audio_data) > 0:
                duration = len(audio_data) / float(self.audio_engine.sample_rate)
                max_duration = max(max_duration, duration)
        
        self.playback_state.end_time = start_time + max_duration
        
        # 为每个音轨单独播放，使用Channel支持实时音量控制
        # 先准备所有Sound对象和Channel，然后同步启动以确保对齐
        self._current_sounds = []
        channels_to_start = []  # [(channel, sound, loops), ...]
        
        # 计算实际播放的音轨数量（排除空音频）
        valid_tracks = [t for t, audio, _ in track_audio_list if len(audio) > 0]
        num_tracks = len(valid_tracks)
        
        # 当多个音轨同时播放时，需要降低每个音轨的音量以防止硬件混合时的削波
        # 使用更保守的衰减策略，确保混合后不会失真
        if num_tracks > 1:
            # 使用 1/N 衰减，这样N个音轨混合后的总音量约为单个音轨的1倍
            # 这是最保守的方法，确保不会削波，但可能会稍微降低整体音量
            # 用户可以通过主音量或播放设置中的音量占比来调整
            volume_scale = 1.0 / num_tracks
        else:
            volume_scale = 1.0
        
        # 保存音量缩放因子，用于实时音量更新
        self.current_volume_scale = volume_scale
        print(f"[DEBUG] sequencer.play() - num_tracks: {num_tracks}, volume_scale: {volume_scale:.4f}")
        
        for track, audio_data, track_id in track_audio_list:
            # 调试信息：检查音频数据
            print(f"[DEBUG] Track: {track.name}, track_id: {track_id}, audio_len: {len(audio_data)}, track.volume: {track.volume}")
            if len(audio_data) == 0:
                print(f"[DEBUG] Skipping track {track.name} - empty audio")
                continue
            
            # 检查音频数据是否全为0
            if np.max(np.abs(audio_data)) < 0.001:
                print(f"[DEBUG] Warning: Track {track.name} audio is nearly silent (max amplitude: {np.max(np.abs(audio_data))})")
            
            # 获取该音轨的音量占比
            volume_ratio = self.playback_volume_ratios.get(track_id, 1.0) if self.playback_volume_ratios else 1.0
            # 注意：track.volume已经在generate_note_audio中应用到音频了
            # 所以这里只需要传入volume_ratio，最终音量 = volume_ratio * master_volume * volume_scale
            initial_volume = volume_ratio * volume_scale  # 应用音量缩放以防止削波
            
            # 创建Sound对象和Channel，但不立即播放
            sound, channel = self.audio_engine.prepare_track_audio(
                audio_data,
                volume=initial_volume,
                track_id=track_id
            )
            
            if sound and channel:
                self._current_sounds.append(sound)
                channels_to_start.append((channel, sound, -1 if loop else 0))
        
        # 同步启动所有Channel，确保音轨对齐
        for channel, sound, loops in channels_to_start:
            channel.play(sound, loops=loops)
        
        self.playback_state.is_playing = True
        self.playback_state.current_time = start_time
    
    def pause(self) -> None:
        """暂停播放"""
        self.audio_engine.stop_all()
        self.playback_state.is_playing = False
    
    def stop(self) -> None:
        """停止播放"""
        self.audio_engine.stop_all()
        self._current_sounds = []
        self.playback_state.is_playing = False
        self.playback_state.current_time = 0.0
        self.playback_state.end_time = 0.0
    
    def set_loop_region(self, start_time: float, end_time: Optional[float] = None) -> None:
        """
        设置循环区域
        
        Args:
            start_time: 循环开始时间（秒）
            end_time: 循环结束时间（秒），None表示到项目结束
        """
        self.playback_state.loop_start = start_time
        self.playback_state.loop_end = end_time
    
    def clear_loop_region(self) -> None:
        """清除循环区域"""
        self.playback_state.loop_start = 0.0
        self.playback_state.loop_end = None
    
    def set_bpm(self, bpm: float) -> None:
        """
        设置BPM
        
        Args:
            bpm: 节拍速度
        """
        self.project.bpm = max(30.0, min(300.0, bpm))
    
    def get_bpm(self) -> float:
        """获取BPM"""
        return self.project.bpm
    
    def beats_to_seconds(self, beats: float) -> float:
        """
        将节拍数转换为秒
        
        Args:
            beats: 节拍数
        
        Returns:
            秒数
        """
        return beats * 60.0 / self.project.bpm
    
    def seconds_to_beats(self, seconds: float) -> float:
        """
        将秒数转换为节拍数
        
        Args:
            seconds: 秒数
        
        Returns:
            节拍数
        """
        return seconds * self.project.bpm / 60.0
    
    def modify_note(self, track: Track, note: Note, **kwargs) -> None:
        """
        修改音符属性（通过命令模式）
        
        Args:
            track: 目标轨道
            note: 要修改的音符
            **kwargs: 要修改的属性
        """
        command = ModifyNoteCommand(self, track, note, **kwargs)
        self.command_history.execute_command(command)
    
    def batch_modify_notes(self, notes_and_tracks: list, **kwargs) -> None:
        """
        批量修改多个音符属性（通过命令模式）
        
        Args:
            notes_and_tracks: [(note, track), ...] 音符和轨道对列表
            **kwargs: 要修改的属性
        """
        if not notes_and_tracks or not kwargs:
            return
        
        command = BatchModifyNotesCommand(self, notes_and_tracks, **kwargs)
        self.command_history.execute_command(command)
    
    def move_note(self, track: Track, note: Note, new_start_time: float) -> None:
        """
        移动音符位置（通过命令模式）
        
        Args:
            track: 目标轨道
            note: 要移动的音符
            new_start_time: 新的开始时间
        """
        command = MoveNoteCommand(self, track, note, new_start_time)
        self.command_history.execute_command(command)
    
    def undo(self) -> Optional[str]:
        """
        撤销上一个操作
        
        Returns:
            命令描述，如果无法撤销则返回None
        """
        return self.command_history.undo()
    
    def redo(self) -> Optional[str]:
        """
        重做下一个操作
        
        Returns:
            命令描述，如果无法重做则返回None
        """
        return self.command_history.redo()
    
    def can_undo(self) -> bool:
        """是否可以撤销"""
        return self.command_history.can_undo()
    
    def can_redo(self) -> bool:
        """是否可以重做"""
        return self.command_history.can_redo()
    
    def cleanup(self) -> None:
        """清理资源"""
        self.stop()
        self.audio_engine.cleanup()

