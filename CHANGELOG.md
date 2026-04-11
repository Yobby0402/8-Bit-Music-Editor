# Changelog

本项目版本号遵循 SemVer。

## [Unreleased]

### 2026-04-02

- Fixed the top locator strip alignment in `ui/grid_sequence_widget.py` by making the main scene's top padding match the locator bar height, so the locator row and the first track lane now share the same vertical baseline without leaking note content or leaving a seam.
- Kept the locator strip on the same horizontal scale as the main sequence view and restored direct scrollbar sync, so dragging or scrubbing in the locator uses the same timing geometry as the track area again.
- Fixed a playback-mode regression in the locator row: fixed-playhead playback now continues syncing the locator strip's horizontal scroll with the main sequence viewport instead of letting the locator playhead drift.
- Reserved the main view's vertical-scrollbar width on the locator row and remapped locator dragging through the main sequence viewport geometry, so locator scrubbing no longer runs ahead of the lower track area when the main view shows a vertical scrollbar.
- Reserved the main splitter handle width in the locator row as well, fixing the remaining constant horizontal offset where the locator baseline did not include the divider space between the left track panel and the main sequence view.
- Fixed editor note-entry track targeting: melody/bass insertion now prefers the currently selected compatible track, falls back to the first compatible project track when nothing is selected, and drum insertion falls back to the first drum track instead of an unrelated note-track role match.
- Synced track selection state into the unified editor target-track context when clicking a track lane or selecting a note/event, so subsequent note insertion follows the track the user most recently selected.
- Reworked the sequence lane header in `ui/grid_sequence_widget.py`: the left track-name area now uses a shared-coordinate painted header panel instead of stacking temporary child widgets, which removes the cumulative vertical drift that became obvious in large multi-track projects.
- Polished the always-visible locator strip so playback-position targeting no longer depends on the top 20px of the main lane viewport; the locator row is now labeled, visibly separate, and keeps sharing the same scene alignment as the musical grid.
- Unified wheel routing across the main sequence view, the left track header area, and the locator strip; `Ctrl + mouse wheel` vertical lane zoom now works again no matter which track-region subpanel the pointer is over.
- Validation for this follow-up: `python -m pytest` (`186 passed`) and `python -m compileall -q app_info.py main.py core ui tests`.

### 2026-03-26

- Renamed the unified editor's internal melody/bass mode semantics to an explicit entry-role concept in `ui/unified_editor_widget.py`: the widget now uses `current_entry_role` internally while keeping `current_track_type` as a backward-compatible alias.
- Updated note-entry cleanup paths to read the unified editor's role-mode semantics directly, reducing the remaining naming ambiguity between structural `track_type` and note-entry role.
- Extended `ui/main_window_dialogs.py` with explicit note-track role selection for the “添加音轨” dialog and added a typed `NewTrackSelection` result object instead of overloading the old tuple semantics.
- Extended `core/sequencer.py` so `Sequencer.add_track()` can accept an initial note-track role and automatically clears it for drum tracks.
- Updated `ui/main_window_app_ops.py` so manually created tracks now persist the selected initial role into the project model.
- Added regression coverage for manual track creation with role propagation, dialog role/default-name helpers, and the new sequencer track-role parameter; the full suite now passes at `176` tests.

### 2026-03-25

- Added an explicit `Track.role` / `TrackRole` model layer for note tracks, separating structural `track_type` (`note` / `drum`) from musical role (`melody` / `bass` / `harmony` / `effect`).
- Added backward-compatible role normalization in `core/models.py`: old projects without a saved `role` now infer note-track role from legacy track names on load, while drum tracks normalize role to `None`.
- Extended the property panel with a dedicated `音轨角色` editor for note tracks, so `音轨类型` no longer has to carry “主旋律/低音” style semantics.
- Updated note-entry routing so bass-mode insertion now prefers `role=bass` note tracks instead of any note track, and newly auto-created note-entry tracks inherit the intended role/default name.
- Removed the last `track.name`-based melody/bass inference in `ui/grid_sequence_widget.py`; lane rendering now follows canonical `track_type + role`.
- Added regression coverage for track-role round trips, legacy role inference, property-panel role mapping, role-aware note-entry routing, and role-based grid rendering; the full suite now passes at `172` tests.
- Normalized the track-type editor semantics in `ui/property_panel_widget.py`: the combo now reflects the real structural types (`音符音轨` / `打击乐音轨`) instead of mixing role labels such as “主旋律/低音” into the data model.
- Added a safety guard for track-type changes: non-empty tracks can no longer be switched directly between note-track and drum-track modes, preventing the old behavior where existing notes/drum events were silently reinterpreted or hidden.
- Fixed the sequence-lane background horizontal lines in `ui/grid_sequence_widget.py` so they start at `x=0` with the rest of the musical content instead of leaving an empty strip at the beginning due to the removed legacy left gutter.
- Added regression coverage for canonical track-type combo mapping, unsafe cross-type switching on non-empty tracks, and the corrected lane-line origin; the full suite now passes at `166` tests.
- Tightened track-lane alignment again in `ui/grid_sequence_widget.py`: the right view now reports vertical visibility from the actual scrollbar position, left-side track items stay alive during scroll updates instead of rebuilding every tick, and the track-name widget uses the full lane height so label centering matches the lane center more closely.
- Fixed the remaining horizontal zoom-out limit: scene width is now derived from musical content plus viewport width instead of old fixed `1000/2000px` minimums, and the minimum zoom scale adapts to fit the whole song into the current viewport when possible.
- Added regression coverage for scrollbar-based visible-range calculation, adaptive whole-song zoom fitting, viewport-width scene shrinking, and the in-place left-track-list scroll sync path; the full suite now passes at `161` tests.
- Fixed track-list / note-lane vertical alignment in `ui/grid_sequence_widget.py`: the left track list now accounts for partial vertical scroll offsets instead of only whole-track steps, so track names stay aligned with the visible lane area.
- Finished the per-track display-height groundwork: `Track.display_height` now has regression coverage, block layout refresh paths use the shared track-height model, and zoom refresh keeps custom lane heights/stacks consistent.
- Fixed a UI regression where recycled left-side track-list widgets and legacy checkbox widgets could be detached with `setParent(None)` and appear as stray top-level windows during MIDI import or vertical scrolling; they are now hidden and scheduled for deletion correctly.
- Relaxed the top editor pane's splitter sizing policy so the lower playback/track area can be dragged taller instead of feeling one-directional.
- Lowered the effective minimum height of the main track/playback area by reducing the sequence/oscilloscope pane minimums, so the center splitter can collapse further when you want to prioritize the upper editor.
- Improved per-track height editing: drag-resize now keeps visible track-list items alive during the drag instead of rebuilding them on every mouse move, which makes single-track height adjustment feel continuous.
- Added compact lane support by letting tracks shrink further and scaling note-block height with lane height so low-priority tracks can be displayed much smaller without immediately overlapping neighbors.
- Added tests for compact track lanes, track layout metrics, track-list widget cleanup, per-track height clamping/persistence, and the center splitter sizing/shrink policy; the full suite now passes at `157` tests.

### 2026-03-24

- Added a playback display mode setting in the settings dialog: users can now choose between the existing moving-playhead follow-scroll mode and a fixed-playhead mode where notes scroll left during playback.
- Added regression coverage for the new playback display mode routing and fixed-playhead scrolling behavior; the full suite now passes at `148` tests.
- Fixed a playback freeze regression in dense variable-tempo projects: `SequenceBlock.boundingRect()` now uses cached tick-first geometry instead of rebuilding beat timing from seconds during scene repaints.
- Added cached `Project` tempo-region reuse so repeated `seconds_to_ticks()` / `ticks_to_seconds()` / `seconds_to_beats()` calls no longer rebuild the tempo map for each conversion.
- Added regression coverage for the project-level tempo cache and the sequence-block geometry hotfix; the full suite now passes at `146` tests.
- Smoothed playback follow-scrolling in `ui/grid_sequence_widget.py`: the playhead now nudges the horizontal scrollbar in smaller edge-triggered steps during playback instead of calling `centerOn()` only after leaving the viewport, which reduces the visible hitch when crossing to the next screen.
- Applied additional `QGraphicsView` viewport/optimization flags for the sequence scene and added optional `[PROFILE] grid.playhead_autoscroll ...` breadcrumbs for slow follow-scroll updates.
- Added regression coverage for the new playback auto-scroll helper; the full suite now passes at `144` tests.
- Reduced `GridSequenceWidget` timing-conversion overhead again by making note/block position calculations prefer stored `start_tick` / `duration_ticks` over repeated `seconds_to_beats()` tempo-map conversions during scene rebuilds.
- Added cached waveform-color lookup and module-level note/drum label tables in `ui/grid_sequence_widget.py`, trimming per-block setup cost during dense MIDI imports.
- Very narrow note blocks now skip pitch-label text drawing, reducing paint cost for high-density passages where labels are unreadable anyway.
- Added regression coverage for the tick-first beat conversion path in `tests/test_grid_sequence_widget.py`; the full suite now passes at `143` tests.
- Reduced full-sequence rebuild churn in `ui/grid_sequence_widget.py` by wrapping force-full refreshes in a bulk scene-update mode that temporarily suspends viewport repaints and scene indexing while thousands of note blocks are rebuilt.
- Added `[PROFILE] grid.full_refresh ...` stage breakdowns so slow scene rebuilds now report `clear_scene / draw_grid / draw_content / build_blocks / stack_layout / playhead` costs directly in the terminal.
- Added regression coverage for the new bulk scene-update guard in `tests/test_grid_sequence_widget.py`; the full suite now passes at `142` tests.
- Fixed the false `project.import_midi outcome=cancelled` profiling report on successful imports by closing the MIDI progress dialog with signals temporarily blocked.
- Added UI-side MIDI import apply profiling so successful imports can now print `[PROFILE] project.import_midi_ui_apply ...` with `apply_project / reset_selection / refresh_project / update_file_label / persist_directory` stage timings.
- Added refresh-stage profiling in `ui/main_window_refresh_ops.py`; slow full-window refreshes now report `set_tracks / sequence_refresh / playback_settings` timing breakdowns to help isolate remaining white-screen stalls after import.
- Batched playback-settings panel updates into a single rebuild, removed noisy debug prints, and fixed its layout cleanup so repeated refreshes no longer accumulate stale spacer items or emit duplicate all-enabled state resets.
- Finished the pending `core/midi_io.py` cleanup by reusing the shared track-name extraction helper in the optimized MIDI import path.
- Added regression coverage for the MIDI-import progress-dialog close path and the batched playback-settings refresh path; the full suite now passes at `141` tests.
- Unified note-edit refresh decisions in `ui/main_window_editor_ops.py` so note dragging, single-note property edits, property-panel refresh requests, and batch note edits now share one lightweight refresh helper.
- Property-panel batch edits and note drag updates in waveform view now avoid full-window `refresh_ui()` while keeping both the hidden sequence scene and oscilloscope view in sync.
- Linked duration edits now batch the edited note together with adjusted following notes into one local block-sync pass instead of syncing each block separately.
- Fixed the remaining oscilloscope-view note-refresh gaps across note entry, delete, undo/redo, and score-apply flows; score apply now treats failed note-local sync as a correctness fallback to full refresh instead of silently leaving the sequence scene stale.
- Reduced `GridSequenceWidget` local-edit churn again: overlap stack layout now only walks the affected track group's blocks, drum-track local sync skips note-stack work entirely, and block position updates now avoid redundant `setPos()` calls.
- Changed playhead refresh to reuse the existing graphics item when geometry is unchanged or only needs a line update, instead of removing and recreating the item on every local note edit.
- Tightened oscilloscope empty-track edge handling so invalid manual render selections no longer leak back into empty waveform renders, and already-empty waveform view now skips redundant clear passes.
- Added lightweight profiling instrumentation in `ui/performance_utils.py` for MIDI import, playback prepare, and note-edit refresh flows; long operations now emit console `[PROFILE]` timings while keeping a small in-memory history on the main window.
- Reduced variable-tempo MIDI import cost by prebuilding tempo regions once per import and reusing them while populating note second timing, instead of rebuilding tick-to-second conversion state for every imported note.
- Added stage-level MIDI import console profiling (`[PROFILE] midi.import_stages ...`) so slow imports now show `load / tempo / tracks` breakdowns directly in the terminal.
- Added focused oscilloscope/performance/import regression coverage and raised the full suite to `144` passing tests.

### 2026-03-23

- Reduced property-panel refresh pressure again: note updates now prefer local sync or oscilloscope repaint, and track-property updates now distinguish lightweight changes from structural ones.
- Added lightweight track-presentation sync so rename/effect edits update track labels and related panels without rebuilding the whole sequence scene.
- Tightened oscilloscope refresh behavior by keeping a stable render signature and removing redundant `update()` calls from view-switch and render-selection flows.
- Added `tests/test_oscilloscope_widget.py` and expanded regression coverage to `117` passing tests.
- Fixed a regression-prone oscilloscope path where manually selected render tracks could be short-circuited into a BPM-only refresh and miss note-content repaints.
- Changed score-snippet apply to return explicit added items and prefer batch local UI sync before falling back to a full refresh.
- Reduced theme-apply cost by switching `refresh_theme_from_settings()` from forced full refresh to incremental refresh.
- Added regression coverage for score-apply lightweight refresh and theme-refresh mode selection.
- Changed `undo/redo` to return structured command-history results so the UI can choose lightweight refresh paths instead of blindly rebuilding the whole window.
- Note-centric `undo/redo` flows now prefer local note-block sync, track-only sync, and targeted property-panel updates before falling back to full `refresh_ui()`.
- Made `Sequencer` audio initialization optional for headless/test environments and stabilized playback-plan tests on machines without an available WASAPI endpoint.
- Removed duplicate note-overlap scanning from `GridSequenceWidget._update_or_create_block()` and cleaned out temporary note-position debug prints so block sync pays the stacking-layout cost only once per affected track.
- Expanded regression coverage again; the full suite now passes at `123` tests.

### Changed

- 清理并移除了已废弃的 WiFi 设备播放链路。
- 统一文档路径到 `docs/`，并建立持续维护的重构路线图。
- 将应用版本统一收敛到 `app_info.py` 作为单一来源。
- 补齐 `pyproject.toml`、`requirements-dev.txt`、CI 与基础测试框架。
- 规范 `main.py` 启动入口的导入与异常处理结构。
- 持续收缩 `ui/main_window.py`，将项目流程、播放控制、视图切换、编辑逻辑、应用动作、Seed 入口、主题刷新、刷新同步与窗口壳层逐步迁移到独立模块。
- 将 `ui/main_window.py` 进一步收缩为薄入口类，本轮把菜单、布局、状态栏与关闭生命周期迁移到 `ui/main_window_shell_ops.py`。
- 启动全量 `ruff` 收敛，先清理了一批叶子 UI 组件中的 import 排序和未使用导入问题。
- 继续清理核心层、设备脚本和历史 UI 大文件中的 lint 噪音，并完成全量 `python -m ruff check .` 收敛。
- 将 Seed 风格目录从 `core/seed_music_generator.py` 中抽离到独立的 `core/seed_style_catalog.py`，统一管理风格枚举、默认参数、元数据、变体与运行时覆盖。
- 将 Seed 风格配置类与工厂从 `core/seed_music_generator.py` 中抽离到独立的 `core/seed_style_configs.py`，让生成器主文件更聚焦于项目结构装配与生成流程。
- 将结构预设与 Seed 通用 helper 从 `core/seed_music_generator.py` 中抽离到 `core/seed_structure_catalog.py` 和 `core/seed_generation_utils.py`，继续压缩生成器主文件的目录型职责。
- 将乐句分析、变体行为与 `quiet_bars` 规划从 `core/seed_music_generator.py` 中抽离到 `core/seed_generation_planner.py`，统一生成期规划逻辑并减少旋律/和声/鼓点之间的重复判断。
- 将低音、和声与鼓点轨道构建逻辑从 `core/seed_music_generator.py` 中抽离到 `core/seed_track_builders.py`，并保留生成器兼容导出。
- 确认后续架构转向标准 `tick + tempo_events + second(派生)` 时间模型，不再以“秒优先”作为长期方向。
- 将 `Project.beats_to_seconds()` 与 `Project.seconds_to_beats()` 统一收口到标准 tick tempo map。
- 将 BPM 编辑器从按秒编辑 `bpm_segments` 迁移为按 beat/tick 编辑 `tempo_events`。
- 将 [docs/为什么使用秒而不是ticks.md](/f:/Code/8bit/docs/为什么使用秒而不是ticks.md) 标记为历史说明，并以标准时间模型文档作为当前方案来源。
- 继续推进 `Note` 的 tick 桥接层，使新增音符、tempo 替换和完整项目保存都会同步 note 的 tick/second 双视图。
- 将 MIDI 导入导出切换到项目标准时间模型：导入保留原始 `ticks_per_beat` 与 tempo events，导出按项目 tick/resolution 写回。
- 将属性面板中的时间编辑链路切到 tick-aware 语义，开始时间、结束时间、时长和连续后续音符位移都优先按 tick 计算。
- 将 MIDI 导入与播放前音频预渲染迁移到 `QThread` worker，避免导入大型 MIDI 和点击播放时长时间阻塞主线程。
- 将 `Sequencer` 播放链路拆为“后台预渲染计划”和“主线程启动播放”两段，后续继续做缓存、流式播放或更细粒度调度时不必再挤在一个入口里。
- 将 `Sequencer.play()` 正式收口到 prepared playback pipeline，并把播放计划中的音频缓冲前移为 pygame-ready 的 `int16 stereo` 数据，继续减少点击播放时的主线程工作量。
- 收敛 `refresh_ui()` 期间的重复序列视图刷新，避免 `set_tracks()` 与 `set_bpm()` 各自再触发一次 `refresh()`，降低编辑时的卡顿和白屏概率。
- 为单音符新增、移动、属性修改与删除补上局部 block 同步路径，高频编辑动作现在优先更新单块和场景边界，而不是每次整页重绘。
- 为批量属性修改、批量删除和拖动结束后的收尾逻辑补上批量局部 block 同步，继续减少编辑时的大范围重绘。
- 将设置对话框关闭后的重复整页刷新移除，改为只做快捷键重绑收尾。
- 将音轨启用切换从延迟整页刷新改为按需刷新示波器，避免切换启用状态时重建整个序列区。

### Added

- `docs/p1_normalization.md`，用于跟踪 `P0-P3` 重构路线和完成状态。
- `core/project_io.py`、`core/project_service.py`、`core/seed_generation_service.py`。
- `core/seed_style_catalog.py`。
- `core/seed_style_configs.py`。
- `core/seed_structure_catalog.py`、`core/seed_generation_utils.py`。
- `core/seed_generation_planner.py`。
- `core/seed_track_builders.py`。
- `ui/main_window_dialogs.py`、`ui/main_window_file_ops.py`、`ui/main_window_project_ops.py`、`ui/main_window_playback_ops.py`。
- `ui/main_window_score_ops.py`、`ui/main_window_view_ops.py`、`ui/main_window_editor_ops.py`、`ui/main_window_note_entry_ops.py`。
- `ui/main_window_app_ops.py`、`ui/main_window_seed_ops.py`、`ui/main_window_theme_ops.py`、`ui/main_window_refresh_ops.py`、`ui/main_window_shell_ops.py`。
- `docs/standard_time_model_refactor.md`。
- `core/musical_time.py`。
- `ui/background_tasks.py`。
- `tests/test_musical_time.py`。
- `tests/test_main_window_refresh_ops.py`。
- `tests/test_sequencer_playback_plan.py`。
- `tests/test_seed_track_builders.py`。
- 覆盖上述 helper 与服务层的测试文件，当前测试集为 `111` 项。

### Removed

- 已失效的 WiFi 相关代码与一批可删除的旧测试/演示脚本。
- `ui/main_window.py` 顶部的路径注入逻辑。

### Fixed

- 修复导出 `.midi` 与 `.oga` 时可能重复追加扩展名的问题。
- 修复示波器视图在“手动选择音轨 + 启用过滤”组合场景下的筛选分支问题。
- 修复重复调用 `setup_shortcuts()` 时可能叠加注册 action 的问题。
- 修复 `ui/main_window.py` 中 `self.current_midi_file_path` 被历史注释串吞掉的问题。
- 修复 `core/midi_io.py` 中轨道名 ASCII 回退映射和音符避重叠分支的历史问题。
- 修复 `StyleParamsWidget` 中 `WORKSHOP` 风格缺少友好显示名的问题。
- 修复 variable BPM 工程在播放/渲染时仍按固定 BPM 计算的问题。
- 新增 `core/tempo_map.py` 统一 beat/second 换算，并让 `Project.get_total_duration()` 与 `Sequencer` 共用同一时间语义。
- 修复鼓轨在变速 BPM 和单 BPM 缩放场景下的播放时间对齐问题。
- 补充 `tests/test_tempo_map.py`、`tests/test_audio_engine_tempo.py` 与 `tests/test_models.py` 回归测试。
- 修复 BPM 编辑、拍点换算与项目 tempo source 之间长期并存两套时间真相的风险，开始统一到 `tempo_events`。
- 修复 tempo map 改动后 note 秒值可能不再随 tick 位置重新推导的问题。
- 补充 `tests/test_midi_io.py` 与 `tests/test_models.py`，覆盖 MIDI tick/resolution 回归和 note 随 tempo map 重定时。
- 补充 `tests/test_property_panel_timing.py`，覆盖属性面板时间编辑在 tick 语义下的开始/结束/时长与连续位移规则。
- 修复播放准备和 MIDI 导入都压在 UI 主线程导致的严重卡顿问题，导入、开始播放和部分播放设置变更现在会先进入后台准备阶段。
- 修复刷新链路中同一次 UI 更新触发多次序列视图重绘的问题。
- 修复播放启动前仍在主线程完成音频缓冲打包的问题，开始播放时的启动负担进一步前移到后台准备阶段。
- 修复单音符移动、属性修改、常规插入和删除最后一个音符仍会触发整页刷新导致的编辑卡顿问题。
- 修复音符拖动完成后仍会被历史 `QTimer(... self.refresh)` 拉回整页重绘的问题。
- 修复批量属性修改、批量删除和设置应用收尾中的重复刷新问题。

## [3.1.1]

### Fixed

- 修复左侧音轨名称列表与右侧视图不同步的问题。
- 优化多选音轨高亮逻辑，支持 `Ctrl` / `Shift` 选择。
- 修复 MIDI 导入后音符显示位置错误的问题。
- 改进空白区域点击取消选择与堆叠布局计算。

## [3.0.0]

### Added

- 引入基于 Seed 的多风格自动配乐。
- 新增 `SeedMusicStyle`、风格参数和完整项目生成流程。
- 将 Seed 生成功能接入主窗口与 BPM 同步流程。

## [2.4.0]

### Fixed

- 修复 V2 系列中的部分 UI、示波器、MIDI 导入与播放同步问题。
