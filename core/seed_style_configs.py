"""
Seed 风格配置类与工厂。

集中管理各个风格的生成策略实现，
让 `seed_music_generator` 更专注于总体结构与项目装配流程。
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from .models import Track
from .seed_style_catalog import SeedMusicStyle, StyleParams, get_style_params
from .track_events import DrumEvent, DrumType


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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        if drum_density >= 8:
            v = int(42 * self.style_params.drum_velocity_scale)
            for hb in (0.5, 1.5, 2.5, 3.5):
                events.append(
                    DrumEvent(
                        drum_type=DrumType.HIHAT,
                        start_beat=bar_start + hb,
                        duration_beats=0.125,
                        velocity=v,
                    )
                )
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        
        if drum_density >= 6:
            v = int((32 + drum_density * 4) * self.style_params.drum_velocity_scale)
            for hb in (0.5, 1.5, 2.5, 3.5):
                events.append(
                    DrumEvent(
                        drum_type=DrumType.HIHAT,
                        start_beat=bar_start + hb,
                        duration_beats=0.125,
                        velocity=v,
                    )
                )
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
        quiet_bars: Optional[set] = None,
        drum_density: int = 5,
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
