# BPM与播放速度关系说明

## 当前处理流程

### 1. MIDI导入阶段 (`core/midi_io.py`)

**步骤：**
1. 从MIDI文件查找第一个tempo消息，获取BPM
2. 如果没有tempo消息，默认使用120 BPM
3. 使用该BPM将MIDI ticks转换为秒：
   ```
   seconds = ticks * (tempo_microseconds / 1_000_000.0) / ticks_per_beat
   ```
4. 创建项目：`bpm = 解析的BPM`，`original_bpm = 解析的BPM`

**示例：**
- 如果MIDI文件是60 BPM：480 ticks = 1.0秒（1拍）
- 如果MIDI文件是120 BPM：480 ticks = 0.5秒（1拍）

### 2. 音频生成阶段 (`core/audio_engine.py`)

**步骤：**
1. `generate_project_audio`：
   - 如果 `original_bpm == current_bpm`，设置 `original_bpm = None`（不缩放）
   - 否则，保留 `original_bpm` 用于缩放
2. `generate_track_audio`：
   - 如果 `original_bpm == None`，`bpm_ratio = 1.0`（不缩放）
   - 否则，`bpm_ratio = original_bpm / current_bpm`
3. `_generate_note_track_audio`：
   - 如果 `bpm_ratio ≈ 1.0`，直接使用 `note.start_time` 和 `note.duration`
   - 否则，缩放时间：`scaled_time = original_time * bpm_ratio`

**示例：**
- MIDI导入（60 BPM）：
  - `original_bpm = 60`，`current_bpm = 60`
  - 检测到相同，设置 `original_bpm = None`
  - `bpm_ratio = 1.0`，不缩放
- 用户修改BPM（60 → 120）：
  - `original_bpm = 60`，`current_bpm = 120`
  - `bpm_ratio = 60/120 = 0.5`
  - 缩放：`scaled_time = original_time * 0.5`（时间变短，播放变快）

### 3. 播放阶段

**步骤：**
1. 直接播放生成的音频
2. 播放线根据实际播放时间更新

## 问题分析

### 如果小于120BPM都播放慢，可能的原因：

1. **MIDI解析时使用了错误的BPM**
   - 如果MIDI文件没有tempo消息，默认使用120 BPM
   - 如果实际文件是60 BPM，解析时间会偏短（480 ticks = 0.5s 而不是 1.0s）
   - 但这会导致播放快，不是慢

2. **音频生成时错误地应用了缩放**
   - 如果 `original_bpm` 和 `current_bpm` 相同，理论上应该不缩放
   - 但如果代码有bug，可能会错误地应用缩放

3. **最可能的问题**
   - MIDI文件中的tempo消息解析有误
   - 或者，MIDI文件没有tempo消息，但实际BPM低于120
   - 导致解析时使用了错误的BPM

## 需要检查的地方

1. MIDI文件是否包含tempo消息
2. tempo消息的位置是否正确
3. 音频生成时是否正确使用了tempo信息
4. 播放时的时间计算是否正确

