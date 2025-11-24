"""
音频导出模块

支持多种音频格式的导出：WAV、MP3、OGG等
"""

import numpy as np
from typing import Optional
import os

from .models import Project


class AudioExporter:
    """音频导出器"""
    
    @staticmethod
    def export_wav(audio_data: np.ndarray, file_path: str, sample_rate: int = 44100) -> None:
        """
        导出为WAV文件
        
        Args:
            audio_data: 音频数据（浮点数数组，范围-1.0到1.0）
            file_path: 输出文件路径
            sample_rate: 采样率
        """
        from scipy.io import wavfile
        
        # 确保数据在-1到1之间
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # 转换为16位整数
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # 保存为WAV文件
        wavfile.write(file_path, sample_rate, audio_int16)
    
    @staticmethod
    def export_mp3(audio_data: np.ndarray, file_path: str, sample_rate: int = 44100, bitrate: str = "192k") -> None:
        """
        导出为MP3文件
        
        尝试多种方法：
        1. 使用moviepy（会自动下载内置ffmpeg）
        2. 使用pydub + ffmpeg（如果已安装）
        
        Args:
            audio_data: 音频数据（浮点数数组，范围-1.0到1.0）
            file_path: 输出文件路径
            sample_rate: 采样率
            bitrate: 比特率（如 "128k", "192k", "320k"）
        
        Raises:
            ImportError: 如果所有方法都不可用
        """
        # 方法1：尝试使用moviepy（会自动下载内置ffmpeg）
        try:
            from moviepy import AudioFileClip
            import tempfile
            import os
            
            # 先导出为临时WAV文件
            temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_wav_path = temp_wav.name
            temp_wav.close()
            
            try:
                # 导出为临时WAV
                AudioExporter.export_wav(audio_data, temp_wav_path, sample_rate)
                
                # 使用moviepy转换为MP3
                audio_clip = AudioFileClip(temp_wav_path)
                # moviepy 2.x版本不再支持verbose和logger参数
                audio_clip.write_audiofile(file_path, codec='mp3', bitrate=bitrate)
                audio_clip.close()
            finally:
                # 删除临时文件
                if os.path.exists(temp_wav_path):
                    try:
                        os.unlink(temp_wav_path)
                    except:
                        pass  # 忽略删除失败
            
            return  # 成功，返回
        except ImportError as e:
            # moviepy未安装，继续尝试下一个方法
            pass  # moviepy未安装，尝试下一个方法
        except Exception as e:
            # moviepy失败，但可能是其他原因（如ffmpeg问题）
            # 如果moviepy已安装但失败，应该直接抛出错误，而不是尝试pydub
            # 因为如果moviepy都失败了，pydub很可能也会失败
            error_msg = str(e)
            raise RuntimeError(
                f"使用moviepy导出MP3失败: {error_msg}\n\n"
                "请检查moviepy是否正确安装，或尝试重新安装：\n"
                "pip install --upgrade moviepy"
            )
        
        # 方法2：使用pydub + ffmpeg（如果已安装）
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "导出MP3需要安装以下库之一：\n"
                "1. moviepy（推荐，会自动下载内置ffmpeg）: pip install moviepy\n"
                "2. pydub + ffmpeg: pip install pydub，并安装ffmpeg"
            )
        
        # 确保数据在-1到1之间
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # 转换为16位整数
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # 创建AudioSegment对象
        audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            channels=1,  # 单声道
            sample_width=2  # 16位 = 2字节
        )
        
        # 导出为MP3
        try:
            audio_segment.export(file_path, format="mp3", bitrate=bitrate)
        except Exception as e:
            raise ImportError(
                f"导出MP3失败: {str(e)}\n\n"
                "建议安装moviepy（会自动下载内置ffmpeg）:\n"
                "pip install moviepy"
            )
    
    @staticmethod
    def export_ogg(audio_data: np.ndarray, file_path: str, sample_rate: int = 44100, quality: int = 5) -> None:
        """
        导出为OGG文件
        
        Args:
            audio_data: 音频数据（浮点数数组，范围-1.0到1.0）
            file_path: 输出文件路径
            sample_rate: 采样率
            quality: 质量等级（0-10，5为默认）
        
        Raises:
            ImportError: 如果soundfile未安装
        """
        try:
            import soundfile as sf
        except ImportError:
            raise ImportError("导出OGG需要安装soundfile库。请运行: pip install soundfile")
        
        # 确保数据在-1到1之间
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        # 保存为OGG文件
        sf.write(file_path, audio_data, sample_rate, format='OGG', subtype='VORBIS')
    
    @staticmethod
    def export_audio(
        audio_data: np.ndarray,
        file_path: str,
        sample_rate: int = 44100,
        format: str = "wav",
        **kwargs
    ) -> None:
        """
        导出音频文件（根据文件扩展名自动选择格式）
        
        Args:
            audio_data: 音频数据（浮点数数组，范围-1.0到1.0）
            file_path: 输出文件路径
            sample_rate: 采样率
            format: 格式（"wav", "mp3", "ogg"），如果为None则根据文件扩展名自动判断
            **kwargs: 其他格式特定的参数
                - mp3: bitrate (默认 "192k")
                - ogg: quality (默认 5)
        """
        # 如果format为None，根据文件扩展名判断
        if format is None or format == "auto":
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".wav":
                format = "wav"
            elif ext == ".mp3":
                format = "mp3"
            elif ext == ".ogg" or ext == ".oga":
                format = "ogg"
            else:
                # 默认使用WAV
                format = "wav"
        
        # 根据格式调用相应的导出方法
        if format.lower() == "wav":
            AudioExporter.export_wav(audio_data, file_path, sample_rate)
        elif format.lower() == "mp3":
            bitrate = kwargs.get("bitrate", "192k")
            AudioExporter.export_mp3(audio_data, file_path, sample_rate, bitrate)
        elif format.lower() == "ogg":
            quality = kwargs.get("quality", 5)
            AudioExporter.export_ogg(audio_data, file_path, sample_rate, quality)
        else:
            raise ValueError(f"不支持的音频格式: {format}")

