"""
Seed 风格目录与默认参数。

集中管理 Seed 生成所需的风格枚举、默认音色参数、UI 元信息、
变体说明以及运行时覆盖接口，避免这些目录型数据继续堆积在生成器主文件中。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import ADSRParams, WaveformType


class SeedMusicStyle(Enum):
    """Seed 生成音乐的风格类型。"""

    CLASSIC_8BIT = "classic_8bit"  # 经典 8bit / FC 游戏风
    LOFI = "lofi"  # 稍慢、柔和一点的节奏与音色
    BATTLE = "battle"  # 更紧张、偏战斗/Boss 的感觉
    SUSPENSE = "suspense"  # 悬疑 / 惊悚，阴郁、悬而未决
    CALM = "calm"  # 舒缓 / 美好，明亮、治愈
    ROCK = "rock"  # 重金属 / 摇滚，突出鼓点和打击乐
    DANCE = "dance"  # 慢摇/舞曲，动感律动，适合跳舞
    WORKSHOP = "workshop"  # 工作坊 / 专注，Ambient Techno 风格


@dataclass
class StyleParams:
    """
    单一风格的参数配置。

    主要控制音色与动态，而非基础旋律结构。
    """

    melody_waveform: WaveformType
    melody_duty: float
    melody_adsr: ADSRParams
    bass_waveform: WaveformType
    bass_duty: float
    bass_adsr: ADSRParams
    harmony_waveform: WaveformType
    harmony_duty: float
    harmony_adsr: ADSRParams
    drum_velocity_scale: float


def _build_style_params() -> dict[SeedMusicStyle, StyleParams]:
    """
    定义各个风格下的默认音色与动态配置。

    这里不改变“音符落在哪一拍 / 音高怎么走”的基础旋律逻辑，
    只决定“用什么音色、力度、包络去说这句话”。
    """

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
            drum_velocity_scale=0.8,
        ),
        SeedMusicStyle.CALM: StyleParams(
            melody_waveform=WaveformType.TRIANGLE,
            melody_duty=0.4,
            melody_adsr=ADSRParams(attack=0.01, decay=0.15, sustain=0.85, release=0.35),
            bass_waveform=WaveformType.TRIANGLE,
            bass_duty=0.5,
            bass_adsr=pad_adsr,
            harmony_waveform=(
                WaveformType.SINE if hasattr(WaveformType, "SINE") else WaveformType.TRIANGLE
            ),
            harmony_duty=0.5,
            harmony_adsr=pad_adsr,
            drum_velocity_scale=0.7,
        ),
        SeedMusicStyle.ROCK: StyleParams(
            melody_waveform=WaveformType.SAWTOOTH,
            melody_duty=0.5,
            melody_adsr=ADSRParams(attack=0.001, decay=0.1, sustain=0.7, release=0.15),
            bass_waveform=WaveformType.SQUARE,
            bass_duty=0.5,
            bass_adsr=pluck_adsr,
            harmony_waveform=WaveformType.SAWTOOTH,
            harmony_duty=0.5,
            harmony_adsr=ADSRParams(attack=0.005, decay=0.12, sustain=0.75, release=0.2),
            drum_velocity_scale=1.3,
        ),
        SeedMusicStyle.DANCE: StyleParams(
            melody_waveform=WaveformType.SQUARE,
            melody_duty=0.5,
            melody_adsr=ADSRParams(attack=0.002, decay=0.08, sustain=0.75, release=0.12),
            bass_waveform=WaveformType.SQUARE,
            bass_duty=0.5,
            bass_adsr=ADSRParams(attack=0.001, decay=0.05, sustain=0.9, release=0.1),
            harmony_waveform=WaveformType.SQUARE,
            harmony_duty=0.4,
            harmony_adsr=ADSRParams(attack=0.01, decay=0.1, sustain=0.7, release=0.2),
            drum_velocity_scale=1.2,
        ),
        SeedMusicStyle.WORKSHOP: StyleParams(
            melody_waveform=WaveformType.SQUARE,
            melody_duty=0.45,
            melody_adsr=ADSRParams(attack=0.01, decay=0.1, sustain=0.8, release=0.2),
            bass_waveform=WaveformType.SQUARE,
            bass_duty=0.5,
            bass_adsr=ADSRParams(attack=0.005, decay=0.08, sustain=0.85, release=0.15),
            harmony_waveform=WaveformType.TRIANGLE,
            harmony_duty=0.5,
            harmony_adsr=ADSRParams(attack=0.02, decay=0.15, sustain=0.75, release=0.3),
            drum_velocity_scale=1.0,
        ),
    }


STYLE_PARAMS_MAP = _build_style_params()

# 运行时风格参数覆盖（由 UI 调整，不影响默认常量）
RUNTIME_STYLE_OVERRIDES: dict[SeedMusicStyle, StyleParams] = {}


def get_style_params(style: SeedMusicStyle) -> StyleParams:
    """
    对外暴露的风格参数访问接口。

    若存在运行时覆盖（来自 UI 的风格参数面板），优先使用覆盖值。
    """

    if style in RUNTIME_STYLE_OVERRIDES:
        return RUNTIME_STYLE_OVERRIDES[style]
    return STYLE_PARAMS_MAP.get(style, STYLE_PARAMS_MAP[SeedMusicStyle.CLASSIC_8BIT])


def set_style_runtime_override(style: SeedMusicStyle, params: StyleParams) -> None:
    """由 UI 调用，用于在运行时覆盖某个风格的参数。"""

    RUNTIME_STYLE_OVERRIDES[style] = params


def clear_style_runtime_override(style: SeedMusicStyle | None = None) -> None:
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
STYLE_META: dict[SeedMusicStyle, dict[str, object]] = {
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
        "short_desc": "高 BPM、小调为主、主旋律简单重复、低音强烈每拍踩点、鼓点密集强烈（双踩、密集 hi-hat），使用锯齿波和方波营造失真感，突出节奏和打击乐。",
    },
    SeedMusicStyle.DANCE: {
        "default_bpm": 130,
        "mood": "动感 / 律动 / House舞曲",
        "short_desc": "House 舞曲风格，BPM 130、大调为主、主旋律简单重复易记、低音每拍踩点厚重有力、鼓点每小节两个'动次打次'（Kick-Snare-Kick-Snare），hi-hat 在弱拍，结构：Intro（纯鼓点）→ Verse（基础旋律）→ 主旋律进入，适合跳舞和动感场景。",
    },
    SeedMusicStyle.WORKSHOP: {
        "default_bpm": 108,
        "mood": "平静 / 专注 / 技术感",
        "short_desc": "Ambient Techno 风格，BPM 108、大调或中性调式、主旋律简单重复不干扰、低音每拍稳定踩点、鼓点清晰但不激烈（Kick 每拍，Snare 在 2、4 拍），hi-hat 在弱拍，整体平静但有推进感，适合工作、研发、制作装备等专注场景。",
    },
}


def get_style_meta(style: SeedMusicStyle) -> dict[str, object]:
    """
    提供给 UI / 其它模块使用的风格元信息接口。

    包含 `default_bpm` / `mood` / `short_desc` 等只读信息。
    """

    return STYLE_META.get(style, STYLE_META[SeedMusicStyle.CLASSIC_8BIT])


# 风格变体元信息（在基础风格之上做轻量偏移，不改变默认行为）
STYLE_VARIANT_META: dict[SeedMusicStyle, list[dict[str, str]]] = {
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


def get_style_variants(style: SeedMusicStyle) -> list[dict[str, str]]:
    """
    返回某个风格下可用的变体列表。

    每个元素为 `{ "id": str, "name": str, "desc": str }`。
    若未定义专门的变体，则返回仅包含“默认”的列表。
    """

    if style in STYLE_VARIANT_META:
        return STYLE_VARIANT_META[style]
    return [
        {
            "id": "default",
            "name": "默认",
            "desc": "",
        }
    ]


__all__ = [
    "RUNTIME_STYLE_OVERRIDES",
    "STYLE_META",
    "STYLE_PARAMS_MAP",
    "STYLE_VARIANT_META",
    "SeedMusicStyle",
    "StyleParams",
    "clear_style_runtime_override",
    "get_style_meta",
    "get_style_params",
    "get_style_variants",
    "set_style_runtime_override",
]
