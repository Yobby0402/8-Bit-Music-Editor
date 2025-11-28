"""
8bit音乐制作器 - 程序入口

运行此文件启动应用程序。
""" 

import sys
import os

# 确保项目根目录在 Python 路径中，以便正确导入模块
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.main_window import MainWindow


def main():
    """主函数"""
    # 启用高DPI支持（在创建QApplication之前）
    # Windows上启用DPI感知
    if sys.platform == "win32":
        # 设置环境变量启用高DPI支持
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        # 启用DPI感知
        try:
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            # 这里是启动前的兼容性设置，失败时不影响后续逻辑，不必中断程序
            pass

    # 安装全局异常捕获，确保任何未捕获的异常都会打印完整堆栈，方便排查闪退
    def _handle_exception(exc_type, exc_value, exc_traceback):
        import traceback
        # 避免重复打印 KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        print("\n========== 未捕获的异常（Uncaught Exception） ==========")
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print("=====================================================\n")

    sys.excepthook = _handle_exception

    app = QApplication(sys.argv)
    
    # 设置自适应字体大小（根据DPI）
    # 获取屏幕DPI缩放比例
    screen = app.primaryScreen()
    dpi_scale = screen.logicalDotsPerInch() / 96.0  # 96是标准DPI
    base_font_size = max(9, int(9 * dpi_scale))  # 基础字体大小，最小9px
    
    # 设置应用程序默认字体
    default_font = QFont()
    default_font.setPointSize(base_font_size)
    app.setFont(default_font)
    
    # 设置应用程序信息
    app.setApplicationName("8bit音乐制作器")
    app.setApplicationVersion("2.4.0")
    app.setOrganizationName("8bit Music Maker")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

