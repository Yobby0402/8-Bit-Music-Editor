# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller配置文件
用于打包8bit音乐制作器

使用方法:
    pyinstaller build.spec
"""

from app_info import APP_NAME

block_cipher = None

a = Analysis(
    ['main.py', 'mcp_server_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'numpy',
        'scipy',
        'scipy.io',
        'scipy.io.wavfile',
        'pygame',
        'soundfile',
        'mido',
        'mido.backends',
        'mcp',
        'mcp.server.fastmcp',
        'mcp_server',
        'mcp_server.eightbit_mcp_server',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    [script for script in a.scripts if script[0] == 'main'],
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以在这里指定图标文件路径，例如: 'icon.ico'
)


mcp_exe = EXE(
    pyz,
    [script for script in a.scripts if script[0] == 'mcp_server_launcher'],
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='8bit-mcp-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
