"""
包络处理模块

提供ADSR包络和音高包络的处理功能。
"""

import numpy as np
from typing import Optional

from .models import ADSRParams


class EnvelopeProcessor:
    """包络处理器"""
    
    def __init__(self, sample_rate: int = 44100):
        """
        初始化包络处理器
        
        Args:
            sample_rate: 采样率，默认44100Hz
        """
        self.sample_rate = sample_rate
    
    def generate_adsr_envelope(
        self,
        duration: float,
        adsr: ADSRParams,
        sustain_duration: Optional[float] = None
    ) -> np.ndarray:
        """
        生成ADSR包络
        
        Args:
            duration: 总持续时间（秒）
            adsr: ADSR参数
            sustain_duration: 延音持续时间（秒），None表示持续到结束
        
        Returns:
            包络数组（0-1）
        """
        num_samples = int(self.sample_rate * duration)
        envelope = np.ones(num_samples, dtype=np.float32)
        
        # 计算各阶段的采样数
        attack_samples = int(adsr.attack * self.sample_rate)
        decay_samples = int(adsr.decay * self.sample_rate)
        release_samples = int(adsr.release * self.sample_rate)
        
        # 计算延音阶段的采样数
        if sustain_duration is None:
            # 延音持续到释放阶段
            sustain_samples = num_samples - attack_samples - decay_samples - release_samples
        else:
            sustain_samples = int(sustain_duration * self.sample_rate)
            # 调整总时长
            total_sustain_samples = num_samples - attack_samples - decay_samples - release_samples
            if sustain_samples > total_sustain_samples:
                sustain_samples = total_sustain_samples
        
        # 确保各阶段采样数有效
        attack_samples = max(0, min(attack_samples, num_samples))
        decay_samples = max(0, min(decay_samples, num_samples - attack_samples))
        sustain_samples = max(0, min(sustain_samples, 
                                     num_samples - attack_samples - decay_samples - release_samples))
        release_samples = max(0, min(release_samples,
                                    num_samples - attack_samples - decay_samples - sustain_samples))
        
        current_sample = 0
        
        # Attack阶段：从0到1
        if attack_samples > 0:
            envelope[current_sample:current_sample + attack_samples] = np.linspace(
                0, 1, attack_samples
            )
            current_sample += attack_samples
        
        # Decay阶段：从1到sustain级别
        if decay_samples > 0:
            envelope[current_sample:current_sample + decay_samples] = np.linspace(
                1, adsr.sustain, decay_samples
            )
            current_sample += decay_samples
        
        # Sustain阶段：保持sustain级别
        if sustain_samples > 0:
            envelope[current_sample:current_sample + sustain_samples] = adsr.sustain
            current_sample += sustain_samples
        
        # Release阶段：从sustain到0
        if release_samples > 0:
            release_start = current_sample
            envelope[release_start:release_start + release_samples] = np.linspace(
                adsr.sustain, 0, release_samples
            )
        
        return envelope
    
    def apply_adsr_to_waveform(
        self,
        waveform: np.ndarray,
        adsr: ADSRParams,
        sustain_duration: Optional[float] = None
    ) -> np.ndarray:
        """
        将ADSR包络应用到波形
        
        Args:
            waveform: 输入波形数据
            adsr: ADSR参数
            sustain_duration: 延音持续时间（秒）
        
        Returns:
            应用包络后的波形
        """
        duration = len(waveform) / self.sample_rate
        envelope = self.generate_adsr_envelope(duration, adsr, sustain_duration)
        
        # 确保长度匹配
        min_len = min(len(waveform), len(envelope))
        return (waveform[:min_len] * envelope[:min_len]).astype(np.float32)
    
    def generate_pitch_envelope(
        self,
        duration: float,
        start_frequency: float,
        end_frequency: float,
        curve_type: str = "linear"
    ) -> np.ndarray:
        """
        生成音高包络（频率随时间变化）
        
        Args:
            duration: 持续时间（秒）
            start_frequency: 起始频率（Hz）
            end_frequency: 结束频率（Hz）
            curve_type: 曲线类型，"linear"（线性）或"exponential"（指数）
        
        Returns:
            频率数组
        """
        num_samples = int(self.sample_rate * duration)
        
        if curve_type == "linear":
            frequencies = np.linspace(start_frequency, end_frequency, num_samples)
        elif curve_type == "exponential":
            # 指数曲线
            t = np.linspace(0, 1, num_samples)
            frequencies = start_frequency * (end_frequency / start_frequency) ** t
        else:
            # 默认线性
            frequencies = np.linspace(start_frequency, end_frequency, num_samples)
        
        return frequencies.astype(np.float32)
    
    def apply_vibrato(
        self,
        base_frequency: float,
        duration: float,
        depth: float = 2.0,
        rate: float = 6.0
    ) -> np.ndarray:
        """
        应用颤音效果（频率调制）
        
        Args:
            base_frequency: 基础频率（Hz）
            duration: 持续时间（秒）
            depth: 颤音深度（半音数）
            rate: 颤音速度（Hz）
        
        Returns:
            调制后的频率数组
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples)
        
        # 计算频率调制
        # depth转换为频率变化比例
        freq_ratio = 2 ** (depth / 12.0)
        modulation = np.sin(2 * np.pi * rate * t)
        
        # 频率在 base_frequency * (1/freq_ratio) 到 base_frequency * freq_ratio 之间变化
        frequencies = base_frequency * (1 + (freq_ratio - 1) * (modulation + 1) / 2)
        
        return frequencies.astype(np.float32)
    
    def apply_tremolo(
        self,
        waveform: np.ndarray,
        rate: float = 6.0,
        depth: float = 0.5
    ) -> np.ndarray:
        """
        应用颤音效果（音量调制）
        
        Args:
            waveform: 输入波形数据
            rate: 颤音速度（Hz）
            depth: 颤音深度（0-1）
        
        Returns:
            调制后的波形
        """
        duration = len(waveform) / self.sample_rate
        num_samples = len(waveform)
        t = np.linspace(0, duration, num_samples)
        
        # 生成调制信号
        modulation = 1.0 - depth * (1 - np.sin(2 * np.pi * rate * t)) / 2
        
        return (waveform * modulation).astype(np.float32)

