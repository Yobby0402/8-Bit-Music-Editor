"""
UI 错误处理工具。
"""

import sys
import traceback

from PyQt5.QtWidgets import QMessageBox


def show_error_with_console(parent, title: str, message: str, level: str = "critical", exc_info=None):
    """
    显示错误对话框，同时在终端输出错误信息。

    Args:
        parent: 父窗口
        title: 对话框标题
        message: 错误消息
        level: 错误级别 ("critical", "warning", "information")
        exc_info: 异常信息元组，如果提供则打印完整堆栈
    """
    print(f"\n{'=' * 60}")
    print(f"[{level.upper()}] {title}")
    print(f"{'=' * 60}")
    print(message)

    if exc_info is not None:
        exc_type, exc_value, exc_tb = exc_info
        print("\n完整堆栈跟踪:")
        traceback.print_exception(exc_type, exc_value, exc_tb)
    elif "Traceback" not in message and sys.exc_info()[0] is not None:
        print("\n完整堆栈跟踪:")
        traceback.print_exc()

    print(f"{'=' * 60}\n")

    if level == "critical":
        QMessageBox.critical(parent, title, message)
    elif level == "warning":
        QMessageBox.warning(parent, title, message)
    else:
        QMessageBox.information(parent, title, message)
