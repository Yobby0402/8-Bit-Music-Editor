"""Package the desktop app and the MCP stdio server as Windows executables."""

from __future__ import annotations

import os
import sys

import PyInstaller.__main__

from app_info import APP_NAME

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

COMMON_HIDDEN_IMPORTS = [
    "PyQt5.QtCore",
    "PyQt5.QtGui",
    "PyQt5.QtWidgets",
    "numpy",
    "scipy",
    "scipy.io",
    "scipy.io.wavfile",
    "pygame",
    "soundfile",
    "mido",
    "mido.backends",
    "mcp",
    "mcp.server.fastmcp",
    "mcp_server",
    "mcp_server.eightbit_mcp_server",
]

COMMON_EXCLUDES = [
    "matplotlib",
    "tkinter",
    "IPython",
    "jupyter",
]


def _hidden_import_args() -> list[str]:
    return [f"--hidden-import={name}" for name in COMMON_HIDDEN_IMPORTS]


def _exclude_args() -> list[str]:
    return [f"--exclude-module={name}" for name in COMMON_EXCLUDES]


def _build_args(entry: str, name: str, *, windowed: bool) -> list[str]:
    mode = "--windowed" if windowed else "--console"
    return [
        entry,
        f"--name={name}",
        "--onefile",
        mode,
        "--clean",
        "--noconfirm",
        *_hidden_import_args(),
        *_exclude_args(),
        "--distpath=dist",
        "--workpath=build",
    ]


def main() -> int:
    print("Starting package build...")
    print("=" * 50)
    try:
        PyInstaller.__main__.run(_build_args("main.py", APP_NAME, windowed=True))
        PyInstaller.__main__.run(
            _build_args("mcp_server_launcher.py", "8bit-mcp-server", windowed=False)
        )
    except Exception as exc:
        print(f"Package build failed: {exc}")
        return 1

    print("=" * 50)
    print("Package build complete")
    print(f"Desktop exe: {os.path.join(PROJECT_ROOT, 'dist', APP_NAME + '.exe')}")
    print(f"MCP server exe: {os.path.join(PROJECT_ROOT, 'dist', '8bit-mcp-server.exe')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
