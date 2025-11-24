"""
简谱转JSON项目文件

将简谱（jianpu）转换为8bit音乐制作器的JSON项目文件
"""

import json
from typing import List, Tuple

from core.models import Note, Track, Project, WaveformType, ADSRParams


def jianpu_to_midi(jianpu_note: str, key: str = "C") -> int:
    """
    将简谱数字转换为MIDI音高
    
    Args:
        jianpu_note: 简谱数字（如 "1", "1²", "6₅", "⁷"）
        key: 调号（如 "C", "F"），默认C大调
    
    Returns:
        MIDI音高（0-127），如果是休止符返回None
    """
    # 简谱到音名的映射（C大调）
    # 1=do(C), 2=re(D), 3=mi(E), 4=fa(F), 5=sol(G), 6=la(A), 7=si(B)
    jianpu_to_note = {
        "1": 0,  # C
        "2": 2,  # D
        "3": 4,  # E
        "4": 5,  # F
        "5": 7,  # G
        "6": 9,  # A
        "7": 11, # B
    }
    
    # 调号偏移（相对于C大调）
    key_offsets = {
        "C": 0,
        "D": 2,
        "E": 4,
        "F": 5,
        "G": 7,
        "A": 9,
        "B": 11,
    }
    
    # 提取基础数字（可能是上标数字，如 ⁷）
    base_note = None
    octave_offset = 0
    
    # 检查是否是上标数字（高八度）
    superscript_map = {
        "¹": ("1", 1),
        "²": ("2", 1),
        "³": ("3", 1),
        "⁴": ("4", 1),
        "⁵": ("5", 1),
        "⁶": ("6", 1),
        "⁷": ("7", 1),
        "⁸": ("8", 1),
    }
    
    # 检查是否是下标数字（低八度）
    subscript_map = {
        "₁": ("1", -1),
        "₂": ("2", -1),
        "₃": ("3", -1),
        "₄": ("4", -1),
        "₅": ("5", -1),
        "₆": ("6", -1),
        "₇": ("7", -1),
        "₈": ("8", -1),
    }
    
    # 先检查第一个字符
    first_char = jianpu_note[0] if jianpu_note else ""
    
    if first_char in superscript_map:
        base_note, octave_offset = superscript_map[first_char]
    elif first_char in subscript_map:
        base_note, octave_offset = subscript_map[first_char]
    elif first_char.isdigit():
        base_note = first_char
        # 检查后续是否有上标或下标
        if len(jianpu_note) > 1:
            for char in jianpu_note[1:]:
                if char in superscript_map:
                    octave_offset = 1
                    break
                elif char in subscript_map:
                    octave_offset = -1
                    break
    else:
        return None  # 无法识别
    
    if not base_note or base_note == "0":
        return None  # 休止符
    
    if base_note not in jianpu_to_note:
        return None  # 无效的音符
    
    # 计算MIDI音高
    # C4 (60) 作为基准
    base_pitch = 60
    semitone_offset = jianpu_to_note[base_note]
    key_offset = key_offsets.get(key, 0)
    
    # MIDI音高 = 基准 + 调号偏移 + 音级偏移 + 八度偏移*12
    midi_pitch = base_pitch + key_offset + semitone_offset + octave_offset * 12
    
    # 限制在有效范围内
    return max(0, min(127, midi_pitch))


def parse_jianpu_duration(jianpu_note: str, default_beat: float = 0.25) -> float:
    """
    解析简谱音符的时值
    
    Args:
        jianpu_note: 简谱数字（可能包含时值标记）
        default_beat: 默认节拍数（简谱中通常默认是四分音符，但为了不重叠，使用更短的时值）
    
    Returns:
        节拍数
    """
    # 如果包含点，是附点音符
    if "." in jianpu_note:
        return default_beat * 1.5
    
    # 如果包含多个横线，是延长音
    if "-" in jianpu_note:
        dash_count = jianpu_note.count("-")
        # 延长音：基础时值 + 每个横线延长0.5倍
        return default_beat * (1 + dash_count * 0.5)
    
    # 如果包含下划线，是短音符（八分音符或更短）
    if "_" in jianpu_note:
        underscore_count = jianpu_note.count("_")
        return default_beat * (0.5 ** underscore_count)  # 每个下划线减半
    
    # 默认时值（四分音符，但为了不重叠，使用较短时值）
    return default_beat


def beats_to_note_value(beats: float) -> int:
    """
    将节拍数转换为音符类型（几分音符）
    
    Args:
        beats: 节拍数（假设四分音符=1拍）
    
    Returns:
        音符类型：1=全音符(4拍), 2=二分音符(2拍), 4=四分音符(1拍), 8=八分音符(0.5拍), 16=十六分音符(0.25拍)
    """
    # 假设四分音符=1拍
    if beats >= 3.5:
        return 1  # 全音符（4拍）
    elif beats >= 1.5:
        return 2  # 二分音符（2拍）
    elif beats >= 0.75:
        return 4  # 四分音符（1拍）
    elif beats >= 0.375:
        return 8  # 八分音符（0.5拍）
    else:
        return 16  # 十六分音符（0.25拍）


def find_grid_size(all_notes: List[Tuple[int, float, float]]) -> int:
    """
    找到最短音符，确定网格大小
    
    Args:
        all_notes: 音符列表 [(pitch, duration_beats, start_beats), ...]
    
    Returns:
        grid_size: 网格大小（16=十六分音符, 8=八分音符, 4=四分音符等）
    """
    if not all_notes:
        return 16  # 默认十六分音符网格
    
    min_beats = min(beats for _, beats, _ in all_notes if beats > 0)
    
    # 根据最短节拍数确定网格大小
    if min_beats <= 0.125:
        return 32  # 三十二分音符网格
    elif min_beats <= 0.25:
        return 16  # 十六分音符网格
    elif min_beats <= 0.5:
        return 8  # 八分音符网格
    elif min_beats <= 1.0:
        return 4  # 四分音符网格
    elif min_beats <= 2.0:
        return 2  # 二分音符网格
    else:
        return 1  # 全音符网格


def parse_jianpu_line(jianpu_line: str, key: str = "C", bpm: float = 120) -> List[Tuple[int, float, float]]:
    """
    解析一行简谱
    
    Args:
        jianpu_line: 简谱行（如 "6.6653235 | 6.6656 65 |"）
        key: 调号
        bpm: 节拍速度
    
    Returns:
        音符列表 [(MIDI音高, 节拍数, 开始节拍位置), ...]
    """
    beat_duration = 60.0 / bpm
    notes = []
    current_beat = 0.0
    default_beat = 0.25  # 默认时值（八分音符，0.25拍）
    
    # 移除小节线，保留其他符号
    line = jianpu_line.replace("|", " ").replace("||", " ")
    
    # 上标和下标字符
    superscript_chars = "¹²³⁴⁵⁶⁷⁸"
    subscript_chars = "₁₂₃₄₅₆₇₈"
    
    i = 0
    while i < len(line):
        char = line[i]
        
        # 跳过空格
        if char == " ":
            i += 1
            continue
        
        # 检查是否是上标或下标数字（单独的音符）
        if char in superscript_chars or char in subscript_chars:
            note_str = char
            i += 1
            # 收集后续的点、横线等
            while i < len(line) and line[i] in [".", "-", "_"]:
                note_str += line[i]
                i += 1
            
            # 注意：midi_pitch 的解析应该在 while 循环外部
            midi_pitch = jianpu_to_midi(note_str, key)
            if midi_pitch is not None:
                # 计算时值：如果有延长音标记，使用计算的时值；否则使用短时值
                if "-" in note_str:
                    duration = parse_jianpu_duration(note_str, default_beat)
                else:
                    # 没有延长音标记，使用短时值（八分音符）
                    duration = default_beat * 0.5
                
                notes.append((midi_pitch, duration, current_beat))
                # 下一个音符的开始时间 = 当前音符开始时间 + 当前音符时值
                current_beat += duration
            continue
        
        # 普通数字
        if char.isdigit():
            if char == "0":
                # 休止符
                note_str = "0"
                i += 1
                # 收集后续的点、横线等
                while i < len(line) and line[i] in [".", "-", "_"]:
                    note_str += line[i]
                    i += 1
                duration = parse_jianpu_duration(note_str, default_beat)
                current_beat += duration
            else:
                # 音符
                note_str = char
                i += 1
                # 收集后续的标记（点、横线、上标、下标）
                while i < len(line):
                    next_char = line[i]
                    if next_char in [".", "-", "_"] or next_char in superscript_chars or next_char in subscript_chars:
                        note_str += next_char
                        i += 1
                    elif next_char == " " or next_char.isdigit():
                        # 下一个音符或空格
                        break
                    else:
                        i += 1
                
                midi_pitch = jianpu_to_midi(note_str, key)
                if midi_pitch is not None:
                    # 计算时值：如果有延长音标记，使用计算的时值；否则使用短时值
                    if "-" in note_str:
                        duration = parse_jianpu_duration(note_str, default_beat)
                    else:
                        # 没有延长音标记，使用短时值（八分音符）
                        duration = default_beat * 0.5
                    
                    notes.append((midi_pitch, duration, current_beat))
                    # 下一个音符的开始时间 = 当前音符开始时间 + 当前音符时值
                    current_beat += duration
        else:
            # 跳过其他字符（如括号、冒号等）
            i += 1
    
    return notes


def create_project_from_jianpu(jianpu_lines: List[str], title: str = "简谱音乐", 
                               key: str = "C", bpm: float = 120) -> Project:
    """
    从简谱创建项目
    
    Args:
        jianpu_lines: 简谱行列表
        title: 项目标题
        key: 调号
        bpm: 节拍速度
    
    Returns:
        项目对象
    """
    project = Project(name=title, bpm=bpm, original_bpm=bpm)  # 保存原始BPM
    
    # 创建主旋律轨道
    melody_track = Track(name="主旋律", waveform=WaveformType.SQUARE)
    melody_adsr = ADSRParams(attack=0.001, decay=0.05, sustain=0.8, release=0.1)
    
    all_notes = []  # 存储 (midi_pitch, duration_beats, start_beats)
    current_beat_offset = 0.0  # 累积节拍偏移，确保每行连续
    
    # 解析所有简谱行
    for line in jianpu_lines:
        line_notes = parse_jianpu_line(line, key, bpm)
        # 调整每行音符的开始时间，使其连续
        for note_data in line_notes:
            midi_pitch, duration, start_beats = note_data
            if midi_pitch is not None:  # 只添加非休止符
                all_notes.append((midi_pitch, duration, start_beats + current_beat_offset))
        # 更新累积偏移：找到这行的最后一个音符的结束时间
        if line_notes:
            last_note = line_notes[-1]
            last_end_beat = last_note[2] + last_note[1]  # 开始节拍 + 持续节拍
            current_beat_offset = last_end_beat
    
    if not all_notes:
        project.add_track(melody_track)
        return project
    
    # 按开始节拍排序
    all_notes.sort(key=lambda x: x[2])  # 按开始节拍位置排序
    
    # 找到最短音符，确定网格大小
    grid_size = find_grid_size(all_notes)
    
    # 将音符转换为网格格式（note_value + grid_index）
    # grid_size确定每格多少拍（假设四分音符=1拍）
    # 例如：grid_size=16（十六分音符网格），每格=1/16拍
    beats_per_grid = 4.0 / grid_size  # 每格多少拍
    
    current_grid_index = 0  # 当前格子索引
    
    for midi_pitch, duration_beats, start_beats in all_notes:
        # 计算应该放在哪个格子
        grid_index = int(round(start_beats / beats_per_grid))
        
        # 确保格子索引递增（每个格子只能放一个音符）
        if grid_index < current_grid_index:
            grid_index = current_grid_index
        
        # 将节拍数转换为音符类型（几分音符）
        note_value = beats_to_note_value(duration_beats)
        
        # 计算这个音符占几个格子
        # 例如：四分音符(1拍)在十六分音符网格(每格0.25拍)中占4格
        note_grids = int(round(duration_beats / beats_per_grid))
        if note_grids < 1:
            note_grids = 1
        
        # 添加音符（使用临时的start_time和duration，实际导入时会根据grid_index和note_value重新计算）
        note = Note(
            pitch=midi_pitch,
            start_time=0.0,  # 临时值
            duration=0.0,  # 临时值
            waveform=WaveformType.SQUARE,
            velocity=127,
            duty_cycle=0.5,
            adsr=melody_adsr,
            note_value=note_value,
            grid_index=grid_index
        )
        melody_track.notes.append(note)
        
        # 更新当前格子索引（跳过被这个音符占据的格子）
        current_grid_index = grid_index + note_grids
    
    project.add_track(melody_track)
    
    return project


def main():
    """主函数 - 根据红豆曲简谱生成JSON"""
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("正在从简谱生成JSON项目文件...")
    
    # 红豆曲简谱（根据图片描述）
    # 调号：1=F，稍缓（BPM约80-90）
    jianpu_lines = [
        "6.6653235 | 6.6656 65 | 6)3 323¹ 76 | 01 72762.32 |",
        "033⁶⁵ 6.7567 | 6 3:432²- | 03 56¹ 76 | 01⁷²⁷⁶ 2361 |",
        "0 562726. 727 | 6--- | ⁷.2 766 765 | 0 1.6125 535 |",
        "6 3.43211 7 6 | 2.32 05 5231-231765 | 03 3231³ 76 |",
        "01⁷²⁷⁸ 2.32 | 0 33⁶⁵ 6.7587 | 6 3:432²- | 03 56¹-76 |",
        "01⁷²⁷⁶ 238¹ | 0 56727⁶. 727 | 6--61 | 2.2³-432 |",
        "211 - | 61 | 2.3 2.7 23 | 5. 505³ 35 |",
        "⁶.17611 7 | 6765 3.1⁶ 5 | 61 32- |",
        "5576- | 32 35.356 | 6--- | 6--- ||",
    ]
    
    # 创建项目（F大调，稍缓约85 BPM）
    project = create_project_from_jianpu(
        jianpu_lines,
        title="红豆曲",
        key="F",
        bpm=85
    )
    
    # 转换为字典（使用网格格式，只存储note_value和grid_index）
    project_dict = project.to_dict_grid()
    
    # 保存为JSON文件
    output_file = "红豆曲.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(project_dict, f, indent=2, ensure_ascii=False)
    
    # 计算总时长
    total_duration = project.get_total_duration()
    
    print(f"[OK] 项目文件已生成: {output_file}")
    print(f"  - 项目名称: {project.name}")
    print(f"  - 调号: F大调 (1=F)")
    print(f"  - BPM: {project.bpm}")
    print(f"  - 轨道数: {len(project.tracks)}")
    print(f"  - 总时长: {total_duration:.2f} 秒")
    print(f"  - 文件大小: {len(json.dumps(project_dict, ensure_ascii=False).encode('utf-8')) / 1024:.1f} KB")
    print("\n可以在软件中打开此JSON文件并播放！")


if __name__ == "__main__":
    main()

