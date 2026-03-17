"""
主窗口文件操作相关的纯函数辅助工具。
"""

from dataclasses import dataclass
from typing import Literal, Optional

OPEN_IMPORT_FILE_FILTER = (
    "所有支持的文件 (*.json *.mid *.midi);;"
    "JSON文件 (*.json);;"
    "MIDI文件 (*.mid *.midi);;"
    "所有文件 (*.*)"
)
PROJECT_OPEN_FILE_FILTER = "JSON文件 (*.json);;所有文件 (*.*)"
MIDI_OPEN_FILE_FILTER = "MIDI文件 (*.mid *.midi);;所有文件 (*.*)"
EXPORT_FILE_FILTER = (
    "JSON项目文件 (*.json);;"
    "MIDI文件 (*.mid);;"
    "WAV音频文件 (*.wav);;"
    "MP3音频文件 (*.mp3);;"
    "OGG音频文件 (*.ogg);;"
    "所有文件 (*.*)"
)

OpenFileKind = Literal["project", "midi"]
ExportKind = Literal["project", "midi", "audio"]


@dataclass(frozen=True)
class ExportTarget:
    """导出目标解析结果。"""

    kind: ExportKind
    file_path: str
    audio_format: Optional[str] = None
    updates_current_project_path: bool = False


def detect_open_file_kind(file_path: str) -> Optional[OpenFileKind]:
    """根据文件扩展名判断应该按项目还是 MIDI 打开。"""
    normalized = file_path.lower()
    if normalized.endswith(".json"):
        return "project"
    if normalized.endswith((".mid", ".midi")):
        return "midi"
    return None


def resolve_export_target(file_path: str, selected_filter: str) -> ExportTarget:
    """
    根据文件名和保存对话框过滤器，解析最终导出目标。

    这里统一处理后缀补全，避免 `.midi` / `.oga` 等路径被重复追加扩展名。
    """
    selected_filter = selected_filter or ""
    if "JSON" in selected_filter:
        return ExportTarget(
            kind="project",
            file_path=_ensure_suffix(file_path, (".json",), ".json"),
            updates_current_project_path=True,
        )
    if "MIDI" in selected_filter:
        return ExportTarget(kind="midi", file_path=_ensure_suffix(file_path, (".mid", ".midi"), ".mid"))
    if "WAV" in selected_filter:
        return ExportTarget(kind="audio", file_path=_ensure_suffix(file_path, (".wav",), ".wav"), audio_format="wav")
    if "MP3" in selected_filter:
        return ExportTarget(kind="audio", file_path=_ensure_suffix(file_path, (".mp3",), ".mp3"), audio_format="mp3")
    if "OGG" in selected_filter:
        return ExportTarget(
            kind="audio",
            file_path=_ensure_suffix(file_path, (".ogg", ".oga"), ".ogg"),
            audio_format="ogg",
        )

    normalized = file_path.lower()
    if normalized.endswith(".json"):
        return ExportTarget(kind="project", file_path=file_path, updates_current_project_path=True)
    if normalized.endswith((".mid", ".midi")):
        return ExportTarget(kind="midi", file_path=file_path)
    if normalized.endswith(".wav"):
        return ExportTarget(kind="audio", file_path=file_path, audio_format="wav")
    if normalized.endswith(".mp3"):
        return ExportTarget(kind="audio", file_path=file_path, audio_format="mp3")
    if normalized.endswith((".ogg", ".oga")):
        return ExportTarget(kind="audio", file_path=file_path, audio_format="ogg")

    return ExportTarget(
        kind="project",
        file_path=_ensure_suffix(file_path, (".json",), ".json"),
        updates_current_project_path=True,
    )


def _ensure_suffix(file_path: str, valid_suffixes: tuple[str, ...], preferred_suffix: str) -> str:
    """在缺少扩展名时补全一个默认扩展名。"""
    normalized = file_path.lower()
    if normalized.endswith(valid_suffixes):
        return file_path
    return f"{file_path}{preferred_suffix}"
