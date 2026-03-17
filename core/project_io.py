"""
项目文件读写工具。
"""

import json
from pathlib import Path

from core.models import Project


def load_project_from_file(file_path: str) -> Project:
    """从 JSON 项目文件读取并构建 Project。"""
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return Project.from_dict(data)


def save_project_to_file(project: Project, file_path: str) -> None:
    """将 Project 保存到 JSON 项目文件。"""
    path = Path(file_path)
    with path.open("w", encoding="utf-8") as file:
        json.dump(project.to_dict(), file, indent=2, ensure_ascii=False)
