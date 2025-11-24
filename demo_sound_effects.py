"""
8bit音效演示脚本

生成并播放各种游戏音效，也可以保存为WAV文件。
"""

import numpy as np
from scipy.io import wavfile
import pygame
import time

from core.waveform_generator import WaveformGenerator
from core.envelope_processor import EnvelopeProcessor
from core.models import WaveformType, ADSRParams


class SoundEffectGenerator:
    """音效生成器"""
    
    def __init__(self, sample_rate: int = 44100):
        """初始化音效生成器"""
        self.sample_rate = sample_rate
        self.waveform_gen = WaveformGenerator(sample_rate)
        self.envelope_proc = EnvelopeProcessor(sample_rate)
        
        # 初始化pygame mixer
        pygame.mixer.init(frequency=sample_rate, size=-16, channels=2, buffer=512)
    
    def generate_jump_sound(self) -> np.ndarray:
        """
        生成跳跃音效
        
        特点：快速上升的音高，短促
        """
        duration = 0.15
        # 从C4快速滑到E5
        start_freq = self.waveform_gen.midi_to_frequency(60)  # C4
        end_freq = self.waveform_gen.midi_to_frequency(76)    # E5
        
        # 生成频率包络
        frequencies = self.envelope_proc.generate_pitch_envelope(
            duration, start_freq, end_freq, "exponential"
        )
        
        # 生成方波，频率随时间变化
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        wave = np.zeros(num_samples)
        
        for i, freq in enumerate(frequencies):
            phase = 2 * np.pi * freq * t[i]
            wave[i] = np.sign(np.sin(phase))  # 方波
        
        # 应用快速衰减包络
        adsr = ADSRParams(attack=0.01, decay=0.05, sustain=0.0, release=0.09)
        envelope = self.envelope_proc.generate_adsr_envelope(duration, adsr)
        wave = wave * envelope
        
        return wave.astype(np.float32)
    
    def generate_collect_sound(self) -> np.ndarray:
        """
        生成收集物品音效
        
        特点：上升的琶音，明亮欢快
        """
        duration = 0.3
        # C大调三和弦：C-E-G
        notes = [60, 64, 67]  # C4, E4, G4
        
        num_samples = int(self.sample_rate * duration)
        wave = np.zeros(num_samples)
        
        # 每个音符持续0.1秒
        note_duration = duration / len(notes)
        note_samples = int(self.sample_rate * note_duration)
        
        for i, midi_note in enumerate(notes):
            freq = self.waveform_gen.midi_to_frequency(midi_note)
            start_sample = i * note_samples
            end_sample = start_sample + note_samples
            
            # 确保不越界
            if end_sample > num_samples:
                end_sample = num_samples
            if start_sample >= num_samples:
                break
            
            # 计算实际长度
            actual_length = end_sample - start_sample
            
            # 生成方波
            t = np.linspace(0, note_duration, actual_length, False)
            note_wave = np.sign(np.sin(2 * np.pi * freq * t))
            
            # 应用包络 - 确保长度匹配
            adsr = ADSRParams(attack=0.01, decay=0.05, sustain=0.8, release=0.04)
            envelope = self.envelope_proc.generate_adsr_envelope(note_duration, adsr)
            
            # 确保包络长度与波形长度匹配
            if len(envelope) != actual_length:
                envelope = self.envelope_proc.generate_adsr_envelope(
                    actual_length / self.sample_rate, adsr
                )
            
            # 确保长度完全匹配
            min_len = min(len(note_wave), len(envelope))
            note_wave = note_wave[:min_len] * envelope[:min_len]
            
            wave[start_sample:start_sample + min_len] = note_wave
        
        return wave.astype(np.float32)
    
    def generate_explosion_sound(self) -> np.ndarray:
        """
        生成爆炸音效
        
        特点：噪声 + 快速衰减
        """
        duration = 0.4
        
        # 生成噪声
        noise = self.waveform_gen.generate_noise(duration, amplitude=1.0, noise_type="white")
        
        # 应用快速衰减包络
        adsr = ADSRParams(attack=0.01, decay=0.1, sustain=0.0, release=0.29)
        envelope = self.envelope_proc.generate_adsr_envelope(duration, adsr)
        
        # 添加低频成分（更像爆炸）
        low_freq = self.waveform_gen.generate_square_wave(60, duration, 0.3, 0.5)
        wave = noise * envelope + low_freq * envelope * 0.5
        
        # 归一化
        max_amp = np.max(np.abs(wave))
        if max_amp > 1.0:
            wave = wave / max_amp
        
        return wave.astype(np.float32)
    
    def generate_shoot_sound(self) -> np.ndarray:
        """
        生成射击音效
        
        特点：短促的方波脉冲
        """
        duration = 0.08
        
        # 短促的方波
        freq = self.waveform_gen.midi_to_frequency(80)  # E5
        wave = self.waveform_gen.generate_square_wave(freq, duration, 1.0, 0.25)
        
        # 快速衰减
        adsr = ADSRParams(attack=0.001, decay=0.02, sustain=0.0, release=0.059)
        envelope = self.envelope_proc.generate_adsr_envelope(duration, adsr)
        wave = wave * envelope
        
        return wave.astype(np.float32)
    
    def generate_click_sound(self) -> np.ndarray:
        """
        生成UI点击音效
        
        特点：非常短促的方波
        """
        duration = 0.05
        
        freq = self.waveform_gen.midi_to_frequency(69)  # A4
        wave = self.waveform_gen.generate_square_wave(freq, duration, 0.8, 0.5)
        
        # 快速衰减
        adsr = ADSRParams(attack=0.001, decay=0.01, sustain=0.0, release=0.039)
        envelope = self.envelope_proc.generate_adsr_envelope(duration, adsr)
        wave = wave * envelope
        
        return wave.astype(np.float32)
    
    def generate_error_sound(self) -> np.ndarray:
        """
        生成错误音效
        
        特点：不和谐的音程，下降音调
        """
        duration = 0.2
        
        # 不和谐音程：C和C#同时播放
        freq1 = self.waveform_gen.midi_to_frequency(60)  # C4
        freq2 = self.waveform_gen.midi_to_frequency(61)  # C#4
        
        wave1 = self.waveform_gen.generate_square_wave(freq1, duration, 0.5, 0.5)
        wave2 = self.waveform_gen.generate_square_wave(freq2, duration, 0.5, 0.5)
        
        # 混合并下降
        wave = (wave1 + wave2) / 2
        
        # 频率下降
        t = np.linspace(0, duration, len(wave), False)
        freq_envelope = np.linspace(1.0, 0.7, len(wave))
        # 简化处理：应用音量包络模拟频率下降
        adsr = ADSRParams(attack=0.01, decay=0.1, sustain=0.3, release=0.09)
        envelope = self.envelope_proc.generate_adsr_envelope(duration, adsr)
        wave = wave * envelope
        
        return wave.astype(np.float32)
    
    def generate_powerup_sound(self) -> np.ndarray:
        """
        生成强化道具音效
        
        特点：上升的琶音，更长更华丽
        """
        duration = 0.6
        # C大调音阶：C-D-E-F-G-A-B-C
        notes = [60, 62, 64, 65, 67, 69, 71, 72]  # C4到C5
        
        num_samples = int(self.sample_rate * duration)
        wave = np.zeros(num_samples)
        
        note_duration = duration / len(notes)
        note_samples = int(self.sample_rate * note_duration)
        
        for i, midi_note in enumerate(notes):
            freq = self.waveform_gen.midi_to_frequency(midi_note)
            start_sample = i * note_samples
            end_sample = start_sample + note_samples
            
            # 确保不越界
            if end_sample > num_samples:
                end_sample = num_samples
            if start_sample >= num_samples:
                break
            
            # 计算实际长度
            actual_length = end_sample - start_sample
            
            # 生成音符波形
            t = np.linspace(0, note_duration, actual_length, False)
            note_wave = np.sign(np.sin(2 * np.pi * freq * t))
            
            # 应用包络 - 确保长度匹配
            adsr = ADSRParams(attack=0.01, decay=0.03, sustain=0.7, release=0.06)
            envelope = self.envelope_proc.generate_adsr_envelope(note_duration, adsr)
            
            # 确保包络长度与波形长度匹配
            if len(envelope) != actual_length:
                # 重新生成包络，使用实际长度
                envelope = self.envelope_proc.generate_adsr_envelope(
                    actual_length / self.sample_rate, adsr
                )
            
            # 确保长度完全匹配
            min_len = min(len(note_wave), len(envelope))
            note_wave = note_wave[:min_len] * envelope[:min_len]
            
            # 写入波形数组
            wave[start_sample:start_sample + min_len] = note_wave
        
        return wave.astype(np.float32)
    
    def play_sound(self, audio_data: np.ndarray):
        """播放音效"""
        # 转换为16位整数
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        
        # 转换为立体声
        stereo = np.column_stack((audio_int16, audio_int16))
        
        # 创建并播放
        sound = pygame.sndarray.make_sound(stereo)
        sound.play()
        
        # 等待播放完成
        while pygame.mixer.get_busy():
            pygame.time.wait(10)
    
    def save_wav(self, audio_data: np.ndarray, filename: str):
        """保存为WAV文件"""
        audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        wavfile.write(filename, self.sample_rate, audio_int16)
        print(f"已保存: {filename}")


def main():
    """主函数"""
    print("=" * 60)
    print("8bit音效演示")
    print("=" * 60)
    print()
    
    generator = SoundEffectGenerator()
    
    # 音效列表
    effects = {
        "1": ("跳跃音效", generator.generate_jump_sound),
        "2": ("收集物品音效", generator.generate_collect_sound),
        "3": ("爆炸音效", generator.generate_explosion_sound),
        "4": ("射击音效", generator.generate_shoot_sound),
        "5": ("UI点击音效", generator.generate_click_sound),
        "6": ("错误音效", generator.generate_error_sound),
        "7": ("强化道具音效", generator.generate_powerup_sound),
    }
    
    print("可用的音效：")
    for key, (name, _) in effects.items():
        print(f"  {key}. {name}")
    print()
    print("输入数字播放音效，输入 'save' 保存所有音效，输入 'q' 退出")
    print()
    
    while True:
        try:
            choice = input("请选择 (1-7/save/q): ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 'save':
                # 保存所有音效
                print("\n正在保存所有音效...")
                for key, (name, func) in effects.items():
                    audio = func()
                    filename = f"sound_effect_{name}.wav"
                    generator.save_wav(audio, filename)
                print("\n所有音效已保存！")
            elif choice in effects:
                name, func = effects[choice]
                print(f"\n播放: {name}")
                audio = func()
                generator.play_sound(audio)
                print("播放完成\n")
            else:
                print("无效选择，请重试\n")
        
        except KeyboardInterrupt:
            print("\n\n退出...")
            break
        except Exception as e:
            print(f"错误: {str(e)}\n")
    
    pygame.mixer.quit()
    print("\n感谢使用！")


if __name__ == "__main__":
    main()

