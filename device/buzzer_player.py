"""
ESP32-S3 MicroPython 蜂鸣器播放程序

通过USB串口接收音符数据并驱动蜂鸣器播放。

数据格式：frequency,duty_cycle,duration\n
- frequency: 频率（Hz），整数
- duty_cycle: 占空比（0-1023），整数（ESP32-S3 PWM分辨率10位）
- duration: 持续时间（秒），浮点数

使用方法：
1. 将本文件上传到ESP32-S3
2. 修改 BUZZER_PIN 为实际使用的引脚（ESP32-S3支持PWM的引脚见下方）
3. 运行程序
4. 通过USB串口发送数据，格式：频率,占空比,持续时间\n

示例：
523,512,0.5\n  # 播放523Hz，占空比50%，持续0.5秒

ESP32-S3 PWM引脚：
- GPIO 1-21, 26-48（大部分GPIO都支持PWM）
- 推荐使用：GPIO 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21
- 避免使用：GPIO 0（可能用于启动模式），GPIO 43-46（USB相关）
"""

import time

import machine
from machine import PWM, Pin

# 配置参数
# ESP32-S3 PWM引脚推荐：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21
# 避免使用：GPIO 0（启动模式），GPIO 43-46（USB相关）
BUZZER_PIN = 2  # 修改为实际使用的引脚（推荐使用GPIO 2-21）
BAUDRATE = 115200  # 串口波特率
PWM_FREQUENCY = 1000  # PWM基础频率（Hz），实际频率由数据指定

# UART配置（ESP32-S3专用）
# 重要：ESP32-S3的UART(0)被REPL占用，无法在用户代码中使用
# 必须使用UART(1)或UART(2)，并通过额外的USB转串口模块连接
# 或者：如果您的ESP32-S3有多个USB接口，可以使用USB-CDC（需要特殊配置）
USE_UART_NUM = 1  # 1=使用UART(1)（推荐），2=使用UART(2)，0=UART(0)（不可用）
UART_TX_PIN = 17  # UART TX引脚（ESP32-S3推荐：GPIO 17）
UART_RX_PIN = 18  # UART RX引脚（ESP32-S3推荐：GPIO 18）

# 初始化PWM（蜂鸣器）
# ESP32-S3 PWM API: duty()范围0-1023，duty_u16()范围0-65535
buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(PWM_FREQUENCY)
buzzer.duty(0)  # 初始静音（duty范围0-1023，0表示0%占空比）

# 初始化串口（ESP32-S3通过USB连接）
# 注意：ESP32-S3的UART(0)被REPL占用，必须使用UART(1)或UART(2)
uart = None
if USE_UART_NUM == 0:
    print("错误：ESP32-S3的UART(0)被REPL占用，无法使用")
    print("请将USE_UART_NUM改为1或2，使用UART(1)或UART(2)")
    raise ValueError("UART(0)在ESP32-S3上不可用，请使用UART(1)或UART(2)")
elif USE_UART_NUM == 1:
    # 使用UART(1)（ESP32-S3推荐）
    # 需要额外的USB转串口模块连接到这些引脚
    if UART_TX_PIN is None or UART_RX_PIN is None:
        # ESP32-S3推荐引脚：GPIO 17 (TX), GPIO 18 (RX)
        uart = machine.UART(1, baudrate=BAUDRATE, tx=17, rx=18)
        print("使用UART(1)，TX=GPIO17, RX=GPIO18")
    else:
        uart = machine.UART(1, baudrate=BAUDRATE, tx=UART_TX_PIN, rx=UART_RX_PIN)
        print(f"使用UART(1)，TX=GPIO{UART_TX_PIN}, RX=GPIO{UART_RX_PIN}")
    print("注意：需要额外的USB转串口模块连接到这些引脚")
    print("连接方式：USB转串口模块的TX -> ESP32-S3的RX引脚，RX -> ESP32-S3的TX引脚")
elif USE_UART_NUM == 2:
    # 使用UART(2)
    if UART_TX_PIN is None or UART_RX_PIN is None:
        uart = machine.UART(2, baudrate=BAUDRATE, tx=17, rx=18)
        print("使用UART(2)，TX=GPIO17, RX=GPIO18")
    else:
        uart = machine.UART(2, baudrate=BAUDRATE, tx=UART_TX_PIN, rx=UART_RX_PIN)
        print(f"使用UART(2)，TX=GPIO{UART_TX_PIN}, RX=GPIO{UART_RX_PIN}")
    print("注意：需要额外的USB转串口模块连接到这些引脚")
else:
    raise ValueError(f"不支持的UART编号: {USE_UART_NUM}，请使用0、1或2")

print("=" * 50)
print("ESP32-S3 蜂鸣器播放器已启动")
print(f"蜂鸣器引脚: GPIO {BUZZER_PIN}")
print(f"串口: UART({USE_UART_NUM})")
print(f"串口波特率: {BAUDRATE}")
print("=" * 50)
print("等待数据...")
print("数据格式：频率,占空比,持续时间\\n")
print("示例：523,512,0.5\\n")

# 发送就绪信号到串口（用于上位机检测）
# 格式：READY\n
try:
    if uart:
        ready_msg = "READY\n"
        uart.write(ready_msg.encode('utf-8'))
        uart.flush()
        print("已发送就绪信号")
except Exception as e:
    print(f"发送就绪信号失败: {e}")

# 接收缓冲区
buffer = ""

def parse_note_data(data_str):
    """
    解析音符数据
    
    Args:
        data_str: 数据字符串，格式：频率,占空比,持续时间
    
    Returns:
        (frequency, duty_cycle, duration) 或 None（如果解析失败）
    """
    try:
        parts = data_str.strip().split(',')
        if len(parts) != 3:
            return None
        
        frequency = int(parts[0])
        duty_cycle = int(parts[1])
        duration = float(parts[2])
        
        # 验证数据范围
        if frequency < 20 or frequency > 20000:
            print(f"警告: 频率 {frequency} Hz 超出范围 (20-20000)")
            return None
        
        if duty_cycle < 0 or duty_cycle > 1023:
            print(f"警告: 占空比 {duty_cycle} 超出范围 (0-1023)")
            return None
        
        if duration < 0.001 or duration > 10.0:
            print(f"警告: 持续时间 {duration} 秒超出范围 (0.001-10)")
            return None
        
        return (frequency, duty_cycle, duration)
    except Exception as e:
        print(f"解析数据失败: {e}")
        return None

def play_note(frequency, duty_cycle, duration):
    """
    播放单个音符
    
    Args:
        frequency: 频率（Hz）
        duty_cycle: 占空比（0-1023），ESP32-S3使用duty()方法
        duration: 持续时间（秒）
    """
    try:
        # 设置频率（ESP32-S3支持1Hz到40MHz）
        buzzer.freq(int(frequency))
        
        # 设置占空比（ESP32-S3: duty()范围0-1023）
        # duty_cycle已经是0-1023范围的值，直接使用
        duty_value = int(duty_cycle)
        duty_value = max(0, min(1023, duty_value))  # 确保在范围内
        buzzer.duty(duty_value)
        
        # 播放指定时长
        time.sleep(duration)
        
        # 停止播放（静音）
        buzzer.duty(0)
        
    except Exception as e:
        print(f"播放音符失败: {e}")
        try:
            buzzer.duty(0)  # 确保静音
        except Exception:
            pass

# 主循环
while True:
    try:
        # 检查是否有数据可读
        if uart.any():
            # 读取数据
            data = uart.read(uart.any())
            if data:
                # 将字节转换为字符串
                buffer += data.decode('utf-8', errors='ignore')
                
                # 处理完整的行（以\n结尾）
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        # 检查是否是连接测试命令
                        if line.strip() == "PING" or line.strip() == "TEST":
                            # 发送应答
                            try:
                                response = "PONG\n"
                                uart.write(response.encode('utf-8'))
                                uart.flush()
                                print("收到连接测试，已发送应答")
                            except Exception as e:
                                print(f"发送应答失败: {e}")
                            continue
                        
                        # 解析并播放音符
                        note_data = parse_note_data(line)
                        if note_data:
                            frequency, duty_cycle, duration = note_data
                            print(f"播放: {frequency}Hz, 占空比={duty_cycle}, 持续={duration:.3f}秒")
                            play_note(frequency, duty_cycle, duration)
                        else:
                            print(f"无效数据: {line}")
        
        # 短暂延迟，避免CPU占用过高
        time.sleep(0.001)
        
    except KeyboardInterrupt:
        print("\n程序中断")
        break
    except Exception as e:
        print(f"错误: {e}")
        buzzer.duty(0)  # 确保静音
        time.sleep(0.1)

# 清理
buzzer.duty(0)
print("程序结束")
