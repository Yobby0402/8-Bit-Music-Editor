"""
线程 / Qt 诊断：设置环境变量 EIGHTBIT_DEBUG_THREADS=1 后输出到 stderr。

用于排查 QThread、LM Studio 请求等问题。
"""

from __future__ import annotations

import os
import sys


def thread_debug_enabled() -> bool:
    v = os.environ.get("EIGHTBIT_DEBUG_THREADS", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def thread_log(msg: str) -> None:
    if thread_debug_enabled():
        print(f"[EIGHTBIT_THREAD] {msg}", file=sys.stderr, flush=True)


def install_qt_message_handler() -> None:
    """将 Qt 警告（含 QThread: Destroyed while thread is still running）打到 stderr。"""
    if not thread_debug_enabled():
        return
    try:
        from PyQt5.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler
    except Exception:
        return

    def _handler(mode: QtMsgType, context: QMessageLogContext, message: str) -> None:
        loc = ""
        fn = getattr(context, "file", None) or ""
        ln = getattr(context, "line", 0) or 0
        if fn:
            loc = f"{fn}:{ln} "
        print(f"[Qt {int(mode)}] {loc}{message}", file=sys.stderr, flush=True)

    qInstallMessageHandler(_handler)


__all__ = ["install_qt_message_handler", "thread_debug_enabled", "thread_log"]
