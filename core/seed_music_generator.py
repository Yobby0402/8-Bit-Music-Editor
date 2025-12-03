"""
基于 Seed 的简单 8bit 音乐生成器（V3 规划的第一步）

目标：类似 Minecraft 的世界生成，用一个 seed 生成一段简单但可编辑的音乐。
当前实现：最小可用版本，只生成一个主旋律轨道，用于验证流程和可重复性。

重构版本：使用风格配置类系统，每个风格独立管理其生成逻辑。
"""

from typing import Union, List, Tuple, Optional, Dict, Callable
import random
from enum import Enum
from abc import ABC, abstractmethod

from .models import Project, Track, Note, WaveformType, ADSRParams, TrackType
from .track_events import DrumEvent, DrumType


class SeedMusicStyle(Enum):
    """Seed 生成音乐的风格类型"""
    CLASSIC_8BIT = "classic_8bit"   # 经典 8bit / FC 游戏风
    LOFI = "lofi"                   # 稍慢、柔和一点的节奏与音色
    BATTLE = "battle"               # 更紧张、偏战斗/Boss 的感觉
    SUSPENSE = "suspense"           # 悬疑 / 惊悚，阴郁、悬而未决
    CALM = "calm"                   # 舒缓 / 美好，明亮、治愈
    ROCK = "rock"                   # 重金属 / 摇滚，突出鼓点和打击乐
    DANCE = "dance"                 # 慢摇/舞曲，动感律动，适合跳舞
    WORKSHOP = "workshop"           # 工作坊 / 专注，Ambient Techno风格，适合工作研发


class StyleParams:
    """
    单一风格的参数配置（主要控制音色与动态，而非基础旋律结构）。
    后续如果要增加更多控制项，可以在这里扩展字段。
    """

    def __init__(
        self,
        melody_waveform: WaveformType,
        melody_duty: float,
        melody_adsr: ADSRParams,
        bass_waveform: WaveformType,
        bass_duty: float,
        bass_adsr: ADSRParams,
        harmony_waveform: WaveformType,
        harmony_duty: float,
        harmony_adsr: ADSRParams,
        drum_velocity_scale: float,
    ):
        self.melody_waveform = melody_waveform
        self.melody_duty = melody_duty
        self.melody_adsr = melody_adsr
        self.bass_waveform = bass_waveform
        self.bass_duty = bass_duty
        self.bass_adsr = bass_adsr
        self.harmony_waveform = harmony_waveform
        self.harmony_duty = harmony_duty
        self.harmony_adsr = harmony_adsr
        self.drum_velocity_scale = drum_velocity_scale


class MusicStyleConfig(ABC):
    """
    音乐风格配置基类。
    每个风格应该继承此类并实现所有抽象方法，定义该风格的生成逻辑。
    """
    
    def __init__(self, style: SeedMusicStyle, style_params: StyleParams):
        self.style = style
        self.style_params = style_params
    
    @abstractmethod
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        """
        返回该风格可选的音阶配置。
        返回: (根音MIDI, 调式名称, 音阶间隔列表)
        """
        pass
    
    @abstractmethod
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        """
        返回该风格的和弦进行模板。
        返回: [[和弦级数列表], ...]，例如 [[1, 5, 6, 4], [1, 4, 5, 1]]
        """
        pass
    
    @abstractmethod
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        """
        返回该风格的主旋律动机模式。
        返回: [[(相对度数, 拍长), ...], ...]
        """
        pass
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        """
        生成低音模式。
        返回: [(起始拍, 持续拍, 力度), ...]
        默认实现：每小节2个音（1、3拍）
        """
        return [(0.0, 2.0, 100), (2.0, 2.0, 100)]
    
    def get_harmony_chord_degrees(
        self,
        rng: random.Random,
        bar_root_degree: int,
        bar_idx: int,
        phrase_role: str,
        variant_id: Optional[str] = None,
        scale_offsets: Optional[List[int]] = None
    ) -> List[int]:
        """
        返回和声使用的音阶度数。
        默认实现：标准三和弦（1、3、5度）
        """
        scale_len = len(scale_offsets) if scale_offsets else 7
        return [
            bar_root_degree,
            (bar_root_degree + 2) % scale_len,
            (bar_root_degree + 4) % scale_len,
        ]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        """
        生成该小节的鼓点事件。
        返回: [DrumEvent, ...]
        默认实现：基础4/4拍（KICK在1、3拍，SNARE在2、4拍）
        """
        events = []
        
        # Intro部分的处理
        if phrase_role == "intro":
            half_intro = max(1, intro_bars // 2)
            if bar_idx < half_intro:
                return []  # 完全无鼓
            else:
                # 极简的弱底鼓
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 0.0,
                    duration_beats=0.25,
                    velocity=int(70 * self.style_params.drum_velocity_scale),
                ))
                return events
        
        # 安静小节处理（悬疑风格）
        if quiet_bars and bar_idx in quiet_bars:
            return []
        
        # 基础4/4拍
        events.append(DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=bar_start + 0.0,
            duration_beats=0.25,
            velocity=int(100 * self.style_params.drum_velocity_scale),
        ))
        events.append(DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=bar_start + 2.0,
            duration_beats=0.25,
            velocity=int(100 * self.style_params.drum_velocity_scale),
        ))
        events.append(DrumEvent(
            drum_type=DrumType.SNARE,
            start_beat=bar_start + 1.0,
            duration_beats=0.25,
            velocity=int(100 * self.style_params.drum_velocity_scale),
        ))
        events.append(DrumEvent(
            drum_type=DrumType.SNARE,
            start_beat=bar_start + 3.0,
            duration_beats=0.25,
            velocity=int(100 * self.style_params.drum_velocity_scale),
        ))
        return events
    
    def apply_melody_effects(self, melody_track: Track) -> None:
        """
        为主旋律轨道应用风格特定的效果（如滤波、颤音等）。
        默认实现：不应用任何效果。
        """
        pass
    
    def get_track_volumes(
        self,
        variant_id: Optional[str] = None
    ) -> Dict[str, float]:
        """
        返回各轨道的音量平衡。
        返回: {"melody": 1.0, "bass": 0.8, "harmony": 0.7, "drum_boost": 0.0}
        """
        return {
            "melody": 1.0,
            "bass": 0.8,
            "harmony": 0.7,
            "drum_boost": 0.0,
        }


def _build_style_params() -> dict:
    """
    定义各个风格下的默认音色与动态配置。
    这里不改变“音符落在哪一拍 / 音高怎么走”的基础旋律逻辑，
    只决定“用什么音色、力度、包络去说这句话”。
    """
    # 通用 ADSR 模板，便于少量调整
    # 原始主旋律用的是类似 soft_lead 的包络（attack 很短、sustain 较高），
    # 这里保留一份，避免战斗风格主旋律过于短促只剩“pop”。
    soft_lead_adsr = ADSRParams(attack=0.001, decay=0.05, sustain=0.8, release=0.1)
    soft_adsr = ADSRParams(attack=0.01, decay=0.15, sustain=0.8, release=0.25)
    pluck_adsr = ADSRParams(attack=0.001, decay=0.08, sustain=0.3, release=0.1)
    pad_adsr = ADSRParams(attack=0.02, decay=0.2, sustain=0.8, release=0.4)

    return {
        SeedMusicStyle.CLASSIC_8BIT: StyleParams(
            melody_waveform=WaveformType.SQUARE,
            melody_duty=0.5,
            melody_adsr=soft_lead_adsr,
            bass_waveform=WaveformType.TRIANGLE,
            bass_duty=0.5,
            bass_adsr=soft_adsr,
            harmony_waveform=WaveformType.SQUARE,
            harmony_duty=0.25,
            harmony_adsr=soft_adsr,
            drum_velocity_scale=1.0,
        ),
        SeedMusicStyle.LOFI: StyleParams(
            melody_waveform=WaveformType.SQUARE,
            melody_duty=0.35,
            melody_adsr=soft_adsr,
            bass_waveform=WaveformType.TRIANGLE,
            bass_duty=0.5,
            bass_adsr=pad_adsr,
            harmony_waveform=WaveformType.TRIANGLE,
            harmony_duty=0.5,
            harmony_adsr=pad_adsr,
            drum_velocity_scale=0.8,
        ),
        SeedMusicStyle.BATTLE: StyleParams(
            melody_waveform=WaveformType.SQUARE,
            melody_duty=0.25,
            melody_adsr=soft_lead_adsr,
            bass_waveform=WaveformType.SQUARE,
            bass_duty=0.5,
            bass_adsr=pluck_adsr,
            harmony_waveform=WaveformType.SAWTOOTH,
            harmony_duty=0.5,
            harmony_adsr=soft_adsr,
            drum_velocity_scale=1.0,
        ),
        SeedMusicStyle.SUSPENSE: StyleParams(
            melody_waveform=WaveformType.SAWTOOTH,
            melody_duty=0.2,
            melody_adsr=ADSRParams(attack=0.005, decay=0.18, sustain=0.4, release=0.2),
            bass_waveform=WaveformType.SQUARE,
            bass_duty=0.5,
            bass_adsr=ADSRParams(attack=0.005, decay=0.2, sustain=0.5, release=0.25),
            harmony_waveform=WaveformType.SAWTOOTH,
            harmony_duty=0.5,
            harmony_adsr=pad_adsr,
            drum_velocity_scale=0.8,  # 悬疑：鼓点整体偏弱，只做节奏背景
        ),
        SeedMusicStyle.CALM: StyleParams(
            melody_waveform=WaveformType.TRIANGLE,
            melody_duty=0.4,
            melody_adsr=ADSRParams(attack=0.01, decay=0.15, sustain=0.85, release=0.35),
            bass_waveform=WaveformType.TRIANGLE,
            bass_duty=0.5,
            bass_adsr=pad_adsr,
            harmony_waveform=WaveformType.SINE if hasattr(WaveformType, "SINE") else WaveformType.TRIANGLE,
            harmony_duty=0.5,
            harmony_adsr=pad_adsr,
            drum_velocity_scale=0.7,
        ),
        SeedMusicStyle.ROCK: StyleParams(
            # 摇滚：使用锯齿波和方波营造失真感
            melody_waveform=WaveformType.SAWTOOTH,  # 锯齿波有失真感
            melody_duty=0.5,
            melody_adsr=ADSRParams(attack=0.001, decay=0.1, sustain=0.7, release=0.15),  # 快速起音，中等sustain
            bass_waveform=WaveformType.SQUARE,  # 低音用方波，更硬
            bass_duty=0.5,
            bass_adsr=pluck_adsr,  # 短促的低音
            harmony_waveform=WaveformType.SAWTOOTH,  # 和声也用锯齿波
            harmony_duty=0.5,
            harmony_adsr=ADSRParams(attack=0.005, decay=0.12, sustain=0.75, release=0.2),
            drum_velocity_scale=1.3,  # 鼓点非常突出，力度放大30%
        ),
        SeedMusicStyle.DANCE: StyleParams(
            # 舞曲：动感律动，适合跳舞
            melody_waveform=WaveformType.SQUARE,  # 方波主旋律，清晰明亮
            melody_duty=0.5,
            melody_adsr=ADSRParams(attack=0.002, decay=0.08, sustain=0.75, release=0.12),  # 快速起音，保持律动
            bass_waveform=WaveformType.SQUARE,  # 低音用方波，厚重有力
            bass_duty=0.5,
            bass_adsr=ADSRParams(attack=0.001, decay=0.05, sustain=0.9, release=0.1),  # 低音持续，每拍踩点
            harmony_waveform=WaveformType.SQUARE,  # 和声也用方波，保持统一
            harmony_duty=0.4,
            harmony_adsr=ADSRParams(attack=0.01, decay=0.1, sustain=0.7, release=0.2),
            drum_velocity_scale=1.2,  # 鼓点突出，力度放大20%
        ),
        SeedMusicStyle.WORKSHOP: StyleParams(
            # 工作坊：Ambient Techno风格，平静专注，适合工作研发
            melody_waveform=WaveformType.SQUARE,  # 方波主旋律，电子感
            melody_duty=0.45,  # 稍薄，更电子感
            melody_adsr=ADSRParams(attack=0.01, decay=0.1, sustain=0.8, release=0.2),  # 中等起音，持续稳定
            bass_waveform=WaveformType.SQUARE,  # 低音用方波，稳定有力
            bass_duty=0.5,
            bass_adsr=ADSRParams(attack=0.005, decay=0.08, sustain=0.85, release=0.15),  # 低音持续稳定
            harmony_waveform=WaveformType.TRIANGLE,  # 和声用三角波，柔和背景
            harmony_duty=0.5,
            harmony_adsr=ADSRParams(attack=0.02, decay=0.15, sustain=0.75, release=0.3),  # Pad包络，柔和持续
            drum_velocity_scale=1.0,  # 鼓点清晰但不激烈
        ),
    }


STYLE_PARAMS_MAP = _build_style_params()

# 运行时风格参数覆盖（由 UI 调整，不影响默认常量）
RUNTIME_STYLE_OVERRIDES: dict = {}


def get_style_params(style: SeedMusicStyle) -> StyleParams:
    """
    对外暴露的风格参数访问接口：
    - 如果未来风格增加字段或新风格，只需要在 _build_style_params 里补充。
    - 生成逻辑只通过这个函数拿配置，避免到处写 if style == xxx。
    - 若存在运行时覆盖（来自 UI 的风格参数面板），优先使用覆盖值。
    """
    if style in RUNTIME_STYLE_OVERRIDES:
        return RUNTIME_STYLE_OVERRIDES[style]
    return STYLE_PARAMS_MAP.get(style, STYLE_PARAMS_MAP[SeedMusicStyle.CLASSIC_8BIT])


def set_style_runtime_override(style: SeedMusicStyle, params: StyleParams):
    """
    由 UI 调用，用于在运行时覆盖某个风格的音色/ADSR/鼓力度等参数。

    注意：
    - 这会影响后续所有该风格的 Seed 生成结果（直到重启或清除覆盖）。
    - Seed 的确定性仍然成立：同一版本下，相同 seed + 相同运行时参数 → 结果一致。
    """
    RUNTIME_STYLE_OVERRIDES[style] = params


def clear_style_runtime_override(style: SeedMusicStyle = None):
    """
    清除运行时风格参数覆盖。
    - 不传 style：清除全部覆盖；
    - 传入具体 style：仅清除该风格的覆盖。
    """
    if style is None:
        RUNTIME_STYLE_OVERRIDES.clear()
    else:
        RUNTIME_STYLE_OVERRIDES.pop(style, None)


# 基础风格元信息，用于 UI 展示与默认参数说明（不影响核心生成逻辑）
STYLE_META = {
    SeedMusicStyle.CLASSIC_8BIT: {
        "default_bpm": 120,
        "mood": "经典 8bit / 复古游戏感",
        "short_desc": "标准 8bit 方波主旋律 + 三角波低音，C 大调 / A 小调为主，节奏中速偏快。",
    },
    SeedMusicStyle.LOFI: {
        "default_bpm": 80,
        "mood": "放松 / 温柔 / 背景感",
        "short_desc": "中低音区、节奏偏慢，音色柔和、鼓点轻，适合作为安静背景或练习用配乐。",
    },
    SeedMusicStyle.BATTLE: {
        "default_bpm": 170,
        "mood": "紧张 / 战斗 / 高能",
        "short_desc": "高 BPM、主旋律短促重复、鼓点密集、低音强烈踩点，整体推动感很强，适合战斗或追逐场景。",
    },
    SeedMusicStyle.SUSPENSE: {
        "default_bpm": 125,
        "mood": "阴郁 / 不安 / 悬疑",
        "short_desc": "日式和风小调（类似 Hirajoshi / Phrygian），中高音区、半音抖动和三连击节奏，鼓点偏弱、多留白，营造紧张却克制的氛围。",
    },
    SeedMusicStyle.CALM: {
        "default_bpm": 90,
        "mood": "舒缓 / 明亮 / 治愈",
        "short_desc": "大调为主、和声走向稳定（I–IV–V–I 变体），音符更长、力度更柔和，鼓点简单稳定，适合温柔场景。",
    },
    SeedMusicStyle.ROCK: {
        "default_bpm": 150,
        "mood": "激烈 / 重金属 / 摇滚",
        "short_desc": "高 BPM、小调为主、主旋律简单重复、低音强烈每拍踩点、鼓点密集强烈（双踩、密集hi-hat），使用锯齿波和方波营造失真感，突出节奏和打击乐。",
    },
    SeedMusicStyle.DANCE: {
        "default_bpm": 130,
        "mood": "动感 / 律动 / House舞曲",
        "short_desc": "House舞曲风格，BPM 130、大调为主、主旋律简单重复易记、低音每拍踩点厚重有力、鼓点每小节两个'动次打次'（Kick-Snare-Kick-Snare），hi-hat在弱拍，结构：Intro（纯鼓点）→ Verse（基础旋律）→ 主旋律进入，适合跳舞和动感场景。",
    },
    SeedMusicStyle.WORKSHOP: {
        "default_bpm": 108,
        "mood": "平静 / 专注 / 技术感",
        "short_desc": "Ambient Techno风格，BPM 108、大调或中性调式、主旋律简单重复不干扰、低音每拍稳定踩点、鼓点清晰但不激烈（Kick每拍，Snare在2、4拍），hi-hat在弱拍，整体平静但有推进感，适合工作、研发、制作装备等专注场景。",
    },
}


# ==================== 风格配置类实现 ====================

class Classic8bitStyleConfig(MusicStyleConfig):
    """经典 8bit 风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (57, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # A 小调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [1, 5, 6, 4],  # I–V–vi–IV
            [1, 4, 5, 1],  # I–IV–V–I
            [1, 6, 4, 5],  # I–vi–IV–V
            [1, 5, 1, 4],  # I–V–I–IV
            [1, 4, 1, 5],  # I–IV–I–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        return [
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 强-中-强，4 拍
            [(4, 1.0), (2, 1.0), (0, 2.0)],  # 下行回答
            [(0, 0.5), (4, 0.5), (5, 1.0), (4, 1.0), (2, 1.0)],  # 跳进 + 级进
            [(0, 0.5), (1, 0.5), (0, 0.5), (1, 0.5), (2, 2.0)],  # 短音型重复
            [(0, 0.5), (2, 0.5), (4, 0.5), (2, 0.5), (0, 2.0)],  # 上行-下行
            [(0, 1.0), (4, 1.0), (0, 2.0)],  # 根音-五度-根音
            [(2, 0.5), (4, 0.5), (5, 0.5), (4, 0.5), (2, 0.5), (0, 1.5)],  # 级进上行-下行
            [(0, 0.5), (0, 0.5), (2, 0.5), (2, 0.5), (4, 2.0)],  # 重复音型上行
            [(4, 0.5), (5, 0.5), (4, 0.5), (2, 0.5), (0, 2.0)],  # 五度-六度-五度-三度-根音
            [(0, 1.0), (1, 0.5), (2, 0.5), (4, 2.0)],  # 级进上行到五度
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 经典8bit：多种低音模式变化
        if variant_id == "classic_8bit_bass_heavy":
            # 重低音变体：每拍都有
            return [
                (0.0, 0.5, 110),
                (1.0, 0.5, 100),
                (2.0, 0.5, 110),
                (3.0, 0.5, 100),
            ]
        elif variant_id == "classic_8bit_bass_simple":
            # 简单变体：只在强拍
            return [(0.0, 2.0, 100), (2.0, 2.0, 100)]
        else:
            # 默认：根据小节位置变化
            if bar_idx % 2 == 0:
                # 偶数小节：根音-五度交替
                fifth_degree = (bar_root_degree + 4) % len(scale_offsets)
                return [
                    (0.0, 2.0, 100),  # 根音
                    (2.0, 2.0, 100),  # 五度
                ]
            else:
                # 奇数小节：根音持续
                return [(0.0, beats_per_bar, 100)]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分处理
        if phrase_role == "intro":
            half_intro = max(1, intro_bars // 2)
            if bar_idx < half_intro:
                return []
            else:
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 0.0,
                    duration_beats=0.25,
                    velocity=int(70 * self.style_params.drum_velocity_scale),
                ))
                return events
        
        # 经典8bit：简单清晰的4/4拍，根据乐句角色调整
        if phrase_role in ("statement", "question"):
            # 起/问：标准4/4
            kick_beats = [0.0, 2.0]
            snare_beats = [1.0, 3.0]
        elif phrase_role in ("development", "answer"):
            # 承/答：稍微加强
            kick_beats = [0.0, 2.0]
            snare_beats = [1.0, 3.0]
        elif phrase_role == "variation":
            # 转：更密集
            kick_beats = [0.0, 1.5, 2.0, 3.5]
            snare_beats = [1.0, 3.0]
        else:  # resolution
            # 合：回归标准
            kick_beats = [0.0, 2.0]
            snare_beats = [1.0, 3.0]
        
        # 底鼓
        for k in kick_beats:
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + k,
                duration_beats=0.25,
                velocity=int(100 * self.style_params.drum_velocity_scale),
            ))
        
        # 军鼓
        for s in snare_beats:
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + s,
                duration_beats=0.25,
                velocity=int(100 * self.style_params.drum_velocity_scale),
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "classic_8bit_bass_heavy":
            return {"melody": 0.9, "bass": 1.0, "harmony": 0.7, "drum_boost": 0.0}
        elif variant_id == "classic_8bit_bass_simple":
            return {"melody": 1.0, "bass": 0.7, "harmony": 0.7, "drum_boost": 0.0}
        else:
            return {"melody": 1.0, "bass": 0.8, "harmony": 0.7, "drum_boost": 0.0}


class LofiStyleConfig(MusicStyleConfig):
    """Lofi 风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        scale_choices = [
            (57, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # A 大调
            (55, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # G 小调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [1, 6, 4, 5],  # I–vi–IV–V
            [1, 4, 1, 5],  # I–IV–I–V
            [1, 6, 2, 5],  # I–vi–ii–V
            [1, 3, 6, 4],  # I–iii–vi–IV
            [1, 4, 6, 5],  # I–IV–vi–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # Lofi：更柔和、更连贯的动机
        return [
            [(0, 1.5), (2, 1.0), (4, 1.5)],  # 更长音值
            [(0, 2.0), (2, 2.0)],  # 简单两音
            [(4, 1.0), (2, 1.5), (0, 1.5)],  # 下行
            [(0, 1.0), (1, 1.0), (2, 2.0)],  # 级进上行
            [(0, 2.0), (4, 2.0)],  # 根音-五度
            [(2, 1.0), (4, 1.0), (5, 1.0), (4, 1.0)],  # 三度-五度-六度-五度
            [(0, 1.0), (2, 1.5), (0, 1.5)],  # 根音-三度-根音
            [(4, 1.0), (2, 1.0), (1, 1.0), (0, 1.0)],  # 五度下行级进
            [(0, 1.5), (4, 1.0), (2, 1.5)],  # 根音-五度-三度
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # Lofi：更长的低音，多种变化
        if variant_id == "lofi_slower":
            # 更慢变体：整小节持续
            return [(0.0, beats_per_bar, 100)]
        elif variant_id == "lofi_warm":
            # 温暖变体：根音-五度交替
            fifth_degree = (bar_root_degree + 4) % len(scale_offsets)
            return [
                (0.0, 2.0, 100),
                (2.0, 2.0, 100),
            ]
        else:
            # 默认：30%整小节，70%两拍
            if rng.random() < 0.3:
                return [(0.0, beats_per_bar, 100)]
            else:
                return [(0.0, 2.0, 100), (2.0, 2.0, 100)]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分处理
        if phrase_role == "intro":
            if bar_idx < intro_bars:
                return []
        
        # Lofi：轻、稀疏的鼓点，Shuffle节奏感
        # 只在强拍（1和3拍）有底鼓
        if rng.random() < 0.8:  # 80%概率有底鼓
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + 0.0,
                duration_beats=0.25,
                velocity=int(70 * self.style_params.drum_velocity_scale),
            ))
        
        if rng.random() < 0.6:  # 60%概率在第3拍有底鼓
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + 2.0,
                duration_beats=0.25,
                velocity=int(65 * self.style_params.drum_velocity_scale),
            ))
        
        # 偶尔有军鼓（30%概率）
        if rng.random() < 0.3:
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + 2.0,
                duration_beats=0.25,
                velocity=int(60 * self.style_params.drum_velocity_scale),
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "lofi_slower":
            return {"melody": 0.85, "bass": 0.7, "harmony": 0.6, "drum_boost": -0.15}
        elif variant_id == "lofi_warm":
            return {"melody": 0.9, "bass": 0.8, "harmony": 0.7, "drum_boost": -0.1}
        else:
            return {
                "melody": 0.9,
                "bass": 0.75,
                "harmony": 0.65,
                "drum_boost": -0.1,
            }


class BattleStyleConfig(MusicStyleConfig):
    """战斗/紧张风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        scale_choices = [
            (60, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # C 小调
            (62, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # D 小调
            (59, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # B 小调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [6, 4, 1, 5],  # vi–IV–I–V（更紧张）
            [1, 5, 6, 5],  # I–V–vi–V
            [1, 4, 6, 5],  # I–IV–vi–V
            [6, 1, 4, 5],  # vi–I–IV–V
            [1, 6, 4, 5],  # I–vi–IV–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 战斗：短促重复的动机
        return [
            [(0, 0.5), (0, 0.5), (2, 1.0), (0, 2.0)],  # 短促重复
            [(0, 0.5), (4, 0.5), (0, 0.5), (4, 0.5), (2, 2.0)],  # 根音-五度快速重复
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 上行跳进
            [(0, 0.5), (2, 0.5), (0, 0.5), (2, 0.5), (4, 2.0)],  # 根音-三度快速重复-五度
            [(4, 0.5), (0, 0.5), (4, 0.5), (0, 0.5), (2, 2.0)],  # 五度-根音快速重复-三度
            [(0, 0.5), (4, 0.5), (2, 0.5), (0, 0.5), (4, 2.0)],  # 根音-五度-三度-根音-五度
            [(0, 1.0), (4, 1.0), (0, 2.0)],  # 根音-五度-根音
            [(2, 0.5), (4, 0.5), (2, 0.5), (0, 0.5), (2, 2.0)],  # 三度-五度-三度-根音-三度
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 战斗：根据乐句角色调整低音密度
        if variant_id == "battle_melody":
            # 偏旋律：低音稍微稀疏
            return [
                (0.0, 0.5, 110),
                (2.0, 0.5, 110),
            ]
        elif variant_id == "battle_drums":
            # 偏鼓点：低音更密集
            return [
                (0.0, 0.5, 125),
                (1.0, 0.5, 120),
                (2.0, 0.5, 125),
                (3.0, 0.5, 120),
            ]
        else:
            # 默认：每拍都有短促的低音
            return [
                (0.0, 0.5, 120),
                (1.0, 0.5, 120),
                (2.0, 0.5, 120),
                (3.0, 0.5, 120),
            ]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        base_kick_vel = 125
        base_snare_vel = 120
        base_hihat_vel = 80
        
        # 根据乐句角色调整
        if phrase_role == "statement":
            kick_beats = [0.0, 2.0]
            hihat_density = 0.5
        elif phrase_role == "development":
            kick_beats = [0.0, 1.0, 2.0, 3.0]
            base_kick_vel = 130
            hihat_density = 0.75
        elif phrase_role == "variation":
            kick_beats = [0.0, 1.0, 2.0, 3.0]
            base_kick_vel = 135
            base_snare_vel = 125
            hihat_density = 1.0
        elif phrase_role == "resolution":
            kick_beats = [0.0, 2.0]
            base_kick_vel = 130
            hihat_density = 0.6
        else:
            kick_beats = [0.0, 2.0] if phrase_role == "question" else [0.0, 1.0, 2.0, 3.0]
            hihat_density = 0.7
        
        # 底鼓
        for k in kick_beats:
            vel_mult = 1.1 if is_phrase_end else 1.0
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + k,
                duration_beats=0.25,
                velocity=int(base_kick_vel * vel_mult * self.style_params.drum_velocity_scale),
            ))
        
        # 军鼓
        if phrase_role in ("variation", "resolution"):
            snare_beats = [1.0, 3.0]
        else:
            snare_beats = [1.0, 3.0] if phrase_progress > 0.5 else [1.0]
        
        for s in snare_beats:
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + s,
                duration_beats=0.25,
                velocity=int(base_snare_vel * self.style_params.drum_velocity_scale),
            ))
        
        # Hi-hat
        if hihat_density >= 1.0:
            hihat_beats = [i * 0.25 for i in range(0, 16)]
        elif hihat_density >= 0.8:
            hihat_beats = [i * 0.5 for i in range(0, 8)]
        else:
            hihat_beats = [i * 0.5 for i in range(0, 4)]
        
        for h in hihat_beats:
            events.append(DrumEvent(
                drum_type=DrumType.HIHAT,
                start_beat=bar_start + h,
                duration_beats=0.25,
                velocity=int(base_hihat_vel * self.style_params.drum_velocity_scale),
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "battle_melody":
            return {"melody": 1.0, "bass": 0.8, "harmony": 0.7, "drum_boost": -0.2}
        elif variant_id == "battle_drums":
            return {"melody": 0.8, "bass": 0.9, "harmony": 0.7, "drum_boost": 0.2}
        else:
            return {"melody": 0.95, "bass": 0.85, "harmony": 0.7, "drum_boost": 0.0}


class SuspenseStyleConfig(MusicStyleConfig):
    """悬疑/惊悚风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        # 日本和风小调（类似 Hirajoshi）
        japanese_offsets = [0, 1, 5, 7, 10, 12, 13, 17]
        scale_choices = [
            (62, "japanese_like", japanese_offsets),  # D4 附近
            (64, "japanese_like", japanese_offsets),  # E4 附近
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [6, 2, 5, 1],  # vi–ii–V–I
            [1, 2, 6, 5],  # I–ii–vi–V
            [1, 6, 2, 5],  # I–vi–ii–V
            [6, 1, 2, 5],  # vi–I–ii–V
            [2, 6, 1, 5],  # ii–vi–I–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 悬疑：短音与"抖动"型动机
        return [
            # 8 个八分音符，围绕 0 / +1 / -1 抖动
            [(0, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5),
             (0, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5)],
            # 前半段碎音，后半段拉长悬挂
            [(0, 0.5), (2, 0.5), (1, 0.5), (0, 0.5),
             (0, 1.0), (2, 1.0)],
            # 由高向下的阴郁走向
            [(2, 1.0), (0, 0.5), (1, 0.5), (0, 1.0), (-2, 1.0)],
            # 半音抖动上行
            [(0, 0.5), (1, 0.5), (2, 0.5), (1, 0.5), (0, 2.0)],
            # 突然跳进下行
            [(2, 0.5), (0, 1.0), (-1, 0.5), (0, 2.0)],
            # 长音悬挂
            [(0, 1.0), (1, 0.5), (0, 2.5)],
            # 半音抖动下行
            [(2, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5), (0, 2.0)],
            # 快速抖动后长音
            [(0, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5), (0, 2.0)],
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 悬疑：根据变体调整低音模式
        if variant_id == "suspense_dense":
            # 更紧张：低音稍微密集一些
            return [
                (0.0, 1.0, 100),
                (2.0, 1.0, 100),
            ]
        elif variant_id == "suspense_sparse":
            # 更空灵：低音更稀疏
            if rng.random() < 0.5:
                return [(0.0, 1.0, 90)]
            else:
                return []
        else:
            # 默认：偏重 1、3 拍，但时值较短
            # 偶尔使用根音-五度交替增加不稳定性
            if rng.random() < 0.3:
                fifth_degree = (bar_root_degree + 4) % len(scale_offsets)
                return [
                    (0.0, 1.0, 100),
                    (2.0, 1.0, 95),
                ]
            else:
                return [(0.0, 1.0, 100), (2.0, 1.0, 100)]
    
    def get_harmony_chord_degrees(
        self,
        rng: random.Random,
        bar_root_degree: int,
        bar_idx: int,
        phrase_role: str,
        variant_id: Optional[str] = None,
        scale_offsets: Optional[List[int]] = None
    ) -> List[int]:
        # 悬疑：使用"恐怖和弦"模板
        horror_templates = [
            [0, 1, 4],  # 1, ♭2, 5
            [0, 3, 6],  # 1, 4, ♭7
            [1, 4, 6],  # ♭2, 5, ♭7
        ]
        tmpl = rng.choice(horror_templates)
        chord_degrees = []
        scale_len = len(scale_offsets) if scale_offsets else 8  # 默认日本小调音阶长度
        for rel in tmpl:
            idx = (bar_root_degree + rel) % scale_len
            chord_degrees.append(idx)
        return chord_degrees
    
    def apply_melody_effects(self, melody_track: Track) -> None:
        # 悬疑：添加高通滤波和颤音
        from .effect_processor import FilterParams, FilterType, VibratoParams
        melody_track.filter_params = FilterParams(
            filter_type=FilterType.HIGHPASS,
            cutoff_frequency=600.0,
            resonance=1.2,
            enabled=True,
        )
        melody_track.vibrato_params = VibratoParams(
            rate=6.0,
            depth=0.4,
            enabled=True,
        )
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "suspense_dense":
            return {"melody": 1.0, "bass": 0.75, "harmony": 0.5, "drum_boost": 0.1}
        elif variant_id == "suspense_sparse":
            return {"melody": 1.0, "bass": 0.5, "harmony": 0.35, "drum_boost": -0.15}
        else:
            return {"melody": 1.0, "bass": 0.65, "harmony": 0.45, "drum_boost": 0.0}


class CalmStyleConfig(MusicStyleConfig):
    """舒缓/美好风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (65, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # F 大调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [1, 4, 1, 5],  # I–IV–I–V
            [1, 4, 5, 1],  # I–IV–V–I
            [1, 6, 4, 5],  # I–vi–IV–V
            [1, 3, 6, 4],  # I–iii–vi–IV
            [1, 4, 6, 5],  # I–IV–vi–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 舒缓：更长音值、更少跳进
        return [
            [(0, 2.0), (2, 2.0)],  # I → Ⅲ，整小节两音
            [(0, 1.0), (1, 1.0), (2, 2.0)],  # 1-2-3，级进上行
            [(2, 2.0), (0, 2.0)],  # Ⅲ → I
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 级进上行到五度
            [(0, 2.0), (4, 2.0)],  # 根音-五度
            [(2, 1.0), (4, 1.0), (5, 1.0), (4, 1.0)],  # 三度-五度-六度-五度
            [(0, 1.5), (2, 1.0), (0, 1.5)],  # 根音-三度-根音
            [(4, 1.0), (2, 1.0), (1, 1.0), (0, 1.0)],  # 五度下行级进
            [(0, 1.0), (1, 1.0), (2, 1.0), (4, 1.0)],  # 级进上行
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 舒缓：根据变体调整低音模式
        if variant_id == "calm_slower":
            # 更慢：整小节持续
            return [(0.0, beats_per_bar, 100)]
        elif variant_id == "calm_brighter":
            # 更明亮：偶尔根音-三度交替
            if rng.random() < 0.3:
                third_degree = (bar_root_degree + 2) % len(scale_offsets)
                return [
                    (0.0, 2.0, 100),
                    (2.0, 2.0, 95),
                ]
            else:
                return [(0.0, beats_per_bar, 100)]
        else:
            # 默认：更长的根音
            return [(0.0, beats_per_bar, 100)]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分处理
        if phrase_role == "intro":
            if bar_idx < intro_bars:
                return []
        
        # 舒缓：非常轻、简单的鼓点
        # 只在强拍（1拍）有底鼓，30%概率
        if rng.random() < 0.3:
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + 0.0,
                duration_beats=0.25,
                velocity=int(50 * self.style_params.drum_velocity_scale),
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "calm_slower":
            return {"melody": 0.85, "bass": 0.75, "harmony": 0.55, "drum_boost": -0.15}
        elif variant_id == "calm_brighter":
            return {"melody": 0.95, "bass": 0.85, "harmony": 0.65, "drum_boost": -0.1}
        else:
            return {"melody": 0.9, "bass": 0.8, "harmony": 0.6, "drum_boost": -0.1}
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        return {"melody": 0.9, "bass": 0.8, "harmony": 0.6, "drum_boost": -0.1}


class RockStyleConfig(MusicStyleConfig):
    """重金属/摇滚风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        scale_choices = [
            (64, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # E 小调
            (57, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # A 小调
            (62, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # D 小调
            (60, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # C 小调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        return [
            [1, 4, 5, 1],  # I–IV–V–I（经典摇滚）
            [1, 5, 6, 4],  # I–V–vi–IV
            [6, 4, 1, 5],  # vi–IV–I–V
            [1, 4, 6, 5],  # I–IV–vi–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 摇滚：简单重复的动机
        return [
            [(0, 1.0), (4, 1.0), (0, 2.0)],  # 根音-五度-根音
            [(0, 0.5), (0, 0.5), (2, 1.0), (0, 2.0)],  # 短促重复
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 上行跳进
            [(0, 1.0), (1, 1.0), (2, 2.0)],  # 简单级进
            [(0, 0.5), (4, 0.5), (0, 0.5), (4, 0.5), (0, 2.0)],  # 根音-五度快速重复
            [(4, 1.0), (0, 1.0), (4, 2.0)],  # 五度-根音-五度
            [(0, 1.0), (2, 0.5), (4, 0.5), (2, 2.0)],  # 根音-三度-五度-三度
            [(0, 0.5), (2, 0.5), (0, 0.5), (2, 0.5), (4, 2.0)],  # 根音-三度快速重复-五度
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 摇滚：根据乐句角色调整低音模式
        # 在variation阶段（Solo），低音会简化（在主生成逻辑中处理）
        # 这里处理正常部分
        if variant_id == "rock_heavier":
            # 更重：每拍都有低音
            return [
                (0.0, 1.0, 110),
                (1.0, 1.0, 105),
                (2.0, 1.0, 110),
                (3.0, 1.0, 105),
            ]
        else:
            # 默认：低音更连贯，使用长持续音
            if rng.random() < 0.3:
                return [(0.0, beats_per_bar, 100)]  # 30%概率：整个小节一个长音
            else:
                return [(0.0, 2.0, 100), (2.0, 2.0, 100)]  # 70%概率：前2拍和后2拍各一个长音
    
    def get_harmony_chord_degrees(
        self,
        rng: random.Random,
        bar_root_degree: int,
        bar_idx: int,
        phrase_role: str,
        variant_id: Optional[str] = None,
        scale_offsets: Optional[List[int]] = None
    ) -> List[int]:
        # 摇滚：使用强力和弦（Power Chord），只有根音和五度
        scale_len = len(scale_offsets) if scale_offsets else 7
        if phrase_role == "variation":  # Solo阶段
            return [bar_root_degree, (bar_root_degree + 4) % scale_len]
        else:
            # 正常阶段：强力和弦（根音 + 五度 + 八度可选）
            chord_degrees = [
                bar_root_degree,
                (bar_root_degree + 4) % scale_len,
            ]
            # 可选：添加八度
            if rng.random() < 0.5:
                octave_degree = (bar_root_degree + 7) % scale_len
                if octave_degree < scale_len:  # 确保在音阶范围内
                    chord_degrees.append(octave_degree)
            return list(dict.fromkeys(chord_degrees))  # 去重
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分：纯鼓开头
        if phrase_role == "intro":
            half_intro = max(1, intro_bars // 2)
            if bar_idx < half_intro:
                return []  # 完全无鼓
            else:
                # 极简的弱底鼓
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 0.0,
                    duration_beats=0.25,
                    velocity=int(70 * self.style_params.drum_velocity_scale),
                ))
                return events
        
        # 正常部分：根据乐句角色调整
        if phrase_role == "development":
            # 添加双踩
            for beat in [0.0, 1.0, 2.0, 3.0]:
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + beat,
                    duration_beats=0.25,
                    velocity=int(120 * self.style_params.drum_velocity_scale),
                ))
        elif phrase_role == "variation":
            # Solo阶段：三连踩、同步踩
            for beat in [0.0, 1.0, 2.0, 3.0]:
                # 三连踩
                for i in range(3):
                    events.append(DrumEvent(
                        drum_type=DrumType.KICK,
                        start_beat=bar_start + beat + i * 0.33,
                        duration_beats=0.25,
                        velocity=int(125 * self.style_params.drum_velocity_scale),
                    ))
                # 同步踩
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + beat + 0.5,
                    duration_beats=0.25,
                    velocity=int(115 * self.style_params.drum_velocity_scale),
                ))
            # 额外军鼓
            for s in [1.0, 2.5, 3.0]:
                events.append(DrumEvent(
                    drum_type=DrumType.SNARE,
                    start_beat=bar_start + s,
                    duration_beats=0.25,
                    velocity=int(120 * self.style_params.drum_velocity_scale),
                ))
            # 密集hi-hat（十六分音符）
            for i in range(16):
                events.append(DrumEvent(
                    drum_type=DrumType.HIHAT,
                    start_beat=bar_start + i * 0.25,
                    duration_beats=0.25,
                    velocity=int(80 * self.style_params.drum_velocity_scale),
                ))
            # 乐句结尾：鼓点填充
            if is_phrase_end:
                for i in range(4, 8):
                    events.append(DrumEvent(
                        drum_type=DrumType.SNARE,
                        start_beat=bar_start + i * 0.25,
                        duration_beats=0.25,
                        velocity=int(100 + i * 5 * self.style_params.drum_velocity_scale),
                    ))
                events.append(DrumEvent(
                    drum_type=DrumType.CRASH,
                    start_beat=bar_start + 4.0,
                    duration_beats=0.5,
                    velocity=int(110 * self.style_params.drum_velocity_scale),
                ))
        elif phrase_role == "resolution":
            # 合：添加吊镲
            events.append(DrumEvent(
                drum_type=DrumType.CRASH,
                start_beat=bar_start + 0.0,
                duration_beats=0.5,
                velocity=int(105 * self.style_params.drum_velocity_scale),
            ))
        
        # 基础底鼓和军鼓（如果还没有添加）
        if not any(e.drum_type == DrumType.KICK for e in events):
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + 0.0,
                duration_beats=0.25,
                velocity=int(120 * self.style_params.drum_velocity_scale),
            ))
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + 2.0,
                duration_beats=0.25,
                velocity=int(120 * self.style_params.drum_velocity_scale),
            ))
        
        if not any(e.drum_type == DrumType.SNARE for e in events):
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + 1.0,
                duration_beats=0.25,
                velocity=int(115 * self.style_params.drum_velocity_scale),
            ))
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + 3.0,
                duration_beats=0.25,
                velocity=int(115 * self.style_params.drum_velocity_scale),
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        if variant_id == "rock_heavier":
            return {"melody": 0.8, "bass": 1.1, "harmony": 0.7, "drum_boost": 0.35}
        else:
            return {"melody": 0.85, "bass": 1.0, "harmony": 0.75, "drum_boost": 0.3}


class WorkshopStyleConfig(MusicStyleConfig):
    """工作坊/专注风格配置 - Ambient Techno风格"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        # 工作坊：大调或中性调式，平静专注
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (65, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # F 大调
            (57, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # A 小调（中性）
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        # 工作坊：简单稳定的和弦进行
        return [
            [1, 4, 5, 1],  # I–IV–V–I（稳定循环）
            [1, 6, 4, 5],  # I–vi–IV–V（柔和）
            [1, 4, 1, 5],  # I–IV–I–V（简单）
            [1, 5, 1, 4],  # I–V–I–IV（稳定）
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 工作坊：简单重复，不干扰，长音值
        return [
            [(0, 2.0), (2, 2.0)],  # 根音-三度，长音
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 级进上行到五度
            [(0, 2.0), (4, 2.0)],  # 根音-五度
            [(2, 1.0), (4, 1.0), (2, 2.0)],  # 三度-五度-三度
            [(0, 1.0), (1, 1.0), (2, 2.0)],  # 级进上行
            [(0, 1.5), (2, 1.0), (0, 1.5)],  # 根音-三度-根音
            [(4, 1.0), (2, 1.0), (0, 2.0)],  # 五度-三度-根音，下行
            [(0, 1.0), (4, 1.0), (0, 2.0)],  # 根音-五度-根音
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 工作坊：每拍稳定踩点，提供推进感
        return [
            (0.0, 0.5, 100),  # 第1拍
            (1.0, 0.5, 95),   # 第2拍，稍轻
            (2.0, 0.5, 100),  # 第3拍
            (3.0, 0.5, 95),   # 第4拍，稍轻
        ]
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分处理
        if phrase_role == "intro":
            half_intro = max(1, intro_bars // 2)
            if bar_idx < half_intro:
                return []  # 完全无鼓
            else:
                # 极简的弱底鼓
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 0.0,
                    duration_beats=0.25,
                    velocity=int(70 * self.style_params.drum_velocity_scale),
                ))
                return events
        
        # 工作坊：Ambient Techno风格 - Kick每拍，Snare在2、4拍，清晰但不激烈
        # Kick：每拍都有，提供稳定节奏
        for k in [0.0, 1.0, 2.0, 3.0]:
            events.append(DrumEvent(
                drum_type=DrumType.KICK,
                start_beat=bar_start + k,
                duration_beats=0.3,  # 稍短，清晰
                velocity=int(100 * self.style_params.drum_velocity_scale),  # 清晰但不激烈
            ))
        
        # Snare：在2、4拍，清晰但不重
        for s in [1.0, 3.0]:
            events.append(DrumEvent(
                drum_type=DrumType.SNARE,
                start_beat=bar_start + s,
                duration_beats=0.3,
                velocity=int(95 * self.style_params.drum_velocity_scale),  # 清晰但不重
            ))
        
        # Hi-hat：在弱拍位置（0.5, 1.5, 2.5, 3.5），增加律动感
        for h in [0.5, 1.5, 2.5, 3.5]:
            events.append(DrumEvent(
                drum_type=DrumType.HIHAT,
                start_beat=bar_start + h,
                duration_beats=0.25,
                velocity=int(60 * self.style_params.drum_velocity_scale),  # 轻，作为填充
            ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        # 工作坊：鼓点清晰，主旋律和和声适中，不干扰工作
        return {"melody": 0.8, "bass": 0.85, "harmony": 0.65, "drum_boost": 0.1}


class DanceStyleConfig(MusicStyleConfig):
    """慢摇/舞曲风格配置"""
    
    def get_scale_choices(self, rng: random.Random) -> Tuple[int, str, List[int]]:
        # 舞曲：大调为主，明亮动感
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (65, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # F 大调
            (67, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # G 大调
            (62, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # D 大调
        ]
        return rng.choice(scale_choices)
    
    def get_chord_progression_templates(self, rng: random.Random) -> List[List[int]]:
        # 舞曲：经典流行和弦进行
        return [
            [1, 5, 6, 4],  # I–V–vi–IV（最经典的流行进行）
            [1, 4, 5, 1],  # I–IV–V–I（经典摇滚进行）
            [1, 6, 4, 5],  # I–vi–IV–V
            [6, 4, 1, 5],  # vi–IV–I–V
        ]
    
    def get_melody_motifs(self, rng: random.Random, variant_id: Optional[str] = None) -> List[List[Tuple[int, float]]]:
        # 舞曲：简单重复、易记的动机
        return [
            [(0, 1.0), (2, 1.0), (4, 2.0)],  # 根音-三度-五度，简单上行
            [(0, 0.5), (0, 0.5), (2, 1.0), (0, 2.0)],  # 短促重复，强调根音
            [(0, 1.0), (4, 1.0), (2, 1.0), (0, 1.0)],  # 根音-五度-三度-根音，循环
            [(0, 1.0), (1, 1.0), (2, 2.0)],  # 简单级进上行
            [(4, 1.0), (2, 1.0), (0, 2.0)],  # 五度-三度-根音，下行
        ]
    
    def get_bass_pattern(
        self, 
        rng: random.Random, 
        bar_idx: int, 
        bar_root_degree: int, 
        root_midi: int, 
        scale_offsets: List[int],
        beats_per_bar: float,
        beat_duration: float,
        variant_id: Optional[str] = None
    ) -> List[Tuple[float, float, int]]:
        # 舞曲：低音每拍踩点，厚重有力
        # 强拍（1和3）更重，弱拍（2和4）稍轻
        if rng.random() < 0.7:
            # 70%概率：每拍都有低音
            return [
                (0.0, 0.5, 110),  # 第1拍，强拍，力度大
                (1.0, 0.5, 100),  # 第2拍，弱拍
                (2.0, 0.5, 110),  # 第3拍，强拍，力度大
                (3.0, 0.5, 100),  # 第4拍，弱拍
            ]
        else:
            # 30%概率：只在强拍（1和3）
            return [
                (0.0, 1.0, 110),  # 第1拍，长音
                (2.0, 1.0, 110),  # 第3拍，长音
            ]
    
    def get_harmony_chord_degrees(
        self,
        rng: random.Random,
        bar_root_degree: int,
        bar_idx: int,
        phrase_role: str,
        variant_id: Optional[str] = None,
        scale_offsets: Optional[List[int]] = None
    ) -> List[int]:
        # 舞曲：使用三和弦（根音+三度+五度），明亮和谐
        scale_len = len(scale_offsets) if scale_offsets else 7
        chord_degrees = [
            bar_root_degree,  # 根音
            (bar_root_degree + 2) % scale_len,  # 三度
            (bar_root_degree + 4) % scale_len,  # 五度
        ]
        # 可选：添加八度增加厚度
        if rng.random() < 0.4:
            octave_degree = (bar_root_degree + 7) % scale_len
            if octave_degree < scale_len:
                chord_degrees.append(octave_degree)
        return list(dict.fromkeys(chord_degrees))  # 去重
    
    def generate_drum_pattern(
        self,
        rng: random.Random,
        bar_idx: int,
        bar_start: float,
        phrase_role: str,
        phrase_progress: float,
        is_phrase_end: bool,
        beats_per_bar: float,
        variant_id: Optional[str] = None,
        intro_bars: int = 0,
        quiet_bars: Optional[set] = None
    ) -> List[DrumEvent]:
        events = []
        
        # Intro部分：纯鼓点开头（1-2小节）- House风格"动次打次"模式（每小节两个循环）
        if phrase_role == "intro":
            if bar_idx < min(2, intro_bars):
                # 前1-2小节：House风格，每小节两个"动次打次"
                # 第一个"动次打次"：Kick(1拍) - Snare(2拍)
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 0.0,
                    duration_beats=0.4,  # 稍短，更紧凑
                    velocity=int(150 * self.style_params.drum_velocity_scale),  # 非常重
                ))
                events.append(DrumEvent(
                    drum_type=DrumType.SNARE,
                    start_beat=bar_start + 1.0,
                    duration_beats=0.4,
                    velocity=int(145 * self.style_params.drum_velocity_scale),  # 非常重
                ))
                # 第二个"动次打次"：Kick(3拍) - Snare(4拍)
                events.append(DrumEvent(
                    drum_type=DrumType.KICK,
                    start_beat=bar_start + 2.0,
                    duration_beats=0.4,
                    velocity=int(150 * self.style_params.drum_velocity_scale),  # 非常重
                ))
                events.append(DrumEvent(
                    drum_type=DrumType.SNARE,
                    start_beat=bar_start + 3.0,
                    duration_beats=0.4,
                    velocity=int(145 * self.style_params.drum_velocity_scale),  # 非常重
                ))
                # Hi-hat在弱拍位置（0.5, 1.5, 2.5, 3.5）
                for h in [0.5, 1.5, 2.5, 3.5]:
                    events.append(DrumEvent(
                        drum_type=DrumType.HIHAT,
                        start_beat=bar_start + h,
                        duration_beats=0.25,
                        velocity=int(70 * self.style_params.drum_velocity_scale),
                    ))
                return events
        
        # 正常部分：House风格 - 每小节两个"动次打次"（Kick-Snare-Kick-Snare）
        # 第一个"动次打次"：Kick(1拍) - Snare(2拍)
        events.append(DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=bar_start + 0.0,
            duration_beats=0.4,  # 稍短，更紧凑有力
            velocity=int(155 * self.style_params.drum_velocity_scale),  # 非常重，突出"动"
        ))
        events.append(DrumEvent(
            drum_type=DrumType.SNARE,
            start_beat=bar_start + 1.0,
            duration_beats=0.4,
            velocity=int(150 * self.style_params.drum_velocity_scale),  # 非常重，突出"打"
        ))
        
        # 第二个"动次打次"：Kick(3拍) - Snare(4拍)
        events.append(DrumEvent(
            drum_type=DrumType.KICK,
            start_beat=bar_start + 2.0,
            duration_beats=0.4,
            velocity=int(155 * self.style_params.drum_velocity_scale),  # 非常重，突出"动"
        ))
        events.append(DrumEvent(
            drum_type=DrumType.SNARE,
            start_beat=bar_start + 3.0,
            duration_beats=0.4,
            velocity=int(150 * self.style_params.drum_velocity_scale),  # 非常重，突出"打"
        ))
        
        # House风格：Hi-hat在弱拍位置，增加律动感
        # 在每拍的弱拍位置（0.5, 1.5, 2.5, 3.5）添加Hi-hat
        for h in [0.5, 1.5, 2.5, 3.5]:
            events.append(DrumEvent(
                drum_type=DrumType.HIHAT,
                start_beat=bar_start + h,
                duration_beats=0.25,
                velocity=int(70 * self.style_params.drum_velocity_scale),  # 保持清晰
            ))
        
        # 根据乐句角色，可以添加更多Hi-hat增强律动感
        if phrase_role in ("development", "variation"):
            # 发展/变化阶段：在每拍的更细分位置添加额外的Hi-hat（十六分音符）
            for h in [0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75]:
                events.append(DrumEvent(
                    drum_type=DrumType.HIHAT,
                    start_beat=bar_start + h,
                    duration_beats=0.25,
                    velocity=int(65 * self.style_params.drum_velocity_scale),  # 稍轻，作为填充
                ))
        
        return events
    
    def get_track_volumes(self, variant_id: Optional[str] = None) -> Dict[str, float]:
        # 舞曲：鼓点为主，非常突出，主旋律和和声降低以突出鼓点
        if variant_id == "dance_drums_focus":
            # 鼓点焦点变体：鼓点更突出，其他轨道更弱
            return {"melody": 0.65, "bass": 0.9, "harmony": 0.5, "drum_boost": 0.6}
        else:
            # 默认：鼓点为主，但保持一定平衡
            return {"melody": 0.75, "bass": 0.95, "harmony": 0.6, "drum_boost": 0.5}


# 风格配置工厂函数
def get_style_config(style: SeedMusicStyle) -> MusicStyleConfig:
    """根据风格类型返回对应的配置类实例"""
    style_params = get_style_params(style)
    
    if style == SeedMusicStyle.CLASSIC_8BIT:
        return Classic8bitStyleConfig(style, style_params)
    elif style == SeedMusicStyle.LOFI:
        return LofiStyleConfig(style, style_params)
    elif style == SeedMusicStyle.BATTLE:
        return BattleStyleConfig(style, style_params)
    elif style == SeedMusicStyle.SUSPENSE:
        return SuspenseStyleConfig(style, style_params)
    elif style == SeedMusicStyle.CALM:
        return CalmStyleConfig(style, style_params)
    elif style == SeedMusicStyle.ROCK:
        return RockStyleConfig(style, style_params)
    elif style == SeedMusicStyle.DANCE:
        return DanceStyleConfig(style, style_params)
    elif style == SeedMusicStyle.WORKSHOP:
        return WorkshopStyleConfig(style, style_params)
    else:
        # 默认返回经典8bit
        return Classic8bitStyleConfig(style, style_params)


def get_style_meta(style: SeedMusicStyle) -> dict:
    """
    提供给 UI / 其它模块使用的风格元信息接口：
    - 包含 default_bpm / mood / short_desc 等只读信息；
    - 若未来新增字段（例如推荐音色说明、推荐用途），可以在 STYLE_META 中扩展。
    """
    return STYLE_META.get(style, STYLE_META[SeedMusicStyle.CLASSIC_8BIT])


# 风格变体元信息（在基础风格之上做轻量偏移，不改变默认行为）
# 说明：
# - id: 内部标识，用于生成逻辑分支（例如 "battle_default" / "battle_melody" / "battle_drums"）
# - name: 在 UI 中展示的名称（例如 "默认""偏旋律""偏鼓点"）
# - desc: 简短说明，不影响任何逻辑
STYLE_VARIANT_META = {
    SeedMusicStyle.CLASSIC_8BIT: [
        {
            "id": "default",
            "name": "默认",
            "desc": "经典8bit风格的默认平衡：方波主旋律 + 三角波低音，标准4/4拍。",
        },
        {
            "id": "classic_8bit_bass_heavy",
            "name": "重低音",
            "desc": "低音更密集，每拍都有，适合需要强烈节奏感的场景。",
        },
        {
            "id": "classic_8bit_bass_simple",
            "name": "简单低音",
            "desc": "低音更简单，只在强拍，突出主旋律。",
        },
    ],
    SeedMusicStyle.LOFI: [
        {
            "id": "default",
            "name": "默认",
            "desc": "Lofi风格的默认平衡：柔和、连贯，适合背景音乐。",
        },
        {
            "id": "lofi_slower",
            "name": "更慢",
            "desc": "节奏更慢，低音整小节持续，更空灵的氛围。",
        },
        {
            "id": "lofi_warm",
            "name": "更温暖",
            "desc": "低音使用根音-五度交替，音色更温暖。",
        },
    ],
    SeedMusicStyle.BATTLE: [
        {
            "id": "battle_default",
            "name": "默认",
            "desc": "当前战斗风格的默认平衡：主旋律和鼓点都比较突出。",
        },
        {
            "id": "battle_melody",
            "name": "偏旋律",
            "desc": "主旋律更响、更扎眼，低音和鼓点略微收一点，适合突出主题旋律的战斗场景。",
        },
        {
            "id": "battle_drums",
            "name": "偏鼓点",
            "desc": "鼓点更炸、更密，低音更密集，主旋律略微靠后一些，适合节奏感更强的紧张段落。",
        },
    ],
    SeedMusicStyle.SUSPENSE: [
        {
            "id": "suspense_default",
            "name": "默认",
            "desc": "当前悬疑风格的默认平衡：旋律与留白适中，整体阴郁克制。",
        },
        {
            "id": "suspense_dense",
            "name": "更紧张",
            "desc": "主旋律更连续、安静小节更少，低音稍微密集，适合持续高压的悬疑段落。",
        },
        {
            "id": "suspense_sparse",
            "name": "更空灵",
            "desc": "休止和安静小节更多，低音更稀疏，鼓点也更弱，适合非常压抑、拉长气氛的环境音。",
        },
    ],
    SeedMusicStyle.CALM: [
        {
            "id": "default",
            "name": "默认",
            "desc": "舒缓风格的默认平衡：长音、级进，柔和治愈。",
        },
        {
            "id": "calm_slower",
            "name": "更慢",
            "desc": "节奏更慢，低音整小节持续，更空灵的氛围。",
        },
        {
            "id": "calm_brighter",
            "name": "更明亮",
            "desc": "低音偶尔使用根音-三度交替，音色更明亮。",
        },
    ],
    SeedMusicStyle.ROCK: [
        {
            "id": "default",
            "name": "默认",
            "desc": "摇滚风格的默认平衡：突出节奏和打击乐，Solo阶段有快速跑动。",
        },
        {
            "id": "rock_heavier",
            "name": "更重",
            "desc": "低音更密集，每拍都有，整体更重更激烈。",
        },
    ],
    SeedMusicStyle.DANCE: [
        {
            "id": "default",
            "name": "默认",
            "desc": "舞曲风格的默认平衡：鼓点为主，非常突出，主旋律和和声适当降低。",
        },
        {
            "id": "dance_drums_focus",
            "name": "鼓点焦点",
            "desc": "鼓点极度突出，主旋律和和声进一步降低，适合纯节奏感的舞曲。",
        },
    ],
}


def get_style_variants(style: SeedMusicStyle):
    """
    返回某个风格下可用的变体列表，每个元素为：
    { "id": str, "name": str, "desc": str }
    - 若未定义专门的变体，则返回一个仅包含“默认”的列表。
    """
    if style in STYLE_VARIANT_META:
        return STYLE_VARIANT_META[style]
    # 其他风格暂时只有默认变体，保持接口统一
    return [
        {
            "id": "default",
            "name": "默认",
            "desc": "",
        }
    ]


def get_rng_from_seed(seed: Union[int, str]) -> random.Random:
    """
    根据 seed 构造一个独立的随机数发生器。

    - 同一版本中：相同 seed → 生成结果完全一致（确定性）。
    - seed 可以是数字或字符串，内部统一转成字符串再 seed。
    """
    rng = random.Random()
    # 使用字符串形式，避免 int / str 在不同调用中产生不一致
    rng.seed(str(seed))
    return rng


# 音乐结构预设：定义不同长度对应的乐句结构
MUSIC_STRUCTURE_PRESETS = {
    16: {
        "name": "起-承-转-合",
        "phrases": [4, 4, 4, 4],  # 4 个 4 小节乐句
        "pattern": "full_structure",  # 完整的起承转合
    },
    24: {
        "name": "扩展段落",
        "phrases": [4, 4, 4, 4, 4, 4],  # 6 个 4 小节乐句
        "pattern": "extended_structure",
    },
    32: {
        "name": "完整段落",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4],  # 8 个 4 小节乐句
        "pattern": "full_paragraph",
    },
    48: {
        "name": "短曲（Intro-Verse-Chorus）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 12 个 4 小节乐句
        "pattern": "short_song",  # Intro + Verse + Chorus 结构
    },
    64: {
        "name": "中曲（Intro-Verse-Chorus-Verse-Chorus）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 16 个 4 小节乐句
        "pattern": "medium_song",  # Intro + Verse + Chorus + Verse + Chorus 结构
    },
    80: {
        "name": "长曲（Intro-Verse-Chorus-Verse-Chorus-Bridge）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 20 个 4 小节乐句
        "pattern": "long_song",  # Intro + Verse + Chorus + Verse + Chorus + Bridge 结构
    },
    96: {
        "name": "完整曲（Intro-Verse-Chorus-Verse-Chorus-Bridge-Chorus）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 24 个 4 小节乐句
        "pattern": "full_song",  # Intro + Verse + Chorus + Verse + Chorus + Bridge + Chorus 结构
    },
    112: {
        "name": "扩展曲（Intro-Verse-Chorus-Verse-Chorus-Bridge-Chorus-Outro）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 28 个 4 小节乐句
        "pattern": "extended_song",  # Intro + Verse + Chorus + Verse + Chorus + Bridge + Chorus + Outro 结构
    },
    128: {
        "name": "完整作品（Intro-Verse-Chorus-Verse-Chorus-Bridge-Chorus-Outro-扩展）",
        "phrases": [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],  # 32 个 4 小节乐句
        "pattern": "complete_work",  # 完整的曲子结构，包含所有部分
    },
}


def get_structure_for_bars(bars: int) -> dict:
    """
    根据小节数返回对应的结构预设。
    如果不在预设中，返回最接近的预设并做智能调整。
    """
    if bars in MUSIC_STRUCTURE_PRESETS:
        return MUSIC_STRUCTURE_PRESETS[bars].copy()
    
    # 智能适配：找到最接近的预设
    closest = min(MUSIC_STRUCTURE_PRESETS.keys(), key=lambda x: abs(x - bars))
    base_structure = MUSIC_STRUCTURE_PRESETS[closest].copy()
    
    # 如果输入的小节数与预设不同，做智能调整
    if bars < closest:
        # 截断：去掉多余的乐句
        phrase_count = bars // 4
        base_structure["phrases"] = base_structure["phrases"][:phrase_count]
    elif bars > closest:
        # 扩展：重复最后一个乐句或添加新乐句
        phrase_count = bars // 4
        current_phrases = len(base_structure["phrases"])
        if phrase_count > current_phrases:
            last_phrase = base_structure["phrases"][-1]
            base_structure["phrases"].extend([last_phrase] * (phrase_count - current_phrases))
    
    return base_structure


def _pick_with_weights(rng: random.Random, choices: List[Tuple[int, float]]) -> int:
    """
    从 (value, weight) 列表中按权重选择一个值。
    """
    total = sum(w for _, w in choices)
    r = rng.random() * total
    acc = 0.0
    for value, weight in choices:
        acc += weight
        if r <= acc:
            return value
    return choices[-1][0]


def generate_simple_project_from_seed(
    seed: Union[int, str],
    length_bars: int = 16,
    style: SeedMusicStyle = SeedMusicStyle.CLASSIC_8BIT,
    variant_id: str = "default",
    enable_bass: bool = True,
    enable_harmony: bool = True,
    enable_drums: bool = True,
) -> Project:
    """
    使用 seed 生成一个简单但更有「乐句感」的 8bit 项目（目前：单主旋律轨）。

    润色逻辑（相对上一版的提升）：
    - 有明确的小节结构和和声走向（I–V–vi–IV / I–IV–V–I 等模板）。
    - 使用短「动机模式」（相对音级 + 节奏）并重复 / 微调，形成可辨识乐句。
    - 强拍 / 小节开头优先使用和弦内音，弱拍使用经过音或邻音。
    - 简单的句式轮廓：前两句相似，后两句做小变化或拉高结尾。
    """
    rng = get_rng_from_seed(seed)
    style_params = get_style_params(style)
    
    # 获取风格配置类
    style_config = get_style_config(style)

    # ---- 全局参数（随风格略有变化）----
    # 使用 STYLE_META 中的默认 BPM，保证 UI 展示与生成逻辑完全一致
    bpm = get_style_meta(style)["default_bpm"]
    beats_per_bar = 4.0  # 4/4 拍
    # 长度限制：最小8小节（至少问-答结构），最大128小节（完整曲子）
    length_bars = max(8, min(length_bars, 128))
    total_beats = length_bars * beats_per_bar
    beat_duration = 60.0 / bpm

    project = Project(name=f"Seed Music ({seed})", bpm=bpm)

    # ---- 结构层：根据预设决定乐句结构 ----
    structure = get_structure_for_bars(length_bars)
    phrase_lengths = structure["phrases"]  # 每个乐句的小节数列表
    structure_pattern = structure["pattern"]
    
    # 程序自动决定 Intro：对于 8 小节及以上，前 2 小节作为 Intro
    intro_bars = 2 if length_bars >= 8 else 0
    main_bars = length_bars - intro_bars

    # ---- 风格变体开关（不改变默认行为，只在对应变体下做轻量调整）----
    is_battle_default = style == SeedMusicStyle.BATTLE and variant_id in ("battle_default", "default", "", None)
    is_battle_melody = style == SeedMusicStyle.BATTLE and variant_id == "battle_melody"
    is_battle_drums = style == SeedMusicStyle.BATTLE and variant_id == "battle_drums"

    is_suspense_default = style == SeedMusicStyle.SUSPENSE and variant_id in ("suspense_default", "default", "", None)
    is_suspense_dense = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_dense"
    is_suspense_sparse = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_sparse"

    # ---- 调式与音阶（使用配置类）----
    root_midi, mode_name, scale_offsets = style_config.get_scale_choices(rng)

    # 底层和声：用和弦级数（1=I,4=IV,5=V,6=vi,2=ii）
    # 使用配置类获取和弦进行模板
    progression_templates = style_config.get_chord_progression_templates(rng)
    prog = rng.choice(progression_templates)
    # 根据小节数重复 / 截断
    bars_progression = [prog[i % len(prog)] for i in range(length_bars)]

    # 悬疑风格：预先决定哪些小节作为「极静/氛围小节」，
    # 这些小节里会弱化低音和鼓点，只保留少量和声或长音，制造对比。
    quiet_bars = set()
    if style == SeedMusicStyle.SUSPENSE:
        # 默认：约每 4 小节中有 1 小节是安静小节
        base_prob = 0.4
        # 变体：更紧张 -> 安静小节明显更少；更空灵 -> 安静小节明显更多
        if is_suspense_dense:
            base_prob = 0.12   # 几乎一直在响，更像“持续紧张”
        elif is_suspense_sparse:
            base_prob = 0.75   # 氛围声为主，经常整小节留白

        for i in range(length_bars):
            # 每 4 小节中，约有一小节作为安静处理（从第 2 小节开始更常见）
            if i % 4 in (1, 3) and rng.random() < base_prob:
                quiet_bars.add(i)

    # 把和弦级数映射到音阶 degree（0-based）——简单粗暴：I=0, II=1...
    def chord_root_degree(scale_degree: int) -> int:
        return (scale_degree - 1) % 7

    # ---- 动机模式：相对音级 + 节奏 ----
    # 使用配置类获取该风格的动机模式
    motifs = style_config.get_melody_motifs(rng, variant_id)

    melody_track = Track(name="Seed 主旋律", track_type=TrackType.NOTE_TRACK)
    # 使用风格配置的 ADSR，而不是在这里写死
    melody_adsr = style_params.melody_adsr

    current_beat = 0.0
    last_pitch = root_midi + scale_offsets[chord_root_degree(bars_progression[0])]
    # 控制整体音域：避免旋律跑得过高或过低
    pitch_min = root_midi - 5
    pitch_max = root_midi + 14

    # ---- 改进1：乐句结构识别 ----
    # 根据phrase_lengths确定每个乐句的起始小节
    phrase_starts = []
    current_bar = intro_bars  # Intro之后开始主旋律
    for phrase_len in phrase_lengths:
        phrase_starts.append(current_bar)
        current_bar += phrase_len
    
    # 确保phrase_starts覆盖所有主旋律小节
    if phrase_starts and phrase_starts[-1] + phrase_lengths[-1] < length_bars:
        # 如果最后一个乐句没有覆盖完，扩展它
        phrase_lengths[-1] = length_bars - phrase_starts[-1]
    
    def get_phrase_index(bar_idx: int) -> int:
        """返回当前小节属于第几个乐句（从0开始）"""
        for i, start in enumerate(phrase_starts):
            if i == len(phrase_starts) - 1:
                return i
            if start <= bar_idx < phrase_starts[i + 1]:
                return i
        return len(phrase_starts) - 1
    
    def get_phrase_role(phrase_idx: int, total_phrases: int) -> str:
        """返回乐句在结构中的角色：question/answer/statement/development/variation/resolution"""
        if total_phrases == 1:
            return "statement"
        elif total_phrases == 2:
            return "question" if phrase_idx == 0 else "answer"
        elif total_phrases == 3:
            roles = ["statement", "development", "variation"]
            return roles[min(phrase_idx, 2)]
        elif total_phrases == 4:
            roles = ["statement", "development", "variation", "resolution"]
            return roles[min(phrase_idx, 3)]
        else:
            # 更多乐句：循环使用基本角色
            roles = ["statement", "development", "variation", "resolution"]
            return roles[phrase_idx % 4]

    # ---- 改进2：主题-变奏-回归的动机选择 ----
    # 为每个乐句选择一个"主题动机"，后续乐句基于主题进行变奏
    theme_motif = None  # 主题动机（第一个乐句使用）
    phrase_motifs = {}  # 每个乐句使用的动机
    
    # 先处理Intro部分（如果有）
    # 摇滚风格：前1-2小节完全只有鼓点，主旋律延迟进入
    # 舞曲风格：Intro部分纯鼓点，和声先进入，主旋律稍后进入
    dance_melody_start_bar = 0
    dance_harmony_start_bar = 0
    if style == SeedMusicStyle.DANCE and intro_bars >= 1:
        # 舞曲风格：前1-2小节纯鼓点，和声从第2小节开始，主旋律从第3小节开始
        dance_drum_only_bars = min(2, intro_bars)  # 最多2小节纯鼓点
        dance_harmony_start_bar = dance_drum_only_bars  # 和声从第2小节开始（如果有2小节Intro）
        dance_melody_start_bar = dance_drum_only_bars + 1  # 主旋律从第3小节开始（如果有2小节Intro）
        # 如果只有1小节Intro，和声从第1小节开始，主旋律从第2小节开始
        if intro_bars == 1:
            dance_harmony_start_bar = 0  # 和声从第1小节开始
            dance_melody_start_bar = 1  # 主旋律从第2小节开始
    
    if style == SeedMusicStyle.ROCK and intro_bars >= 2:
        # 摇滚风格：前1-2小节纯鼓点，主旋律从第2小节开始（如果有2小节Intro）
        # 或者从第1小节后半段开始（如果只有1小节Intro）
        rock_drum_only_bars = min(2, intro_bars)  # 最多2小节纯鼓点
        rock_melody_start_bar = rock_drum_only_bars  # 主旋律从这个位置开始
        
        # 纯鼓点小节：不生成主旋律
        for bar_idx in range(rock_drum_only_bars):
            # 这些小节完全跳过主旋律生成，只保留鼓点
            pass
        
        # 主旋律延迟进入：从rock_melody_start_bar开始生成Intro旋律
        for bar_idx in range(rock_melody_start_bar, intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro部分：使用简单的动机，不参与乐句结构
            motif = rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(pitch_min, min(pitch, pitch_max))
                
                start_time = global_beat * beat_duration
                # 主旋律延迟进入时，力度逐渐增强
                progress = (bar_idx - rock_melody_start_bar) / max(1, intro_bars - rock_melody_start_bar)
                base_velocity = int(80 * (0.5 + 0.5 * progress))  # 从50%逐渐增强到100%
                
                duration_beats_for_time = dur_beats
                duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    elif style == SeedMusicStyle.DANCE and intro_bars >= 1:
        # 舞曲风格：前1-2小节纯鼓点，主旋律从第2小节开始
        # 主旋律延迟进入：从dance_melody_start_bar开始生成Intro旋律
        for bar_idx in range(dance_melody_start_bar, intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro部分：使用简单的动机，不参与乐句结构
            motif = rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(60, min(84, pitch))  # 限制在C4-C6范围
                
                start_time = global_beat * beat_duration
                duration = dur_beats * beat_duration
                
                # 舞曲：Intro部分主旋律逐渐增强
                progress = (bar_idx - dance_melody_start_bar) / max(1, intro_bars - dance_melody_start_bar)
                base_velocity = int(85 * (0.6 + 0.4 * progress))  # 从60%逐渐增强到100%
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    else:
        # 其他风格：正常的Intro处理
        for bar_idx in range(intro_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # Intro部分：使用简单的动机，不参与乐句结构
            motif = rng.choice(motifs)
            beat_in_bar = 0.0
            for rel_degree, dur_beats in motif:
                if beat_in_bar >= beats_per_bar - 1e-6:
                    break
                if beat_in_bar + dur_beats > beats_per_bar:
                    dur_beats = beats_per_bar - beat_in_bar
                
                global_beat = bar_start + beat_in_bar
                is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6
                
                if is_strong_beat:
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + rng.choice(chord_tones)
                else:
                    base_degree = bar_root_degree + rel_degree
                
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                pitch = max(pitch_min, min(pitch, pitch_max))
                
                start_time = global_beat * beat_duration
                base_velocity = int(80 * 0.65)  # Intro部分力度很弱
                
                duration_beats_for_time = dur_beats
                duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=base_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                beat_in_bar += dur_beats
    
    # 处理主旋律部分（带乐句结构）
    # 舞曲风格：主旋律从dance_melody_start_bar开始（如果dance_melody_start_bar > intro_bars）
    melody_start_bar = intro_bars
    if style == SeedMusicStyle.DANCE and dance_melody_start_bar > intro_bars:
        melody_start_bar = dance_melody_start_bar
    
    for bar_idx in range(melody_start_bar, length_bars):
        bar_start = bar_idx * beats_per_bar
        bar_chord_degree = bars_progression[bar_idx]
        bar_root_degree = chord_root_degree(bar_chord_degree)

        # 确定当前小节属于哪个乐句
        phrase_idx = get_phrase_index(bar_idx)
        phrase_role = get_phrase_role(phrase_idx, len(phrase_lengths))
        
        # 如果是乐句的第一小节，选择或生成动机
        phrase_start_bar = phrase_starts[phrase_idx]
        is_phrase_start = (bar_idx == phrase_start_bar)
        
        if is_phrase_start:
            if phrase_idx == 0:
                # 第一个乐句：选择主题动机
                theme_motif = rng.choice(motifs)
                phrase_motifs[phrase_idx] = theme_motif
            else:
                # 后续乐句：基于主题进行变奏
                if phrase_role == "answer":
                    # 答句：使用主题的"镜像"或"倒影"（上行变下行，下行变上行）
                    theme = phrase_motifs.get(0, rng.choice(motifs))
                    # 简单变奏：反转相对度数
                    phrase_motifs[phrase_idx] = [(-rel, dur) for rel, dur in theme]
                elif phrase_role == "variation":
                    # 变奏：使用主题的节奏，但改变音高走向
                    theme = phrase_motifs.get(0, rng.choice(motifs))
                    # 保持节奏，改变音高模式
                    phrase_motifs[phrase_idx] = [(rel + (1 if rng.random() < 0.5 else -1), dur) for rel, dur in theme]
                elif phrase_role == "resolution":
                    # 解决：回归主题，但简化
                    theme = phrase_motifs.get(0, rng.choice(motifs))
                    # 使用主题的前半部分
                    phrase_motifs[phrase_idx] = theme[:len(theme)//2] if len(theme) > 2 else theme
                else:
                    # 其他：直接使用主题或轻微变奏
                    if rng.random() < 0.6:
                        phrase_motifs[phrase_idx] = phrase_motifs.get(0, rng.choice(motifs))
                    else:
                        phrase_motifs[phrase_idx] = rng.choice(motifs)
        
        # 获取当前乐句的动机
        motif = phrase_motifs.get(phrase_idx, rng.choice(motifs))
        
        # 句式控制：根据乐句角色调整音高中心
        phrase_shift = 0
        if phrase_role == "variation":
            phrase_shift = 2  # 变奏乐句抬高
        elif phrase_role == "resolution":
            phrase_shift = 0  # 解决乐句回归
        elif phrase_role == "answer":
            phrase_shift = 1  # 答句略微抬高

        # 摇滚风格：在variation阶段生成solo（快速、密集的音符）
        if style == SeedMusicStyle.ROCK and phrase_role == "variation":
            # Solo特征：快速、密集、音阶跑动
            # 使用十六分音符（0.25拍）生成快速跑动，确保覆盖整个小节
            beat_in_bar = 0.0
            solo_last_degree = bar_root_degree  # 初始化solo的起始度数
            dur_beats = 0.25  # 十六分音符
            
            # 确保覆盖整个小节：生成到小节末尾，不留余量
            # 计算能生成多少个十六分音符（每小节4拍 = 16个十六分音符）
            max_notes = int(beats_per_bar / dur_beats)  # 16个十六分音符
            
            for note_idx in range(max_notes):
                beat_in_bar = note_idx * dur_beats
                # 确保不超过小节末尾
                if beat_in_bar >= beats_per_bar:
                    break
                    
                global_beat = bar_start + beat_in_bar
                # 强拍判断：每拍的第1个十六分音符（0.0, 1.0, 2.0, 3.0拍）
                is_strong_beat = abs(beat_in_bar % 1.0) < 1e-6
                
                # Solo音高选择：基于当前和弦，但允许更大的跳进和音阶跑动
                if is_strong_beat or note_idx == 0:
                    # 强拍或第一个音：使用和弦音
                    chord_tones = [0, 2, 4]
                    base_degree = bar_root_degree + rng.choice(chord_tones)
                else:
                    # 弱拍：音阶跑动（级进或小跳）
                    if rng.random() < 0.6:
                        # 60%概率级进（+1或-1）
                        base_degree = solo_last_degree + rng.choice([-1, 1])
                    else:
                        # 40%概率小跳（+2或-2）
                        base_degree = solo_last_degree + rng.choice([-2, 2])
                
                # 叠加句式偏移（variation阶段抬高）
                base_degree += phrase_shift
                
                # 允许更大的音域范围（solo可以更高）
                degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                pitch = root_midi + scale_offsets[degree_clamped]
                # Solo音域可以更高
                solo_pitch_max = min(pitch_max + 12, 96)  # 允许高一个八度
                pitch = max(pitch_min, min(pitch, solo_pitch_max))
                
                # Solo力度：动态变化，强拍更重
                if is_strong_beat:
                    solo_velocity = int(100 + rng.uniform(-10, 15))
                else:
                    solo_velocity = int(85 + rng.uniform(-10, 10))
                solo_velocity = max(70, min(127, solo_velocity))
                
                start_time = global_beat * beat_duration
                duration = dur_beats * beat_duration
                
                note = Note(
                    pitch=pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=solo_velocity,
                    waveform=style_params.melody_waveform,
                    duty_cycle=style_params.melody_duty,
                    adsr=melody_adsr,
                )
                melody_track.notes.append(note)
                
                solo_last_degree = degree_clamped
        else:
            # 非solo部分：正常生成
            beat_in_bar = 0.0
            # 计算motif的总时长
            motif_total_beats = sum(dur for _, dur in motif)
            
            # 如果motif总时长小于小节长度，需要重复motif直到填满整个小节
            while beat_in_bar < beats_per_bar - 1e-6:
                # 遍历motif中的每个音符
                for rel_degree, dur_beats in motif:
                    if beat_in_bar >= beats_per_bar - 1e-6:
                        break

                    # 如果剩余拍不够，缩短到小节末尾
                    if beat_in_bar + dur_beats > beats_per_bar:
                        dur_beats = beats_per_bar - beat_in_bar

                    global_beat = bar_start + beat_in_bar

                    # 强拍（小节头 / 第 3 拍）优先用三和弦内音：根、三、五
                    is_strong_beat = abs(beat_in_bar - 0.0) < 1e-6 or abs(beat_in_bar - 2.0) < 1e-6

                    # 在节奏层面引入「休止」：
                    # - 对弱拍（非 1/3 拍），有一定概率整拍变成休止（不发音但时间前进）；
                    # - 这样可以在乐句中产生呼吸和断句，而不会改变整体节奏网格。
                    if not is_strong_beat:
                        # 风格化地调整弱拍休止概率
                        if style == SeedMusicStyle.SUSPENSE:
                            # 悬疑：默认适度留白；更紧张 → 明显更少休止；更空灵 → 明显更多休止
                            if is_suspense_dense:
                                rest_prob = 0.12
                            elif is_suspense_sparse:
                                rest_prob = 0.45
                            else:
                                rest_prob = 0.25
                        elif style == SeedMusicStyle.CALM:
                            rest_prob = 0.15  # 舒缓：旋律更连贯，少休止
                        elif style == SeedMusicStyle.LOFI:
                            rest_prob = 0.3   # Lofi：适度留白
                        else:
                            rest_prob = 0.25  # 默认

                        # 为避免「音符都集中在前半小节」，仅在前 2 拍允许休止，后 2 拍保持较高填充度
                        if rng.random() < rest_prob and beat_in_bar < beats_per_bar * 0.5:
                            beat_in_bar += dur_beats
                            current_beat = global_beat + dur_beats
                            continue
                    
                    if is_strong_beat:
                        if style == SeedMusicStyle.SUSPENSE:
                            # 悬疑：强拍有更高概率落在「危险音」：♭2、♭6、♭7（相对于当前和弦根音）
                            # 这里使用相对度数 1, 5, 6（对应 scale_offsets 中的半音阶位置）
                            tense_choices = [1, 5, 6]
                            if rng.random() < 0.6:
                                base_degree = bar_root_degree + rng.choice(tense_choices)
                            else:
                                chord_tones = [0, 2, 4]  # 仍保留少量 1,3,5 以维持可听性
                                base_degree = bar_root_degree + rng.choice(chord_tones)
                        else:
                            chord_tones = [0, 2, 4]  # 1,3,5
                            base_degree = bar_root_degree + rng.choice(chord_tones)
                    else:
                        # 弱拍可以用经过音 / 邻音（在和弦度数附近浮动）
                        base_degree = bar_root_degree + rel_degree
                        if style == SeedMusicStyle.SUSPENSE and rng.random() < 0.25:
                            # 在部分弱拍上增加半音邻音抖动，制造不安的"日本小调"味道
                            jitter = rng.choice([-1, 1])
                            base_degree += jitter

                    # 叠加句式偏移
                    base_degree += phrase_shift

                    # ---- 改进3：增强音高方向感（规划上行-下行-回归线条）----
                    # 根据乐句角色和位置，规划旋律线条的方向
                    phrase_progress = (bar_idx - phrase_start_bar) / phrase_lengths[phrase_idx] if phrase_lengths[phrase_idx] > 0 else 0.5
                    
                    # 确定当前乐句的音高方向
                    if phrase_role == "statement":
                        # 陈述：平稳或轻微上行
                        direction_bias = 0.3  # 轻微上行倾向
                    elif phrase_role == "development":
                        # 发展：上行积累
                        direction_bias = 0.6
                    elif phrase_role == "variation":
                        # 变奏：达到高点
                        direction_bias = 0.8
                    elif phrase_role == "resolution":
                        # 解决：下行回归
                        direction_bias = -0.4
                    elif phrase_role == "answer":
                        # 答句：先上后下
                        direction_bias = 0.4 if phrase_progress < 0.5 else -0.2
                    else:
                        direction_bias = 0.0
                    
                    # 根据方向倾向调整音高
                    if direction_bias > 0:
                        # 上行倾向：增加度数
                        base_degree += int(direction_bias * 2)
                    elif direction_bias < 0:
                        # 下行倾向：减少度数
                        base_degree += int(direction_bias * 2)

                    # ---- 改进5：强化调性中心（更频繁回归主音）----
                    # 在乐句结尾和强拍上，有更高概率回归主音
                    tonic_degree = chord_root_degree(1)  # 主音度数
                    is_phrase_end = (bar_idx == phrase_starts[phrase_idx] + phrase_lengths[phrase_idx] - 1) if phrase_idx < len(phrase_starts) else False
                    
                    if is_phrase_end or (is_strong_beat and rng.random() < 0.3):
                        # 乐句结尾或30%的强拍：回归主音
                        if abs(base_degree - tonic_degree) > 3:
                            # 如果离主音太远，向主音靠拢
                            if base_degree > tonic_degree:
                                base_degree = tonic_degree + 2
                            else:
                                base_degree = tonic_degree - 2

                    # 控制旋律流畅：避免离上一个音跳太远
                    degree_clamped = max(0, min(base_degree, len(scale_offsets) - 1))
                    pitch = root_midi + scale_offsets[degree_clamped]
                    if abs(pitch - last_pitch) > 12:
                        # 如果跳太大，往上一个音靠拢一点（默认最大约五度）
                        if pitch > last_pitch:
                            pitch = last_pitch + 7  # 五度
                        else:
                            pitch = last_pitch - 7

                    # 舒缓风格：进一步压缩跳进，尽量控制在五度以内
                    if style == SeedMusicStyle.CALM and abs(pitch - last_pitch) > 7:
                        if pitch > last_pitch:
                            pitch = last_pitch + 5
                        else:
                            pitch = last_pitch - 5

                    # 限制在整体音域范围内
                    pitch = max(pitch_min, min(pitch, pitch_max))

                    # 避免出现「同一个音连续出现太多次」：如果已经连续两次相同，则强制小级进
                    if len(melody_track.notes) >= 2:
                        if (melody_track.notes[-1].pitch == last_pitch and
                                melody_track.notes[-2].pitch == last_pitch and
                                pitch == last_pitch):
                            # 尝试往上或往下半音阶移动一个音阶度数
                            adjust = 1 if rng.random() < 0.5 else -1
                            adj_degree = degree_clamped + adjust
                            adj_degree = max(0, min(adj_degree, len(scale_offsets) - 1))
                            pitch = root_midi + scale_offsets[adj_degree]
                            pitch = max(pitch_min, min(pitch, pitch_max))

                    last_pitch = pitch
                    last_pitch_degree = degree_clamped  # 保存度数，用于solo

                    start_time = global_beat * beat_duration

                    # ---- 改进4：改进节奏层次（积累-释放模式）----
                    # 根据乐句进度和角色，调整力度和节奏密度
                    phrase_progress = (bar_idx - phrase_start_bar) / phrase_lengths[phrase_idx] if phrase_lengths[phrase_idx] > 0 else 0.5
                    
                    # 节奏积累：乐句前半段逐渐增强，后半段释放
                    if phrase_progress < 0.5:
                        # 积累阶段：逐渐增强
                        rhythm_intensity = 0.7 + phrase_progress * 0.3
                    else:
                        # 释放阶段：保持或略微减弱
                        rhythm_intensity = 1.0 - (phrase_progress - 0.5) * 0.2
                    
                    # 根据节奏强度和强拍弱拍计算基础力度
                    if is_strong_beat:
                        base_velocity = int(100 + 20 * rhythm_intensity)
                    else:
                        base_velocity = int(80 + 15 * rhythm_intensity * rng.random())

                    if style == SeedMusicStyle.BATTLE:
                        # 战斗：主旋律整体更突出一些；变体可再微调
                        if is_battle_melody:
                            base_velocity = min(127, int(base_velocity * 1.35))
                        elif is_battle_drums:
                            base_velocity = min(127, int(base_velocity * 1.1))
                        else:
                            base_velocity = min(127, int(base_velocity * 1.2))
                    elif style == SeedMusicStyle.SUSPENSE:
                        # 悬疑：主旋律既要动态起伏，又要压过背景
                        jitter = int(rng.uniform(-10, 10))
                        base_velocity = max(55, min(127, int(base_velocity * 1.15) + jitter))
                    elif style == SeedMusicStyle.CALM:
                        # 舒缓：整体力度更柔和
                        base_velocity = int(base_velocity * 0.8)
                    elif style == SeedMusicStyle.ROCK:
                        # 摇滚：主旋律力度较强，但不过于突出（因为要突出鼓点）
                        base_velocity = min(127, int(base_velocity * 1.1))

                    # Intro段已经在前面单独处理，这里不需要再处理

                    if style == SeedMusicStyle.BATTLE and dur_beats >= 0.5:
                        # 战斗风格：同一格子里把音符切成两次短促触发，营造紧张感
                        sub_beats = dur_beats / 2.0
                        sub_time = sub_beats * beat_duration
                        # 单次触发的实际持续时间更短一些
                        duration_beats_for_time = max(0.25, sub_beats * 0.5)
                        duration = duration_beats_for_time * beat_duration

                        for rep in range(2):
                            rep_start = start_time + rep * sub_time
                            velocity = base_velocity + (5 if rep == 1 else 0)  # 第二下略微更重一点
                            note = Note(
                                pitch=pitch,
                                start_time=rep_start,
                                duration=duration,
                                velocity=velocity,
                                waveform=style_params.melody_waveform,
                                duty_cycle=style_params.melody_duty,
                                adsr=melody_adsr,
                            )
                            melody_track.notes.append(note)
                    else:
                        # 其他风格：按照正常节拍长度生成一个音，但可按风格微调时值和音符数量
                        if style == SeedMusicStyle.SUSPENSE and dur_beats >= 0.5:
                            # 悬疑：在当前节拍格子内打三连击，同时保证整格几乎被填满，避免"一段一段断掉"的感觉
                            sub_beats = dur_beats / 3.0
                            sub_time = sub_beats * beat_duration
                            # 前两下略短，最后一下略长，三者合起来基本覆盖整格
                            sub_durations = [
                                max(0.18 * beat_duration, sub_time * 0.75),
                                max(0.18 * beat_duration, sub_time * 0.8),
                                max(0.25 * beat_duration, sub_time * 1.0),
                            ]

                            current_start = start_time
                            for i in range(3):
                                # 中间那个略重，前后略轻，形成「弱-强-弱」的惊悚律动
                                if i == 1:
                                    vel = min(127, int(base_velocity * 1.05))
                                else:
                                    vel = max(50, int(base_velocity * 0.9))
                                note = Note(
                                    pitch=pitch,
                                    start_time=current_start,
                                    duration=sub_durations[i],
                                    velocity=vel,
                                    waveform=style_params.melody_waveform,
                                    duty_cycle=style_params.melody_duty,
                                    adsr=melody_adsr,
                                )
                                melody_track.notes.append(note)
                                # 下一次的起点紧跟上一音结束，减少空白
                                current_start += sub_time
                        else:
                            if style == SeedMusicStyle.CALM:
                                # 舒缓：略微拉长音符，让句子更连贯
                                duration_beats_for_time = dur_beats * 1.1
                            else:
                                duration_beats_for_time = dur_beats
                            duration = max(0.25 * beat_duration, duration_beats_for_time * beat_duration)

                            # 在强拍上添加叠音（形成和弦感）
                            will_add_overlay = is_strong_beat and rng.random() < 0.4  # 40%概率添加叠音
                            
                            # 如果有叠音，降低主音力度，避免叠加后音量突然增大
                            if will_add_overlay:
                                # 主音力度降低到70%，为叠音留出空间
                                adjusted_velocity = max(60, int(base_velocity * 0.7))
                            else:
                                adjusted_velocity = base_velocity
                            
                            note = Note(
                                pitch=pitch,
                                start_time=start_time,
                                duration=duration,
                                velocity=adjusted_velocity,
                                waveform=style_params.melody_waveform,
                                duty_cycle=style_params.melody_duty,
                                adsr=melody_adsr,
                            )
                            melody_track.notes.append(note)
                            
                            # 添加叠音
                            if will_add_overlay:
                                # 选择添加三度或五度叠音
                                overlay_choice = rng.choice(["third", "fifth"])
                                if overlay_choice == "third":
                                    # 添加三度（+2个度数）
                                    overlay_degree = degree_clamped + 2
                                else:
                                    # 添加五度（+4个度数）
                                    overlay_degree = degree_clamped + 4
                                
                                # 确保度数在有效范围内
                                overlay_degree = max(0, min(overlay_degree, len(scale_offsets) - 1))
                                overlay_pitch = root_midi + scale_offsets[overlay_degree]
                                overlay_pitch = max(pitch_min, min(overlay_pitch, pitch_max))
                                
                                # 叠音的力度设为原主音的50%，与降低后的主音叠加后总音量约等于原主音的85%
                                overlay_velocity = max(50, int(base_velocity * 0.5))
                                
                                overlay_note = Note(
                                    pitch=overlay_pitch,
                                    start_time=start_time,
                                    duration=duration * 0.8,  # 叠音稍短一些
                                    velocity=overlay_velocity,
                                    waveform=style_params.melody_waveform,
                                    duty_cycle=style_params.melody_duty,
                                    adsr=melody_adsr,
                                )
                                melody_track.notes.append(overlay_note)

                    beat_in_bar += dur_beats
                    current_beat = global_beat + dur_beats
                
                # 如果motif总时长小于小节长度，且还没有填满小节，继续重复
                if motif_total_beats < beats_per_bar and beat_in_bar < beats_per_bar - 1e-6:
                    # 继续循环，重复motif
                    continue
                else:
                    # motif已经填满或超过小节长度，退出
                    break

    # 对结尾做一个简单的「终止式」处理：确保最后一个音落在主和弦上并稍长一点
    if melody_track.notes:
        last_note = melody_track.notes[-1]
        tonic_pitch = root_midi + scale_offsets[chord_root_degree(1)]
        # 如果最后一个音不是主音附近，则强制靠近主音
        if abs(last_note.pitch - tonic_pitch) > 2:
            last_note.pitch = tonic_pitch
        # 延长最后一个音到曲子结束的 1 小节内（不改总长度，只拉长尾音）
        song_end_time = total_beats * beat_duration
        desired_end = song_end_time
        last_note.duration = max(last_note.duration, desired_end - last_note.start_time)

    project.add_track(melody_track)

    # ---- 低音轨道：按和弦根音弹「踩点」 ----
    bass_track = None
    if enable_bass:
        bass_track = Track(name="Seed 低音", track_type=TrackType.NOTE_TRACK)
        bass_adsr = style_params.bass_adsr

        for bar_idx in range(length_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)
            
            # 获取乐句信息（用于特殊处理）
            phrase_role = None
            if bar_idx >= intro_bars:
                adjusted_bar_idx = bar_idx - intro_bars
                phrase_idx = get_phrase_index(adjusted_bar_idx)
                phrase_role = get_phrase_role(phrase_idx, len(phrase_lengths))
                
                # 摇滚solo阶段：低音减弱或简化
                if style == SeedMusicStyle.ROCK and phrase_role == "variation":
                    # Solo阶段：低音简化，只在强拍，力度减弱
                    if bar_idx % 2 == 0:  # 只在偶数小节
                        bass_root_pitch = root_midi - 12 + scale_offsets[bar_root_degree]
                        start_time = bar_start * beat_duration
                        duration = 1.0 * beat_duration  # 只持续1拍
                        note = Note(
                            pitch=bass_root_pitch,
                            start_time=start_time,
                            duration=duration,
                            velocity=70,  # Solo时低音减弱
                            waveform=style_params.bass_waveform,
                            duty_cycle=style_params.bass_duty,
                            adsr=bass_adsr,
                        )
                        bass_track.notes.append(note)
                    continue  # 跳过正常的低音生成
            
            # 悬疑风格的安静小节处理
            if style == SeedMusicStyle.SUSPENSE and bar_idx in quiet_bars:
                continue
            
            # 低音通常比旋律低一个或两个八度
            if style == SeedMusicStyle.SUSPENSE:
                # 悬疑：低音尽量简单，只在日本小调的主音或五度上徘徊
                bass_degree = 0 if (bar_idx % 2 == 0) else 3
                bass_root_pitch = root_midi - 12 + scale_offsets[max(0, min(bass_degree, len(scale_offsets) - 1))]
            else:
                bass_root_pitch = root_midi - 12 + scale_offsets[bar_root_degree]
            
            # 使用配置类获取低音模式
            bass_pattern = style_config.get_bass_pattern(
                rng, bar_idx, bar_root_degree, root_midi, scale_offsets,
                beats_per_bar, beat_duration, variant_id
            )
            
            # 处理低音模式，生成音符
            for start_beat, dur_beats, base_velocity in bass_pattern:
                start_time = (bar_start + start_beat) * beat_duration
                is_strong_beat = abs(start_beat - 0.0) < 1e-6 or abs(start_beat - 2.0) < 1e-6
                
                # 根据风格调整持续时间
                if style == SeedMusicStyle.BATTLE:
                    duration_beats_for_time = max(0.25, dur_beats * 0.7)
                elif style == SeedMusicStyle.SUSPENSE:
                    duration_beats_for_time = max(0.5, dur_beats * 0.7)
                elif style == SeedMusicStyle.ROCK:
                    if dur_beats >= beats_per_bar:
                        duration_beats_for_time = dur_beats
                    else:
                        duration_beats_for_time = dur_beats * 1.1
                elif style == SeedMusicStyle.CALM:
                    duration_beats_for_time = dur_beats * 1.1
                else:
                    duration_beats_for_time = dur_beats
                
                duration = duration_beats_for_time * beat_duration
                
                # 在强拍上偶尔添加八度叠音（低八度或高八度）
                will_add_octave = is_strong_beat and rng.random() < 0.3  # 30%概率添加八度叠音
                
                # 如果有八度叠音，降低主音力度，避免叠加后音量突然增大
                if will_add_octave:
                    bass_velocity = max(70, int(base_velocity * 0.75))
                else:
                    bass_velocity = base_velocity
                
                note = Note(
                    pitch=bass_root_pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=bass_velocity,
                    waveform=style_params.bass_waveform,
                    duty_cycle=style_params.bass_duty,
                    adsr=bass_adsr,
                )
                bass_track.notes.append(note)
                
                # 添加八度叠音
                if will_add_octave:
                    # 选择低八度或高八度
                    octave_choice = rng.choice(["lower", "higher"])
                    if octave_choice == "lower":
                        overlay_pitch = bass_root_pitch - 12  # 低八度
                    else:
                        overlay_pitch = bass_root_pitch + 12  # 高八度
                    
                    # 确保音高在有效范围内
                    overlay_pitch = max(24, min(overlay_pitch, 96))  # MIDI范围限制
                    
                    # 八度叠音的力度设为原主音的45%，与降低后的主音叠加后总音量约等于原主音的90%
                    overlay_velocity = max(60, int(base_velocity * 0.45))
                    
                    overlay_note = Note(
                        pitch=overlay_pitch,
                        start_time=start_time,
                        duration=duration * 0.9,  # 稍短一些
                        velocity=overlay_velocity,
                        waveform=style_params.bass_waveform,
                        duty_cycle=style_params.bass_duty,
                        adsr=bass_adsr,
                    )
                    bass_track.notes.append(overlay_note)

    # 应用风格特定的效果（使用配置类）
    style_config.apply_melody_effects(melody_track)

    if bass_track is not None:
        project.add_track(bass_track)

    # ---- 和声轨道：简单三和弦铺垫（与主旋律同区略低） ----
    harmony_track = None
    if enable_harmony:
        harmony_track = Track(name="Seed 和声", track_type=TrackType.NOTE_TRACK)
        harmony_adsr = style_params.harmony_adsr

        for bar_idx in range(length_bars):
            bar_start = bar_idx * beats_per_bar
            bar_chord_degree = bars_progression[bar_idx]
            bar_root_degree = chord_root_degree(bar_chord_degree)

            # 获取当前小节的乐句信息
            phrase_role = None
            if bar_idx >= intro_bars:
                adjusted_bar_idx = bar_idx - intro_bars
                phrase_idx = get_phrase_index(adjusted_bar_idx)
                phrase_role = get_phrase_role(phrase_idx, len(phrase_lengths))
            
            # 使用配置类获取和声度数
            chord_degrees = style_config.get_harmony_chord_degrees(
                rng, bar_root_degree, bar_idx, phrase_role or "statement",
                variant_id, scale_offsets
            )

            # 舞曲风格：和声延迟进入
            if style == SeedMusicStyle.DANCE and bar_idx < dance_harmony_start_bar:
                # 在和声进入之前，不生成和声
                continue
            
            # 获取当前小节的乐句信息，用于调整和声密度
            # 注意：和声生成循环的是整个length_bars，包括intro部分
            # 对于intro部分，使用稀疏和声；对于main部分，根据乐句角色调整
            is_solo_section = False  # 初始化变量，避免未定义错误
            if bar_idx < intro_bars:
                # Intro部分：舞曲风格使用重复的轻和声
                if style == SeedMusicStyle.DANCE:
                    # 舞曲：重复的轻和声，覆盖整个小节，力度较轻
                    # 使用简单的重复模式：每拍一个和声音符
                    harmony_beats = [0.0, 1.0, 2.0, 3.0]  # 每拍都有和声，形成重复
                    harmony_duration_beats = 1.0  # 每个和声音符持续1拍
                else:
                    # 其他风格：稀疏和声，只在前2拍
                    harmony_beats = [0.0]
                    harmony_duration_beats = 2.0
            else:
                # Main部分：根据乐句角色调整
                adjusted_bar_idx = bar_idx - intro_bars
                phrase_idx = get_phrase_index(adjusted_bar_idx)
                phrase_role = get_phrase_role(phrase_idx, len(phrase_lengths))
                
                # 根据乐句角色决定和声覆盖范围
                if style == SeedMusicStyle.DANCE:
                    # 舞曲：重复的轻和声，每拍都有，形成重复模式
                    harmony_beats = [0.0, 1.0, 2.0, 3.0]  # 每拍都有和声
                    harmony_duration_beats = 1.0  # 每个和声音符持续1拍，形成重复
                elif phrase_role == "statement":
                    # 起：稀疏，只在前2拍
                    harmony_beats = [0.0]
                    harmony_duration_beats = 2.0
                elif phrase_role == "development":
                    # 承：逐渐增加，覆盖前3拍
                    harmony_beats = [0.0]
                    harmony_duration_beats = 3.0
                elif phrase_role == "variation":
                    # 转：最密集，覆盖整个小节（solo阶段会减弱音量）
                    harmony_beats = [0.0]
                    harmony_duration_beats = beats_per_bar
                    is_solo_section = (style == SeedMusicStyle.ROCK)
                elif phrase_role == "resolution":
                    # 合：回归，覆盖前3拍
                    harmony_beats = [0.0]
                    harmony_duration_beats = 3.0
                else:
                    # 默认（question/answer）：覆盖前2-3拍
                    harmony_beats = [0.0]
                    harmony_duration_beats = 2.5 if phrase_role == "question" else 3.0

            # 悬疑风格下，安静小节只保留一个长和声音，其他和声全部省略
            if style == SeedMusicStyle.SUSPENSE and bar_idx in quiet_bars:
                # 选择模板中的第一个度数，拉一个整小节的长音
                d = chord_degrees[0]
                pitch = root_midi - 12 + scale_offsets[d]
                harmony_velocity = 50
                long_start = bar_start * beat_duration
                long_duration = beats_per_bar * beat_duration
                note = Note(
                    pitch=pitch,
                    start_time=long_start,
                    duration=long_duration,
                    velocity=harmony_velocity,
                    waveform=style_params.harmony_waveform,
                    duty_cycle=style_params.harmony_duty,
                    adsr=harmony_adsr,
                )
                harmony_track.notes.append(note)
                continue

            # 为每个和声拍点生成和弦
            for harmony_beat in harmony_beats:
                start_time = (bar_start + harmony_beat) * beat_duration
                duration = harmony_duration_beats * beat_duration
                
                # 舞曲风格：和声力度更轻，作为背景
                if style == SeedMusicStyle.DANCE:
                    base_harmony_velocity = 60  # 舞曲和声力度较轻
                else:
                    base_harmony_velocity = 80  # 其他风格正常力度
                
                for d in chord_degrees:
                    pitch = root_midi - 12 + scale_offsets[d]  # 比旋律低一组
                    # 根据风格调整和声力度
                    if style == SeedMusicStyle.DANCE:
                        harmony_velocity = base_harmony_velocity  # 舞曲和声较轻，作为背景
                    elif style == SeedMusicStyle.SUSPENSE:
                        harmony_velocity = 55
                    elif style == SeedMusicStyle.ROCK:
                        if is_solo_section:
                            harmony_velocity = 45  # Solo阶段和声减弱到45%
                        else:
                            harmony_velocity = 90  # 摇滚和声要明显，但不过于突出
                    elif style == SeedMusicStyle.CALM:
                        harmony_velocity = 70
                    else:
                        harmony_velocity = 80  # 默认力度

                    note = Note(
                        pitch=pitch,
                        start_time=start_time,
                        duration=duration,
                        velocity=harmony_velocity,
                        waveform=style_params.harmony_waveform,
                        duty_cycle=style_params.harmony_duty,
                        adsr=harmony_adsr,
                    )
                    harmony_track.notes.append(note)

    # 根据风格 / 变体微调各轨道音量，确保主旋律在混音中始终清晰
    # 使用配置类获取音量平衡
    volumes = style_config.get_track_volumes(variant_id)
    melody_track.volume = volumes["melody"]
    if bass_track is not None:
        bass_track.volume = volumes["bass"]
    if harmony_track is not None:
        harmony_track.volume = volumes["harmony"]
    drum_boost = volumes["drum_boost"]

    if harmony_track is not None:
        project.add_track(harmony_track)

    # ---- 鼓轨道：根据风格和乐句结构生成不同节奏 ----
    drum_track = None
    if enable_drums:
        drum_track = Track(name="Seed 鼓点", track_type=TrackType.DRUM_TRACK)
        
        # 复用主旋律的乐句结构信息
        def get_phrase_index_for_drums(bar_idx: int) -> int:
            """返回当前小节属于第几个乐句（从0开始），考虑Intro"""
            if bar_idx < intro_bars:
                return -1  # Intro部分
            adjusted_idx = bar_idx - intro_bars
            for i, start in enumerate(phrase_starts):
                if i == len(phrase_starts) - 1:
                    return i
                if start <= adjusted_idx + intro_bars < phrase_starts[i + 1]:
                    return i
            return len(phrase_starts) - 1
        
        def get_phrase_role_for_drums(phrase_idx: int) -> str:
            """返回乐句角色"""
            if phrase_idx == -1:
                return "intro"
            return get_phrase_role(phrase_idx, len(phrase_lengths))

        for bar_idx in range(length_bars):
            bar_start = bar_idx * beats_per_bar
            phrase_idx = get_phrase_index_for_drums(bar_idx)
            phrase_role = get_phrase_role_for_drums(phrase_idx)
            
            # 确定当前小节在乐句中的位置（0.0-1.0）
            if phrase_idx >= 0:
                phrase_start_bar = phrase_starts[phrase_idx]
                phrase_progress = (bar_idx - phrase_start_bar) / phrase_lengths[phrase_idx] if phrase_lengths[phrase_idx] > 0 else 0.5
                is_phrase_end = (bar_idx == phrase_start_bar + phrase_lengths[phrase_idx] - 1) if phrase_idx < len(phrase_starts) else False
            else:
                phrase_progress = bar_idx / intro_bars if intro_bars > 0 else 0.5
                is_phrase_end = (bar_idx == intro_bars - 1)

            # 使用配置类生成鼓点模式
            drum_events = style_config.generate_drum_pattern(
                rng, bar_idx, bar_start, phrase_role, phrase_progress,
                is_phrase_end, beats_per_bar, variant_id, intro_bars, quiet_bars
            )
            
            # 添加生成的鼓点事件
            for event in drum_events:
                drum_track.drum_events.append(event)

        # 根据风格 / 变体微调鼓点整体音量
        if style == SeedMusicStyle.DANCE:
            base = 1.2  # 舞曲鼓点非常突出，作为主要元素
            drum_track.volume = max(0.2, min(1.8, base + drum_boost))  # 最高可达1.8
        elif style == SeedMusicStyle.WORKSHOP:
            base = 0.95  # 工作坊：鼓点清晰但不激烈
            drum_track.volume = max(0.2, min(1.3, base + drum_boost))
        elif style == SeedMusicStyle.SUSPENSE:
            base = 0.6
            drum_track.volume = max(0.2, min(1.2, base + drum_boost))
        elif style == SeedMusicStyle.ROCK:
            base = 1.1  # 摇滚鼓点非常突出
            drum_track.volume = max(0.2, min(1.5, base + drum_boost))
        elif style == SeedMusicStyle.BATTLE:
            base = 1.0
            drum_track.volume = max(0.2, min(1.2, base + drum_boost))

        project.add_track(drum_track)

    return project


