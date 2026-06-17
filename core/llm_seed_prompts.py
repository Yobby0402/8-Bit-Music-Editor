"""Seed 对话框调用本地 LLM 时使用的提示词。"""

from __future__ import annotations

from typing import Any, Dict, List


def build_seed_suggest_messages(style_label: str, user_description: str) -> List[Dict[str, Any]]:
    """构造 chat completion 的 messages。"""
    desc = (user_description or "").strip() or "（用户未填写具体描述，请自由发挥，但仍要符合风格）"
    system = (
        "你是 8bit 游戏音乐种子助手。用户已选定「曲风」，你必须保持该曲风气质，"
        "只输出两行纯文本，不要标题、不要 Markdown、不要 JSON。\n"
        "第一行：一个简短的 seed 短语（中文或英文均可，不超过 80 个字符），用作随机种子标签。\n"
        "第二行：必须严格符合格式 K:a,b,c,d —— 其中 a、b、c、d 各为 0-9 的单个数字，"
        "含义依次为：旋律动机分组偏好(0-9)、鼓点密度(0-9)、低音活跃度(0-9)、和声浓淡(0-9)；"
        "数字越大通常越饱满或越密。示例：K:3,6,2,4\n"
        "除上述两行外不要输出任何其他文字。"
    )
    user = f"曲风（已锁定）：{style_label}\n用户大致描述：{desc}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


__all__ = ["build_seed_suggest_messages"]
