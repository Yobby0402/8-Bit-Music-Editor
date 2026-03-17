"""
ESP32-S3 MicroPython 蜂鸣器播放程序（独立版本 - 无需网络）

从文件系统加载音频文件并自动播放，完全独立运行，无需网络连接。

工作模式：
1. 启动时自动从文件系统加载音频文件（/audio.daf）
2. 自动开始播放（或通过按钮控制）

文件格式：
- 文件路径：/audio.daf
- 格式：设备音频格式（.daf）
  * 文件头包含BPM、总时长、音符数量
  * 数据行：time,freq,duty,duration

使用方法：
1. 将本文件上传到ESP32-S3
2. 使用上位机导出音频文件（.daf格式）
3. 将导出的.daf文件上传到ESP32-S3的根目录，重命名为audio.daf
4. 修改 BUZZER_PIN 为实际使用的引脚
5. 修改 AUTO_PLAY 为 True（自动播放）或 False（等待按钮）
6. 如果使用按钮控制，修改 BUTTON_PIN 为实际使用的引脚
7. 运行程序

ESP32-S3 PWM引脚：
- GPIO 1-21, 26-48（大部分GPIO都支持PWM）
- 推荐使用：GPIO 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21
- 避免使用：GPIO 0（可能用于启动模式），GPIO 43-46（USB相关）
"""

import time

from machine import PWM, Pin

# 配置参数
BUZZER_PIN = 1  # 修改为实际使用的引脚（推荐使用GPIO 2-21）
PWM_FREQUENCY = 1000  # PWM基础频率（Hz），实际频率由数据指定

# 播放控制
AUTO_PLAY = True  # True: 加载后自动播放, False: 等待按钮按下
BUTTON_PIN = 0  # 按钮引脚（如果AUTO_PLAY=False，需要配置此引脚）

# 文件系统相关
AUDIO_FILE_PATH = "/audio.daf"  # 音频文件保存路径
loaded_bpm = None  # 从文件加载的BPM
loaded_duration = None  # 从文件加载的总时长

# 初始化PWM（蜂鸣器）
# ESP32-S3 PWM API: duty()范围0-1023，duty_u16()范围0-65535
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(PWM_FREQUENCY)
buzzer.duty(0)  # 初始静音（duty范围0-1023，0表示0%占空比）

# 初始化按钮（如果使用）
button = None
if not AUTO_PLAY and BUTTON_PIN >= 0:
    button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

# 音符队列（从文件加载）
note_queue = []  # 存储 (start_time, frequency, duty_cycle, duration)
playback_start_time = 0
is_playing = False

def load_audio_file(file_path):
    """从文件系统加载音频文件并解析"""
    global note_queue, loaded_bpm, loaded_duration
    try:
        print("正在加载音频文件: " + file_path)
        
        # 检查文件是否存在
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            print("读取文件失败: " + str(e))
            return False
        
        if not content:
            print("文件为空")
            return False
        
        # 解析文件
        lines = content.strip().split('\n')
        bpm = None
        duration = None
        notes = []
        in_header = True
        line_count = 0
        error_count = 0
        
        print("开始解析文件，共 " + str(len(lines)) + " 行")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('#'):
                if line.startswith('#BPM:'):
                    try:
                        bpm = float(line[5:])
                        print("BPM: " + str(bpm))
                    except Exception as e:
                        print("解析BPM失败: " + str(e))
                elif line.startswith('#DURATION:'):
                    try:
                        duration = float(line[10:])
                        print("时长: " + str(duration) + " 秒")
                    except Exception as e:
                        print("解析时长失败: " + str(e))
                elif line.startswith('#NOTES:'):
                    try:
                        note_count = int(line[7:])
                        print("预期音符数: " + str(note_count))
                    except ValueError:
                        pass
                elif line == "#END_HEADER":
                    in_header = False
                    print("文件头解析完成，开始解析音符数据...")
                continue
            
            if not in_header:
                try:
                    parts = line.split(',')
                    if len(parts) == 4:
                        start_time = float(parts[0])
                        frequency = float(parts[1])
                        duty_cycle = int(parts[2])
                        duration_note = float(parts[3])
                        notes.append((start_time, frequency, duty_cycle, duration_note))
                        line_count += 1
                        
                        # 每解析100个音符输出一次进度
                        if line_count % 100 == 0:
                            print("已解析 " + str(line_count) + " 个音符...")
                    else:
                        error_count += 1
                        if error_count <= 5:  # 只显示前5个错误
                            print("第 " + str(line_num) + " 行格式错误: " + line)
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        print("第 " + str(line_num) + " 行解析失败: " + line + ", 错误: " + str(e))
                    continue
        
        if error_count > 5:
            print("还有 " + str(error_count - 5) + " 行解析错误（未显示）")
        
        # 更新全局变量
        note_queue = notes
        loaded_bpm = bpm
        loaded_duration = duration
        
        # 按开始时间排序
        if notes:
            print("正在排序音符...")
            note_queue.sort(key=lambda x: x[0])
        
        print("=" * 50)
        print("文件加载完成!")
        print("BPM: " + str(bpm))
        print("时长: " + str(duration) + " 秒")
        print("音符数: " + str(len(notes)))
        print("错误行数: " + str(error_count))
        print("=" * 50)
        return True
    except Exception as e:
        print("加载音频文件失败: " + str(e))
        import sys
        sys.print_exception(e)
        return False

def start_playback():
    """开始播放音符队列"""
    global playback_start_time, is_playing, note_queue
    if not note_queue:
        print("音符队列为空，无法播放")
        return
    
    playback_start_time = time.time()
    is_playing = True
    print("开始播放，共 " + str(len(note_queue)) + " 个音符")

def stop_playback():
    """停止播放"""
    global is_playing
    is_playing = False
    buzzer.duty(0)
    print("停止播放")

def update_playback():
    """
    更新播放状态（按时间戳播放音符）
    在主循环中定期调用，实现同步播放
    处理重叠音符：选择优先级最高的音符（与示波器逻辑一致）
    """
    global is_playing, note_queue, playback_start_time
    
    if not is_playing or not note_queue:
        return
    
    current_time = time.time() - playback_start_time
    
    # 找到当前时间应该播放的音符（处理重叠）
    # 规则：1) 优先选择 start_time 最大（靠后开始的）
    #       2) 如果 start_time 相同，则选择 pitch 较高的（这里用frequency代替）
    active_note = None
    eps = 0.001
    
    for start_time, frequency, duty_cycle, duration in note_queue:
        note_end_time = start_time + duration
        
        # 如果音符在当前时间范围内
        if start_time <= current_time < note_end_time:
            if active_note is None:
                active_note = (start_time, frequency, duty_cycle, duration)
            else:
                # 选择优先级更高的音符
                active_start, active_freq, _, _ = active_note
                if (start_time > active_start + eps or
                    (abs(start_time - active_start) <= eps and frequency > active_freq)):
                    active_note = (start_time, frequency, duty_cycle, duration)
    
    # 播放选中的音符
    if active_note:
        _, frequency, duty_cycle, _ = active_note
        try:
            # 确保frequency是int类型（PWM频率必须是整数）
            freq_int = int(round(frequency))
            # 限制频率范围（20Hz - 20000Hz）
            freq_int = max(20, min(20000, freq_int))
            buzzer.freq(freq_int)
            # 确保duty_cycle是int类型且在有效范围内
            duty_value = max(0, min(1023, int(duty_cycle)))
            buzzer.duty(duty_value)
        except Exception as e:
            print("播放音符失败: " + str(e))
            print("频率: " + str(frequency) + " (类型: " + str(type(frequency)) + ")")
            print("占空比: " + str(duty_cycle) + " (类型: " + str(type(duty_cycle)) + ")")
    else:
        # 没有活动音符，静音
        buzzer.duty(0)
    
    # 删除已播放完毕的音符
    notes_to_remove = []
    for i, (start_time, frequency, duty_cycle, duration) in enumerate(note_queue):
        note_end_time = start_time + duration
        if current_time >= note_end_time:
            notes_to_remove.append(i)
    
    # 从后往前删除，避免索引问题
    for i in reversed(notes_to_remove):
        note_queue.pop(i)
    
    # 如果所有音符都播放完毕，停止播放
    if not note_queue:
        stop_playback()

# 主程序
print("=" * 50)
print("ESP32-S3 蜂鸣器播放器（独立版本）")
print("蜂鸣器引脚: GPIO " + str(BUZZER_PIN))
if not AUTO_PLAY:
    print("按钮引脚: GPIO " + str(BUTTON_PIN))
print("=" * 50)

# 启动时自动加载音频文件
print("=" * 50)
print("正在加载音频文件...")
if load_audio_file(AUDIO_FILE_PATH):
    print("音频文件加载成功，准备播放")
    if AUTO_PLAY:
        print("自动播放模式：3秒后开始播放...")
        time.sleep(3)
        start_playback()
    else:
        print("按钮控制模式：等待按钮按下...")
else:
    print("警告: 音频文件加载失败，请确保文件存在: " + AUDIO_FILE_PATH)
    print("请使用上位机导出音频文件并上传到ESP32")
print("=" * 50)

# 主循环（持续播放）
last_button_state = True  # 按钮状态（上拉，按下为False）
while True:
    try:
        # 更新播放状态（按时间戳播放音符）
        update_playback()
        
        # 如果使用按钮控制，检查按钮状态
        if not AUTO_PLAY and button is not None:
            button_state = button.value()
            # 检测按钮按下（从高到低）
            if last_button_state and not button_state:
                if is_playing:
                    print("按钮按下：停止播放")
                    stop_playback()
                else:
                    print("按钮按下：开始播放")
                    start_playback()
            last_button_state = button_state
        
        # 短暂延迟，避免CPU占用过高
        time.sleep(0.01)  # 10ms延迟
        
    except Exception as e:
        print("发生错误: " + str(e))
        import sys
        sys.print_exception(e)
        time.sleep(1)  # 短暂延迟后继续
