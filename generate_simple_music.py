"""
生成一个简单但完整的8bit音乐示例

创建一个简单的、完整的音乐项目，便于测试和参考
"""

import json

from core.models import Note, Track, Project, WaveformType, ADSRParams


def create_simple_music():
    """创建一个简单但完整的音乐示例"""
    
    # 创建项目
    project = Project(name="Simple 8bit Music", bpm=120)
    
    # 创建主旋律轨道
    melody_track = Track(name="主旋律", waveform=WaveformType.SQUARE)
    
    bpm = 120
    beat_duration = 60.0 / bpm  # 每拍时长（秒）
    
    # 简单的C大调旋律：C D E F G A B C (音阶上行)
    melody_adsr = ADSRParams(attack=0.001, decay=0.05, sustain=0.8, release=0.1)
    
    # 第一段：C大调音阶上行和下行
    melody_notes = [
        # 上行：C D E F G A B C
        (60, 0.5, 0.0),    # C4
        (62, 0.5, 0.5),    # D4
        (64, 0.5, 1.0),    # E4
        (65, 0.5, 1.5),    # F4
        (67, 0.5, 2.0),    # G4
        (69, 0.5, 2.5),    # A4
        (71, 0.5, 3.0),    # B4
        (72, 1.0, 3.5),    # C5 (长)
        
        # 下行：C B A G F E D C
        (72, 0.5, 4.5),    # C5
        (71, 0.5, 5.0),    # B4
        (69, 0.5, 5.5),    # A4
        (67, 0.5, 6.0),    # G4
        (65, 0.5, 6.5),    # F4
        (64, 0.5, 7.0),    # E4
        (62, 0.5, 7.5),    # D4
        (60, 1.0, 8.0),    # C4 (长)
        
        # 第二段：简单的旋律片段
        (60, 0.5, 9.0),    # C4
        (64, 0.5, 9.5),    # E4
        (67, 1.0, 10.0),   # G4 (长)
        (67, 0.5, 11.0),   # G4
        (64, 0.5, 11.5),   # E4
        (60, 1.0, 12.0),   # C4 (长)
        
        # 第三段：重复一遍
        (60, 0.5, 13.0),   # C4
        (62, 0.5, 13.5),   # D4
        (64, 0.5, 14.0),   # E4
        (65, 0.5, 14.5),   # F4
        (67, 0.5, 15.0),   # G4
        (69, 0.5, 15.5),   # A4
        (71, 0.5, 16.0),   # B4
        (72, 2.0, 16.5),   # C5 (很长)
    ]
    
    # 添加主旋律音符
    for pitch, beats, start_beats in melody_notes:
        start_time = start_beats * beat_duration
        duration = beats * beat_duration
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            waveform=WaveformType.SQUARE,
            velocity=127,
            duty_cycle=0.5,
            adsr=melody_adsr
        )
        melody_track.notes.append(note)
    
    project.add_track(melody_track)
    
    # 创建低音轨道（简单的根音）
    bass_track = Track(name="低音", waveform=WaveformType.TRIANGLE)
    
    bass_adsr = ADSRParams(attack=0.001, decay=0.1, sustain=0.7, release=0.15)
    
    # 简单的低音线：每2拍一个根音
    bass_notes = [
        (48, 2.0, 0.0),    # C3
        (48, 2.0, 2.0),    # C3
        (48, 2.0, 4.0),    # C3
        (48, 2.0, 6.0),    # C3
        (48, 2.0, 8.0),    # C3
        (48, 2.0, 10.0),   # C3
        (48, 2.0, 12.0),   # C3
        (48, 2.0, 14.0),   # C3
        (48, 2.0, 16.0),   # C3
        (48, 2.0, 18.0),   # C3
    ]
    
    for pitch, beats, start_beats in bass_notes:
        start_time = start_beats * beat_duration
        duration = beats * beat_duration
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            waveform=WaveformType.TRIANGLE,
            velocity=100,
            adsr=bass_adsr
        )
        bass_track.notes.append(note)
    
    project.add_track(bass_track)
    
    # 创建打击乐轨道（简单的节拍）
    drum_track = Track(name="打击乐", waveform=WaveformType.SQUARE)
    
    # 每拍一个底鼓
    total_beats = 20
    for beat in range(0, total_beats):
        note = Note(
            pitch=36,  # C2，低音
            start_time=beat * beat_duration,
            duration=0.1,
            waveform=WaveformType.SQUARE,
            velocity=100,
            duty_cycle=0.5,
            adsr=ADSRParams(attack=0.001, decay=0.05, sustain=0.0, release=0.03)
        )
        drum_track.notes.append(note)
    
    project.add_track(drum_track)
    
    return project


def main():
    """主函数"""
    import sys
    # 设置UTF-8编码输出
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("正在生成简单但完整的8bit音乐示例...")
    
    # 创建项目
    project = create_simple_music()
    
    # 转换为字典
    project_dict = project.to_dict()
    
    # 保存为JSON文件
    output_file = "simple_music.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(project_dict, f, indent=2, ensure_ascii=False)
    
    # 计算总时长
    total_duration = project.get_total_duration()
    
    print(f"[OK] 项目文件已生成: {output_file}")
    print(f"  - 项目名称: {project.name}")
    print(f"  - BPM: {project.bpm}")
    print(f"  - 轨道数: {len(project.tracks)}")
    print(f"  - 总时长: {total_duration:.2f} 秒")
    print(f"  - 文件大小: {len(json.dumps(project_dict, ensure_ascii=False).encode('utf-8')) / 1024:.1f} KB")
    print("\n可以在软件中打开此JSON文件并播放！")
    print("这个音乐包含：")
    print("  - 主旋律：C大调音阶上行和下行，简单的旋律片段")
    print("  - 低音：C3根音，每2拍一个")
    print("  - 打击乐：简单的节拍，每拍一个底鼓")


if __name__ == "__main__":
    main()

