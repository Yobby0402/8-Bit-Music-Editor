"""
快捷键管理模块

管理应用程序的所有快捷键，支持自定义配置。
"""

import json
import os
from typing import Dict, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication


class ShortcutManager(QObject):
    """快捷键管理器"""
    
    # 默认快捷键配置
    DEFAULT_SHORTCUTS = {
        # 钢琴键盘 - 白键
        "piano_c": "Q",
        "piano_d": "W",
        "piano_e": "E",
        "piano_f": "R",
        "piano_g": "T",
        "piano_a": "Y",
        "piano_b": "U",
        
        # 钢琴键盘 - 黑键（升号）
        "piano_c_sharp": "2",
        "piano_d_sharp": "3",
        "piano_f_sharp": "5",
        "piano_g_sharp": "6",
        "piano_a_sharp": "7",
        
        # 波形选择
        "waveform_square": "1",
        "waveform_triangle": "2",
        "waveform_sawtooth": "3",
        "waveform_sine": "4",
        
        # 节拍长度
        "duration_quarter": "Ctrl+1",  # 1/4拍
        "duration_half": "Ctrl+2",      # 1/2拍
        "duration_whole": "Ctrl+3",     # 1拍
        "duration_double": "Ctrl+4",    # 2拍
        "duration_quad": "Ctrl+5",      # 4拍
        
        # 打击乐
        "drum_kick": "Z",
        "drum_snare": "X",
        "drum_hihat": "C",
        "drum_crash": "V",
        
        # 八度控制
        "octave_up": "PageUp",
        "octave_down": "PageDown",
        
        # 休止符
        "rest": "0",
        
        # 删除最后一个音符
        "delete_last_note": "Backspace",
    }
    
    def __init__(self, parent=None):
        """初始化快捷键管理器"""
        super().__init__(parent)
        self.shortcuts: Dict[str, str] = {}
        self.actions: Dict[str, Callable] = {}
        self.config_file = os.path.join(
            QApplication.instance().applicationDirPath(),
            "shortcuts.json"
        )
        # 如果不在应用程序目录，使用用户配置目录
        if not os.path.exists(QApplication.instance().applicationDirPath()):
            from PyQt5.QtCore import QStandardPaths
            config_dir = QStandardPaths.writableLocation(QStandardPaths.ConfigLocation)
            self.config_file = os.path.join(config_dir, "8bit_music_editor", "shortcuts.json")
        
        self.load_shortcuts()
    
    def load_shortcuts(self):
        """加载快捷键配置"""
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()
        
        # 尝试从文件加载
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_shortcuts = json.load(f)
                    # 合并保存的快捷键（只更新存在的键）
                    for key, value in saved_shortcuts.items():
                        if key in self.shortcuts:
                            self.shortcuts[key] = value
            except Exception as e:
                print(f"加载快捷键配置失败: {e}")
    
    def save_shortcuts(self):
        """保存快捷键配置"""
        try:
            # 确保目录存在
            config_dir = os.path.dirname(self.config_file)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.shortcuts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存快捷键配置失败: {e}")
    
    def get_shortcut(self, key: str) -> str:
        """获取快捷键"""
        return self.shortcuts.get(key, "")
    
    def set_shortcut(self, key: str, value: str):
        """设置快捷键"""
        if key in self.shortcuts:
            self.shortcuts[key] = value
            self.save_shortcuts()
    
    def register_action(self, key: str, action: Callable):
        """注册动作"""
        self.actions[key] = action
    
    def get_key_sequence(self, key: str) -> Optional[QKeySequence]:
        """获取QKeySequence对象"""
        shortcut_str = self.get_shortcut(key)
        if shortcut_str:
            try:
                return QKeySequence(shortcut_str)
            except:
                return None
        return None
    
    def get_all_shortcuts(self) -> Dict[str, str]:
        """获取所有快捷键"""
        return self.shortcuts.copy()
    
    def reset_to_defaults(self):
        """重置为默认快捷键"""
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()
        self.save_shortcuts()


# 全局快捷键管理器实例
_shortcut_manager: Optional[ShortcutManager] = None


def get_shortcut_manager() -> ShortcutManager:
    """获取全局快捷键管理器实例"""
    global _shortcut_manager
    if _shortcut_manager is None:
        _shortcut_manager = ShortcutManager()
    return _shortcut_manager

