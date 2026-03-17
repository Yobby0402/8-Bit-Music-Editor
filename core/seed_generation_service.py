"""
Seed 生成服务层。

负责把 Seed 生成请求规范化，并通过核心生成器返回统一结果。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.models import Project
from core.seed_music_generator import SeedMusicStyle, generate_simple_project_from_seed


@dataclass(frozen=True)
class SeedGenerationRequest:
    """描述一次 Seed 生成请求。"""

    seed: str
    length_bars: int
    style: SeedMusicStyle
    variant_id: str = "default"
    use_harmony: bool = True
    use_drums: bool = True

    def normalized(self) -> "SeedGenerationRequest":
        """返回标准化后的请求副本。"""
        seed = "" if self.seed is None else str(self.seed).strip()
        variant_id = self.variant_id
        if isinstance(variant_id, str):
            variant_id = variant_id.strip()

        return SeedGenerationRequest(
            seed=seed,
            length_bars=int(self.length_bars),
            style=self.style,
            variant_id=variant_id or "default",
            use_harmony=bool(self.use_harmony),
            use_drums=bool(self.use_drums),
        )


@dataclass(frozen=True)
class SeedGenerationResult:
    """Seed 生成服务返回的统一结果。"""

    request: SeedGenerationRequest
    project: Project


def validate_seed_generation_request(request: SeedGenerationRequest) -> None:
    """校验 Seed 生成请求。"""
    if not request.seed:
        raise ValueError("seed 不能为空")
    if request.length_bars <= 0:
        raise ValueError("length_bars 必须大于 0")
    if not isinstance(request.style, SeedMusicStyle):
        raise ValueError("style 必须是 SeedMusicStyle")


def generate_seed_project(request: SeedGenerationRequest) -> SeedGenerationResult:
    """根据请求生成 Project，并返回统一结果对象。"""
    normalized_request = request.normalized()
    validate_seed_generation_request(normalized_request)

    project = generate_simple_project_from_seed(
        normalized_request.seed,
        length_bars=normalized_request.length_bars,
        style=normalized_request.style,
        variant_id=normalized_request.variant_id,
        enable_bass=True,
        enable_harmony=normalized_request.use_harmony,
        enable_drums=normalized_request.use_drums,
    )
    return SeedGenerationResult(request=normalized_request, project=project)
