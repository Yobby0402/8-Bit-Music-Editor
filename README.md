# 8bit音乐制作器

一个基于 PyQt5 的桌面 8bit 音乐编辑器，支持音符编辑、MIDI 导入导出、音频导出、Seed 自动配乐和实时试听。

## 当前版本

`3.1.1`

版本号遵循 SemVer，正式变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 功能概览

- 音符轨 / 鼓轨编辑
- MIDI 导入与导出
- WAV / MP3 / OGG 音频导出
- Seed 多风格自动配乐
- 示波器、属性面板、乐谱片段库
- 多轨播放、循环和 BPM 编辑

## 安装

```bash
pip install -r requirements.txt
```

## 开发环境

```bash
pip install -r requirements-dev.txt
```

常用命令：

```bash
python -m ruff check app_info.py main.py tests
python -m pytest
python -m compileall -q app_info.py main.py core ui device build_exe.py
```

## 运行

```bash
python main.py
```

## 项目结构

```text
8bit/
├── app_info.py        # 应用名称与版本号
├── main.py            # 程序入口
├── core/              # 核心逻辑
├── ui/                # 桌面界面
├── device/            # 设备端参考脚本
├── docs/              # 项目文档
├── build_exe.py       # PyInstaller 打包脚本
└── README.md
```

## 文档

- [文档索引](docs/README.md)
- [使用说明](docs/使用说明.md)
- [开发进度](docs/开发进度.md)
- [P0-P3 重构路线图](docs/p1_normalization.md)
- [打包说明](docs/打包说明.md)

## 工程基线

- `pyproject.toml`：统一 `pytest` / `ruff` 配置
- `requirements-dev.txt`：开发依赖入口
- `.github/workflows/ci.yml`：最小 CI，执行编译、lint 和测试
- `tests/`：核心层回归测试

## 说明

- 内置的 WiFi 设备播放链路已移除，`device/` 目录目前只保留设备端参考脚本。
- 仓库中的示例工程仍使用 JSON 作为项目文件格式。

## 许可证

MIT License

