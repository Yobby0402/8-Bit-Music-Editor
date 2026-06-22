# -*- mode: python ; coding: utf-8 -*-

from app_info import APP_NAME


a = Analysis(
    ['main.py', 'mcp_server_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'numpy', 'scipy', 'scipy.io', 'scipy.io.wavfile', 'pygame', 'soundfile', 'mido', 'mido.backends', 'mcp', 'mcp.server.fastmcp', 'mcp_server', 'mcp_server.eightbit_mcp_server'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'IPython', 'jupyter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    [script for script in a.scripts if script[0] == 'main'],
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

mcp_exe = EXE(
    pyz,
    [script for script in a.scripts if script[0] == 'mcp_server_launcher'],
    a.binaries,
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
)
