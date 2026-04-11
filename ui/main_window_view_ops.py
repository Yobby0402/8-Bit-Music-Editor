"""
主窗口中的视图切换和示波器相关操作。
"""

from __future__ import annotations

from typing import Sequence

from core.models import Track
from ui.main_window_dialogs import (
    prompt_oscilloscope_code_language,
    prompt_oscilloscope_pre_render_count,
    prompt_oscilloscope_render_count,
    prompt_track_selection,
)
from ui.theme import theme_manager

OSCILLOSCOPE_NO_ENABLED_TRACKS = "no_enabled_tracks"
OSCILLOSCOPE_USER_SELECTION_DISABLED = "user_selection_disabled"
OSCILLOSCOPE_NO_SELECTED_TRACK = "no_selected_track"
OSCILLOSCOPE_SELECTED_TRACK_DISABLED = "selected_track_disabled"


def get_enabled_tracks(
    tracks: Sequence[Track],
    playback_enabled: dict[int, bool] | None,
) -> list[Track]:
    """按播放设置面板的启用状态筛出可渲染音轨。"""
    if playback_enabled:
        return [track for track in tracks if playback_enabled.get(id(track), track.enabled)]
    return [track for track in tracks if track.enabled]


def filter_render_tracks(
    selected_tracks: Sequence[Track],
    enabled_tracks: Sequence[Track],
) -> list[Track]:
    """过滤掉已失效或未启用的示波器渲染选择。"""
    enabled_track_ids = {id(track) for track in enabled_tracks}
    return [track for track in selected_tracks if id(track) in enabled_track_ids]


def resolve_oscilloscope_tracks(
    enabled_tracks: Sequence[Track],
    user_selected_tracks: Sequence[Track] | None,
    selected_track: Track | None,
) -> tuple[list[Track], str | None]:
    """决定示波器当前应渲染哪些音轨。"""
    if not enabled_tracks:
        return [], OSCILLOSCOPE_NO_ENABLED_TRACKS

    if user_selected_tracks:
        filtered_tracks = filter_render_tracks(user_selected_tracks, enabled_tracks)
        if filtered_tracks:
            return filtered_tracks, None
        return [], OSCILLOSCOPE_USER_SELECTION_DISABLED

    if selected_track is None:
        return [], OSCILLOSCOPE_NO_SELECTED_TRACK
    enabled_track_ids = {id(track) for track in enabled_tracks}
    if id(selected_track) not in enabled_track_ids:
        return [], OSCILLOSCOPE_SELECTED_TRACK_DISABLED

    return list(enabled_tracks), None


class MainWindowViewOpsMixin:
    """承载 MainWindow 中的视图切换和示波器配置流程。"""

    def _get_enabled_tracks_for_render(self) -> list[Track]:
        """根据音轨启用状态和播放设置获取可渲染音轨。"""
        playback_enabled = getattr(self.sequencer, "playback_enabled_tracks", {})
        return get_enabled_tracks(self.sequencer.project.tracks, playback_enabled)

    def _set_view_index(self, index: int):
        """切换视图并同步拨动开关状态。"""
        if hasattr(self, "view_stack"):
            self.view_stack.setCurrentIndex(index)

        if not hasattr(self, "view_toggle_switch"):
            return

        try:
            self.view_toggle_switch.position_changed.disconnect(self.on_view_switch_changed)
        except TypeError:
            pass

        self.view_toggle_switch.animate_to(index)
        self.view_toggle_switch.position_changed.connect(self.on_view_switch_changed)

    def _show_oscilloscope_issue(self, issue_code: str | None):
        """统一展示示波器切换失败的提示。"""
        message_map = {
            OSCILLOSCOPE_NO_ENABLED_TRACKS: "没有启用的音轨，请先启用音轨",
            OSCILLOSCOPE_USER_SELECTION_DISABLED: "选择的音轨未启用，请先启用音轨",
            OSCILLOSCOPE_NO_SELECTED_TRACK: "请先选择一个音轨",
            OSCILLOSCOPE_SELECTED_TRACK_DISABLED: "当前选中的音轨未启用，请先启用音轨",
        }
        if issue_code in message_map:
            self.statusBar().showMessage(message_map[issue_code])

    def switch_view(self, index: int):
        """切换序列视图和示波器视图。"""
        if index == 1 and hasattr(self, "oscilloscope_widget"):
            enabled_tracks = self._get_enabled_tracks_for_render()
            user_selected_tracks = list(
                getattr(self.oscilloscope_widget, "_selected_tracks_for_render", []) or []
            )
            selected_track = self._get_selected_track()
            tracks_to_render, issue_code = resolve_oscilloscope_tracks(
                enabled_tracks,
                user_selected_tracks,
                selected_track,
            )

            if tracks_to_render:
                if user_selected_tracks:
                    self.oscilloscope_widget.set_tracks(tracks_to_render)
                else:
                    self.oscilloscope_widget.set_tracks(
                        tracks_to_render,
                        selected_track=selected_track,
                    )
            else:
                self.oscilloscope_widget.set_tracks([])
                self._show_oscilloscope_issue(issue_code)

        self._set_view_index(index)

    def _get_selected_track(self):
        """从多个可能来源获取当前选中的音轨。"""
        if hasattr(self, "sequence_widget") and hasattr(self.sequence_widget, "highlighted_track"):
            if self.sequence_widget.highlighted_track:
                return self.sequence_widget.highlighted_track

        if hasattr(self, "selected_track") and self.selected_track:
            return self.selected_track

        if hasattr(self, "unified_editor") and hasattr(self.unified_editor, "selected_track"):
            if self.unified_editor.selected_track:
                return self.unified_editor.selected_track

        return None

    def on_view_switch_changed(self, position: int):
        """视图拨动开关位置改变。"""
        self.switch_view(position)

    def on_render_waveform_requested(self, _track):
        """根据当前启用的音轨切换到示波器渲染。"""
        enabled_tracks = self._get_enabled_tracks_for_render()
        if not enabled_tracks:
            self.statusBar().showMessage("没有启用的音轨，请先启用音轨")
            return

        if len(enabled_tracks) <= 3:
            self.oscilloscope_widget.set_selected_tracks(enabled_tracks)
            self.oscilloscope_widget.set_tracks(enabled_tracks)
            self._set_view_index(1)
            self.statusBar().showMessage(f"正在渲染 {len(enabled_tracks)} 个音轨的波形")
            return

        self.show_track_selection_dialog(enabled_tracks)

    def show_oscilloscope_render_count_dialog(self):
        """显示示波器渲染音符数量设置对话框。"""
        if not hasattr(self, "oscilloscope_widget"):
            return

        value = prompt_oscilloscope_render_count(
            self,
            theme_manager.current_theme,
            self.oscilloscope_widget.max_notes_to_render,
        )
        if value is None:
            return

        self.oscilloscope_widget.max_notes_to_render = value
        if hasattr(self.oscilloscope_widget, "waveform_cache"):
            self.oscilloscope_widget.waveform_cache.clear()
        self.oscilloscope_widget.update()

    def show_oscilloscope_pre_render_dialog(self):
        """显示示波器预渲染音符数量设置对话框。"""
        if not hasattr(self, "oscilloscope_widget"):
            return

        value = prompt_oscilloscope_pre_render_count(
            self,
            theme_manager.current_theme,
            self.oscilloscope_widget.pre_render_notes,
        )
        if value is None:
            return

        self.oscilloscope_widget.pre_render_notes = value
        self.oscilloscope_widget.update()

    def show_oscilloscope_code_language_dialog(self):
        """显示示波器代码语言设置对话框。"""
        if not hasattr(self, "oscilloscope_widget"):
            return

        result = prompt_oscilloscope_code_language(
            self,
            theme_manager.current_theme,
            self.oscilloscope_widget.code_language,
            self.oscilloscope_widget.code_templates,
        )
        if result is None:
            return

        selected_language, template = result
        self.oscilloscope_widget.code_language = selected_language
        self.oscilloscope_widget.code_templates[selected_language] = template
        self.oscilloscope_widget.update()

    def show_track_selection_dialog(self, enabled_tracks):
        """在音轨较多时弹出示波器渲染选择对话框。"""
        default_selected = list(
            getattr(self.oscilloscope_widget, "_selected_tracks_for_render", []) or enabled_tracks[:3]
        )
        selected_tracks = prompt_track_selection(
            self,
            theme_manager.current_theme,
            enabled_tracks,
            default_selected,
        )
        if not selected_tracks:
            return

        self.oscilloscope_widget.set_selected_tracks(selected_tracks)
        self.oscilloscope_widget.set_tracks(selected_tracks)
        self._set_view_index(1)
        self.statusBar().showMessage(f"正在渲染 {len(selected_tracks)} 个音轨的波形")
