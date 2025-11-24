"""
快速音效演示

快速生成并播放几个常用音效。
"""

import numpy as np
import pygame
from scipy.io import wavfile

from core.waveform_generator import WaveformGenerator
from core.envelope_processor import EnvelopeProcessor
from core.models import ADSRParams


def play_audio(audio_data: np.ndarray, sample_rate: int = 44100):
    """播放音频"""
    pygame.mixer.init(frequency=sample_rate, size=-16, channels=2, buffer=512)
    
    audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
    stereo = np.column_stack((audio_int16, audio_int16))
    sound = pygame.sndarray.make_sound(stereo)
    sound.play()
    
    while pygame.mixer.get_busy():
        pygame.time.wait(10)
    
    pygame.mixer.quit()


def main():
    """主函数"""
    print("=" * 60)
    print("8bit音效快速演示")
    print("=" * 60)
    print()
    
    gen = WaveformGenerator()
    env = EnvelopeProcessor()
    
    # 1. 跳跃音效
    print("1. 生成跳跃音效...")
    duration = 0.15
    start_freq = gen.midi_to_frequency(60)  # C4
    end_freq = gen.midi_to_frequency(76)   # E5
    
    frequencies = env.generate_pitch_envelope(duration, start_freq, end_freq, "exponential")
    num_samples = int(44100 * duration)
    t = np.linspace(0, duration, num_samples, False)
    wave = np.zeros(num_samples)
    
    for i, freq in enumerate(frequencies):
        phase = 2 * np.pi * freq * t[i]
        wave[i] = np.sign(np.sin(phase))
    
    adsr = ADSRParams(attack=0.01, decay=0.05, sustain=0.0, release=0.09)
    envelope = env.generate_adsr_envelope(duration, adsr)
    wave = wave * envelope
    
    print("   播放中...")
    play_audio(wave)
    print("   完成！\n")
    
    # 2. 收集物品音效
    print("2. 生成收集物品音效...")
    duration = 0.3
    notes = [60, 64, 67]  # C, E, G
    
    num_samples = int(44100 * duration)
    wave = np.zeros(num_samples)
    note_duration = duration / len(notes)
    
    for i, midi_note in enumerate(notes):
        freq = gen.midi_to_frequency(midi_note)
        start_sample = int(i * note_duration * 44100)
        end_sample = int((i + 1) * note_duration * 44100)
        
        t = np.linspace(0, note_duration, end_sample - start_sample, False)
        note_wave = np.sign(np.sin(2 * np.pi * freq * t))
        
        adsr = ADSRParams(attack=0.01, decay=0.05, sustain=0.8, release=0.04)
        envelope = env.generate_adsr_envelope(note_duration, adsr)
        note_wave = note_wave * envelope
        
        wave[start_sample:end_sample] = note_wave
    
    print("   播放中...")
    play_audio(wave)
    print("   完成！\n")
    
    # 3. 爆炸音效
    print("3. 生成爆炸音效...")
    duration = 0.4
    noise = gen.generate_noise(duration, amplitude=1.0, noise_type="white")
    adsr = ADSRParams(attack=0.01, decay=0.1, sustain=0.0, release=0.29)
    envelope = env.generate_adsr_envelope(duration, adsr)
    wave = noise * envelope
    
    max_amp = np.max(np.abs(wave))
    if max_amp > 1.0:
        wave = wave / max_amp
    
    print("   播放中...")
    play_audio(wave)
    print("   完成！\n")
    
    # 4. UI点击音效
    print("4. 生成UI点击音效...")
    duration = 0.05
    freq = gen.midi_to_frequency(69)  # A4
    wave = gen.generate_square_wave(freq, duration, 0.8, 0.5)
    adsr = ADSRParams(attack=0.001, decay=0.01, sustain=0.0, release=0.039)
    envelope = env.generate_adsr_envelope(duration, adsr)
    wave = wave * envelope
    
    print("   播放中...")
    play_audio(wave)
    print("   完成！\n")
    
    print("=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n提示：运行 'python demo_sound_effects.py' 可以交互式试听更多音效")


if __name__ == "__main__":
    main()

