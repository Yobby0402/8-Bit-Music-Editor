# P0-P3 重构与规范化路线图

> 目标：在不打断现有功能的前提下，逐步把项目整理成更稳定、更易维护、也更方便继续迭代的工程。
> 约定：每次执行规范化或重构改动时，同时更新本路线图与根目录 `CHANGELOG.md`。

## 当前状态

- `P0`：已完成，主要是清理废弃功能、统一版本与文档落点。
- `P1`：基本完成，主窗口已从超大单文件拆成薄入口 + 多个 mixin，剩余工作以收尾和规范化为主。
- `P2`：进行中，已经开始把 UI 与核心服务边界拆开，并推进更细的模块职责划分。
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
- [x] 为新提炼的 helper 和服务层补充测试，当前 `pytest` 为 `62 passed`。

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
- [x] 完成全量 `ruff check .` 收敛，清理 import 排序、未使用导入、未使用变量、重复定义、无占位 f-string 和部分过宽异常。
- [ ] 继续梳理 `core/` 内模型、生成器、IO、播放控制的边界，减少 UI 对核心实现细节的直接依赖。
- [ ] 评估 `ui/main_window_shell_ops.py` 是否还需要继续下沉成更细的 builder/helper；如果壳层规模保持稳定，可以先不继续拆。

## P3 长期维护与产品化

- [ ] 建立更完整的回归测试策略，包括更多核心逻辑测试和最小集成验证。
- [ ] 规范发布流程，串联版本号、changelog、打包脚本和发布说明。
- [ ] 为大工程、长时播放与复杂导入场景建立性能与稳定性检查项。
- [ ] 评估是否需要更清晰的设备端边界、插件入口或脚本接口。
- [ ] 持续降低历史 lint 噪音，为更严格的工程规范做准备。

## 本轮更新

- 新增 `ui/main_window_shell_ops.py`，承接窗口壳层、布局装配、菜单、状态栏和关闭流程。
- 新增 `tests/test_main_window_shell_ops.py`，覆盖窗口几何和 Dock 宽度 helper。
- 将 `ui/main_window.py` 进一步收缩到 `66` 行，仅保留组合入口和兼容钩子。
- 修复 `self.current_midi_file_path` 被历史注释串吞掉的问题，恢复为正式属性初始化。
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
- 当前 `python -m ruff check .`、`python -m pytest` 与 `python -m compileall -q app_info.py main.py core ui tests` 已全部通过。
- 验证通过：
  `python -m ruff check ui/main_window.py ui/main_window_shell_ops.py tests/test_main_window_shell_ops.py`
  `python -m pytest`
  `python -m compileall -q app_info.py main.py core ui tests`
