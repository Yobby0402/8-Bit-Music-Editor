"""
8bit音乐制作器 - 程序入口

运行此文件启动应用程序。
"""

import os
import sys
import traceback


def _ensure_project_root_on_path():
    """确保直接运行入口文件时也能正确导入项目模块。"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _install_excepthook():
    """安装全局异常钩子，避免 GUI 启动后吞掉堆栈信息。"""

    def _handle_exception(exc_type, exc_value, exc_traceback):
        # 避免重复打印 KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        print("\n========== 未捕获的异常（Uncaught Exception） ==========")
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print("=====================================================\n")

    sys.excepthook = _handle_exception


def main():
    """主函数"""
    _ensure_project_root_on_path()

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication

    from app_info import APP_NAME, APP_VERSION
    from ui.main_window import MainWindow

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

    _install_excepthook()

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
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("8bit Music Maker")

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

