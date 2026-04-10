# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

# Collect hidden imports for PaddleOCR and ONNX
hidden_imports = ['cv2', 'requests', 'PyQt5', 'sqlite3', 'onnxruntime', 'paddleocr', 'paddle']
hidden_imports += collect_submodules('paddleocr')
hidden_imports += collect_submodules('paddle')

# Gather ONNX and Paddle dynamic libraries explicitly
binaries_list = []
binaries_list += collect_dynamic_libs('onnxruntime')
binaries_list += collect_dynamic_libs('paddle')

a = Analysis(
    ['src/main_ui.py'],
    pathex=['.'],
    binaries=binaries_list,
    datas=[('assets/*', 'assets')],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SabrePatrolLPR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
