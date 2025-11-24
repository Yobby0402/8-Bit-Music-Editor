"""
基础功能测试

测试核心模块的基本功能。
"""

import numpy as np
from core.models import Project, Track, Note, WaveformType, ADSRParams
from core.waveform_generator import WaveformGenerator
from core.envelope_processor import EnvelopeProcessor
from core.audio_engine import AudioEngine
from core.sequencer import Sequencer


def test_waveform_generator():
    """测试波形生成器"""
    print("测试波形生成器...")
    generator = WaveformGenerator()
    
    # 测试方波
    square = generator.generate_square_wave(440, 0.5, 1.0, 0.5)
    assert len(square) > 0, "方波生成失败"
    print("[OK] 方波生成成功")
    
    # 测试三角波
    triangle = generator.generate_triangle_wave(440, 0.5, 1.0)
    assert len(triangle) > 0, "三角波生成失败"
    print("[OK] 三角波生成成功")
    
    # 测试MIDI转换
    freq = generator.midi_to_frequency(69)  # A4
    assert abs(freq - 440.0) < 0.1, "MIDI转换失败"
    print("[OK] MIDI转换成功")
    
    print("波形生成器测试通过！\n")


def test_envelope_processor():
    """测试包络处理器"""
    print("测试包络处理器...")
    processor = EnvelopeProcessor()
    adsr = ADSRParams(attack=0.01, decay=0.1, sustain=0.7, release=0.2)
    
    # 测试ADSR包络
    envelope = processor.generate_adsr_envelope(1.0, adsr)
    assert len(envelope) > 0, "包络生成失败"
    assert envelope[0] < 0.1, "起音阶段失败"
    print("[OK] ADSR包络生成成功")
    
    print("包络处理器测试通过！\n")


def test_audio_engine():
    """测试音频引擎"""
    print("测试音频引擎...")
    engine = AudioEngine()
    
    # 创建测试音符
    note = Note(
        pitch=60,  # C4
        start_time=0.0,
        duration=0.5,
        velocity=127,
        waveform=WaveformType.SQUARE
    )
    
    # 生成音频
    audio = engine.generate_note_audio(note)
    assert len(audio) > 0, "音频生成失败"
    print("[OK] 音符音频生成成功")
    
    # 清理
    engine.cleanup()
    print("音频引擎测试通过！\n")


def test_sequencer():
    """测试序列器"""
    print("测试序列器...")
    sequencer = Sequencer()
    
    # 添加轨道
    track = sequencer.add_track("Test Track", WaveformType.SQUARE)
    assert track is not None, "添加轨道失败"
    print("[OK] 添加轨道成功")
    
    # 添加音符
    note = sequencer.add_note(track, 60, 0.0, 0.5, 127)
    assert note is not None, "添加音符失败"
    print("[OK] 添加音符成功")
    
    # 测试BPM
    sequencer.set_bpm(120)
    assert sequencer.get_bpm() == 120, "BPM设置失败"
    print("[OK] BPM设置成功")
    
    # 清理
    sequencer.cleanup()
    print("序列器测试通过！\n")


def test_project():
    """测试项目模型"""
    print("测试项目模型...")
    
    # 创建项目
    project = Project(name="Test Project", bpm=120)
    
    # 添加轨道
    track = Track(name="Track 1", waveform=WaveformType.SQUARE)
    project.add_track(track)
    
    # 添加音符
    note = Note(pitch=60, start_time=0.0, duration=0.5)
    track.add_note(note)
    
    # 测试序列化
    data = project.to_dict()
    assert data["name"] == "Test Project", "项目序列化失败"
    print("[OK] 项目序列化成功")
    
    # 测试反序列化
    project2 = Project.from_dict(data)
    assert project2.name == "Test Project", "项目反序列化失败"
    print("[OK] 项目反序列化成功")
    
    print("项目模型测试通过！\n")


if __name__ == "__main__":
    print("=" * 50)
    print("8bit音乐制作器 - 基础功能测试")
    print("=" * 50)
    print()
    
    try:
        test_waveform_generator()
        test_envelope_processor()
        test_audio_engine()
        test_sequencer()
        test_project()
        
        print("=" * 50)
        print("所有测试通过！[OK]")
        print("=" * 50)
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

