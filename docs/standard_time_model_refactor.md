# 标准时间模型重构方案

## 目标

把项目从“普通音符以秒为主、鼓事件以拍为主、UI/播放各自转换”的历史状态，
重构为标准的 DAW / MIDI 风格时间模型：

- 音乐编辑主时间轴：`tick`
- 播放与渲染主时间轴：`second`
- 两者之间只通过统一的 `TempoMap` 转换

这次重构的核心目的不是“修一个 variable BPM bug”，而是统一整套时间语义，
让后续这些需求都变成自然能力：

- 可变 BPM 播放正确
- 分段 BPM 编辑正确
- 改 tempo map 后音符不漂移
- 网格吸附、拖拽、量化统一
- MIDI 导入导出更标准
- 后续扩展循环、片段、批处理、自动化时不会继续堆历史兼容逻辑

## 当前进度

- `Phase 1` 已落地并稳定：`core/musical_time.py`、`Project.resolution`、`tempo_events`、`Note/DrumEvent/BassEvent` 的 tick 桥接接口已经进入仓库。
- `Phase 2` 已切入第一刀：`Project.beats_to_seconds()` / `seconds_to_beats()` 已统一走标准 tick tempo map，`ui/bpm_editor_widget.py` 已改为编辑 `tempo_events`。
- `Phase 2` 第二刀已落地：`Sequencer.add_note()`、MIDI 导入、MIDI 导出和项目 tempo 替换流程都会写入或使用 tick，并在需要时把 note 的秒值从 tick 重新推导。
- `Phase 2` 第三刀已推进：属性面板中的开始时间、结束时间、时长修改，以及连续后续音符联动，已经优先按 tick 计算后再同步秒值。
- `Phase 4` 已开始切第一刀：播放前预渲染和真正启动播放已拆成两个阶段，MIDI 导入与播放预渲染都开始从 UI 主线程移出。
- `Phase 4` 第二刀已落地：播放准备阶段会直接生成 pygame-ready 的 `int16 stereo buffer`，`Sequencer.play()` 也已完全收口到 prepared playback pipeline，播放启动时主线程只保留 `Sound/Channel` 创建和真正开播。
- 编辑层也已开始收口：单音符新增、移动、属性修改和删除优先走局部 block 同步，而不是每次都整页 `refresh_ui()`，给后续继续把编辑器全面迁到 tick 驱动先清掉 UI 卡顿障碍。
- 同一轮又继续压掉一批历史 UI 回刷：批量属性修改、批量删除、拖动结束后的历史 `self.refresh()`，以及设置应用后的重复二次刷新都已经开始改为单次或局部更新。
- 当前仍保留 `bpm_segments`，但它已经降级为兼容旧 UI / 导出路径的派生视图，而不是长期主语义。

## 现状问题

当前项目的主要问题不是“有没有转换”，而是“转换和主数据混在一起”。

现状大致是：

- 普通音符主要存 `start_time` / `duration`
- 鼓事件主要存 `start_beat` / `duration_beats`
- `bpm_segments` 以秒为锚点
- UI 某些地方按固定 BPM 换算，某些地方按 tempo map 换算
- 播放端、编辑端、显示端并没有共享同一套时间模型

这会导致：

- variable BPM 项目在播放、显示、编辑之间出现偏差
- UI 刷新或 BPM 同步时可能错误回写音符时间
- 新功能每做一步都要补更多“兼容分支”

## 标准方案

### 1. 统一两个时间域

- 音乐时间域：`tick`
- 绝对时间域：`second`

规则：

- 事件位置和时值只以 `tick` 作为主数据
- `second` 只在播放、渲染、进度显示时使用
- 任何“改 BPM / 改 tempo map”的操作都不直接修改事件 tick

### 2. Project 维护唯一 TempoMap

项目层统一维护：

- `resolution`：PPQN，默认 `960`
- `tempo_events`：`[{tick, bpm}]`

语义：

- `tempo_events` 永远锚定在音乐时间轴上
- `TempoMap` 提供：
  - `ticks_to_seconds`
  - `seconds_to_ticks`
  - `beats_to_ticks`
  - `ticks_to_beats`

### 3. 所有事件统一到 tick 语义

最终状态：

- `Note` 以 `start_tick`、`duration_ticks` 为主
- `DrumEvent` 也通过 tick 访问
- `BassEvent` 同样通过 tick 访问

过渡阶段允许保留旧字段，但旧字段必须成为派生值或兼容层，而不是新的真相来源。

### 4. UI 全部按音乐时间编辑

编辑器、属性面板、拖拽、网格、吸附都按 tick 工作。

显示时：

- 网格显示拍、小节、量化分辨率
- 播放头可以显示秒
- 进度条和时间标签通过 `TempoMap` 从 tick 推导秒

## 关键设计决策

### 为什么选 tick，而不是继续把秒做主存储

因为对可变 BPM 来说：

- 秒适合播放
- tick 适合编辑

编辑位置如果存秒，那么改 tempo map 时就必须决定：

- 音符是“跟拍走”
- 还是“跟绝对时间走”

音乐软件默认应该是“跟拍走”，所以主数据必须锚定到音乐时间轴。

### 为什么仍然保留秒

不是为了做双主存储，而是为了：

- 音频渲染
- 播放状态
- 用户时间显示
- 外部音频接口

秒是派生域，不是编辑真相。

### 为什么选 PPQN = 960

原因：

- 标准 MIDI 兼容性好
- 对 1/4、1/8、1/16、三连音等常见量化足够细
- 整数精度稳定，避免浮点积累误差

## 推荐迁移策略

### Phase 1：建立标准时间模型基础设施

目标：先把“正确的底座”落下来，不一次性炸 UI。

内容：

- 新增 `core/musical_time.py`
- `Project` 新增：
  - `resolution`
  - `tempo_events`
  - tick / beat / second 互转方法
- 为 `Note` / `DrumEvent` / `BassEvent` 增加 tick 访问辅助方法
- 项目序列化开始写入 `resolution`、`tempo_events`

这一阶段完成后：

- 核心层已经具备标准时间模型
- 旧 UI 仍可继续运行
- 可以开始逐步迁移，不需要一次性推倒

### Phase 2：统一 TempoMap 编辑语义

目标：tempo 编辑不再依赖“秒锚点段”作为主语义。

内容：

- BPM 编辑器改为编辑 `tempo_events`
- `bpm_segments` 降级为兼容视图或导出辅助结构
- tempo map 的增删改全部走 tick 语义

### Phase 3：编辑器切换到 tick 驱动

目标：所有编辑行为只操作 tick。

内容：

- `GridSequenceWidget`
- `PropertyPanelWidget`
- `ProgressBarWidget`
- 音符插入、拖拽、吸附、量化
- 播放头定位与滚动

完成后：

- UI 不再按固定 BPM 改写时间
- variable BPM 下编辑与播放使用同一套模型

### Phase 4：播放与渲染完全收口

目标：播放链路不再依赖历史 `original_bpm + scaling` 分支。

内容：

- 播放前统一从 tick 映射到秒
- 音轨渲染统一使用 `TempoMap`
- 把播放启动前的缓冲打包、格式转换和缓存准备尽量前移到后台阶段
- 移除历史 fixed-BPM 兼容路径

### Phase 5：清理兼容层

目标：真正完成“彻底重构”。

内容：

- `Note.start_time / duration` 从主数据降级为派生接口
- 删除依赖旧秒语义的内部调用
- 更新导入导出、测试、文档

## 兼容策略

建议采用“读旧写新、逐步淘汰”的策略：

- 旧工程仍可读取
- 新工程开始写入 `tempo_events` 和 `resolution`
- 过渡期同时保留旧字段，避免一次性打碎 UI
- 等 UI 与播放全面迁移后，再决定是否移除旧字段

## 不建议的做法

- 不建议继续让普通音符存秒、鼓存拍
- 不建议在 UI 每个角落继续补固定 BPM 特判
- 不建议维持“双主数据”长期并存
- 不建议把“改 tempo”与“拉伸内容”混成一个操作

## 实施优先级

优先级顺序建议如下：

1. 核心时间基础设施
2. TempoMap 序列化与项目模型
3. 编辑器主控件迁移
4. 属性面板与插入逻辑迁移
5. 播放 / 渲染完全收口
6. 清理兼容层

## 当前决定

本项目后续采用标准时间模型方案：

- 以 `tick` 作为音乐编辑主时间轴
- 以 `TempoEvent` 作为项目速度真相来源
- 以 `TempoMap` 作为唯一转换入口

当前仓库里的“秒优先”设计文档应视为历史说明，不再作为未来架构方向。

## 2026-03-23 UI/Playback Follow-up

- The variable-BPM correctness work is now paired with another UI refresh reduction pass.
- Property-panel note edits in oscilloscope view no longer force a full `refresh_ui()`; they go through the lighter oscilloscope refresh path.
- Track property edits are now split into `effects` / `metadata` / `structure`, which lets rename/effect changes stay on lightweight UI sync while still preserving a full refresh for structural changes such as track-type switches.
- Oscilloscope render-track updates now keep a stable render signature so we can skip cache/color-map rebuilds when only note content changed on the same rendered tracks.
- Score-snippet apply now returns the newly created items explicitly and prefers batch local UI sync, reducing another editing path that used to fall back straight to full-window refresh.
- Theme refresh now uses incremental UI refresh by default instead of forcing a full sequence-scene rebuild on every settings apply.
- `undo/redo` now also participate in the same refresh-thinning strategy: note-centric history commands expose structured results and prefer local note/track/property-panel sync before falling back to a full UI rebuild.
- `Sequencer(initialize_audio=False)` keeps playback-plan validation usable in headless or device-less test environments, which makes it easier to keep the time-model refactor covered by regression tests.
- `GridSequenceWidget._update_or_create_block()` now skips its old duplicate overlap-scan path; stack layout is recalculated once per affected track instead of once per block and then once per track again.
- `ui/main_window_editor_ops.py` now routes note dragging, property-panel refresh requests, single-note edits, and batch edits through one shared lightweight refresh helper, which keeps oscilloscope view on the cheap repaint path and batches linked duration-following-note updates into one local block-sync pass.
- This keeps the standard time model rollout moving without reintroducing long blocking refreshes during editing.

## 2026-03-24 UI Refresh Correctness Follow-up

- Lightweight note-block sync is now allowed even while waveform view is active, so hidden sequence-scene state stays current instead of waiting for a later full rebuild.
- Local note edits that succeed on lightweight sync now also refresh note-related secondary views, which keeps waveform rendering aligned with note add/move/delete/history changes.
- Score apply no longer treats track-only refresh as sufficient after note-local sync fails; it now falls back to a full UI refresh for correctness in that edge case.
- This closes an important consistency gap without undoing the broader performance work that removed most editing-time full-window refreshes.

## 2026-03-24 Grid Hot-Path Follow-up

- `GridSequenceWidget._apply_stack_layout_for_track()` now operates on the affected track group's own blocks instead of scanning the whole project's `note_blocks` map on every local edit.
- Drum-track local sync paths now skip note-stack relayout entirely, and unchanged block positions no longer trigger redundant `setPos()` calls.
- Playhead refresh now prefers in-place line updates and reuses the existing graphics item, which further reduces local-edit repaint churn after the correctness fixes above.

## 2026-03-24 Instrumentation and Oscilloscope Edge Follow-up

- `OscilloscopeWidget.resolve_tracks_to_render()` now drops invalid manual track selections during empty/disabled render states instead of leaking stale tracks back into the waveform view.
- `MainWindowRefreshOpsMixin._refresh_oscilloscope_widget()` now skips redundant clear passes when waveform view is already empty, which trims another low-value repaint path without affecting correctness.
- Added `ui/performance_utils.py` and wired it into MIDI import, playback prepare, and note-edit refresh flows so long operations now leave lightweight timing breadcrumbs for the next round of anti-stutter work.
- MIDI import now prebuilds tempo regions once and reuses them while populating imported notes, which specifically cuts the old variable-tempo import hot path where every note rebuilt tick-to-second conversion state.
- Slow imports now also emit `[PROFILE] midi.import_stages ...` with `load / tempo / tracks` timing breakdowns, making the remaining import bottlenecks much easier to isolate from UI-side work.
- Validation for this round now reaches `138 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.

## 2026-03-24 MIDI Import UI Apply Follow-up

- Successful MIDI imports no longer risk being mis-profiled as `outcome=cancelled`; the import progress dialog is now closed with signals temporarily blocked so a programmatic `close()` does not race the cancel handler.
- Added `[PROFILE] project.import_midi_ui_apply ...` so the UI-side handoff after background import is now split into `apply_project / reset_selection / refresh_project / update_file_label / persist_directory`.
- Added `[PROFILE] ui.refresh_widgets ...` so slow full refreshes now show whether time is actually going into `set_tracks`, `sequence_refresh`, `playback_settings`, or other widget-binding stages.
- `PlaybackSettingsWidget` now supports batched `set_state(...)` updates, clears old layout items correctly during rebuilds, and no longer emits duplicate debug spam during import-time refreshes.
- This gives the next optimization round much better visibility into whether dense variable-tempo projects are still CPU-bound in MIDI parsing, blocked in sequence-scene rebuilds, or primarily paying the cost later in playback preparation.
- Validation after this follow-up now reaches `141 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.

## 2026-03-24 Grid Rebuild Follow-up

- The new UI-side profiling showed that the remaining import white-screen issue had shifted almost entirely into `GridSequenceWidget.refresh(force_full_refresh=True)`, not MIDI parsing itself.
- Full grid rebuilds are now wrapped in a bulk scene-update guard that temporarily disables viewport updates and switches the graphics scene to `NoIndex` while thousands of note blocks are recreated.
- Added `[PROFILE] grid.full_refresh ...` so the next round can distinguish `clear_scene`, `draw_grid`, `build_blocks`, and `stack_layout` costs instead of treating the whole sequence-scene rebuild as one opaque number.
- This keeps the performance work aligned with the standard time-model migration: we now know the remaining stall is in scene reconstruction, so the next likely wins are reducing per-block construction overhead and rethinking how densely populated timelines are represented.
- Validation after this follow-up now reaches `142 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.

## 2026-03-24 Tick-First Scene Math Follow-up

- The next profiling pass showed that a large part of the remaining full-refresh stall was still being spent on repeated note `second -> beat` conversions inside scene metrics and block layout.
- `GridSequenceWidget` now prefers stored `start_tick` / `duration_ticks` when converting notes into beat positions for scene sizing, block placement, and overlap stack layout; this better matches the standard time-model direction and avoids unnecessary tempo-map work during import-time scene rebuilds.
- Dense-block creation also now reuses cached waveform colors and precomputed note/drum labels, reducing per-item initialization overhead while keeping settings-driven colors intact.
- Very narrow blocks no longer paint pitch labels, which is a deliberate rendering tradeoff for high-density passages where text was effectively unreadable but still expensive to paint.
- Validation after this follow-up now reaches `143 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.

## 2026-03-24 Playback Follow-Scroll Follow-up

- With import-time rebuild cost reduced, the next user-visible hitch moved to playback follow-scrolling when the red playhead crossed the right edge of the current viewport.
- Playback-time follow scrolling now uses small horizontal scrollbar adjustments near the viewport edge instead of a late `centerOn()` jump after the playhead has already left the visible area.
- This is primarily a UX/performance refinement rather than a time-model change, but it matters because dense variable-tempo projects keep many visible blocks alive, and a sudden full-view recenter is noticeably more expensive than smaller forward nudges.
- Added lightweight profiling breadcrumbs for slow follow-scroll updates and enabled a few additional `QGraphicsView` optimization flags to reduce the repaint burden during live playback navigation.
- Validation after this follow-up now reaches `144 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.

## 2026-03-24 Playback Freeze Hotfix

- The latest playback freeze was not an audio-thread failure. Dense playback repaints were still reaching `SequenceBlock.boundingRect()`, and that path could fall back to `project.seconds_to_beats()` for note geometry.
- On variable-tempo projects that meant the UI thread could keep rebuilding tempo regions during paint-time geometry queries, which explains why audio continued but the scene looked frozen or updated only occasionally.
- `SequenceBlock` now caches tick-first geometry (`start/duration beats` plus `QRectF`) and reuses it during `boundingRect()` / paint calls instead of recalculating from second-based note timing on every repaint.
- `Project` now also caches its built tempo regions until the tempo map changes, so repeated timeline conversions share one prebuilt region set instead of rebuilding the same structure over and over.
- Validation after this hotfix now reaches `146 passed`, with `python -m compileall -q app_info.py main.py core ui tests` also passing.
