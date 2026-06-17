"""
Seed 生成的变化维度：盐值与旋钮，用于多路 RNG 与风格内分支。

不依赖 LLM 时也可用「描述 → 哈希盐」拉开听感差异。
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from typing import Tuple

from core.seed_generation_utils import get_rng_from_seed


@dataclass(frozen=True)
class VariationSpec:
    """在固定 SeedMusicStyle 下增加生成随机维度。"""

    variation_salt: str = ""
    knobs: Tuple[int, int, int, int] | None = None
    #: 为真时弱化固定乐句/循环和声进行，使用随机分段与每小节随机和弦级数等。
    free_form_layout: bool = False

    def is_active(self) -> bool:
        return (
            bool(self.variation_salt)
            or self.knobs is not None
            or self.free_form_layout
        )

    def knob(self, index: int, default: int = 0) -> int:
        if self.knobs is None or not (0 <= index < len(self.knobs)):
            return default
        v = self.knobs[index]
        if not isinstance(v, int) or v < 0 or v > 9:
            return default
        return v


def variation_salt_from_description(text: str) -> str:
    """对用户描述做稳定短哈希，用作 RNG 材料。"""
    t = (text or "").strip()
    if not t:
        return ""
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]


_KNOB_LINE = re.compile(
    r"^K:\s*([0-9])\s*,\s*([0-9])\s*,\s*([0-9])\s*,\s*([0-9])\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def parse_knob_line(text: str) -> Tuple[int, int, int, int] | None:
    """解析模型输出的单行旋钮，例如 ``K:2,0,3,1``。"""
    if not text:
        return None
    m = _KNOB_LINE.search(text.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def parse_ai_seed_response(raw: str) -> tuple[str, Tuple[int, int, int, int] | None]:
    """
    解析 LLM 返回：第一行为 seed 文本；可选第二行为 ``K:…`` 旋钮行。

    若无有效第一行则返回 ("", None)。
    """
    if not raw or not str(raw).strip():
        return "", None
    lines = [ln.strip() for ln in str(raw).strip().splitlines() if ln.strip()]
    if not lines:
        return "", None
    seed_line = lines[0][:128]
    knobs: Tuple[int, int, int, int] | None = None
    for ln in lines[1:]:
        parsed = parse_knob_line(ln)
        if parsed is not None:
            knobs = parsed
            break
    return seed_line, knobs


@dataclass(frozen=True)
class RngFamily:
    """多路随机流；legacy 模式下五路可为同一 Random 实例。"""

    structure: random.Random
    melody: random.Random
    bass: random.Random
    harmony: random.Random
    drums: random.Random


def build_rng_family(
    seed: str | int,
    style_value: str,
    variation: VariationSpec | None,
) -> RngFamily:
    """
    无变化规格或未激活时，与旧版一致：单一路 RNG 驱动全部逻辑。

    激活时：为结构/旋律/低音/和声/鼓点派生独立 RNG，并纳入盐与旋钮。
    """
    if variation is None or not variation.is_active():
        rng = get_rng_from_seed(seed)
        return RngFamily(rng, rng, rng, rng, rng)

    material = (
        f"{seed!s}|{style_value}|{variation.variation_salt}|{variation.knobs or ()}"
        f"|ff={int(variation.free_form_layout)}"
    )
    return RngFamily(
        structure=get_rng_from_seed(material + ":structure"),
        melody=get_rng_from_seed(material + ":melody"),
        bass=get_rng_from_seed(material + ":bass"),
        harmony=get_rng_from_seed(material + ":harmony"),
        drums=get_rng_from_seed(material + ":drums"),
    )


def filter_motifs_by_bank(
    motifs: list,
    bank: int,
    n_banks: int = 3,
) -> list:
    """按索引分流动机池，保证非空。"""
    if not motifs:
        return motifs
    b = bank % n_banks
    filtered = [m for i, m in enumerate(motifs) if i % n_banks == b]
    return filtered if filtered else motifs


__all__ = [
    "RngFamily",
    "VariationSpec",
    "build_rng_family",
    "filter_motifs_by_bank",
    "parse_ai_seed_response",
    "parse_knob_line",
    "variation_salt_from_description",
]
