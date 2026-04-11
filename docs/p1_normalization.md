# P0-P3 重构与规范化路线图

> 目标：在不打断现有功能的前提下，逐步把项目整理成更稳定、更易维护、也更方便继续迭代的工程。
> 约定：每次执行规范化或重构改动时，同时更新本路线图与根目录 `CHANGELOG.md`。

## 当前状态

- `P0`：已完成，主要是清理废弃功能、统一版本与文档落点。
- `P1`：基本完成，主窗口已从超大单文件拆成薄入口 + 多个 mixin，剩余工作以收尾和规范化为主。
- `P2`：进行中，已经开始把 UI 与核心服务边界拆开，并切入标准时间模型的第二阶段迁移。
- `P3`：长期规划，重点是发布流程、测试覆盖、性能与长期维护能力。

## P0 紧急清理

- [x] 移除已废弃的 WiFi 播放链路与相关失效代码。
- [x] 清理可删除的测试/演示脚本，降低仓库噪音。
- [x] 将散落文档整理到 `docs/`，统一文档路径。
- [x] 建立根目录 `CHANGELOG.md`。
- [x] 将应用版本统一收敛到 `app_info.py`，作为单一来源。
- [x] 明确版本命名遵循 `SemVer`。

## P1 工程规范化

### 已完成

- [x] 补齐 `pyproject.toml`、`requirements-dev.txt`、CI 与基础测试框架。
- [x] 规范 `main.py` 启动入口，使异常输出和基础 lint 校验更稳定。
- [x] 建立本路线图，用于持续记录已完成项、下一步和中长期建议。
- [x] 将 `StyleParamsWidget` 从 `ui/main_window.py` 拆分到 `ui/style_params_widget.py`。
- [x] 将错误弹窗辅助逻辑拆分到 `ui/error_utils.py`。
- [x] 将添加音轨、Seed 生成、示波器设置、音轨选择等对话框逻辑迁移到 `ui/main_window_dialogs.py`。
- [x] 移除 `ui/main_window.py` 顶部的 `sys.path` 注入，减少顶层副作用。
- [x] 抽离项目 JSON 读写到 `core/project_io.py`。
- [x] 抽离文件类型识别和导出路径解析到 `ui/main_window_file_ops.py`。
- [x] 将新建、打开、保存、导入、导出流程迁移到 `ui/main_window_project_ops.py`。
- [x] 将播放控制、音量/BPM 同步和播放状态更新迁移到 `ui/main_window_playback_ops.py`。
- [x] 将乐谱片段创建、应用、试听、删除流程迁移到 `ui/main_window_score_ops.py`。
- [x] 将视图切换、示波器音轨筛选和视图相关逻辑迁移到 `ui/main_window_view_ops.py`。
- [x] 将编辑联动、属性同步、批量编辑、删除/清空音轨等逻辑迁移到 `ui/main_window_editor_ops.py`。
- [x] 将主旋律/低音/打击乐插入与“删除最后一个音符”逻辑迁移到 `ui/main_window_note_entry_ops.py`。
- [x] 将关于、快捷键、设置入口、面板切换、撤销/重做、添加音轨等应用级动作迁移到 `ui/main_window_app_ops.py`。
- [x] 将 Seed 生成入口、请求构建、结果应用迁移到 `ui/main_window_seed_ops.py`，并补充 `core/seed_generation_service.py`。
- [x] 将主题、显示设置、Dock 宽度同步迁移到 `ui/main_window_theme_ops.py`。
- [x] 将信号连接、播放头同步、整页刷新与示波器刷新计划迁移到 `ui/main_window_refresh_ops.py`。
- [x] 将窗口壳层、布局装配、菜单/状态栏/关闭流程迁移到 `ui/main_window_shell_ops.py`。
- [x] 清理历史 lint 问题，完成全量 `python -m ruff check .` 收敛。
- [x] 为新提炼的 helper 和服务层补充测试，当前全量 `pytest` 为 `111 passed`。

### `ui/main_window.py` 拆分现状

- 粗略行数对比：
  以仓库旧版为参考，`ui/main_window.py` 约为 `3920` 行；完成本轮壳层拆分后当前为 `66` 行。

#### 已移走的职责

- `ui/error_utils.py`：错误弹窗与异常输出辅助逻辑。
- `ui/style_params_widget.py`：Seed 风格参数面板组件。
- `ui/main_window_dialogs.py`：独立对话框逻辑。
- `core/project_io.py`：项目 JSON 读写。
- `ui/main_window_file_ops.py`：文件类型识别、导出路径解析等纯文件逻辑。
- `ui/main_window_project_ops.py`：项目文件打开、保存、导入、导出流程。
- `ui/main_window_playback_ops.py`：播放控制、BPM/音量同步、播放状态更新。
- `ui/main_window_score_ops.py`：乐谱片段工作流与相关 helper。
- `ui/main_window_view_ops.py`：视图切换与示波器筛选逻辑。
- `ui/main_window_editor_ops.py`：编辑联动和批量编辑逻辑。
- `ui/main_window_note_entry_ops.py`：音符插入与删除入口。
- `ui/main_window_app_ops.py`：应用级动作与入口。
- `ui/main_window_seed_ops.py`：Seed 生成入口与结果应用。
- `ui/main_window_theme_ops.py`：主题、显示设置与 Dock 宽度同步。
- `ui/main_window_refresh_ops.py`：刷新、信号同步与播放头联动。
- `ui/main_window_shell_ops.py`：窗口壳层、布局、菜单、状态栏、关闭生命周期。

#### 目前仍留在 `ui/main_window.py` 的职责

- `__init__`：作为主窗口的组合入口，负责装配 mixin、基础状态和初始化顺序。
- `init_default_tracks`：保留为兼容钩子，当前是空实现。

### P1 剩余收尾项

- [ ] 评估 `init_default_tracks` 是否仍需要保留；如果不再使用，可以在兼容确认后移除。
- [ ] 持续同步 `README`、文档索引和示例脚本路径，避免结构变化后文档滞后。

## P2 模块边界重构

- [x] 将项目文件打开、保存、导入、导出流程从主窗口中下沉。
- [x] 为 Seed 生成功能建立更清晰的 UI 层与服务层边界。
- [x] 为项目读取、MIDI 导入、音频导出补充 `core/project_service.py`。
- [x] 将 `Sequencer.play()` 收口到 prepared playback pipeline，并把 `float -> int16/stereo` 播放缓冲打包前移到后台准备阶段，继续削减点击播放时的主线程工作量。
- [x] 为单音符新增、移动、属性修改和删除补上局部 UI 同步路径，优先更新单块与场景边界，避免这些高频编辑动作反复触发整页 `refresh_ui()`。
- [x] 为批量属性修改、批量删除、音轨启用切换和设置应用后的收尾流程继续减重，清掉一批历史遗留的整页刷新与重复重绘。
- [x] 完成全量 `ruff check .` 收敛，清理 import 排序、未使用导入、未使用变量、重复定义、无占位 f-string 和部分过宽异常。
- [x] 抽离 `core/seed_style_catalog.py`，承接 `SeedMusicStyle`、`StyleParams`、风格默认参数、UI 元数据、风格变体与运行时覆盖接口，减少 `core/seed_music_generator.py` 的目录型职责堆积。
- [x] 抽离 `core/seed_style_configs.py`，承接 `MusicStyleConfig`、各风格配置类和 `get_style_config()` 工厂，让生成器主文件回到“结构组装 + 音符生成”主责。
- [x] 抽离 `core/seed_structure_catalog.py` 与 `core/seed_generation_utils.py`，继续下沉结构预设和通用 Seed helper，缩小 `core/seed_music_generator.py` 的非生成职责。
- [x] 抽离 `core/seed_generation_planner.py`，统一乐句布局、角色判定、变体行为和 `quiet_bars` 规划，消除主旋律/和声/鼓点对乐句坐标理解不一致的问题。
- [x] 抽离 `core/seed_track_builders.py`，集中构建低音、和声与鼓点轨道，并由 `core/seed_music_generator.py` 保留兼容导出与装配入口。
- [ ] 继续梳理 `core/` 内模型、生成器、IO、播放控制的边界，减少 UI 对核心实现细节的直接依赖。
- [ ] 评估 `ui/main_window_shell_ops.py` 是否还需要继续下沉成更细的 builder/helper；如果壳层规模保持稳定，可以先不继续拆。

## P3 长期维护与产品化

- [ ] 建立更完整的回归测试策略，包括更多核心逻辑测试和最小集成验证。
- [ ] 规范发布流程，串联版本号、changelog、打包脚本和发布说明。
- [ ] 为大工程、长时播放与复杂导入场景建立性能与稳定性检查项。
- [ ] 评估是否需要更清晰的设备端边界、插件入口或脚本接口。
- [ ] 持续降低历史 lint 噪音，为更严格的工程规范做准备。

## 本轮更新

- 新增 `core/seed_generation_planner.py`，集中放置 `PhrasePlan`、`VariantBehavior`、`build_phrase_plan()`、`build_variant_behavior()` 等生成规划 helper。
- 将 `core/seed_music_generator.py` 中的乐句分析、角色判定、变体开关和 `quiet_bars` 规划迁入 planner 模块，并保留兼容导出。
- 新增 `tests/test_seed_generation_planner.py`，覆盖乐句边界、角色映射、变体行为和旧模块兼容导出；当前测试集扩展为 `81` 项。
- 新增 `core/seed_structure_catalog.py`，集中管理结构预设和小节数到乐句结构的智能映射。
- 新增 `core/seed_generation_utils.py`，集中管理 Seed 随机数构造与权重选择等通用 helper。
- 将 `core/seed_music_generator.py` 中的结构预设和 Seed helper 继续迁出，并保留兼容导出，避免现有调用方断裂。
- 新增 `tests/test_seed_structure_catalog.py` 与 `tests/test_seed_generation_utils.py`，覆盖结构适配、随机确定性和旧模块兼容导出。
- 新增 `core/seed_style_configs.py`，集中放置 `MusicStyleConfig` 基类、各风格实现和工厂函数。
- 将 `core/seed_music_generator.py` 中的风格配置类体系整体迁出，并保留兼容别名，避免现有导入路径被重构打断。
- 新增 `tests/test_seed_style_configs.py`，覆盖风格工厂映射、运行时覆盖透传和旧模块兼容导出。
- 新增 `core/seed_style_catalog.py`，集中管理 Seed 风格枚举、默认参数、元数据、变体目录和运行时覆盖。
- 将 `ui/main_window_dialogs.py`、`ui/style_params_widget.py`、`core/seed_generation_service.py` 与相关测试切换到新的风格 catalog 模块。
- 将 `core/seed_music_generator.py` 进一步收缩到 `795` 行；新拆出的 `core/seed_track_builders.py` 当前为 `342` 行，集中承接低音、和声与鼓点轨道构建逻辑。
- 新增 `tests/test_seed_track_builders.py`，覆盖 builder 直调、舞曲和声延迟进入、鼓点音量与生成器兼容导出；当前测试集扩展为 `86` 项。
- 新增 `tests/test_seed_style_catalog.py`，补充风格 catalog 的完整性、运行时覆盖与默认变体回退测试。
- 补齐 `StyleParamsWidget` 中 `WORKSHOP` 风格的显示名称，避免参数面板回退到枚举名。
- 新增 `ui/main_window_shell_ops.py`，承接窗口壳层、布局装配、菜单、状态栏和关闭流程。
- 新增 `tests/test_main_window_shell_ops.py`，覆盖窗口几何和 Dock 宽度 helper。
- 将 `ui/main_window.py` 进一步收缩到 `66` 行，仅保留组合入口和兼容钩子。
- 修复 `self.current_midi_file_path` 被历史注释串吞掉的问题，恢复为正式属性初始化。
- 新增 `ui/background_tasks.py`，把 MIDI 导入和播放前音频预渲染下沉到 `QThread` worker，先消除导入与开始播放时的主线程长时间阻塞。
- 在 `core/sequencer.py` 中拆出 `prepare_playback_plan()`、`prepare_playback()` 与 `start_prepared_playback()`，把“音频渲染”和“真正启动播放”分成两段，给后续继续做流式播放或缓存留下接口。
- 将 `core/audio_engine.py` 中 `float -> int16/stereo -> pygame Sound` 的前半段整理为可复用 helper，并把播放计划里的缓冲从浮点单声道前移成 pygame-ready 的立体声 `int16` 缓冲，继续减轻点击播放时的主线程启动成本。
- 将 `core/sequencer.py` 的 `play()` 正式收口到 prepared playback pipeline，移除旧的调试型同步播放实现，避免核心 API 再分叉。
- 调整 `ui/main_window_refresh_ops.py` 与 `ui/grid_sequence_widget.py` 的刷新边界，避免 `refresh_ui()` 期间由 `set_tracks()`、`set_bpm()` 触发的重复序列视图刷新，降低编辑时卡顿。
- 为 `ui/grid_sequence_widget.py` 增加 `sync_note_block()`、`remove_note_block()` 和局部场景尺寸同步 helper，并让 `ui/main_window_editor_ops.py` / `ui/main_window_note_entry_ops.py` 在单音符移动、属性修改、常规插入、删除最后一个音符等高频路径优先走局部刷新。
- 新增 `tests/test_main_window_refresh_ops.py` 与 `tests/test_sequencer_playback_plan.py`，覆盖单次刷新约束和播放预渲染计划生成。
- 扩充 `tests/test_main_window_refresh_ops.py` 与 `tests/test_sequencer_playback_plan.py`，补充局部音符刷新 helper 与 `Sequencer.play()` 收口到 prepared playback pipeline 的回归断言；当前测试集扩展为 `108` 项。
- 为 `ui/grid_sequence_widget.py` 继续增加 `sync_note_blocks()`、`remove_note_blocks()`，并移除音符拖动完成后历史遗留的 `QTimer(... self.refresh)` 整页回刷，让批量编辑、批量删除和拖动后收尾也能留在局部刷新路径里。
- 将 `ui/main_window_app_ops.py` 的设置对话框收尾改成只重绑快捷键，不再在 `SettingsDialog.apply_settings()` 已经触发完整刷新之后再额外重绘一遍。
- 将音轨启用切换从“延迟整页 refresh”收口为按需刷新示波器，避免勾选启用状态时也触发完整序列区重建。
- 扩充 `tests/test_main_window_refresh_ops.py` 与 `tests/test_main_window_app_ops.py`，补充批量局部刷新和设置收尾的回归断言；当前测试集扩展为 `111` 项。
- 启动全量 lint 收敛，先清理一批低风险叶子组件：
  `ui/playback_settings_widget.py`
  `ui/progress_bar_widget.py`
  `ui/timeline_widget.py`
  `ui/toggle_switch_widget.py`
  `ui/sequence_widget.py`
  `ui/track_list_widget.py`
  `ui/score_library_widget.py`
  `ui/track_type_dialog.py`
  `ui/settings_manager.py`
- 继续清理核心层、设备脚本和历史 UI 大文件中的未使用变量、重复定义和过宽异常，修复 `core/midi_io.py` 的 ASCII 轨道名回退映射。
- 当前 `python -m ruff check .`、`python -m pytest`（`104 passed`）与 `python -m compileall -q app_info.py main.py core ui tests` 已全部通过。
- 验证通过：
  `python -m ruff check ui/main_window.py ui/main_window_shell_ops.py tests/test_main_window_shell_ops.py`
  `python -m pytest`
  `python -m compileall -q app_info.py main.py core ui tests`
- 本轮验证：
  `python -m pytest`（`111 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
  `python -m ruff check .` 在当前 Windows 环境下被系统策略拦截（`WinError 4551`），需在允许执行 `ruff` 的环境中补做复验。

## Variable BPM 播放正确性修复

- [x] 新增 `core/tempo_map.py`，统一管理 beat 和 second 之间的 tempo map 换算。
- [x] 让 `Project.get_total_duration()`、`Sequencer.beats_to_seconds()` 和 `Sequencer.seconds_to_beats()` 共用同一套时间语义。
- [x] 修复变速 BPM 工程中的鼓轨播放/渲染时间计算，不再把 tempo map 工程错误地套用单 BPM 的 `bpm_ratio`。
- [x] 修复单 BPM 缩放场景下鼓轨从中间位置开始播放时的时间对齐问题。
- [x] 补充 tempo map、鼓轨渲染与总时长回归测试：
  `tests/test_tempo_map.py`
  `tests/test_audio_engine_tempo.py`
  `tests/test_models.py`
- [x] 当前验证结果：
  `python -m ruff check .`
  `python -m pytest`（`91 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] `grid/property panel` 等编辑层仍有若干固定 BPM 换算路径，后续需要继续统一到 tempo map 语义。

## 标准时间模型重构（新方案）

- [x] 确认后续架构从“秒优先”转向“标准音乐时间模型”。
- [x] 新增 [standard_time_model_refactor.md](/f:/Code/8bit/docs/standard_time_model_refactor.md)，明确以 `tick + tempo_events + TempoMap` 为核心的最终方案。
- [x] 新增 `core/musical_time.py`，引入标准 `TempoEvent`、PPQN、tick/beat/second 互转基础设施。
- [x] 为 `Project` 增加 `resolution`、`tempo_events` 以及标准 tick 时间辅助方法。
- [x] 为 `Note` / `DrumEvent` / `BassEvent` 增加 tick 访问或同步辅助接口，作为第一阶段迁移桥接层。
- [x] 将 `Project.beats_to_seconds()` / `Project.seconds_to_beats()` 收口到标准 tick tempo map 计算路径。
- [x] 将 BPM 编辑器从 `bpm_segments(start_time in seconds)` 迁移到 `tempo_events(tick anchored)`。
- [x] 保留 `bpm_segments` 作为 `tempo_events` 的兼容派生视图，先不让旧路径立即断裂。
- [x] 让 `Sequencer.add_note()`、项目 tempo 替换流程和完整项目序列化补齐 note 的 tick 桥接同步。
- [x] 让 MIDI 导入直接保留 `ticks_per_beat` 与 tempo events，导出直接基于项目标准 tick 时间模型写回 MIDI。
- [x] 将属性面板中的开始时间、结束时间、时长编辑和连续后续音符位移迁移到 tick-aware 计算路径。
- [ ] 将 `Note` 正式切换为 `start_tick` / `duration_ticks` 主存储，`start_time` / `duration` 降级为派生或兼容接口。
- [ ] 将序列编辑器、属性面板、进度条、音符插入逻辑全面迁移到 tick 驱动。
- [ ] 将播放 / 渲染链路彻底收口到标准 TempoMap，移除历史 `original_bpm + scaling` 兼容路径。
- [x] 当前验证结果：
  `python -m ruff check .`
  `python -m pytest`（`104 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`

## 2026-03-23 Performance Follow-up

### This Round Done

- [x] `on_property_update_requested()` no longer defaults to full `refresh_ui()`; it now prefers note-local sync and only falls back when needed.
- [x] `on_property_changed()` now refreshes oscilloscope view through the lightweight path instead of forcing a full UI rebuild when we are already in waveform view.
- [x] `track_property_changed` is now classified as `effects` / `metadata` / `structure`, so only structural track changes still trigger a full refresh.
- [x] Added lightweight track presentation sync:
  `GridSequenceWidget.sync_track_presentation()`
  `MainWindowRefreshOpsMixin._sync_track_ui()`
- [x] `OscilloscopeWidget.set_tracks()` now keeps a render signature and avoids cache/color-map rebuilds when the rendered track set is unchanged, while still repainting to pick up note content edits.
- [x] Removed redundant `oscilloscope_widget.update()` calls in `ui/main_window_view_ops.py`.
- [x] Fixed the historical oscilloscope refresh-plan shortcut so manual render-track selection still repaints correctly after note edits.
- [x] Added/updated regression coverage and pushed the test suite from `111` to `117` passing cases.
- [x] `score/snippet` apply now extracts added items explicitly and prefers batch local sync instead of defaulting straight to `refresh_ui()`.
- [x] `refresh_theme_from_settings()` no longer forces `force_full_refresh=True`; theme changes now go through the lighter refresh path first.
- [x] `undo/redo` no longer only return description strings; command history now exposes structured results so the UI can route common note-history operations through lightweight refresh paths.
- [x] Note add/delete/move/modify and batch note-history commands now prefer `_remove_note_blocks_ui()` / `_sync_note_blocks_ui()` and targeted property-panel updates before falling back to full refresh.
- [x] `Sequencer` now supports `initialize_audio=False`, which keeps playback-plan tests stable on headless or audio-device-less Windows environments.
- [x] `GridSequenceWidget._update_or_create_block()` no longer recomputes overlap stacking before `_apply_stack_layout_for_track()` recomputes the same track again; local/full block sync now pay that stack-layout cost only once per affected track.
- [x] Unified note-edit refresh routing in `ui/main_window_editor_ops.py`: note dragging, single-note property edits, property-panel refresh requests, and batch note edits now share `_refresh_after_note_updates()`.
- [x] Property-panel batch edits and note dragging now avoid full `refresh_ui()` in waveform view while keeping both the hidden sequence scene and oscilloscope view in sync.
- [x] Linked duration edits now batch the edited note and adjusted following notes into one `_sync_note_blocks_ui()` pass instead of syncing each note separately.
- [x] Fixed the remaining oscilloscope-view note-refresh correctness gap: note entry, note delete, undo/redo, and score apply now keep the hidden sequence scene synchronized instead of only repainting the visible waveform view.
- [x] Score apply now treats failed note-local sync as a deliberate correctness fallback to full refresh, instead of accepting a track-only refresh that could leave sequence blocks stale.
- [x] `GridSequenceWidget` local-edit hot paths now only walk the affected track group's blocks for stack layout, skip note-stack work on drum tracks, and avoid redundant `setPos()` churn on unchanged block geometry.
- [x] Playhead refresh now reuses the existing graphics item during local edits instead of repeatedly removing and recreating it.
- [x] Oscilloscope empty-track / invalid-selection edge paths now clear safely without reviving stale manual render targets, and already-empty waveform view skips redundant clear passes.
- [x] Added lightweight profiling instrumentation in `ui/performance_utils.py`; MIDI import, playback prepare, and note-edit refresh flows now record timing history and emit `[PROFILE]` console lines for slow paths.
- [x] Variable-tempo MIDI import now prebuilds and reuses tempo regions during note creation, avoiding the previous per-note rebuild of tick-to-second conversion state on dense imports.
- [x] MIDI import now also prints `[PROFILE] midi.import_stages ...` so we can separate file load, tempo extraction, and track parsing costs when chasing remaining stalls.
- [x] Full validation now reaches `138 passed`.

### 12-Item Pool Status

- [x] Agreed optimization pool completed: `12/12`.
- [ ] Score apply / snippet flows still keep a conservative full-refresh fallback when note-local sync genuinely cannot run; this is now a deliberate safety choice rather than an accidental heavyweight path.
- [ ] Track rename and other metadata changes are lighter than before, but more track-only edits can still avoid touching unrelated widgets.

### Validation

- `python -m pytest` -> `138 passed`
- `python -m compileall -q app_info.py main.py core ui tests` -> passed
- `python -m ruff check .` is still blocked in the current Windows environment by system policy (`WinError 4551`), so lint re-verification still needs an allowed environment.

## 2026-03-24 Import/UI Profiling Follow-up

- [x] 修复 `ui/main_window_project_ops.py` 中成功导入却被错误记成 `project.import_midi outcome=cancelled` 的 profiling 误报；现在程序化关闭 `QProgressDialog` 时会临时屏蔽 `canceled` 信号。
- [x] 为导入完成后的主线程接入补充分段计时，慢路径现在会输出 `[PROFILE] project.import_midi_ui_apply ...`，拆出 `apply_project / reset_selection / refresh_project / update_file_label / persist_directory`。
- [x] 为 `ui/main_window_refresh_ops.py` 中的整页刷新补充子阶段 profiling，慢刷新现在会进一步拆出 `project_binding / set_tracks / sequence_refresh / playback_settings / bpm_editor`。
- [x] 为 `ui/playback_settings_widget.py` 增加 `set_state()` 批量入口，避免同一轮刷新里先 `set_tracks()` 又 `set_volume_ratios()` 导致的双重重建。
- [x] 清理播放设置面板的历史布局堆积问题；`refresh_tracks()` 现在会移除旧 widget 和旧 stretch，避免重复刷新后 layout item 持续累加。
- [x] 去除播放设置面板的历史调试输出，并修正其“刷新后默认把所有轨道重新视为启用”的状态回写问题。
- [x] 收尾 `core/midi_io.py` 中待清理的轨道名提取重复代码，统一改为复用 `_extract_track_name()`。
- [x] 新增 `tests/test_main_window_project_ops.py`，并扩充 `tests/test_main_window_refresh_ops.py`，覆盖进度框关闭和 batched playback settings 刷新路径。
- [x] 本轮验证：
  `python -m pytest`（`141 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] 下一步根据新日志判断：导入后的白屏/卡顿究竟主要在 `sequence_widget.refresh()`、播放设置面板，还是后续的 `playback.prepare`。

## 2026-03-24 Grid Full Refresh Bottleneck Follow-up

- [x] 根据新 profiling 确认主瓶颈已从 MIDI 解析切换到 `GridSequenceWidget.refresh(force_full_refresh=True)`，其中 `sequence_refresh_ms` 在大 MIDI 场景下可达约 `33s+`。
- [x] 为 `ui/grid_sequence_widget.py` 新增 `_bulk_scene_update()`，全量刷新时会临时关闭 `QGraphicsView` 更新并把 `QGraphicsScene` 切到 `NoIndex`，避免重建几万个 block 时反复触发昂贵的视图更新与索引维护。
- [x] 移除 `_full_refresh()` 中历史遗留的 `QApplication.processEvents()` 强制事件处理点，避免在场景清空后立刻插入一次中途 UI 刷新。
- [x] 为 `grid full refresh` 加入更细分的终端 profiling；下一次导入大 MIDI 时会额外输出 `[PROFILE] grid.full_refresh ...`，拆出：
  `checkbox_cleanup / clear_scene / calculate_dimensions / draw_grid / draw_tracks_total / build_blocks / stack_layout / update_track_list / draw_playhead`
- [x] 为 `tests/test_grid_sequence_widget.py` 增加回归测试，确保批量场景更新期间的 view/scene 状态会在结束后正确恢复。
- [x] 本轮验证：
  `python -m pytest`（`142 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] 下一步根据新的 `grid.full_refresh` 日志判断，大头究竟是在 `build_blocks_ms` 还是 `stack_layout_ms`；如果仍然很高，再继续下刀到 `SequenceBlock` 构建成本与 scene item 数量控制。

## 2026-03-24 Tick-First Grid Metrics and Dense-Note Rendering Follow-up

- [x] 根据新的 `grid.full_refresh` 日志确认，`calculate_dimensions_ms` 仍然偏高，说明序列视图在大 MIDI 场景下还有大量 note -> beat 转换开销。
- [x] 将 `GridSequenceWidget._item_start_beats()` / `_item_duration_beats()` 改为优先读取 `start_tick` / `duration_ticks`，只有缺失 tick 时才回退到 `seconds_to_beats()`，减少大规模 tempo map 转换。
- [x] 为 `GridSequenceWidget` 新增 `_ticks_to_beats_fast()`，直接使用项目 `resolution` 做轻量换算，避免在视图热路径里反复绕回更重的项目时间辅助链路。
- [x] 为 `SequenceBlock` 引入波形颜色缓存、模块级音名/鼓标签表，避免在创建每一个 block 时都重复取设置、构造颜色表和生成标签文本。
- [x] 对非常窄的 block 跳过音名文字绘制；对于极密集、极短音符片段，优先保证可交互性和刷新流畅度，而不是绘制不可读的 `A1/C#4` 文本。
- [x] 扩充 `tests/test_grid_sequence_widget.py`，新增 tick-first beat conversion 回归测试。
- [x] 本轮验证：
  `python -m pytest`（`143 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] 下一步继续根据新日志判断：若 `build_blocks_ms` 仍高，考虑继续减少 `SequenceBlock` 构建对象数或进一步简化 block 信号/初始化成本；若 `stack_layout_ms` 仍高，则继续针对重叠分组和聚类排序做裁剪。

## 2026-03-24 Playback Follow-Scroll Stutter Follow-up

- [x] 根据用户反馈确认新的主要卡点已转到“播放头到达右侧边缘时的自动横向滚屏”，不再是导入阶段白屏。
- [x] 将 `GridSequenceWidget.set_playhead_time()` 中播放期的自动滚动逻辑，从“超出视口后 `centerOn()` 整屏跳转”改为“小步、边缘触发”的水平跟随滚动，尽量把单次跨屏尖峰成本摊平。
- [x] 新增 `_get_visible_scene_x_range()` / `_follow_playhead_during_playback()`，播放头接近右侧边缘时会提前推动水平滚动条，而不是等完全出界后再一次性重定位。
- [x] 在 `QGraphicsView` 上补充 `MinimalViewportUpdate`、`DontSavePainterState`、`DontAdjustForAntialiasing`，继续降低播放期滚动重绘的额外负担。
- [x] 为播放期自动滚动增加可选 profiling breadcrumb：若某次跟随滚动仍明显偏慢，会打印 `[PROFILE] grid.playhead_autoscroll ...`。
- [x] 扩充 `tests/test_grid_sequence_widget.py`，新增播放期 auto-scroll 走水平滚动条而非 `centerOn()` 的回归测试。
- [x] 本轮验证：
  `python -m pytest`（`144 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] 下一步观察真实播放日志与主观体感；如果仍有明显顿挫，优先继续排查播放头推进频率、可见区域内 item 数量和 `playback.prepare` 的二次触发场景。

## 2026-03-24 Playback Freeze Hotfix

- [x] 重新定位“播放时界面几乎卡死”的根因，确认问题在 `SequenceBlock.boundingRect()` 的渲染热路径，而不是音频线程本身。
- [x] 将 `SequenceBlock` 的几何计算改为缓存式 tick-first 路径，避免在重绘时反复从 `second -> beat` 回查 tempo map。
- [x] 为 `Project` 增加 tempo region 缓存，重复的 `seconds_to_ticks()` / `ticks_to_seconds()` / `seconds_to_beats()` 调用现在会复用同一份 tempo 区间构建结果。
- [x] 补充 `tests/test_models.py` 与 `tests/test_grid_sequence_widget.py` 回归测试，覆盖 tempo 缓存与 block 几何缓存。
- [x] 本轮验证：
  `python -m pytest`（`146 passed`）
  `python -m compileall -q app_info.py main.py core ui tests`
- [ ] 下一步请重新用高音符密度 MIDI 实测；如果界面不再“半天才动一下”但仍有顿挫，下一轮应转去做可见区域重绘和播放期节流，而不是继续纠结 tempo 转换。
## 2026-03-24 Playback Display Mode Setting

- [x] Added a playback display mode entry in the settings dialog for `moving_playhead` and `fixed_playhead`.
- [x] Persisted the playback display mode through `ui/settings_manager.py` so the choice survives app restarts.
- [x] Updated `ui/grid_sequence_widget.py` so playback can keep the playhead visually fixed while the notes scroll left.
- [x] Added regression coverage in `tests/test_grid_sequence_widget.py` for fixed-playhead scrolling and `set_playhead_time()` routing.
- [x] Validation: `python -m pytest` (`148 passed`) and `python -m compileall -q app_info.py main.py core ui tests`.

## 2026-03-25 Track Layout Follow-up

- [x] Corrected the property-panel type semantics: the editable combo now only exposes the real structure types (`音符音轨` / `打击乐音轨`) instead of mixing those with musical roles such as “主旋律/低音”.
- [x] Added a safety guard so non-empty tracks cannot be switched directly between note-track and drum-track modes; this avoids silently hiding existing notes or drum events behind a changed `track_type`.
- [x] Left track names and right note lanes now use the same vertical layout model, including partial-scroll offset handling.
- [x] Tightened residual left/right lane alignment again: vertical visibility now comes from the right view scrollbar, visible left-side track items update in place while scrolling, and the track-name widget centers text against the full lane height instead of a shortened label area.
- [x] The center editor area supports dragging the sequence region taller through the vertical `QSplitter`.
- [x] Per-track height resize is wired through `Track.display_height`, persisted in project data, and covered by tests.
- [x] Zoom/block refresh paths now respect custom track heights instead of falling back to the old fixed-lane assumptions.
- [x] Fixed the regression where rebuilt left-side track widgets could escape as stray top-level windows during MIDI import / scrolling; temporary widgets are now hidden and deleted correctly.
- [x] Relaxed the top editor pane's splitter shrink policy so the lower playback/track area can actually be dragged taller.
- [x] Lowered the effective minimum height of the sequence / oscilloscope panes so the overall track area can be collapsed further.
- [x] Changed single-track height drag to update visible list items in place during the drag, avoiding the old rebuild-on-every-move behavior that made the handle feel stuck.
- [x] Added compact lane support: tracks can now shrink further and note blocks scale down with lane height.
- [x] Removed the remaining horizontal whole-song preview limit by replacing the old fixed scene-width minimums and hard-coded zoom floor with content-aware helpers that can shrink to the viewport and adapt the minimum zoom to the current song length.
- [x] Fixed the remaining lane background issue where horizontal track lines still started after the deleted legacy left gutter; track lines now start at the same `x=0` origin as notes and playhead.
- [x] Validation for this follow-up: `python -m pytest` -> `166 passed`, `python -m compileall -q app_info.py main.py core ui tests` -> passed.
- [ ] Follow-up candidate: decide whether we need an even more compact lane mode for low-priority tracks.

## 2026-03-25 Track Semantics Normalization

- [x] 在 `core/models.py` 中新增显式 `TrackRole`，把“音轨结构”与“音轨角色”拆开：
  `TrackType` 只负责 `note / drum`
  `Track.role` 只负责 `melody / bass / harmony / effect`
- [x] 为旧项目补齐兼容加载逻辑：未保存 `role` 的旧数据会在读取时基于历史音轨名做一次性推断，而鼓轨会统一规范为 `role=None`。
- [x] 在 `ui/property_panel_widget.py` 中新增独立的“音轨角色”编辑器，打击乐音轨不再显示该项，避免再把“主旋律/低音”塞进 `track_type`。
- [x] 在 `ui/grid_sequence_widget.py` 中移除基于 `track.name` 的主旋律/低音推断，改为直接读取 `track.track_type + track.role`。
- [x] 在 `ui/main_window_note_entry_ops.py` 中补齐 role-aware 选轨逻辑：低音模式会优先命中 `role=bass` 的音符轨；自动新建轨时也会带上对应角色和默认命名。
- [x] 补充回归测试覆盖：
  `tests/test_models.py`
  `tests/test_property_panel_timing.py`
  `tests/test_main_window_note_entry_ops.py`
  `tests/test_grid_sequence_widget.py`
  `tests/test_project_io.py`
- [x] 本轮验证：
  `python -m pytest`（`172 passed`）
  `python -m compileall -q core ui tests main.py`
- [x] 后续收尾 1：`ui/unified_editor_widget.py` 内部已改为 `current_entry_role`，并保留 `current_track_type` 兼容别名，减少“结构类型”和“录入角色模式”之间的歧义。
- [x] 后续收尾 2：`prompt_new_track()` 已支持在新建音符轨时直接选择初始角色，并通过 `Sequencer.add_track(role=...)` 正式写入项目模型。

## 2026-03-26 Track Role Follow-up Closure

- [x] 将 `ui/unified_editor_widget.py` 中历史上的 `current_track_type = melody/bass` 收口为更准确的 `current_entry_role` 语义。
- [x] 保留 `current_track_type` / `on_track_type_selected()` 兼容别名，避免这次收尾顺手打断仍依赖旧命名的小路径。
- [x] 将“添加音轨”对话框升级为带 `NewTrackSelection` 返回对象的显式结构，避免继续用 tuple 隐式塞更多字段。
- [x] 在 `ui/main_window_dialogs.py` 中新增音符轨初始角色选择，并根据结构类型动态显示/隐藏角色控件。
- [x] 在 `core/sequencer.py` 中为 `add_track()` 增加 `role` 参数；鼓轨创建时会自动清空 role，避免结构/角色混用。
- [x] 在 `ui/main_window_app_ops.py` 中把手动创建音轨的初始角色正式写回项目模型。
- [x] 新增/扩充回归测试：
  `tests/test_main_window_app_ops.py`
  `tests/test_main_window_dialogs.py`
  `tests/test_sequencer_playback_plan.py`
- [x] 本轮验证：
  `python -m pytest`（`176 passed`）
  `python -m compileall -q core ui tests main.py`
## 2026-04-02 Track Header / Locator Polish

- [x] Replaced the old left-side temporary track-item widget stack in `ui/grid_sequence_widget.py` with a custom-painted `TrackHeaderPanel`, so the track headers and the right-side lanes now share the same vertical metric model instead of relying on two separately rebuilt layouts.
- [x] This specifically targets the long-standing “音轨名称和音轨越多越错位” problem: the header panel now paints directly from track layout metrics and current scroll position, eliminating cumulative per-row drift during dense multi-track sessions.
- [x] Promoted the locator strip into a clearer always-visible positioning area: it now has an explicit label, clearer affordance, and remains usable even when the top of the main lane viewport is scrolled out of sight.
- [x] Unified wheel-event routing across the main lane view, the locator strip, and the left track header area; `Ctrl + 滚轮` vertical lane zoom is restored consistently instead of only working when the pointer happens to be over one specific sub-widget.
- [x] Validation:
  `python -m pytest` -> `176 passed`
  `python -m compileall -q app_info.py main.py core ui tests` -> passed
