# 为什么使用秒而不是ticks？

> 历史说明：本文描述的是项目早期的“秒优先”设计取舍，现已不再代表后续架构方向。
> 当前应优先参考 [standard_time_model_refactor.md](/f:/Code/8bit/docs/standard_time_model_refactor.md)，项目正在迁移到 `tick + tempo_events + second(派生)` 的标准时间模型。

## 当前设计

我们的应用内部使用**秒（seconds）**来存储和操作时间，而不是MIDI的**ticks**。

## 使用秒的原因

### 1. **音频生成需要秒**

音频生成的核心公式是：
```python
num_samples = int(sample_rate * duration)
```

- `sample_rate` 是每秒的采样数（通常是44100 Hz）
- `duration` 必须是秒，才能计算出正确的采样数
- 如果使用ticks，每次生成音频都需要转换：`duration_seconds = ticks * (tempo / 1_000_000.0) / ticks_per_beat`

### 2. **播放控制需要秒**

- 播放时间显示：`00:30`（30秒）
- 进度条位置：基于秒计算
- 播放线位置：基于秒更新
- 用户更容易理解秒，而不是ticks

### 3. **独立于BPM**

- 秒是绝对时间，不依赖于BPM
- 如果BPM改变，秒不需要改变
- 但ticks依赖于BPM和ticks_per_beat

### 4. **代码简化**

- 不需要在每次操作时都考虑BPM和ticks_per_beat
- 时间计算更直观：`start_time + duration`
- 音频生成更直接：`int(sample_rate * duration)`

## 使用ticks的优缺点

### 优点

1. **更符合MIDI标准**
   - MIDI文件使用ticks
   - 如果完全使用ticks，导入/导出会更简单

2. **BPM改变时不需要重新计算**
   - ticks是相对时间，不依赖于BPM
   - 如果BPM改变，ticks保持不变

3. **更精确**
   - ticks是整数，不会有浮点误差
   - 秒是浮点数，可能有精度问题

### 缺点

1. **需要频繁转换**
   - 音频生成时需要转换为秒
   - 播放控制时需要转换为秒
   - 每次转换都需要知道BPM和ticks_per_beat

2. **用户不直观**
   - 用户不理解ticks
   - 显示时间需要转换：`seconds = ticks * (tempo / 1_000_000.0) / ticks_per_beat`

3. **代码复杂**
   - 每个操作都需要考虑BPM和ticks_per_beat
   - 时间计算更复杂：`start_ticks + duration_ticks`

## 当前实现

### MIDI导入时
```python
# 从MIDI文件解析ticks，转换为秒
seconds = ticks * (tempo_microseconds / 1_000_000.0) / ticks_per_beat
note.start_time = seconds  # 存储为秒
note.duration = seconds     # 存储为秒
```

### 音频生成时
```python
# 直接使用秒，不需要转换
num_samples = int(sample_rate * note.duration)
```

### MIDI导出时
```python
# 将秒转换回ticks
ticks = int(seconds * ticks_per_beat * bpm / 60.0)
```

## 总结

**使用秒的优势：**
- ✅ 音频生成更直接
- ✅ 播放控制更简单
- ✅ 用户更易理解
- ✅ 代码更简洁

**使用ticks的优势：**
- ✅ 更符合MIDI标准
- ✅ BPM改变时不需要重新计算
- ✅ 更精确（整数）

**权衡：**
- 我们选择使用秒，因为音频生成和播放控制是核心功能
- 只在导入/导出MIDI时进行ticks ↔ 秒的转换
- 这样既保持了代码的简洁性，又符合用户的使用习惯

## 如果改用ticks

如果改用ticks，需要：
1. 修改所有时间相关的数据结构（Note、Track等）
2. 每次音频生成时都要转换：`seconds = ticks * (tempo / 1_000_000.0) / ticks_per_beat`
3. 每次播放控制时都要转换
4. 用户界面显示时需要转换
5. 代码复杂度大幅增加

**结论：** 使用秒是更合理的选择，因为我们的应用主要关注音频生成和播放，而不是MIDI文件的精确表示。

