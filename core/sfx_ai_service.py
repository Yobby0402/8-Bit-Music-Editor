"""Generate validated SFX specs from natural language via an LLM."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from core.llm_client import chat_completion
from core.sfx_generator import SfxSpec, sfx_spec_from_dict

ChatFn = Callable[..., str]


def build_sfx_generation_messages(description: str) -> list[dict[str, str]]:
    """Build a compact prompt for an OpenAI-compatible chat model."""
    clean_description = (description or "").strip()
    if not clean_description:
        raise ValueError("SFX description cannot be empty")
    return [
        {
            "role": "system",
            "content": (
                "You generate short 8bit game sound effects as JSON only. "
                "Return one object with kind, label, notes, and optional "
                "filter_params, delay_params, tremolo_params, vibrato_params. "
                "Each note needs pitch, start_beat, duration_beats, velocity, "
                "waveform, duty_cycle, and adsr. Use <= 8 notes, duration <= 2 beats. "
                "Allowed waveforms: square, triangle, sawtooth, sine, noise."
            ),
        },
        {
            "role": "user",
            "content": f"Create an 8bit SFX for: {clean_description}",
        },
    ]


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM response is empty")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    elif not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response does not contain a JSON object")
        raw = raw[start : end + 1]

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON response must be an object")
    return data


def generate_sfx_spec_from_description(
    description: str,
    *,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout_sec: float = 120.0,
    temperature: float = 0.4,
    chat_fn: ChatFn = chat_completion,
) -> SfxSpec:
    """Call an OpenAI-compatible model and return a validated SfxSpec."""
    messages = build_sfx_generation_messages(description)
    text = chat_fn(
        base_url,
        model,
        messages,
        api_key=api_key,
        timeout_sec=timeout_sec,
        temperature=temperature,
    )
    return sfx_spec_from_dict(extract_json_object(text))


__all__ = [
    "build_sfx_generation_messages",
    "extract_json_object",
    "generate_sfx_spec_from_description",
]
