"""
音频引擎模块

负责音频生成、混合和播放。
"""

import numpy as np
from typing import List, Optional
import pygame

from .models import Note, Track, Project, WaveformType, ADSRParams, TrackType
from .waveform_generator import WaveformGenerator
from .envelope_processor import EnvelopeProcessor
from .track_events import DrumType, DrumEvent
from .effect_processor import EffectProcessor


class AudioEngine:
    """音频引擎"""
    
    def __init__(self, sample_rate: int = 44100):
        """
        初始化音频引擎
        
        Args:
            sample_rate: 采样率，默认44100Hz
        """
        self.sample_rate = sample_rate
        self.waveform_generator = WaveformGenerator(sample_rate)
        self.envelope_processor = EnvelopeProcessor(sample_rate)
        self.effect_processor = EffectProcessor(sample_rate)
        
        # 初始化pygame mixer
        # 设置足够的Channel数量以支持多音轨同时播放（最多32个音轨）
        pygame.mixer.init(
            frequency=sample_rate,
            size=-16,  # 16位
            channels=2,  # 立体声
            buffer=512
        )
        # 预分配足够的Channel（pygame默认只有8个，我们需要更多）
        pygame.mixer.set_num_channels(32)
        
        self._current_sounds: List[pygame.mixer.Sound] = []
        self._current_channels: List[pygame.mixer.Channel] = []  # 用于实时音量控制
        self._track_channels: dict = {}  # {track_id: Channel} 用于跟踪每个音轨的Channel
        self._next_channel_index: int = 0  # 下一个可用的Channel索引
        self.master_volume: float = 1.0  # 主音量（0.0-1.0）
    
    def generate_note_audio(
        self,
        note: Note,
        track_volume: float = 1.0
    ) -> np.ndarray:
        """
        生成单个音符的音频
        
        Args:
            note: 音符对象
            track_volume: 轨道音量（0-1）
        
        Returns:
            音频数据数组
        """
        # 如果是休止符（pitch=0或负数），返回静音
        if note.pitch <= 0:
            num_samples = int(self.sample_rate * note.duration)
            return np.zeros(num_samples, dtype=np.float32)
        
        # 计算频率
        frequency = self.waveform_generator.midi_to_frequency(note.pitch)
        
        # 计算振幅（考虑velocity和轨道音量）
        amplitude = (note.velocity / 127.0) * track_volume
        
        # 生成基础波形
        waveform = self.waveform_generator.generate_waveform(
            waveform_type=note.waveform,
            frequency=frequency,
            duration=note.duration,
            amplitude=amplitude,
            duty_cycle=note.duty_cycle
        )
        
        # 应用ADSR包络
        if note.adsr:
            waveform = self.envelope_processor.apply_adsr_to_waveform(
                waveform, note.adsr
            )
        
        return waveform
    
    def generate_track_audio(
        self,
        track: Track,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        bpm: Optional[float] = None,
        original_bpm: Optional[float] = None
    ) -> np.ndarray:
        """
        生成轨道的音频
        
        Args:
            track: 轨道对象
            start_time: 开始时间（秒）
            end_time: 结束时间（秒），None表示到最后一个音符结束
            bpm: 当前BPM（如果提供，会根据BPM比例重新计算时间）
            original_bpm: 原始BPM（JSON生成时的BPM）
        
        Returns:
            音频数据数组
        """
        if not track.enabled:
            return np.array([], dtype=np.float32)
        
        # 计算BPM比例（如果提供了BPM和原始BPM）
        bpm_ratio = 1.0
        if bpm is not None and original_bpm is not None and original_bpm > 0:
            bpm_ratio = original_bpm / bpm  # 如果BPM变快，比例变小，时间变短
        
        # 根据音轨类型选择不同的生成方法
        if track.track_type == TrackType.DRUM_TRACK:
            return self._generate_drum_track_audio(track, start_time, end_time, bpm, original_bpm, bpm_ratio)
        else:
            return self._generate_note_track_audio(track, start_time, end_time, bpm, original_bpm, bpm_ratio)
    
    def _generate_note_track_audio(
        self,
        track: Track,
        start_time: float,
        end_time: Optional[float],
        bpm: Optional[float],
        original_bpm: Optional[float],
        bpm_ratio: float
    ) -> np.ndarray:
        """生成音符音轨的音频"""
        if not track.notes:
            return np.array([], dtype=np.float32)
        
        # 确定时间范围（不需要乘以bpm_ratio，因为这是目标播放时长）
        if end_time is None:
            max_end = max(note.end_time for note in track.notes)
            end_time = max_end
        
        duration = end_time - start_time
        if duration <= 0:
            return np.array([], dtype=np.float32)
        
        num_samples = int(self.sample_rate * duration)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # 生成每个音符的音频并混合
        for note in track.notes:
            # 跳过休止符（pitch=0）
            if note.pitch == 0:
                continue
            
            # 检查音符是否在时间范围内（使用原始时间，不应用bpm_ratio）
            if note.end_time <= start_time or note.start_time >= end_time:
                continue
            
            # 计算音符在音频数组中的位置（相对于start_time）
            note_start_sample = int((note.start_time - start_time) * self.sample_rate)
            note_duration_samples = int(note.duration * self.sample_rate)
            note_end_sample = note_start_sample + note_duration_samples
            
            # 生成音符音频
            note_audio = self.generate_note_audio(note, track.volume)
            
            # 确保不越界
            if note_start_sample < 0:
                # 音符在start_time之前开始，截取音频
                skip_samples = -note_start_sample
                if skip_samples < len(note_audio):
                    note_audio = note_audio[skip_samples:]
                    note_start_sample = 0
                else:
                    continue  # 整个音符都在start_time之前
            
            if note_end_sample > num_samples:
                # 音符超出end_time，截取音频
                note_audio = note_audio[:num_samples - note_start_sample]
                note_end_sample = num_samples
            
            # 混合到音频数组
            if note_start_sample < num_samples and note_end_sample > 0 and len(note_audio) > 0:
                # 确保note_audio长度匹配
                actual_length = min(len(note_audio), note_end_sample - note_start_sample)
                if actual_length > 0:
                    audio[note_start_sample:note_start_sample + actual_length] += note_audio[:actual_length]
        
        # 应用轨道效果（对整个轨道应用）
        if len(audio) > 0:
            audio = self.effect_processor.apply_effect_chain(
                audio,
                filter_params=track.filter_params,
                delay_params=track.delay_params,
                tremolo_params=track.tremolo_params,
                vibrato_params=track.vibrato_params
            )
            
            # 对单个音轨进行轻微的归一化，防止单个音轨本身就有削波
            # 但保留一些动态范围，不完全归一化到1.0
            max_amplitude = np.max(np.abs(audio))
            if max_amplitude > 0.95:  # 如果接近削波，进行轻微压缩
                # 使用软压缩，而不是硬归一化
                audio = audio * (0.95 / max_amplitude)
        
        return audio
    
    def _generate_drum_track_audio(
        self,
        track: Track,
        start_time: float,
        end_time: Optional[float],
        bpm: Optional[float],
        original_bpm: Optional[float],
        bpm_ratio: float
    ) -> np.ndarray:
        """生成打击乐音轨的音频"""
        if not track.drum_events:
            return np.array([], dtype=np.float32)
        
        # 使用当前BPM或默认BPM来计算节拍到秒的转换
        current_bpm = bpm if bpm is not None else 120.0
        
        # 确定时间范围（根据BPM比例调整）
        if end_time is None:
            # 找到最后一个打击乐事件的结束时间
            max_end_beat = max(event.end_beat for event in track.drum_events)
            max_end_time = max_end_beat * 60.0 / current_bpm
            end_time = max_end_time * bpm_ratio
        
        duration = (end_time - start_time) * bpm_ratio
        if duration <= 0:
            return np.array([], dtype=np.float32)
        
        num_samples = int(self.sample_rate * duration)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # 生成每个打击乐事件的音频并混合
        for event in track.drum_events:
            # 将节拍转换为秒（使用当前BPM）
            event_start_time = event.start_beat * 60.0 / current_bpm
            event_duration = event.duration_beats * 60.0 / current_bpm
            
            # 根据BPM比例重新计算时间
            adjusted_start_time = event_start_time * bpm_ratio
            adjusted_duration = event_duration * bpm_ratio
            
            # 检查事件是否在时间范围内
            if adjusted_start_time + adjusted_duration <= start_time or adjusted_start_time >= end_time:
                continue
            
            # 生成打击乐音频
            drum_audio = self.generate_drum_audio(
                event.drum_type,
                adjusted_duration,
                event.velocity,
                track.volume
            )
            
            # 计算事件在音频数组中的位置
            event_start_sample = int((adjusted_start_time - start_time) * self.sample_rate)
            event_end_sample = event_start_sample + len(drum_audio)
            
            # 确保不越界
            if event_start_sample < 0:
                drum_audio = drum_audio[-event_start_sample:]
                event_start_sample = 0
            
            if event_end_sample > num_samples:
                drum_audio = drum_audio[:num_samples - event_start_sample]
                event_end_sample = num_samples
            
            # 混合到音频数组
            if event_start_sample < num_samples and event_end_sample > 0:
                audio[event_start_sample:event_end_sample] += drum_audio
        
        # 应用轨道效果（对整个轨道应用）
        if len(audio) > 0:
            audio = self.effect_processor.apply_effect_chain(
                audio,
                filter_params=track.filter_params,
                delay_params=track.delay_params,
                tremolo_params=track.tremolo_params,
                vibrato_params=track.vibrato_params
            )
        
        return audio
    
    def mix_tracks(
        self,
        tracks: List[Track],
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        bpm: Optional[float] = None,
        original_bpm: Optional[float] = None,
        playback_volume_ratios: Optional[dict] = None
    ) -> np.ndarray:
        """
        混合多个轨道的音频
        
        Args:
            tracks: 轨道列表
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            bpm: 当前BPM
            original_bpm: 原始BPM
            playback_volume_ratios: 播放时的音轨音量占比字典 {track_id: ratio (0-1)}
        
        Returns:
            混合后的音频数据
        """
        if not tracks:
            return np.array([], dtype=np.float32)
        
        # 确定总时长
        if end_time is None:
            max_end = 0.0
            for track in tracks:
                if track.notes:
                    max_end = max(max_end, max(note.end_time for note in track.notes))
            end_time = max_end
        
        duration = end_time - start_time
        if duration <= 0:
            return np.array([], dtype=np.float32)
        
        num_samples = int(self.sample_rate * duration)
        mixed_audio = np.zeros(num_samples, dtype=np.float32)
        
        # 混合每个轨道
        for track in tracks:
            # 计算播放时的音量（track.volume * 播放占比）
            track_id = id(track)
            
            # 调试信息：检查 playback_volume_ratios 的传递
            if playback_volume_ratios:
                print(f"[DEBUG] Track: {track.name}, track_id: {track_id}")
                print(f"[DEBUG] playback_volume_ratios keys: {list(playback_volume_ratios.keys())}")
                print(f"[DEBUG] track_id in playback_volume_ratios: {track_id in playback_volume_ratios}")
                if track_id in playback_volume_ratios:
                    print(f"[DEBUG] playback_volume_ratios[{track_id}] = {playback_volume_ratios[track_id]}")
            
            if playback_volume_ratios and track_id in playback_volume_ratios:
                playback_volume = track.volume * playback_volume_ratios[track_id]
                print(f"[DEBUG] track.volume: {track.volume}, playback_ratio: {playback_volume_ratios[track_id]}, playback_volume: {playback_volume}")
            else:
                playback_volume = track.volume
                print(f"[DEBUG] Using default track.volume: {playback_volume}")
            
            track_audio = self.generate_track_audio(track, start_time, end_time, bpm, original_bpm)
            
            # 应用播放音量占比（如果与track.volume不同）
            if playback_volume != track.volume:
                volume_ratio = playback_volume / track.volume if track.volume > 0 else 0
                print(f"[DEBUG] Applying volume_ratio: {volume_ratio}, track_audio shape: {track_audio.shape}, max: {np.max(np.abs(track_audio))}")
                track_audio = track_audio * volume_ratio
                print(f"[DEBUG] After applying ratio, max: {np.max(np.abs(track_audio))}")
            
            # 确保长度匹配
            min_len = min(len(mixed_audio), len(track_audio))
            mixed_audio[:min_len] += track_audio[:min_len]
        
        # 归一化，防止削波
        max_amplitude = np.max(np.abs(mixed_audio))
        if max_amplitude > 1.0:
            mixed_audio = mixed_audio / max_amplitude
        
        return mixed_audio.astype(np.float32)
    
    def generate_project_audio(
        self,
        project: Project,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
        playback_volume_ratios: Optional[dict] = None
    ) -> np.ndarray:
        """
        生成整个项目的音频（混合所有音轨）
        
        Args:
            project: 项目对象
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            playback_volume_ratios: 播放时的音轨音量占比字典 {track_id: ratio (0-1)}
        
        Returns:
            项目音频数据
        """
        # 根据播放设置面板的勾选状态决定哪些轨道启用
        # 如果提供了playback_enabled_tracks，使用它；否则使用track.enabled
        playback_enabled = getattr(project, '_playback_enabled_tracks', None)
        print(f"[DEBUG] generate_project_audio - playback_enabled: {playback_enabled}")
        if playback_enabled:
            enabled_tracks = [track for track in project.tracks 
                            if playback_enabled.get(id(track), track.enabled)]
            print(f"[DEBUG] generate_project_audio - using playback_enabled, enabled tracks: {[t.name for t in enabled_tracks]}")
        else:
            enabled_tracks = [track for track in project.tracks if track.enabled]
            print(f"[DEBUG] generate_project_audio - using track.enabled, enabled tracks: {[t.name for t in enabled_tracks]}")
        
        # 为了保证"时间轴上的音符位置"和"实际播放时间"严格一致，
        # 这里不再根据 BPM 对时间做二次缩放，而是直接使用 note.start_time / duration
        # 作为绝对秒数来生成音频。
        #
        # 说明：
        # - MIDI 导入时已经把 tick 换算成了秒，并写入 Note.start_time / duration；
        # - 如果在这里再根据 (original_bpm, project.bpm) 做缩放，
        #   音频时长会被拉伸/压缩，而网格上的音符位置仍然保持原始秒数，
        #   导致播放线"越来越快超过音符"。
        # - 因此这里仍然禁用「根据 original_bpm 进行二次缩放」：original_bpm 始终为 None。
        # - 但为了让使用"节拍"为单位的鼓点（DrumEvent）能够按当前 BPM 正确换算为秒，
        #   需要把 project.bpm 作为 bpm 传入，仅用于 DrumEvent 的节拍→秒转换。

        project_bpm = getattr(project, "bpm", None)
        return self.mix_tracks(enabled_tracks, start_time, end_time, bpm=project_bpm, original_bpm=None,
                              playback_volume_ratios=playback_volume_ratios)
    
    def generate_track_audio_list(
        self,
        project: Project,
        start_time: float = 0.0,
        end_time: Optional[float] = None
    ) -> List[tuple]:
        """
        为每个音轨生成单独的音频（用于单独播放）
        
        Args:
            project: 项目对象
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
        Returns:
            [(track, audio_data, track_id), ...] 列表
        """
        # 根据播放设置面板的勾选状态决定哪些轨道启用
        playback_enabled = getattr(project, '_playback_enabled_tracks', None)
        if playback_enabled:
            enabled_tracks = [track for track in project.tracks 
                            if playback_enabled.get(id(track), track.enabled)]
        else:
            enabled_tracks = [track for track in project.tracks if track.enabled]
        
        project_bpm = getattr(project, "bpm", None)
        track_audio_list = []
        
        for track in enabled_tracks:
            track_id = id(track)
            # 为每个音轨生成单独的音频（不应用playback_volume_ratios，通过Channel控制）
            track_audio = self.generate_track_audio(track, start_time, end_time, project_bpm, None)
            # 调试信息
            audio_max = np.max(np.abs(track_audio)) if len(track_audio) > 0 else 0.0
            print(f"[DEBUG] generate_track_audio_list - Track: {track.name}, type: {track.track_type}, "
                  f"audio_len: {len(track_audio)}, max_amplitude: {audio_max:.4f}, "
                  f"has_notes: {len(track.notes) if hasattr(track, 'notes') else 0}, "
                  f"has_drums: {len(track.drum_events) if hasattr(track, 'drum_events') else 0}")
            track_audio_list.append((track, track_audio, track_id))
        
        return track_audio_list
    
    def prepare_track_audio(
        self,
        audio_data: np.ndarray,
        volume: Optional[float] = None,
        track_id: Optional[int] = None
    ) -> tuple:
        """
        准备音轨音频（创建Sound和Channel，但不播放）
        
        Args:
            audio_data: 音频数据数组
            volume: 音量（0.0-1.0），None则使用主音量
            track_id: 音轨ID（如果提供，会保存Channel引用以便实时控制）
        
        Returns:
            (sound, channel) 元组，如果失败返回 (None, None)
        """
        # 转换为16位整数
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        
        # 转换为立体声（左右声道相同）
        stereo = np.column_stack((audio_int16, audio_int16))
        
        # 创建Sound对象
        sound = pygame.sndarray.make_sound(stereo)
        
        # 使用Channel播放，支持实时音量控制
        # 为每个音轨分配不同的Channel索引，确保不会冲突
        try:
            channel_index = self._next_channel_index
            channel = pygame.mixer.Channel(channel_index)
            self._next_channel_index = (self._next_channel_index + 1) % 32  # 循环使用32个Channel
            print(f"[DEBUG] prepare_track_audio - allocated channel {channel_index} for track_id {track_id}")
        except Exception as e:
            print(f"[DEBUG] prepare_track_audio - failed to allocate channel: {e}")
            # 回退到find_channel
            channel = pygame.mixer.find_channel(force=True)
            if channel is None:
                return (None, None)
        
        # 设置初始音量
        # 注意：track.volume已经在音频生成时应用了，所以这里只需要应用volume_ratio和master_volume
        if volume is None:
            final_volume = self.master_volume
        else:
            # volume已经是volume_ratio了（不包含track.volume）
            final_volume = volume * self.master_volume  # 结合主音量
        
        channel.set_volume(final_volume)
        print(f"[DEBUG] prepare_track_audio - track_id: {track_id}, volume: {volume}, final_volume: {final_volume}, master_volume: {self.master_volume}")
        
        # 保存Channel引用
        self._current_channels.append(channel)
        if track_id is not None:
            self._track_channels[track_id] = channel
        
        return (sound, channel)
    
    def play_audio(
        self,
        audio_data: np.ndarray,
        loop: bool = False,
        volume: Optional[float] = None,
        use_channel: bool = True,
        track_id: Optional[int] = None
    ) -> pygame.mixer.Sound:
        """
        播放音频数据
        
        Args:
            audio_data: 音频数据数组
            loop: 是否循环播放
            volume: 音量（0.0-1.0），None则使用主音量
            use_channel: 是否使用Channel来支持实时音量控制
            track_id: 音轨ID（如果提供，会保存Channel引用以便实时控制）
        
        Returns:
            pygame Sound对象
        """
        # 不在这里应用音量，而是通过Channel实时控制
        # 转换为16位整数
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        
        # 转换为立体声（左右声道相同）
        stereo = np.column_stack((audio_int16, audio_int16))
        
        # 创建Sound对象
        sound = pygame.sndarray.make_sound(stereo)
        
        if use_channel:
            # 使用Channel播放，支持实时音量控制
            # 为每个音轨分配不同的Channel索引
            try:
                channel_index = self._next_channel_index
                channel = pygame.mixer.Channel(channel_index)
                self._next_channel_index = (self._next_channel_index + 1) % 32
            except Exception as e:
                print(f"[DEBUG] play_audio - failed to allocate channel: {e}")
                # 回退到find_channel
                channel = pygame.mixer.find_channel(force=True)
                if channel is None:
                    # 如果还是失败，回退到直接播放
                    use_channel = False
            
            # 设置初始音量
            if volume is None:
                volume = self.master_volume
            else:
                volume = volume * self.master_volume  # 结合主音量
            
            channel.set_volume(volume)
            channel.play(sound, loops=-1 if loop else 0)
            
            self._current_channels.append(channel)
            
            # 如果提供了track_id，保存Channel引用以便实时控制
            if track_id is not None:
                self._track_channels[track_id] = channel
        else:
            # 直接播放（旧方式）
            if volume is None:
                volume = self.master_volume
            else:
                volume = volume * self.master_volume
            
            audio_data = audio_data * volume
            audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
            stereo = np.column_stack((audio_int16, audio_int16))
            sound = pygame.sndarray.make_sound(stereo)
            sound.play(loops=-1 if loop else 0)
        
        self._current_sounds.append(sound)
        return sound
    
    def set_channel_volume(self, channel_index: int, volume: float) -> None:
        """
        设置Channel的音量（实时生效）
        
        Args:
            channel_index: Channel索引
            volume: 音量（0.0-1.0）
        """
        if 0 <= channel_index < len(self._current_channels):
            channel = self._current_channels[channel_index]
            # Channel的set_volume接受0.0-1.0的值
            channel.set_volume(min(1.0, max(0.0, volume * self.master_volume)))
    
    def set_track_volume(self, track_id: int, volume_ratio: float, track_volume: float = 1.0) -> None:
        """
        设置指定音轨的音量（实时生效）
        
        Args:
            track_id: 音轨ID
            volume_ratio: 播放设置中的音量占比（0.0-1.0），已经包含了volume_scale
            track_volume: 音轨的原始音量（0.0-1.0），默认1.0（注意：已经在音频生成时应用）
        """
        if track_id in self._track_channels:
            channel = self._track_channels[track_id]
            if channel:
                # 如果音量占比为0或非常小，直接设置为0（确保完全静音）
                if volume_ratio <= 0.001:
                    final_volume = 0.0
                else:
                    # 最终音量 = volume_ratio * master_volume
                    # 注意：track_volume已经在音频生成时应用了，所以这里不需要再乘以track_volume
                    # volume_ratio已经包含了volume_scale
                    final_volume = min(1.0, max(0.0, volume_ratio * self.master_volume))
                
                # 无论channel是否busy，都设置音量（确保静音立即生效）
                # 使用pygame.mixer.Channel.set_volume()来设置音量，0.0表示完全静音
                channel.set_volume(final_volume)
                
                # 如果设置为0，也尝试暂停channel（双重保险）
                if final_volume <= 0.001:
                    # 注意：pygame的Channel没有pause方法，但set_volume(0.0)应该足够
                    # 如果仍然有问题，可以考虑使用channel.stop()，但这会停止播放
                    pass
                
                print(f"[DEBUG] set_track_volume - track_id: {track_id}, volume_ratio: {volume_ratio}, final_volume: {final_volume}, channel_busy: {channel.get_busy()}")
    
    def set_track_enabled(self, track_id: int, enabled: bool) -> None:
        """
        启用/禁用指定音轨（实时生效）
        
        Args:
            track_id: 音轨ID
            enabled: 是否启用
        """
        if track_id in self._track_channels:
            channel = self._track_channels[track_id]
            if channel:
                if enabled:
                    # 恢复播放：需要重新应用音量（从playback_volume_ratios获取）
                    # 注意：这里不直接恢复音量，而是等待_update_playback_volumes_realtime来设置正确的音量
                    # 因为音量可能已经改变（用户调整了滑块）
                    pass
                else:
                    # 禁用音轨：立即设置为0音量（完全静音）
                    channel.set_volume(0.0)
                    print(f"[DEBUG] set_track_enabled - track_id: {track_id}, enabled: {enabled}, volume set to 0.0")
    
    def set_all_channels_volume(self, volume: float) -> None:
        """
        设置所有Channel的音量（实时生效）
        
        Args:
            volume: 音量（0.0-1.0）
        """
        for channel in self._current_channels:
            if channel.get_busy():
                channel.set_volume(min(1.0, max(0.0, volume * self.master_volume)))
    
    def set_master_volume(self, volume: float) -> None:
        """
        设置主音量
        
        Args:
            volume: 音量（0.0-1.0）
        """
        self.master_volume = max(0.0, min(1.0, volume))
        
        # 更新当前播放的声音音量（pygame.mixer.Sound没有直接设置音量的方法）
        # 注意：pygame的Sound对象不支持动态改变音量，所以需要在播放前设置
        # 这里我们只保存音量值，下次播放时会应用
    
    def stop_all(self) -> None:
        """停止所有播放"""
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.stop()
        except:
            pass  # mixer可能已经关闭
        self._current_sounds.clear()
        self._current_channels.clear()
        self._track_channels.clear()
        self._next_channel_index = 0  # 重置Channel索引
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        return pygame.mixer.get_busy()
    
    def generate_drum_audio(
        self,
        drum_type: DrumType,
        duration: float,
        velocity: int = 127,
        track_volume: float = 1.0
    ) -> np.ndarray:
        """
        生成打击乐音频
        
        Args:
            drum_type: 打击乐类型
            duration: 持续时间（秒）
            velocity: 力度（0-127）
            track_volume: 轨道音量（0-1）
        
        Returns:
            音频数据数组
        """
        amplitude = (velocity / 127.0) * track_volume
        
        if drum_type == DrumType.KICK:
            # 底鼓：低频噪声，短促，快速衰减
            noise = self.waveform_generator.generate_noise(
                duration=duration,
                amplitude=amplitude,
                noise_type="pink"  # 粉噪声，低频更多
            )
            # 快速衰减的ADSR包络
            adsr = ADSRParams(
                attack=0.001,   # 极快起音
                decay=0.05,     # 快速衰减
                sustain=0.0,   # 不保持
                release=0.05   # 快速释放
            )
        elif drum_type == DrumType.SNARE:
            # 军鼓：中高频噪声，有"啪"的声音特征
            noise = self.waveform_generator.generate_noise(
                duration=duration,
                amplitude=amplitude,
                noise_type="white"  # 白噪声，全频段
            )
            # 中等衰减的ADSR包络
            adsr = ADSRParams(
                attack=0.001,
                decay=0.1,
                sustain=0.1,   # 少量保持
                release=0.1
            )
        elif drum_type == DrumType.HIHAT:
            # 踩镲：高频噪声，很短的持续时间
            noise = self.waveform_generator.generate_noise(
                duration=duration,
                amplitude=amplitude * 0.8,  # 稍微降低音量
                noise_type="white"
            )
            # 非常短的ADSR包络
            adsr = ADSRParams(
                attack=0.001,
                decay=0.02,
                sustain=0.0,
                release=0.02
            )
        elif drum_type == DrumType.CRASH:
            # 吊镲：高频噪声，较长的衰减
            noise = self.waveform_generator.generate_noise(
                duration=duration,
                amplitude=amplitude,
                noise_type="white"
            )
            # 较长的衰减ADSR包络
            adsr = ADSRParams(
                attack=0.001,
                decay=0.2,
                sustain=0.05,
                release=0.3
            )
        else:
            # 默认使用白噪声
            noise = self.waveform_generator.generate_noise(
                duration=duration,
                amplitude=amplitude,
                noise_type="white"
            )
            adsr = ADSRParams()
        
        # 应用ADSR包络
        waveform = self.envelope_processor.apply_adsr_to_waveform(noise, adsr)
        
        return waveform
    
    def cleanup(self) -> None:
        """清理资源"""
        self.stop_all()
        pygame.mixer.quit()

