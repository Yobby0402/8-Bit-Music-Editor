"""
OpenAI 兼容 Chat Completions（用于本地 LM Studio 等）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx


def chat_completion(
    base_url: str,
    model: str,
    messages: List[Dict[str, Any]],
    *,
    api_key: str = "",
    timeout_sec: float = 120.0,
    temperature: float = 0.7,
) -> str:
    """
    调用 ``POST {base_url}/chat/completions``，返回 assistant 文本内容。

    ``base_url`` 通常为 ``http://127.0.0.1:1234/v1``（含 /v1 后缀）。
    """
    root = (base_url or "").strip().rstrip("/")
    if not root:
        raise ValueError("base_url 不能为空")
    url = f"{root}/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("响应中缺少 choices")
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if content is None:
        raise ValueError("响应中缺少 message.content")
    if not isinstance(content, str):
        return json.dumps(content, ensure_ascii=False)
    return content


__all__ = ["chat_completion"]
