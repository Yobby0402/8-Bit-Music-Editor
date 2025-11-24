"""
生成超级马里奥FC经典音乐

生成FC版超级马里奥的经典主题音乐（1-1关卡音乐）
可以保存为JSON项目文件，在软件中打开并播放
"""

import json

from core.models import Note, Track, Project, WaveformType, ADSRParams


def create_mario_theme():
    """创建超级马里奥1-1关卡经典主题音乐"""
    
    # 创建项目 - FC原版BPM约为150
    project = Project(name="Super Mario Bros 1-1 Theme", bpm=150)
    
    # 创建主旋律轨道
    melody_track = Track(name="主旋律", waveform=WaveformType.SQUARE)
    
    # 超级马里奥1-1主题音乐的主旋律
    # 经典旋律：E E E (rest) C E G (rest) G C G E...
    # 使用C大调，BPM 150
    bpm = 150
    beat_duration = 60.0 / bpm  # 每拍时长（秒）
    
    # 定义ADSR包络（8bit风格：快速起音，短衰减）
    melody_adsr = ADSRParams(attack=0.001, decay=0.05, sustain=0.8, release=0.1)
    
    # 完整的超级马里奥1-1主题主旋律（约32拍，循环两遍）
    # 格式：(MIDI音高, 节拍数, 开始节拍位置)
    melody_notes = [
        # 第一段：E E E (rest) C E G (rest) G
        (64, 0.5, 0.0),    # E4
        (64, 0.5, 0.5),    # E4
        (64, 0.5, 1.0),    # E4 (短)
        (60, 0.5, 2.0),    # C4 (rest后)
        (64, 0.5, 2.5),    # E4
        (67, 1.0, 3.0),    # G4 (长)
        (67, 0.5, 4.5),    # G4 (rest后)
        
        # 第二段：C C G E C (rest) G E
        (72, 0.5, 5.5),    # C5
        (72, 0.5, 6.0),    # C5
        (67, 0.5, 6.5),    # G4
        (64, 0.5, 7.0),    # E4
        (60, 1.0, 7.5),    # C4 (长)
        (55, 0.5, 9.0),    # G3 (rest后)
        (60, 0.5, 9.5),    # C4
        (64, 1.0, 10.0),   # E4 (长)
        
        # 第三段：G E G A F G (rest)
        (67, 0.5, 11.5),   # G4
        (64, 0.5, 12.0),   # E4
        (67, 0.5, 12.5),   # G4
        (69, 0.5, 13.0),   # A4
        (65, 0.5, 13.5),   # F4
        (67, 1.0, 14.0),   # G4 (长)
        
        # 第四段：C5 G4 E4 C4 (rest) G3 C4 E4
        (72, 0.5, 15.5),   # C5
        (67, 0.5, 16.0),   # G4
        (64, 0.5, 16.5),   # E4
        (60, 1.0, 17.0),   # C4 (长)
        (55, 0.5, 18.5),   # G3 (rest后)
        (60, 0.5, 19.0),   # C4
        (64, 1.0, 19.5),   # E4 (长)
        
        # 第五段：G E G A F G (rest)
        (67, 0.5, 21.0),   # G4
        (64, 0.5, 21.5),   # E4
        (67, 0.5, 22.0),   # G4
        (69, 0.5, 22.5),   # A4
        (65, 0.5, 23.0),   # F4
        (67, 1.0, 23.5),   # G4 (长)
        
        # 第六段：C5 C5 C5 (rest) C5 D5 C5 (rest) A4
        (72, 0.5, 25.0),   # C5
        (72, 0.5, 25.5),   # C5
        (72, 0.5, 26.0),   # C5
        (72, 0.5, 27.0),   # C5 (rest后)
        (74, 0.5, 27.5),   # D5
        (72, 0.5, 28.0),   # C5
        (69, 1.0, 29.0),   # A4 (rest后，长)
        
        # 第七段：F4 G4 E4 C4 A3 E4 A4 (rest) A4
        (65, 0.5, 30.5),   # F4
        (67, 0.5, 31.0),   # G4
        (64, 0.5, 31.5),   # E4
        (60, 0.5, 32.0),   # C4
        (57, 0.5, 32.5),   # A3
        (64, 0.5, 33.0),   # E4
        (69, 0.5, 33.5),   # A4
        (69, 1.0, 34.5),   # A4 (rest后，长)
    ]
    
    # 添加主旋律音符（使用方波，FC原版风格）
    for pitch, beats, start_beats in melody_notes:
        start_time = start_beats * beat_duration
        duration = beats * beat_duration
        note = Note(
            pitch=pitch,
            start_time=start_time,
            duration=duration,
            waveform=WaveformType.SQUARE,
            velocity=127,
            duty_cycle=0.5,  # 方波占空比50%
            adsr=melody_adsr
        )
        melody_track.notes.append(note)
    
    project.add_track(melody_track)
    
    # 创建低音轨道（使用三角波，FC原版低音风格）
    bass_track = Track(name="低音", waveform=WaveformType.TRIANGLE)
    
    # 低音线（完整和声进行，每2拍一个和弦根音）
    bass_notes = []
    # 第一段：C - - - E - - - G - - - C - - -
    bass_notes.extend([
        (48, 2.0, 0.0),    # C3
        (52, 2.0, 4.0),    # E3
        (55, 2.0, 8.0),    # G3
        (48, 2.0, 12.0),   # C3
    ])
    # 第二段：G - - - C - - - E - - -
    bass_notes.extend([
        (55, 2.0, 16.0),   # G3
        (48, 2.0, 20.0),   # C3
        (52, 2.0, 24.0),   # E3
    ])
    # 第三段：F - - - C - - - F - - - C - - -
    bass_notes.extend([
        (53, 2.0, 28.0),   # F3
        (48, 2.0, 32.0),   # C3
        (53, 2.0, 36.0),   # F3
    ])
    
    # 低音ADSR（稍长的衰减）
    bass_adsr = ADSRParams(attack=0.001, decay=0.1, sustain=0.7, release=0.15)
    
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
    
    # 简单的节拍模式（每拍一个底鼓，在弱拍添加踩镲）
    total_beats = 40  # 总拍数
    for beat in range(0, total_beats, 1):
        # 底鼓（强拍和次强拍）
        if beat % 2 == 0:
            note = Note(
                pitch=36,  # C2，低音
                start_time=beat * beat_duration,
                duration=0.1,
                waveform=WaveformType.SQUARE,
                velocity=120,
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
    
    print("正在生成超级马里奥FC经典主题音乐项目...")
    
    # 创建项目
    project = create_mario_theme()
    
    # 转换为字典
    project_dict = project.to_dict()
    
    # 保存为JSON文件
    output_file = "super_mario_1-1_theme.json"
    
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


if __name__ == "__main__":
    main()

