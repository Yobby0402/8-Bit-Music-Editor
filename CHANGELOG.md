# Changelog

本项目版本号遵循 SemVer。

## [Unreleased]

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

### Added

- `docs/p1_normalization.md`，用于跟踪 `P0-P3` 重构路线和完成状态。
- `core/project_io.py`、`core/project_service.py`、`core/seed_generation_service.py`。
- `ui/main_window_dialogs.py`、`ui/main_window_file_ops.py`、`ui/main_window_project_ops.py`、`ui/main_window_playback_ops.py`。
- `ui/main_window_score_ops.py`、`ui/main_window_view_ops.py`、`ui/main_window_editor_ops.py`、`ui/main_window_note_entry_ops.py`。
- `ui/main_window_app_ops.py`、`ui/main_window_seed_ops.py`、`ui/main_window_theme_ops.py`、`ui/main_window_refresh_ops.py`、`ui/main_window_shell_ops.py`。
- 覆盖上述 helper 与服务层的测试文件，当前测试集为 `62` 项。

### Removed

- 已失效的 WiFi 相关代码与一批可删除的旧测试/演示脚本。
- `ui/main_window.py` 顶部的路径注入逻辑。

### Fixed

- 修复导出 `.midi` 与 `.oga` 时可能重复追加扩展名的问题。
- 修复示波器视图在“手动选择音轨 + 启用过滤”组合场景下的筛选分支问题。
- 修复重复调用 `setup_shortcuts()` 时可能叠加注册 action 的问题。
- 修复 `ui/main_window.py` 中 `self.current_midi_file_path` 被历史注释串吞掉的问题。
- 修复 `core/midi_io.py` 中轨道名 ASCII 回退映射和音符避重叠分支的历史问题。

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
