"""
Seed 音乐结构预设与长度映射。

集中管理不同小节数对应的乐句结构，避免这些目录型数据继续堆在生成器主文件中。
"""

from __future__ import annotations

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

    closest = min(MUSIC_STRUCTURE_PRESETS.keys(), key=lambda x: abs(x - bars))
    base_structure = MUSIC_STRUCTURE_PRESETS[closest].copy()

    if bars < closest:
        phrase_count = bars // 4
        base_structure["phrases"] = base_structure["phrases"][:phrase_count]
    elif bars > closest:
        phrase_count = bars // 4
        current_phrases = len(base_structure["phrases"])
        if phrase_count > current_phrases:
            last_phrase = base_structure["phrases"][-1]
            base_structure["phrases"].extend([last_phrase] * (phrase_count - current_phrases))

    return base_structure


__all__ = ["MUSIC_STRUCTURE_PRESETS", "get_structure_for_bars"]
