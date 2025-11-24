"""
效果处理模块

实现各种音频效果：滤波器、延迟、调制等。
"""

import numpy as np
from typing import Optional, List
from enum import Enum
from dataclasses import dataclass, field


class FilterType(Enum):
    """滤波器类型"""
    LOWPASS = "lowpass"      # 低通滤波器
    HIGHPASS = "highpass"    # 高通滤波器
    BANDPASS = "bandpass"    # 带通滤波器
    BANDSTOP = "bandstop"    # 带阻滤波器


@dataclass
class FilterParams:
    """滤波器参数"""
    filter_type: FilterType = FilterType.LOWPASS
    cutoff_frequency: float = 1000.0  # 截止频率（Hz）
    resonance: float = 1.0  # 共振（Q值，1.0-10.0）
    enabled: bool = False


@dataclass
class DelayParams:
    """延迟效果参数"""
    delay_time: float = 0.1  # 延迟时间（秒）
    feedback: float = 0.3  # 反馈（0-1）
    mix: float = 0.5  # 混合比例（0-1）
    enabled: bool = False


@dataclass
class TremoloParams:
    """颤音效果参数（音量调制）"""
    rate: float = 6.0  # 调制速度（Hz）
    depth: float = 0.5  # 调制深度（0-1）
    enabled: bool = False


@dataclass
class VibratoParams:
    """颤音效果参数（音高调制）"""
    rate: float = 6.0  # 调制速度（Hz）
    depth: float = 2.0  # 调制深度（半音数）
    enabled: bool = False


class EffectProcessor:
    """效果处理器"""
    
    def __init__(self, sample_rate: int = 44100):
        """
        初始化效果处理器
        
        Args:
            sample_rate: 采样率，默认44100Hz
        """
        self.sample_rate = sample_rate
    
    def apply_filter(
        self,
        audio: np.ndarray,
        filter_params: FilterParams
    ) -> np.ndarray:
        """
        应用滤波器
        
        Args:
            audio: 输入音频数据
            filter_params: 滤波器参数
        
        Returns:
            处理后的音频数据
        """
        if not filter_params.enabled:
            return audio
        
        # 简化的IIR滤波器实现
        # 使用双二阶滤波器（Biquad Filter）
        cutoff = filter_params.cutoff_frequency
        resonance = filter_params.resonance
        
        # 限制频率范围
        cutoff = max(20.0, min(cutoff, self.sample_rate / 2 - 1))
        
        # 计算滤波器系数
        if filter_params.filter_type == FilterType.LOWPASS:
            return self._apply_lowpass_filter(audio, cutoff, resonance)
        elif filter_params.filter_type == FilterType.HIGHPASS:
            return self._apply_highpass_filter(audio, cutoff, resonance)
        elif filter_params.filter_type == FilterType.BANDPASS:
            return self._apply_bandpass_filter(audio, cutoff, resonance)
        else:
            return audio
    
    def _apply_lowpass_filter(
        self,
        audio: np.ndarray,
        cutoff: float,
        resonance: float
    ) -> np.ndarray:
        """应用低通滤波器"""
        # 使用简化的低通滤波器（一阶IIR）
        # 更精确的实现可以使用双二阶滤波器
        omega = 2.0 * np.pi * cutoff / self.sample_rate
        alpha = np.sin(omega) / (2.0 * resonance)
        
        cos_omega = np.cos(omega)
        a0 = 1.0 + alpha
        b0 = (1.0 - cos_omega) / 2.0 / a0
        b1 = (1.0 - cos_omega) / a0
        b2 = b0
        a1 = -2.0 * cos_omega / a0
        a2 = (1.0 - alpha) / a0
        
        # 应用滤波器（使用简化的实现）
        # 为了简化，使用一阶低通滤波器
        rc = 1.0 / (2.0 * np.pi * cutoff)
        dt = 1.0 / self.sample_rate
        alpha_filter = dt / (rc + dt)
        
        filtered = np.zeros_like(audio)
        filtered[0] = audio[0]
        
        for i in range(1, len(audio)):
            filtered[i] = filtered[i-1] + alpha_filter * (audio[i] - filtered[i-1])
        
        return filtered
    
    def _apply_highpass_filter(
        self,
        audio: np.ndarray,
        cutoff: float,
        resonance: float
    ) -> np.ndarray:
        """应用高通滤波器"""
        # 简化的高通滤波器实现
        rc = 1.0 / (2.0 * np.pi * cutoff)
        dt = 1.0 / self.sample_rate
        alpha_filter = rc / (rc + dt)
        
        filtered = np.zeros_like(audio)
        filtered[0] = audio[0]
        
        for i in range(1, len(audio)):
            filtered[i] = alpha_filter * (filtered[i-1] + audio[i] - audio[i-1])
        
        return filtered
    
    def _apply_bandpass_filter(
        self,
        audio: np.ndarray,
        cutoff: float,
        resonance: float
    ) -> np.ndarray:
        """应用带通滤波器"""
        # 带通滤波器 = 低通 - 高通
        lowpassed = self._apply_lowpass_filter(audio, cutoff, resonance)
        highpassed = self._apply_highpass_filter(audio, cutoff * 0.5, resonance)
        return lowpassed - highpassed
    
    def apply_delay(
        self,
        audio: np.ndarray,
        delay_params: DelayParams
    ) -> np.ndarray:
        """
        应用延迟效果
        
        Args:
            audio: 输入音频数据
            delay_params: 延迟参数
        
        Returns:
            处理后的音频数据
        """
        if not delay_params.enabled:
            return audio
        
        delay_samples = int(delay_params.delay_time * self.sample_rate)
        if delay_samples <= 0 or delay_samples >= len(audio):
            return audio
        
        # 创建延迟缓冲区
        delayed = np.zeros_like(audio)
        
        # 应用延迟和反馈
        for i in range(len(audio)):
            if i >= delay_samples:
                # 添加延迟信号
                delayed[i] = audio[i] + delay_params.mix * (
                    audio[i - delay_samples] + 
                    delay_params.feedback * delayed[i - delay_samples]
                )
            else:
                delayed[i] = audio[i]
        
        # 归一化，防止削波
        max_amplitude = np.max(np.abs(delayed))
        if max_amplitude > 1.0:
            delayed = delayed / max_amplitude
        
        return delayed
    
    def apply_tremolo(
        self,
        audio: np.ndarray,
        tremolo_params: TremoloParams
    ) -> np.ndarray:
        """
        应用颤音效果（音量调制）
        
        Args:
            audio: 输入音频数据
            tremolo_params: 颤音参数
        
        Returns:
            处理后的音频数据
        """
        if not tremolo_params.enabled:
            return audio
        
        duration = len(audio) / self.sample_rate
        num_samples = len(audio)
        t = np.linspace(0, duration, num_samples)
        
        # 生成调制信号
        modulation = 1.0 - tremolo_params.depth * (1 - np.sin(2 * np.pi * tremolo_params.rate * t)) / 2
        
        return (audio * modulation).astype(np.float32)
    
    def apply_vibrato(
        self,
        audio: np.ndarray,
        vibrato_params: VibratoParams,
        base_frequency: float = 440.0
    ) -> np.ndarray:
        """
        应用颤音效果（音高调制）
        
        注意：音高调制需要重新采样，这里使用简化的相位调制方法
        
        Args:
            audio: 输入音频数据
            vibrato_params: 颤音参数
            base_frequency: 基础频率（Hz），用于计算调制
        
        Returns:
            处理后的音频数据
        """
        if not vibrato_params.enabled:
            return audio
        
        # 使用相位调制实现颤音（简化方法）
        # 更精确的方法需要重新采样
        duration = len(audio) / self.sample_rate
        num_samples = len(audio)
        t = np.linspace(0, duration, num_samples)
        
        # 计算频率调制
        freq_ratio = 2 ** (vibrato_params.depth / 12.0)
        phase_mod = np.sin(2 * np.pi * vibrato_params.rate * t) * (freq_ratio - 1.0)
        
        # 应用相位调制（简化实现）
        # 通过插值实现音高变化
        indices = np.arange(num_samples) + phase_mod * num_samples / (2 * np.pi * base_frequency * duration)
        indices = np.clip(indices, 0, num_samples - 1)
        
        # 使用numpy的线性插值
        if len(audio) > 1:
            # 简单的线性插值
            indices_floor = np.floor(indices).astype(int)
            indices_ceil = np.ceil(indices).astype(int)
            indices_ceil = np.clip(indices_ceil, 0, num_samples - 1)
            indices_floor = np.clip(indices_floor, 0, num_samples - 1)
            
            # 计算插值权重
            weight = indices - indices_floor
            
            # 线性插值
            modulated = audio[indices_floor] * (1 - weight) + audio[indices_ceil] * weight
        else:
            modulated = audio
        
        return modulated.astype(np.float32)
    
    def apply_effect_chain(
        self,
        audio: np.ndarray,
        filter_params: Optional[FilterParams] = None,
        delay_params: Optional[DelayParams] = None,
        tremolo_params: Optional[TremoloParams] = None,
        vibrato_params: Optional[VibratoParams] = None
    ) -> np.ndarray:
        """
        应用效果链（按顺序应用多个效果）
        
        Args:
            audio: 输入音频数据
            filter_params: 滤波器参数
            delay_params: 延迟参数
            tremolo_params: 颤音参数（音量）
            vibrato_params: 颤音参数（音高）
        
        Returns:
            处理后的音频数据
        """
        result = audio.copy()
        
        # 按顺序应用效果
        if filter_params and filter_params.enabled:
            result = self.apply_filter(result, filter_params)
        
        if delay_params and delay_params.enabled:
            result = self.apply_delay(result, delay_params)
        
        if tremolo_params and tremolo_params.enabled:
            result = self.apply_tremolo(result, tremolo_params)
        
        if vibrato_params and vibrato_params.enabled:
            result = self.apply_vibrato(result, vibrato_params)
        
        return result

