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
        pygame.mixer.init(
            frequency=sample_rate,
            size=-16,  # 16位
            channels=2,  # 立体声
            buffer=512
        )
        
        self._current_sounds: List[pygame.mixer.Sound] = []
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
        
        # 确定时间范围（根据BPM比例调整）
        if end_time is None:
            max_end = max(note.end_time for note in track.notes)
            end_time = max_end * bpm_ratio
        
        duration = (end_time - start_time) * bpm_ratio
        if duration <= 0:
            return np.array([], dtype=np.float32)
        
        num_samples = int(self.sample_rate * duration)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # 生成每个音符的音频并混合
        for note in track.notes:
            # 跳过休止符（pitch=0）
            if note.pitch == 0:
                continue
            
            # 根据BPM比例重新计算时间
            adjusted_start_time = note.start_time * bpm_ratio
            adjusted_duration = note.duration * bpm_ratio
            
            # 检查音符是否在时间范围内
            if adjusted_start_time + adjusted_duration <= start_time or adjusted_start_time >= end_time:
                continue
            
            # 生成音符音频（使用调整后的持续时间）
            note_audio = self.generate_note_audio(note, track.volume)
            # 如果持续时间改变了，需要调整音频长度
            if abs(adjusted_duration - note.duration) > 0.001:
                # 重新生成音频以匹配新的持续时间
                from copy import copy
                adjusted_note = copy(note)
                adjusted_note.duration = adjusted_duration
                note_audio = self.generate_note_audio(adjusted_note, track.volume)
            
            # 计算音符在音频数组中的位置（使用调整后的开始时间）
            note_start_sample = int((adjusted_start_time - start_time) * self.sample_rate)
            note_end_sample = note_start_sample + len(note_audio)
            
            # 确保不越界
            if note_start_sample < 0:
                note_audio = note_audio[-note_start_sample:]
                note_start_sample = 0
            
            if note_end_sample > num_samples:
                note_audio = note_audio[:num_samples - note_start_sample]
                note_end_sample = num_samples
            
            # 混合到音频数组
            if note_start_sample < num_samples and note_end_sample > 0:
                audio[note_start_sample:note_end_sample] += note_audio
        
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
        original_bpm: Optional[float] = None
    ) -> np.ndarray:
        """
        混合多个轨道的音频
        
        Args:
            tracks: 轨道列表
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
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
            track_audio = self.generate_track_audio(track, start_time, end_time, bpm, original_bpm)
            
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
        end_time: Optional[float] = None
    ) -> np.ndarray:
        """
        生成整个项目的音频
        
        Args:
            project: 项目对象
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
        
        Returns:
            项目音频数据
        """
        # 只混合启用的轨道
        enabled_tracks = [track for track in project.tracks if track.enabled]
        
        # 使用项目中的BPM和原始BPM来计算时间缩放
        original_bpm = project.original_bpm if hasattr(project, 'original_bpm') and project.original_bpm is not None else project.bpm
        return self.mix_tracks(enabled_tracks, start_time, end_time, project.bpm, original_bpm)
    
    def play_audio(
        self,
        audio_data: np.ndarray,
        loop: bool = False,
        volume: Optional[float] = None
    ) -> pygame.mixer.Sound:
        """
        播放音频数据
        
        Args:
            audio_data: 音频数据数组
            loop: 是否循环播放
            volume: 音量（0.0-1.0），None则使用主音量
        
        Returns:
            pygame Sound对象
        """
        # 应用音量
        if volume is None:
            volume = self.master_volume
        else:
            volume = volume * self.master_volume  # 结合主音量
        
        audio_data = audio_data * volume
        
        # 转换为16位整数
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        
        # 转换为立体声（左右声道相同）
        stereo = np.column_stack((audio_int16, audio_int16))
        
        # 创建Sound对象并播放
        sound = pygame.sndarray.make_sound(stereo)
        sound.play(loops=-1 if loop else 0)
        
        self._current_sounds.append(sound)
        return sound
    
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
        pygame.mixer.stop()
        self._current_sounds.clear()
    
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

