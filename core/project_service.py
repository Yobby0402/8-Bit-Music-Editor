"""
项目相关服务层。

统一承接项目文件读写、MIDI 导入以及导出流程中的核心业务逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.midi_io import MidiIO
from core.models import Project, TrackRole, WaveformType
from core.project_io import load_project_from_file, save_project_to_file

MP3_EXPORT_DEPENDENCY_MESSAGE = (
    "导出MP3需要安装以下库之一：\n\n"
    "方法1（推荐）：安装moviepy（会自动下载内置ffmpeg）\n"
    "  pip install moviepy\n\n"
    "方法2：安装pydub并手动安装ffmpeg\n"
    "  pip install pydub\n"
    "  然后从 https://ffmpeg.org/ 下载安装ffmpeg\n\n"
    "或者，您可以使用OGG格式（无需额外依赖）"
)

OGG_EXPORT_DEPENDENCY_MESSAGE = (
    "导出OGG需要安装soundfile库。\n\n"
    "请运行以下命令安装：\n"
    "pip install soundfile"
)


@dataclass(frozen=True)
class ProjectLoadResult:
    """项目加载结果。"""

    project: Project
    current_file_path: str | None
    current_midi_file_path: str | None


@dataclass(frozen=True)
class ProjectSaveResult:
    """项目保存或导出结果。"""

    file_path: str


@dataclass(frozen=True)
class AudioExportResult:
    """音频导出结果。"""

    file_path: str
    format: str


@dataclass(frozen=True)
class ExportDependencyGuidance:
    """导出依赖缺失时的用户提示。"""

    title: str
    message: str


class EmptyAudioExportError(RuntimeError):
    """项目没有可导出的音频数据。"""


class AudioExportDependencyError(ImportError):
    """导出时缺少必要依赖。"""

    def __init__(self, guidance: ExportDependencyGuidance):
        super().__init__(guidance.message)
        self.title = guidance.title
        self.user_message = guidance.message


def load_project_document(file_path: str) -> ProjectLoadResult:
    """读取项目 JSON 文件。"""
    project = load_project_from_file(file_path)
    return ProjectLoadResult(
        project=project,
        current_file_path=file_path,
        current_midi_file_path=None,
    )


def import_midi_document(
    file_path: str,
    default_waveform: WaveformType,
    *,
    snap_to_beat: bool = False,
    allow_overlap: bool = True,
) -> ProjectLoadResult:
    """导入 MIDI 文件并返回统一的项目加载结果。"""
    project = MidiIO.import_midi(
        file_path,
        default_waveform=default_waveform,
        snap_to_beat=snap_to_beat,
        allow_overlap=allow_overlap,
    )
    return ProjectLoadResult(
        project=project,
        current_file_path=None,
        current_midi_file_path=file_path,
    )


def save_project_document(project: Project, file_path: str) -> ProjectSaveResult:
    """保存项目到 JSON 文件。"""
    save_project_to_file(project, file_path)
    return ProjectSaveResult(file_path=file_path)


def export_midi_document(project: Project, file_path: str) -> ProjectSaveResult:
    """导出项目为 MIDI 文件。"""
    MidiIO.export_midi(project, file_path)
    return ProjectSaveResult(file_path=file_path)


def build_audio_export_dependency_guidance(
    format_name: str,
    error_message: str,
) -> ExportDependencyGuidance | None:
    """将导出依赖错误归一化为可展示的用户提示。"""
    normalized_format = (format_name or "").lower()
    normalized_message = (error_message or "").lower()

    if normalized_format == "mp3" or any(
        keyword in normalized_message
        for keyword in ("mp3", "moviepy", "pydub", "ffmpeg")
    ):
        return ExportDependencyGuidance(
            title="缺少依赖",
            message=MP3_EXPORT_DEPENDENCY_MESSAGE,
        )

    if normalized_format == "ogg" or "soundfile" in normalized_message:
        return ExportDependencyGuidance(
            title="缺少依赖",
            message=OGG_EXPORT_DEPENDENCY_MESSAGE,
        )

    return None


def export_audio_document(
    project: Project,
    audio_engine: Any,
    file_path: str,
    *,
    format: str = "wav",
) -> AudioExportResult:
    """导出项目音频。"""
    from core.audio_export import AudioExporter

    audio = audio_engine.generate_project_audio(project)
    if len(audio) == 0:
        raise EmptyAudioExportError("项目中没有音频数据")

    try:
        AudioExporter.export_audio(audio, file_path, audio_engine.sample_rate, format=format)
    except ImportError as exc:
        guidance = build_audio_export_dependency_guidance(format, str(exc))
        if guidance is not None:
            raise AudioExportDependencyError(guidance) from exc
        raise

    return AudioExportResult(file_path=file_path, format=format.lower())


def export_audio_range_document(
    project: Project,
    audio_engine: Any,
    file_path: str,
    *,
    start_time: float,
    end_time: float,
    format: str = "wav",
    sfx_only: bool = False,
) -> AudioExportResult:
    """Export a time range from the project audio."""
    from core.audio_export import AudioExporter

    if end_time <= start_time:
        raise EmptyAudioExportError("Export range is empty")

    playback_enabled_tracks = None
    if sfx_only:
        playback_enabled_tracks = {
            id(track): track.role == TrackRole.EFFECT
            for track in project.tracks
        }

    audio = audio_engine.generate_project_audio(
        project,
        start_time=start_time,
        end_time=end_time,
        playback_enabled_tracks=playback_enabled_tracks,
    )
    if len(audio) == 0:
        raise EmptyAudioExportError("Project range has no audio data")

    try:
        AudioExporter.export_audio(audio, file_path, audio_engine.sample_rate, format=format)
    except ImportError as exc:
        guidance = build_audio_export_dependency_guidance(format, str(exc))
        if guidance is not None:
            raise AudioExportDependencyError(guidance) from exc
        raise

    return AudioExportResult(file_path=file_path, format=format.lower())
