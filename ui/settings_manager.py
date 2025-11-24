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


# 全局设置管理器实例
_settings_manager = None

def get_settings_manager() -> SettingsManager:
    """获取全局设置管理器实例"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager

