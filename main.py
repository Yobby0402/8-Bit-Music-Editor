"""
8bit音乐制作器 - 程序入口

运行此文件启动应用程序。
""" 

import sys
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("8bit音乐制作器")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("8bit Music Maker")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

