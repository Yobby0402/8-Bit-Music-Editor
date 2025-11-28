"""
波形生成器模块

提供各种波形的生成功能：方波、三角波、锯齿波、正弦波、噪声波。
"""

import numpy as np
from typing import Optional
from enum import Enum

from .models import WaveformType


class WaveformGenerator:
    """波形生成器"""
    
    def __init__(self, sample_rate: int = 44100):
        """
        初始化波形生成器
        
        Args:
            sample_rate: 采样率，默认44100Hz
        """
        self.sample_rate = sample_rate
    
    def generate_square_wave(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 1.0,
        duty_cycle: float = 0.5,
        phase: float = 0.0
    ) -> np.ndarray:
        """
        生成方波
        
        Args:
            frequency: 频率（Hz）
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            duty_cycle: 占空比（0-1），0.5为标准方波
            phase: 初始相位（0-2π）
        
        Returns:
            方波数据数组
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        # 生成方波：根据占空比直接在一个周期内划分「高/低」区域
        # 使用相位归一化到 [0,1)，再与 duty_cycle 比较，避免之前通过正弦阈值导致
        # 在 duty_cycle=0.25 等特殊值时几乎全程为 DC（只听到“pop”而没有音高）。
        phase_norm = (frequency * t + phase / (2 * np.pi)) % 1.0
        wave = np.where(phase_norm < duty_cycle, amplitude, -amplitude)
        
        return wave.astype(np.float32)
    
    def generate_triangle_wave(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 1.0,
        phase: float = 0.0
    ) -> np.ndarray:
        """
        生成三角波
        
        Args:
            frequency: 频率（Hz）
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            phase: 初始相位（0-2π）
        
        Returns:
            三角波数据数组
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        # 三角波：通过锯齿波折叠得到
        # 先生成锯齿波
        sawtooth = 2 * ((t * frequency + phase / (2 * np.pi)) % 1) - 1
        # 折叠成三角波
        triangle = 2 * np.abs(sawtooth) - 1
        
        return (triangle * amplitude).astype(np.float32)
    
    def generate_sawtooth_wave(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 1.0,
        phase: float = 0.0
    ) -> np.ndarray:
        """
        生成锯齿波
        
        Args:
            frequency: 频率（Hz）
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            phase: 初始相位（0-2π）
        
        Returns:
            锯齿波数据数组
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        # 锯齿波：线性上升然后突然下降
        sawtooth = 2 * ((t * frequency + phase / (2 * np.pi)) % 1) - 1
        
        return (sawtooth * amplitude).astype(np.float32)
    
    def generate_sine_wave(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 1.0,
        phase: float = 0.0
    ) -> np.ndarray:
        """
        生成正弦波
        
        Args:
            frequency: 频率（Hz）
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            phase: 初始相位（0-2π）
        
        Returns:
            正弦波数据数组
        """
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        sine = np.sin(2 * np.pi * frequency * t + phase)
        
        return (sine * amplitude).astype(np.float32)
    
    def generate_noise(
        self,
        duration: float,
        amplitude: float = 1.0,
        noise_type: str = "white"
    ) -> np.ndarray:
        """
        生成噪声
        
        Args:
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            noise_type: 噪声类型，"white"（白噪声）或"pink"（粉噪声）
        
        Returns:
            噪声数据数组
        """
        num_samples = int(self.sample_rate * duration)
        
        if noise_type == "white":
            # 白噪声：所有频率均匀分布
            noise = np.random.uniform(-1, 1, num_samples)
        elif noise_type == "pink":
            # 粉噪声：低频更多（简化实现）
            # 实际粉噪声需要更复杂的滤波，这里用简化版本
            white_noise = np.random.uniform(-1, 1, num_samples)
            # 简单的低通滤波模拟粉噪声
            b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
            a = [1, -2.494956002, 2.017265875, -0.522189400]
            noise = np.convolve(white_noise, b, mode='same')
            noise = noise / np.max(np.abs(noise))  # 归一化
        else:
            # 默认使用白噪声
            noise = np.random.uniform(-1, 1, num_samples)
        
        return (noise * amplitude).astype(np.float32)
    
    def generate_waveform(
        self,
        waveform_type: WaveformType,
        frequency: float,
        duration: float,
        amplitude: float = 1.0,
        duty_cycle: float = 0.5,
        phase: float = 0.0,
        noise_type: str = "white"
    ) -> np.ndarray:
        """
        通用波形生成接口
        
        Args:
            waveform_type: 波形类型
            frequency: 频率（Hz），噪声波不使用
            duration: 持续时间（秒）
            amplitude: 振幅（0-1）
            duty_cycle: 占空比（仅用于方波）
            phase: 初始相位
            noise_type: 噪声类型（仅用于噪声波）
        
        Returns:
            波形数据数组
        """
        if waveform_type == WaveformType.SQUARE:
            return self.generate_square_wave(
                frequency, duration, amplitude, duty_cycle, phase
            )
        elif waveform_type == WaveformType.TRIANGLE:
            return self.generate_triangle_wave(
                frequency, duration, amplitude, phase
            )
        elif waveform_type == WaveformType.SAWTOOTH:
            return self.generate_sawtooth_wave(
                frequency, duration, amplitude, phase
            )
        elif waveform_type == WaveformType.SINE:
            return self.generate_sine_wave(
                frequency, duration, amplitude, phase
            )
        elif waveform_type == WaveformType.NOISE:
            return self.generate_noise(duration, amplitude, noise_type)
        else:
            raise ValueError(f"不支持的波形类型: {waveform_type}")
    
    def midi_to_frequency(self, midi_note: int) -> float:
        """
        将MIDI音符编号转换为频率
        
        Args:
            midi_note: MIDI音符编号（0-127）
        
        Returns:
            频率（Hz）
        """
        # A4 (MIDI 69) = 440 Hz
        return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    
    def frequency_to_midi(self, frequency: float) -> int:
        """
        将频率转换为MIDI音符编号
        
        Args:
            frequency: 频率（Hz）
        
        Returns:
            MIDI音符编号（0-127）
        """
        # A4 (MIDI 69) = 440 Hz
        midi = 69 + 12 * np.log2(frequency / 440.0)
        return int(np.round(np.clip(midi, 0, 127)))

