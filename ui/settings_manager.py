"""
设置管理器

管理应用程序的设置，包括是否吸附对齐到节拍、是否允许重叠等。
"""

import json
import os
from typing import Dict, Any
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication


class SettingsManager(QObject):
    """设置管理器"""
    
    DEFAULT_SETTINGS = {
        "snap_to_beat": True,      # 是否吸附对齐到节拍
        "allow_overlap": False,    # 是否允许重叠
        "stack_overlapped_notes": False,  # 是否将重叠音符以"蜘蛛纸牌"方式垂直摞起
        "show_velocity_opacity": False,  # 是否根据力度显示音符透明度（力度越小越透明）
        # 播放相关
        "playhead_refresh_interval_ms": 50,    # 播放线刷新间隔（毫秒），默认50ms≈20FPS
        # 显示与主题相关设置
        "ui_background_color": "#FAFAFA",   # 全局背景色
        "ui_foreground_color": "#2E7D32",   # 全局前景/文字主色
        "ui_font_size": 10,                 # 全局基础字体大小（点数）
        "ui_font_family": "",               # 全局字体（空表示使用系统/Qt默认，如微软雅黑等）
        # 按钮字体（独立于全局字体）
        "ui_button_font_size": 11,
        "ui_button_font_family": "",
        # 背景渐变设置
        "ui_background_gradient_enabled": False,      # 是否启用背景渐变
        "ui_background_gradient_color2": "#FFFFFF",   # 渐变第二颜色
        # 渐变模式：none/center/top_bottom/bottom_top/left_right/right_left/diagonal
        "ui_background_gradient_mode": "none",
        # 不同波形的主题色（用于网格音符、可视化等）
        "waveform_color_square": "#FF6B6B",
        "waveform_color_triangle": "#4ECDC4",
        "waveform_color_sawtooth": "#FFE66D",
        "waveform_color_sine": "#95E1D3",
        "waveform_color_noise": "#969696",
    }
    
    def __init__(self, parent=None):
        """初始化设置管理器"""
        super().__init__(parent)
        self.settings: Dict[str, Any] = {}
        self.config_file = os.path.join(
            QApplication.instance().applicationDirPath(),
            "settings.json"
        )
        # 如果不在应用程序目录，使用用户配置目录
        if not os.path.exists(QApplication.instance().applicationDirPath()):
            from PyQt5.QtCore import QStandardPaths
            config_dir = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
            os.makedirs(os.path.join(config_dir, "8bit_music_editor"), exist_ok=True)
            self.config_file = os.path.join(config_dir, "8bit_music_editor", "settings.json")
        
        self.load_settings()
    
    def load_settings(self):
        """加载设置"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        
        # 尝试从文件加载
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # 合并保存的设置（只更新存在的键）
                    for key, value in saved_settings.items():
                        if key in self.settings:
                            self.settings[key] = value
            except Exception as e:
                print(f"加载设置失败: {e}")
    
    def save_settings(self):
        """保存设置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def get(self, key: str, default=None):
        """获取设置值"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置值"""
        if key in self.DEFAULT_SETTINGS:
            self.settings[key] = value
            self.save_settings()
    
    def reset_to_defaults(self):
        """重置为默认值"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()
    
    # 便捷方法
    def is_snap_to_beat_enabled(self) -> bool:
        """是否启用吸附对齐到节拍"""
        return self.get("snap_to_beat", True)
    
    def is_overlap_allowed(self) -> bool:
        """是否允许重叠"""
        return self.get("allow_overlap", False)
    
    def set_snap_to_beat(self, enabled: bool):
        """设置是否吸附对齐到节拍"""
        self.set("snap_to_beat", enabled)
    
    def set_allow_overlap(self, allowed: bool):
        """设置是否允许重叠"""
        self.set("allow_overlap", allowed)

    def is_stack_overlapped_notes_enabled(self) -> bool:
        """是否启用重叠音符垂直摞起显示（蜘蛛纸牌样式）"""
        return bool(self.get("stack_overlapped_notes", False))

    def set_stack_overlapped_notes(self, enabled: bool):
        """设置是否启用重叠音符垂直摞起显示"""
        self.set("stack_overlapped_notes", bool(enabled))

    # 播放线刷新率相关
    def get_playhead_refresh_interval(self) -> int:
        """获取播放线刷新间隔（毫秒）"""
        return int(self.get("playhead_refresh_interval_ms", self.DEFAULT_SETTINGS["playhead_refresh_interval_ms"]))

    def set_playhead_refresh_interval(self, interval_ms: int):
        """设置播放线刷新间隔（毫秒）"""
        interval_ms = max(10, min(200, int(interval_ms)))  # 限制在10-200ms之间
        self.set("playhead_refresh_interval_ms", interval_ms)
    
    # ===== 显示相关便捷方法 =====
    def get_ui_background_color(self) -> str:
        """获取全局背景色（十六进制字符串）"""
        return self.get("ui_background_color", self.DEFAULT_SETTINGS["ui_background_color"])
    
    def set_ui_background_color(self, color: str):
        """设置全局背景色"""
        self.set("ui_background_color", color)
    
    def get_ui_foreground_color(self) -> str:
        """获取全局前景色（主要文字颜色）"""
        return self.get("ui_foreground_color", self.DEFAULT_SETTINGS["ui_foreground_color"])
    
    def set_ui_foreground_color(self, color: str):
        """设置全局前景色"""
        self.set("ui_foreground_color", color)
    
    def get_ui_font_size(self) -> int:
        """获取全局基础字体大小（点数）"""
        return int(self.get("ui_font_size", self.DEFAULT_SETTINGS["ui_font_size"]))
    
    def set_ui_font_size(self, size: int):
        """设置全局基础字体大小（点数）"""
        self.set("ui_font_size", int(size))
    
    def get_ui_font_family(self) -> str:
        """获取全局字体族名称"""
        return self.get("ui_font_family", self.DEFAULT_SETTINGS["ui_font_family"])
    
    def set_ui_font_family(self, family: str):
        """设置全局字体族名称"""
        self.set("ui_font_family", family or "")
    
    # 波形主题色
    def get_waveform_color(self, waveform_key: str) -> str:
        """根据键名获取波形颜色"""
        default = self.DEFAULT_SETTINGS.get(waveform_key, "#FFFFFF")
        return self.get(waveform_key, default)
    
    def set_waveform_color(self, waveform_key: str, color: str):
        """设置波形颜色"""
        self.set(waveform_key, color)
    
    # 背景渐变相关
    def is_background_gradient_enabled(self) -> bool:
        """是否启用背景渐变"""
        return bool(self.get("ui_background_gradient_enabled", False))
    
    def set_background_gradient_enabled(self, enabled: bool):
        """设置是否启用背景渐变"""
        self.set("ui_background_gradient_enabled", bool(enabled))
    
    def get_background_gradient_color2(self) -> str:
        """获取背景渐变第二颜色"""
        return self.get("ui_background_gradient_color2", self.DEFAULT_SETTINGS["ui_background_gradient_color2"])
    
    def set_background_gradient_color2(self, color: str):
        """设置背景渐变第二颜色"""
        self.set("ui_background_gradient_color2", color)
    
    def get_background_gradient_mode(self) -> str:
        """获取背景渐变模式"""
        return self.get("ui_background_gradient_mode", self.DEFAULT_SETTINGS["ui_background_gradient_mode"])
    
    def set_background_gradient_mode(self, mode: str):
        """设置背景渐变模式"""
        self.set("ui_background_gradient_mode", mode or "none")

    # 按钮字体相关
    def get_button_font_size(self) -> int:
        """获取按钮字体大小"""
        return int(self.get("ui_button_font_size", self.DEFAULT_SETTINGS["ui_button_font_size"]))

    def set_button_font_size(self, size: int):
        """设置按钮字体大小"""
        self.set("ui_button_font_size", int(size))

    def get_button_font_family(self) -> str:
        """获取按钮字体族"""
        return self.get("ui_button_font_family", self.DEFAULT_SETTINGS["ui_button_font_family"])

    def set_button_font_family(self, family: str):
        """设置按钮字体族"""
        self.set("ui_button_font_family", family or "")

    # 力度透明度相关
    def is_velocity_opacity_enabled(self) -> bool:
        """是否启用根据力度显示透明度"""
        return bool(self.get("show_velocity_opacity", False))

    def set_velocity_opacity_enabled(self, enabled: bool):
        """设置是否启用根据力度显示透明度"""
        self.set("show_velocity_opacity", bool(enabled))


# 全局设置管理器实例
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """获取全局设置管理器实例"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager

