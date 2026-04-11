"""
主窗口中的 Seed 生成入口与结果应用逻辑。
"""

from __future__ import annotations

import sys
from typing import Any

from app_info import APP_NAME
from core.seed_generation_service import (
    SeedGenerationRequest,
    SeedGenerationResult,
    generate_seed_project,
)
from ui.error_utils import show_error_with_console
from ui.main_window_dialogs import prompt_seed_generation


def build_seed_generation_settings(selection: Any) -> dict[str, object]:
    """将对话框选择转换为可持久化的最近一次设置。"""
    return {
        "seed": selection.seed,
        "length_index": selection.length_index,
        "style_index": selection.style_index,
        "variant_index": selection.variant_index,
        "harmony": selection.use_harmony,
        "drums": selection.use_drums,
    }


def build_seed_generation_request(selection: Any) -> SeedGenerationRequest | None:
    """将 UI 选择转换为核心服务请求。"""
    request = SeedGenerationRequest(
        seed=selection.seed,
        length_bars=selection.length_bars,
        style=selection.style,
        variant_id=selection.variant_id,
        use_harmony=selection.use_harmony,
        use_drums=selection.use_drums,
    ).normalized()
    if not request.seed:
        return None
    return request


def build_seed_window_title(app_name: str, seed: str) -> str:
    """构建 Seed 生成结果对应的窗口标题。"""
    return f"{app_name} - Seed: {seed}"


def build_seed_status_message(seed: str) -> str:
    """构建 Seed 生成完成后的状态栏文案。"""
    return f"已基于 Seed “{seed}” 生成一个新的项目"


class MainWindowSeedOpsMixin:
    """承载 MainWindow 中的 Seed 生成流程。"""

    def _remember_seed_generation_selection(self, selection: Any):
        """记录最近一次 Seed 生成对话框设置。"""
        self._last_seed_generation_settings = build_seed_generation_settings(selection)

    def _apply_seed_generation_result(self, result: SeedGenerationResult):
        """将 Seed 生成结果应用到当前主窗口。"""
        request = result.request
        project = result.project

        self.stop()
        self.sequencer.set_project(project)
        self.current_file_path = None
        self.current_midi_file_path = None
        self.setWindowTitle(build_seed_window_title(APP_NAME, request.seed))
        self._update_file_name_display()
        self._clear_project_panel_state()
        self._reset_project_selection()
        self._sync_project_bpm_to_ui(float(project.bpm), refresh_sequence_widget=False)

        self.current_seed_style = request.style
        self.current_seed_variant = request.variant_id
        if hasattr(self, "style_params_panel"):
            self.style_params_panel.set_style(request.style, request.variant_id, project)

        self._refresh_project_after_open()
        self.statusBar().showMessage(build_seed_status_message(request.seed))

    def generate_music_from_seed(self):
        """从 UI 收集参数并触发 Seed 生成。"""
        if not self.check_unsaved_changes():
            return

        selection = prompt_seed_generation(
            self,
            getattr(self, "_last_seed_generation_settings", None),
        )
        if selection is None:
            return

        self._remember_seed_generation_selection(selection)
        request = build_seed_generation_request(selection)
        if request is None:
            return

        try:
            result = generate_seed_project(request)
        except Exception as exc:
            error_msg = f"基于 Seed 生成音乐时出错：{exc}"
            show_error_with_console(self, "生成失败", error_msg, "critical", exc_info=sys.exc_info())
            return

        self._apply_seed_generation_result(result)
