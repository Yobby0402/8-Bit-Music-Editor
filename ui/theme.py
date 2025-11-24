"""
主题管理模块

提供统一的主题接口和实现，支持主题切换。
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication


class Theme(ABC):
    """主题基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """主题名称"""
        pass
    
    @property
    @abstractmethod
    def colors(self) -> Dict[str, str]:
        """颜色字典，包含所有主题颜色"""
        pass
    
    @property
    @abstractmethod
    def styles(self) -> Dict[str, str]:
        """样式字典，包含所有组件样式"""
        pass
    
    def get_color(self, key: str) -> str:
        """获取颜色值"""
        return self.colors.get(key, "#FFFFFF")
    
    def get_adaptive_font_size(self, base_size: int) -> int:
        """根据DPI计算自适应字体大小"""
        try:
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                dpi_scale = screen.logicalDotsPerInch() / 96.0  # 96是标准DPI
                return max(base_size, int(base_size * dpi_scale))
        except:
            pass
        return base_size
    
    def get_style(self, component: str) -> str:
        """获取组件样式（自动替换字体大小为自适应大小）"""
        style = self.styles.get(component, "")
        if not style:
            return ""
        
        # 替换所有 font-size: XXpx; 为自适应大小
        import re
        def replace_font_size(match):
            size_str = match.group(1)
            try:
                base_size = int(size_str)
                adaptive_size = self.get_adaptive_font_size(base_size)
                return f"font-size: {adaptive_size}px;"
            except:
                return match.group(0)
        
        # 匹配 font-size: XXpx; 模式
        style = re.sub(r'font-size:\s*(\d+)px;', replace_font_size, style)
        return style
    
    def lighten_color(self, color: str, factor: float = 0.2) -> str:
        """使颜色变亮"""
        rgb = self._hex_to_rgb(color)
        r, g, b = rgb
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return self._rgb_to_hex(r, g, b)
    
    def darken_color(self, color: str, factor: float = 0.2) -> str:
        """使颜色变暗"""
        rgb = self._hex_to_rgb(color)
        r, g, b = rgb
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return self._rgb_to_hex(r, g, b)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """十六进制颜色转RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """RGB转十六进制颜色"""
        return f"#{r:02x}{g:02x}{b:02x}"


class JasmineSnowTheme(Theme):
    """茉莉飘雪主题 - 浅绿到奶白"""
    
    @property
    def name(self) -> str:
        return "茉莉飘雪"
    
    @property
    def colors(self) -> Dict[str, str]:
        return {
            # 主色调 - 浅绿到奶白渐变
            "primary": "#E8F5E9",      # 浅绿色（主背景）
            "primary_light": "#F1F8F4", # 更浅的绿色
            "primary_dark": "#C8E6C9",  # 稍深的绿色
            
            # 次要色调
            "secondary": "#FFF9E6",     # 奶白色
            "secondary_light": "#FFFEF5", # 更浅的奶白
            "secondary_dark": "#F5E6B3",  # 稍深的奶白
            
            # 强调色
            "accent": "#81C784",       # 中等绿色（按钮、高亮）
            "accent_light": "#A5D6A7",  # 浅绿色（悬停）
            "accent_dark": "#66BB6A",  # 深绿色（按下）
            
            # 文本颜色
            "text_primary": "#2E7D32",   # 深绿色（主要文本）
            "text_secondary": "#558B2F", # 中绿色（次要文本）
            "text_disabled": "#A5A5A5",   # 灰色（禁用文本）
            
            # 边框和分割线
            "border": "#B2DFDB",       # 浅青色边框
            "border_light": "#E0F2F1", # 更浅的边框
            "border_dark": "#80CBC4",  # 稍深的边框
            
            # 背景色
            "background": "#FAFAFA",   # 浅灰背景
            "background_light": "#FFFFFF", # 白色背景
            "background_dark": "#F5F5F5", # 稍深的背景
            
            # 状态颜色
            "success": "#66BB6A",      # 成功（绿色）
            "warning": "#FFB74D",      # 警告（橙色）
            "error": "#EF5350",        # 错误（红色）
            "info": "#42A5F5",         # 信息（蓝色）
            
            # 特殊用途
            "highlight": "#FFD54F",    # 高亮（黄色）
            "selection": "#C5E1A5",    # 选中（浅绿）
            "hover": "#E8F5E9",        # 悬停（浅绿）
        }
    
    @property
    def styles(self) -> Dict[str, str]:
        colors = self.colors
        return {
            # 主窗口样式
            "main_window": f"""
                QMainWindow {{
                    background-color: {colors['background_light']};
                    color: {colors['text_primary']};
                }}
            """,
            
            # 按钮样式（标准按钮）
            "button": f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    color: {colors['text_primary']};
                    border: 2px solid {colors['accent_dark']};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                    font-weight: 500;
                    min-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_light']};
                    border-color: {colors['accent']};
                }}
                QPushButton:pressed {{
                    background-color: {colors['accent_dark']};
                    border-color: {colors['accent_dark']};
                }}
                QPushButton:disabled {{
                    background-color: {colors['background_dark']};
                    color: {colors['text_disabled']};
                    border-color: {colors['border_light']};
                }}
            """,
            
            # 小按钮样式（紧凑型）
            "button_small": f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    color: {colors['text_primary']};
                    border: 1px solid {colors['accent_dark']};
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 500;
                    min-height: 24px;
                    max-height: 24px;
                }}
                QPushButton:hover {{
                    background-color: {colors['accent_light']};
                    border-color: {colors['accent']};
                }}
                QPushButton:pressed {{
                    background-color: {colors['accent_dark']};
                }}
            """,
            
            # 切换按钮样式（可选中）
            "button_toggle": f"""
                QPushButton {{
                    background-color: {colors['primary']};
                    color: {colors['text_primary']};
                    border: 2px solid {colors['border']};
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                    font-weight: 500;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    background-color: {colors['primary_light']};
                    border-color: {colors['accent']};
                }}
                QPushButton:checked {{
                    background-color: {colors['accent']};
                    color: {colors['text_primary']};
                    border-color: {colors['accent_dark']};
                    border-width: 3px;
                }}
                QPushButton:pressed {{
                    background-color: {colors['accent_dark']};
                }}
            """,
            
            # 标签样式
            "label": f"""
                QLabel {{
                    color: {colors['text_primary']};
                    font-size: 13px;
                }}
            """,
            
            # 输入框样式
            "line_edit": f"""
                QLineEdit {{
                    background-color: {colors['background_light']};
                    color: {colors['text_primary']};
                    border: 2px solid {colors['border']};
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 13px;
                    min-height: 28px;
                }}
                QLineEdit:focus {{
                    border-color: {colors['accent']};
                }}
            """,
            
            # 下拉框样式
            "combo_box": f"""
                QComboBox {{
                    background-color: {colors['background_light']};
                    color: {colors['text_primary']};
                    border: 2px solid {colors['border']};
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 13px;
                    min-height: 28px;
                }}
                QComboBox:hover {{
                    border-color: {colors['accent']};
                }}
                QComboBox:focus {{
                    border-color: {colors['accent']};
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 20px;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 6px solid {colors['text_primary']};
                    width: 0;
                    height: 0;
                }}
            """,
            
            # 滑块样式
            "slider": f"""
                QSlider::groove:horizontal {{
                    border: 1px solid {colors['border']};
                    height: 6px;
                    background: {colors['primary']};
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: {colors['accent']};
                    border: 2px solid {colors['accent_dark']};
                    width: 18px;
                    height: 18px;
                    border-radius: 9px;
                    margin: -6px 0;
                }}
                QSlider::handle:horizontal:hover {{
                    background: {colors['accent_light']};
                }}
                QSlider::handle:horizontal:pressed {{
                    background: {colors['accent_dark']};
                }}
            """,
            
            # 复选框样式
            "check_box": f"""
                QCheckBox {{
                    color: {colors['text_primary']};
                    font-size: 13px;
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {colors['border']};
                    border-radius: 3px;
                    background-color: {colors['background_light']};
                }}
                QCheckBox::indicator:hover {{
                    border-color: {colors['accent']};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {colors['accent']};
                    border-color: {colors['accent_dark']};
                }}
            """,
            
            # 菜单栏样式
            "menu_bar": f"""
                QMenuBar {{
                    background-color: {colors['primary']};
                    color: {colors['text_primary']};
                    border-bottom: 1px solid {colors['border']};
                    padding: 4px;
                }}
                QMenuBar::item {{
                    padding: 6px 12px;
                    border-radius: 4px;
                }}
                QMenuBar::item:selected {{
                    background-color: {colors['accent_light']};
                }}
            """,
            
            # 菜单样式
            "menu": f"""
                QMenu {{
                    background-color: {colors['background_light']};
                    color: {colors['text_primary']};
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QMenu::item {{
                    padding: 6px 24px;
                    border-radius: 3px;
                }}
                QMenu::item:selected {{
                    background-color: {colors['selection']};
                }}
            """,
            
            # 工具栏样式
            "toolbar": f"""
                QToolBar {{
                    background-color: {colors['primary']};
                    border: none;
                    spacing: 4px;
                    padding: 4px;
                }}
                QToolBar::separator {{
                    background-color: {colors['border']};
                    width: 1px;
                    margin: 4px 2px;
                }}
            """,
            
            # 状态栏样式
            "status_bar": f"""
                QStatusBar {{
                    background-color: {colors['primary']};
                    color: {colors['text_primary']};
                    border-top: 1px solid {colors['border']};
                }}
            """,
            
            # 滚动条样式
            "scroll_bar": f"""
                QScrollBar:vertical {{
                    background: {colors['primary']};
                    width: 12px;
                    border: none;
                }}
                QScrollBar::handle:vertical {{
                    background: {colors['accent']};
                    min-height: 20px;
                    border-radius: 6px;
                    margin: 2px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {colors['accent_light']};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar:horizontal {{
                    background: {colors['primary']};
                    height: 12px;
                    border: none;
                }}
                QScrollBar::handle:horizontal {{
                    background: {colors['accent']};
                    min-width: 20px;
                    border-radius: 6px;
                    margin: 2px;
                }}
                QScrollBar::handle:horizontal:hover {{
                    background: {colors['accent_light']};
                }}
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                    width: 0px;
                }}
            """,
            
            # 对话框样式
            "dialog": f"""
                QDialog {{
                    background-color: {colors['background_light']};
                    color: {colors['text_primary']};
                }}
            """,
            
            # 标签页样式
            "tab_widget": f"""
                QTabWidget::pane {{
                    border: 1px solid {colors['border']};
                    background-color: {colors['background_light']};
                }}
                QTabBar::tab {{
                    background-color: {colors['primary']};
                    color: {colors['text_primary']};
                    border: 1px solid {colors['border']};
                    padding: 8px 16px;
                    margin-right: 2px;
                }}
                QTabBar::tab:selected {{
                    background-color: {colors['accent']};
                    color: {colors['text_primary']};
                }}
                QTabBar::tab:hover {{
                    background-color: {colors['accent_light']};
                }}
            """,
        }


class ThemeManager:
    """主题管理器（单例）"""
    
    _instance = None
    _current_theme: Theme = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._current_theme is None:
            self._current_theme = JasmineSnowTheme()
    
    @property
    def current_theme(self) -> Theme:
        """获取当前主题"""
        return self._current_theme
    
    def set_theme(self, theme: Theme):
        """设置主题"""
        self._current_theme = theme
    
    def get_color(self, key: str) -> str:
        """获取颜色值"""
        return self._current_theme.get_color(key)
    
    def get_style(self, component: str) -> str:
        """获取组件样式"""
        return self._current_theme.get_style(component)
    
    def apply_to_widget(self, widget, component: str = None):
        """应用主题到组件"""
        if component:
            widget.setStyleSheet(self.get_style(component))
        else:
            # 应用所有样式
            styles = self._current_theme.styles
            combined_style = "\n".join(styles.values())
            widget.setStyleSheet(combined_style)


# 全局主题管理器实例
theme_manager = ThemeManager()

