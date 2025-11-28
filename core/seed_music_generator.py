"""
基于 Seed 的简单 8bit 音乐生成器（V3 规划的第一步）

目标：类似 Minecraft 的世界生成，用一个 seed 生成一段简单但可编辑的音乐。
当前实现：最小可用版本，只生成一个主旋律轨道，用于验证流程和可重复性。
"""

from typing import Union, List, Tuple
import random
from enum import Enum

from .models import Project, Track, Note, WaveformType, ADSRParams, TrackType
from .track_events import DrumEvent, DrumType


class SeedMusicStyle(Enum):
    """Seed 生成音乐的风格类型"""
    CLASSIC_8BIT = "classic_8bit"   # 经典 8bit / FC 游戏风
    LOFI = "lofi"                   # 稍慢、柔和一点的节奏与音色
    BATTLE = "battle"               # 更紧张、偏战斗/Boss 的感觉
    SUSPENSE = "suspense"           # 悬疑 / 惊悚，阴郁、悬而未决
    CALM = "calm"                   # 舒缓 / 美好，明亮、治愈


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
}


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
# - name: 在 UI 中展示的名称（例如 “默认”“偏旋律”“偏鼓点”）
# - desc: 简短说明，不影响任何逻辑
STYLE_VARIANT_META = {
    SeedMusicStyle.BATTLE: [
        {
            "id": "battle_default",
            "name": "默认",
            "desc": "当前战斗风格的默认平衡：主旋律和鼓点都比较突出。",
        },
        {
            "id": "battle_melody",
            "name": "偏旋律",
            "desc": "主旋律更响、更扎眼，鼓点略微收一点，适合突出主题旋律的战斗场景。",
        },
        {
            "id": "battle_drums",
            "name": "偏鼓点",
            "desc": "鼓点更炸、更密，主旋律略微靠后一些，适合节奏感更强的紧张段落。",
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
            "desc": "主旋律更连续、安静小节更少，适合持续高压的悬疑段落。",
        },
        {
            "id": "suspense_sparse",
            "name": "更空灵",
            "desc": "休止和安静小节更多，鼓点也更弱，适合非常压抑、拉长气氛的环境音。",
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
    length_bars: int = 8,
    style: SeedMusicStyle = SeedMusicStyle.CLASSIC_8BIT,
    variant_id: str = "default",
    intro_ratio: float = 0.0,
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

    # ---- 全局参数（随风格略有变化）----
    # 使用 STYLE_META 中的默认 BPM，保证 UI 展示与生成逻辑完全一致
    bpm = get_style_meta(style)["default_bpm"]
    beats_per_bar = 4.0  # 4/4 拍
    length_bars = max(4, min(length_bars, 64))
    total_beats = length_bars * beats_per_bar
    beat_duration = 60.0 / bpm

    project = Project(name=f"Seed Music ({seed})", bpm=bpm)

    # ---- 结构层：可选的 Intro + 主循环 ----
    # intro_ratio 由 UI 提供，范围 [0, 0.5]，这里换算成前奏/主循环小节数。
    intro_bars = 0
    main_bars = length_bars
    if intro_ratio > 0.0 and length_bars >= 4:
        intro_bars = max(1, int(length_bars * min(intro_ratio, 0.5)))
        intro_bars = min(intro_bars, length_bars // 2)
        main_bars = max(1, length_bars - intro_bars)

    # ---- 调式与音阶（不同风格偏好略不同）----
    # (根音 MIDI, 大/小调标志, 音阶间隔)
    # ---- 风格变体开关（不改变默认行为，只在对应变体下做轻量调整）----
    is_battle_default = style == SeedMusicStyle.BATTLE and variant_id in ("battle_default", "default", "", None)
    is_battle_melody = style == SeedMusicStyle.BATTLE and variant_id == "battle_melody"
    is_battle_drums = style == SeedMusicStyle.BATTLE and variant_id == "battle_drums"

    is_suspense_default = style == SeedMusicStyle.SUSPENSE and variant_id in ("suspense_default", "default", "", None)
    is_suspense_dense = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_dense"
    is_suspense_sparse = style == SeedMusicStyle.SUSPENSE and variant_id == "suspense_sparse"

    if style == SeedMusicStyle.BATTLE:
        # 战斗向：更多小调 / 较高音区
        scale_choices = [
            (60, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # C 小调
            (62, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # D 小调
            (59, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # B 小调
        ]
    elif style == SeedMusicStyle.LOFI:
        # Lofi：中低音区、偏温和
        scale_choices = [
            (57, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # A 大调
            (55, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # G 小调
        ]
    elif style == SeedMusicStyle.SUSPENSE:
        # 悬疑：使用接近日本「和风小调」的五声音阶（类似 In/Hirajoshi），
        # 强调 1, ♭2, 4, 5, ♭7 这些度数。整体音高放在中高音区，更贴近日系“尖”而不闷。
        # 相对度数（半音）：[0, 1, 5, 7, 10] 为主，后两项是重复/移高，保证索引安全。
        japanese_offsets = [0, 1, 5, 7, 10, 12, 13, 17]
        scale_choices = [
            (62, "japanese_like", japanese_offsets),  # D4 附近
            (64, "japanese_like", japanese_offsets),  # E4 附近
        ]
    elif style == SeedMusicStyle.CALM:
        # 舒缓：明亮大调、舒适音区
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (65, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # F 大调
        ]
    else:
        # 经典 8bit：C 大调等常见调式
        scale_choices = [
            (60, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # C 大调
            (57, "minor", [0, 2, 3, 5, 7, 8, 10, 12]),  # A 小调
            (62, "major", [0, 2, 4, 5, 7, 9, 11, 12]),  # D 大调
        ]

    root_midi, mode_name, scale_offsets = rng.choice(scale_choices)

    # 底层和声：用和弦级数（1=I,4=IV,5=V,6=vi,2=ii）
    # 常见流行走向模板集合 + 不同风格的偏好
    if style == SeedMusicStyle.BATTLE:
        progression_templates = [
            [6, 4, 1, 5],  # vi–IV–I–V（更紧张）
            [1, 5, 6, 5],  # I–V–vi–V
        ]
    elif style == SeedMusicStyle.LOFI:
        progression_templates = [
            [1, 6, 4, 5],  # I–vi–IV–V
            [1, 4, 1, 5],  # I–IV–I–V
        ]
    elif style == SeedMusicStyle.SUSPENSE:
        # 悬疑：更多使用 ii、vi，走向悬而未决
        progression_templates = [
            [6, 2, 5, 1],  # vi–ii–V–I
            [1, 2, 6, 5],  # I–ii–vi–V
        ]
    elif style == SeedMusicStyle.CALM:
        # 舒缓：I / IV 停留更久，整体很“稳”
        progression_templates = [
            [1, 4, 1, 5],  # I–IV–I–V
            [1, 4, 5, 1],  # I–IV–V–I
        ]
    else:
        progression_templates = [
            [1, 5, 6, 4],  # I–V–vi–IV
            [1, 4, 5, 1],  # I–IV–V–I
            [6, 4, 1, 5],  # vi–IV–I–V
        ]
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
    # 一个动机 = [(相对度数, 拍长), ...]，以和弦根音为 0
    # 先定义一个基础动机集合，再根据风格做偏好替换。
    base_motifs: List[List[Tuple[int, float]]] = [
        # 上行型：根音 → 三度 / 五度
        [(0, 1.0), (2, 1.0), (4, 2.0)],            # 强-中-强，4 拍
        # 下行回答
        [(4, 1.0), (2, 1.0), (0, 2.0)],
        # 跳进 + 级进
        [(0, 0.5), (4, 0.5), (5, 1.0), (4, 1.0), (2, 1.0)],
        # 短音型重复
        [(0, 0.5), (1, 0.5), (0, 0.5), (1, 0.5), (2, 2.0)],
    ]

    if style == SeedMusicStyle.CALM:
        # 舒缓：更长音值、更少跳进，像在缓慢歌唱
        motifs: List[List[Tuple[int, float]]] = [
            [(0, 2.0), (2, 2.0)],              # I → Ⅲ，整小节两音
            [(0, 1.0), (1, 1.0), (2, 2.0)],    # 1-2-3，级进上行
            [(2, 2.0), (0, 2.0)],              # Ⅲ → I
        ]
    elif style == SeedMusicStyle.SUSPENSE:
        # 悬疑：更多短音与“抖动”型动机，但总时值统一为 4 拍，确保覆盖整小节
        motifs = [
            # 8 个八分音符，围绕 0 / +1 / -1 抖动
            [(0, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5),
             (0, 0.5), (1, 0.5), (0, 0.5), (-1, 0.5)],
            # 前半段碎音，后半段拉长悬挂
            [(0, 0.5), (2, 0.5), (1, 0.5), (0, 0.5),
             (0, 1.0), (2, 1.0)],
            # 由高向下的阴郁走向，覆盖整小节
            [(2, 1.0), (0, 0.5), (1, 0.5), (0, 1.0), (-2, 1.0)],
        ]
    else:
        motifs = base_motifs

    melody_track = Track(name="Seed 主旋律", track_type=TrackType.NOTE_TRACK)
    # 使用风格配置的 ADSR，而不是在这里写死
    melody_adsr = style_params.melody_adsr

    current_beat = 0.0
    last_pitch = root_midi + scale_offsets[chord_root_degree(bars_progression[0])]
    # 控制整体音域：避免旋律跑得过高或过低
    pitch_min = root_midi - 5
    pitch_max = root_midi + 14

    for bar_idx in range(length_bars):
        bar_start = bar_idx * beats_per_bar
        bar_chord_degree = bars_progression[bar_idx]
        bar_root_degree = chord_root_degree(bar_chord_degree)

        # 句式控制：后半段略微抬高音高中心
        phrase_shift = 0
        if bar_idx >= length_bars * 3 // 4:
            phrase_shift = 1  # 最后 1/4 句抬高一点

        # 选择一个动机，偶尔重复上一小节的动机（形成呼应）
        if bar_idx > 0 and rng.random() < 0.4:
            motif = motifs[(bar_idx - 1) % len(motifs)]
        else:
            motif = rng.choice(motifs)

        beat_in_bar = 0.0
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
                    # 在部分弱拍上增加半音邻音抖动，制造不安的“日本小调”味道
                    jitter = rng.choice([-1, 1])
                    base_degree += jitter

            # 叠加简单的句式偏移
            base_degree += phrase_shift * 2  # 抬高一个三度左右

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

            start_time = global_beat * beat_duration

            # 速度：强拍稍大，弱拍稍小，增加律动感（按风格微调）
            if is_strong_beat:
                base_velocity = 120
            else:
                base_velocity = 90 + int(rng.random() * 20)

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

            # Intro 段：整体淡化主旋律，让其更像背景引子
            if intro_bars > 0 and bar_idx < intro_bars:
                base_velocity = int(base_velocity * 0.65)

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
                    # 悬疑：在当前节拍格子内打三连击，同时保证整格几乎被填满，避免“一段一段断掉”的感觉
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
            current_beat = global_beat + dur_beats

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
            # 低音通常比旋律低一个或两个八度
            if style == SeedMusicStyle.SUSPENSE:
                # 悬疑：低音尽量简单，只在日本小调的主音或五度上徘徊，避免过多不协和
                # 使用度数 0（主音）和 3（约等于五度附近）
                bass_degree = 0 if (bar_idx % 2 == 0) else 3
                bass_root_pitch = root_midi - 12 + scale_offsets[max(0, min(bass_degree, len(scale_offsets) - 1))]
            else:
                bass_root_pitch = root_midi - 12 + scale_offsets[bar_root_degree]

            if style == SeedMusicStyle.SUSPENSE and bar_idx in quiet_bars:
                # 安静小节：完全省略低音，让空间更空
                # 「更空灵」变体下，这类小节会更多；「更紧张」变体下则更少
                continue
            elif style == SeedMusicStyle.BATTLE:
                # 战斗风格：每拍都有短促的低音，增强推进感
                start_beats_list = [0.0, 1.0, 2.0, 3.0]
                dur_beats = 0.5
            elif style == SeedMusicStyle.SUSPENSE:
                # 悬疑：偏重 1、3 拍，但时值较短，留出悬空空间
                start_beats_list = [0.0, 2.0]
                dur_beats = 1.0
            elif style == SeedMusicStyle.CALM:
                # 舒缓：更长的根音，给人稳定感
                start_beats_list = [0.0]
                dur_beats = beats_per_bar
            else:
                # 经典 / Lofi：每小节 2 个音（1、3 拍），偶尔只在 1 拍上弹一个长音
                if rng.random() < 0.3:
                    # 一个整小节的持续根音
                    start_beats_list = [0.0]
                    dur_beats = beats_per_bar
                else:
                    start_beats_list = [0.0, 2.0]
                    dur_beats = 2.0

            for sb in start_beats_list:
                start_time = (bar_start + sb) * beat_duration

                if style == SeedMusicStyle.BATTLE:
                    duration_beats_for_time = max(0.25, dur_beats * 0.7)
                elif style == SeedMusicStyle.SUSPENSE:
                    duration_beats_for_time = max(0.5, dur_beats * 0.7)
                elif style == SeedMusicStyle.CALM:
                    duration_beats_for_time = dur_beats * 1.1
                else:
                    duration_beats_for_time = dur_beats

                duration = duration_beats_for_time * beat_duration
                note = Note(
                    pitch=bass_root_pitch,
                    start_time=start_time,
                    duration=duration,
                    velocity=100,
                    waveform=style_params.bass_waveform,
                    duty_cycle=style_params.bass_duty,
                    adsr=bass_adsr,
                )
                bass_track.notes.append(note)

    # 悬疑风格下，为主旋律轨道增加轻微高通 + 颤音，让音色更“尖锐撕裂”
    if style == SeedMusicStyle.SUSPENSE:
        from .effect_processor import FilterParams, FilterType, VibratoParams
        melody_track.filter_params = FilterParams(
            filter_type=FilterType.HIGHPASS,
            cutoff_frequency=600.0,
            resonance=1.2,
            enabled=True,
        )
        melody_track.vibrato_params = VibratoParams(
            rate=6.0,
            depth=0.4,   # 约小半音内抖动，避免完全失真
            enabled=True,
        )

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

            if style == SeedMusicStyle.SUSPENSE:
                # 悬疑：使用固定的「恐怖和弦」模板，减少传统三和弦的明亮感
                # 模板相对度数基于日本小调的索引：0(主音), 1(♭2), 3(4), 4(5), 6(♭7)
                horror_templates = [
                    [0, 1, 4],  # 1, ♭2, 5
                    [0, 3, 6],  # 1, 4, ♭7
                    [1, 4, 6],  # ♭2, 5, ♭7
                ]
                tmpl = rng.choice(horror_templates)
                chord_degrees = []
                for rel in tmpl:
                    idx = (bar_root_degree + rel) % len(scale_offsets)
                    chord_degrees.append(idx)
            else:
                # 和弦三个音：1、3、5 度
                chord_degrees = [
                    bar_root_degree,
                    (bar_root_degree + 2) % 7,
                    (bar_root_degree + 4) % 7,
                ]

            # 只在每小节的前半段铺一个和弦块
            start_time = bar_start * beat_duration
            duration = 2.0 * beat_duration  # 2 拍和声

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

            for d in chord_degrees:
                pitch = root_midi - 12 + scale_offsets[d]  # 比旋律低一组
                # 悬疑风格下和声音量进一步降低，避免盖过主旋律
                harmony_velocity = 80
                if style == SeedMusicStyle.SUSPENSE:
                    harmony_velocity = 55
                elif style == SeedMusicStyle.CALM:
                    harmony_velocity = 70

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

    # 根据风格 / 变体微调各轨道音量，确保主旋律在混音中始终清晰，
    # 同时让风格变体在听感上的差异更明显一些。
    drum_boost = 0.0  # 给后面的鼓轨道一个可调的整体增益
    if style == SeedMusicStyle.SUSPENSE:
        # 悬疑基础平衡
        melody_track.volume = 1.0
        if bass_track is not None:
            bass_track.volume = 0.65
        if harmony_track is not None:
            harmony_track.volume = 0.45
        if is_suspense_dense:
            # 更紧张：整体更“贴脸”，鼓和低音略更明显
            if bass_track is not None:
                bass_track.volume = 0.75
            if harmony_track is not None:
                harmony_track.volume = 0.5
            drum_boost = 0.1
        elif is_suspense_sparse:
            # 更空灵：主旋律保留，但背景整体更轻、更远
            if bass_track is not None:
                bass_track.volume = 0.5
            if harmony_track is not None:
                harmony_track.volume = 0.35
            drum_boost = -0.15
    elif style == SeedMusicStyle.CALM:
        melody_track.volume = 0.9
        if bass_track is not None:
            bass_track.volume = 0.8
        if harmony_track is not None:
            harmony_track.volume = 0.6
    elif style == SeedMusicStyle.BATTLE:
        # 战斗风格在不同变体下明显区分“主旋律优先/鼓点优先”
        if is_battle_melody:
            melody_track.volume = 1.0
            if bass_track is not None:
                bass_track.volume = 0.8
            if harmony_track is not None:
                harmony_track.volume = 0.7
            drum_boost = -0.2   # 鼓整体略退后
        elif is_battle_drums:
            melody_track.volume = 0.8
            if bass_track is not None:
                bass_track.volume = 0.9
            if harmony_track is not None:
                harmony_track.volume = 0.7
            drum_boost = 0.2    # 鼓整体更靠前
        else:
            melody_track.volume = 0.95
            if bass_track is not None:
                bass_track.volume = 0.85
            if harmony_track is not None:
                harmony_track.volume = 0.7

    if harmony_track is not None:
        project.add_track(harmony_track)

    # ---- 鼓轨道：根据风格生成不同节奏 ----
    drum_track = None
    if enable_drums:
        drum_track = Track(name="Seed 鼓点", track_type=TrackType.DRUM_TRACK)

        for bar_idx in range(length_bars):
            bar_start = bar_idx * beats_per_bar

            # Intro 部分的鼓点策略：
            # - Intro 前半段：完全无鼓（留出空间）；
            # - Intro 后半段：只给极简的弱底鼓，用来“预告”节奏，主循环开始后才进入完整鼓型。
            if intro_bars > 0 and bar_idx < intro_bars:
                half_intro = max(1, intro_bars // 2)
                if bar_idx < half_intro:
                    # 完全无鼓
                    continue
                else:
                    # 极简的弱底鼓：仅 1 拍一个 KICK，速度很轻
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.KICK,
                            start_beat=bar_start + 0.0,
                            duration_beats=0.25,
                            velocity=int(70 * style_params.drum_velocity_scale),
                        )
                    )
                    # Intro 内不再进入完整风格鼓型
                    continue

            if style == SeedMusicStyle.BATTLE:
                # 战斗：四拍到底鼓 + 强拍军鼓 + 密集 hi-hat
                # 底鼓：每拍一个
                for k in [0.0, 1.0, 2.0, 3.0]:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.KICK,
                            start_beat=bar_start + k,
                            duration_beats=0.25,
                            velocity=int(125 * style_params.drum_velocity_scale),
                        )
                    )
                # 军鼓：2、4 拍（即节拍 1 和 3）
                for s in [1.0, 3.0]:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.SNARE,
                            start_beat=bar_start + s,
                            duration_beats=0.25,
                            velocity=int(120 * style_params.drum_velocity_scale),
                        )
                    )
                # Hi-hat：八分 + 少量十六分感觉
                hihat_beats = [i * 0.5 for i in range(0, 8)]  # 0,0.5,...,3.5
                for offset in hihat_beats:
                    vel = 85 if offset % 1.0 == 0 else 75  # 强拍的 hi-hat 略重
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.HIHAT,
                            start_beat=bar_start + offset,
                            duration_beats=0.125,
                            velocity=int(vel * style_params.drum_velocity_scale),
                        )
                    )
                # 偶尔在每 4 小节做一个小 fill（简单加个 crash）
                if (bar_idx + 1) % 4 == 0 and rng.random() < 0.5:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.CRASH,
                            start_beat=bar_start + 3.5,
                            duration_beats=0.5,
                            velocity=int(120 * style_params.drum_velocity_scale),
                        )
                    )
            elif style == SeedMusicStyle.SUSPENSE:
                # 悬疑：节奏略错位、少 hi-hat，更多留白
                # 安静小节：完全移除鼓点，只保留旋律/和声
                if bar_idx in quiet_bars:
                    continue
                # 底鼓：1、3 拍稍提前/推后一点
                for k in [0.0, 2.25]:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.KICK,
                            start_beat=bar_start + k,
                            duration_beats=0.25,
                            velocity=int(110 * style_params.drum_velocity_scale),
                        )
                    )
                # 军鼓：2 拍偏后、4 拍前一点，制造不安
                for s in [1.75, 3.5]:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.SNARE,
                            start_beat=bar_start + s,
                            duration_beats=0.25,
                            velocity=int(115 * style_params.drum_velocity_scale),
                        )
                    )
                # Hi-hat：只在部分弱拍上点几下
                hihat_beats = [0.5, 1.5, 2.5]
                for offset in hihat_beats:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.HIHAT,
                            start_beat=bar_start + offset,
                            duration_beats=0.125,
                            velocity=int(70 * style_params.drum_velocity_scale),
                        )
                    )
            elif style == SeedMusicStyle.CALM:
                # 舒缓：简单、稳定的节奏，少量 hi-hat
                drum_track.drum_events.append(
                    DrumEvent(
                        drum_type=DrumType.KICK,
                        start_beat=bar_start + 0.0,
                        duration_beats=0.25,
                        velocity=int(105 * style_params.drum_velocity_scale),
                    )
                )
                drum_track.drum_events.append(
                    DrumEvent(
                        drum_type=DrumType.SNARE,
                        start_beat=bar_start + 2.0,
                        duration_beats=0.25,
                        velocity=int(100 * style_params.drum_velocity_scale),
                    )
                )
                # 稍微稀疏的 hi-hat：只在 1、3 拍附近
                for offset in [1.0, 3.0]:
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.HIHAT,
                            start_beat=bar_start + offset,
                            duration_beats=0.125,
                            velocity=int(65 * style_params.drum_velocity_scale),
                        )
                    )
            else:
                # 经典 / Lofi：相对简单的 backbeat + hi-hat
                # 底鼓（1 拍）
                drum_track.drum_events.append(
                    DrumEvent(
                        drum_type=DrumType.KICK,
                        start_beat=bar_start + 0.0,
                        duration_beats=0.25,
                        velocity=int(120 * style_params.drum_velocity_scale),
                    )
                )
                # 军鼓（3 拍）
                drum_track.drum_events.append(
                    DrumEvent(
                        drum_type=DrumType.SNARE,
                        start_beat=bar_start + 2.0,
                        duration_beats=0.25,
                        velocity=int(115 * style_params.drum_velocity_scale),
                    )
                )

                # HIHAT：在每个 0.5 拍上轻轻敲一下
                hihat_beats = [0.5, 1.0, 1.5, 2.5, 3.0, 3.5]
                for offset in hihat_beats:
                    vel = 80 if style == SeedMusicStyle.CLASSIC_8BIT else 70
                    drum_track.drum_events.append(
                        DrumEvent(
                            drum_type=DrumType.HIHAT,
                            start_beat=bar_start + offset,
                            duration_beats=0.125,
                            velocity=int(vel * style_params.drum_velocity_scale),
                        )
                    )

        # 根据风格 / 变体微调鼓点整体音量
        if style == SeedMusicStyle.SUSPENSE:
            base = 0.6
            drum_track.volume = max(0.2, min(1.2, base + drum_boost))
        elif style == SeedMusicStyle.BATTLE:
            base = 1.0
            drum_track.volume = max(0.2, min(1.2, base + drum_boost))

        project.add_track(drum_track)

    return project


