"""
打包脚本 - 将8bit音乐制作器打包成单个exe文件

使用方法:
    python build_exe.py

需要先安装PyInstaller:
    pip install pyinstaller
"""

import PyInstaller.__main__
import os
import sys

# 获取项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))

# PyInstaller参数
args = [
    'main.py',                          # 主程序入口
    '--name=8bit音乐制作器',            # 生成的exe文件名
    '--onefile',                        # 打包成单个exe文件
    '--windowed',                       # 不显示控制台窗口（GUI应用）
    '--clean',                          # 清理临时文件
    '--noconfirm',                      # 覆盖输出目录而不询问
    
    # 包含数据文件夹
    '--add-data=data;data',             # Windows使用分号分隔
    
    # 隐藏导入（PyQt5相关）
    '--hidden-import=PyQt5.QtCore',
    '--hidden-import=PyQt5.QtGui',
    '--hidden-import=PyQt5.QtWidgets',
    '--hidden-import=numpy',
    '--hidden-import=scipy',
    '--hidden-import=scipy.io',
    '--hidden-import=scipy.io.wavfile',
    '--hidden-import=pygame',
    '--hidden-import=soundfile',
    '--hidden-import=mido',
    '--hidden-import=mido.backends',
    
    # 排除不需要的模块（减小文件大小）
    '--exclude-module=matplotlib',
    '--exclude-module=tkinter',
    '--exclude-module=IPython',
    '--exclude-module=jupyter',
    
    # 图标（如果有的话，可以取消注释）
    # '--icon=icon.ico',
    
    # 输出目录
    '--distpath=dist',                  # 输出目录
    '--workpath=build',                 # 临时文件目录
]

print("开始打包...")
print("=" * 50)

try:
    PyInstaller.__main__.run(args)
    print("=" * 50)
    print("打包完成！")
    print(f"exe文件位置: {os.path.join(project_root, 'dist', '8bit音乐制作器.exe')}")
except Exception as e:
    print(f"打包失败: {e}")
    sys.exit(1)


