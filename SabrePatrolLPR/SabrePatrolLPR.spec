# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

# Collect extensive hidden imports and DLLs for Torch, EasyOCR, and Ultralytics
hidden_imports = ['cv2', 'requests', 'PyQt5', 'sqlite3', 'easyocr', 'ultralytics', 'torch', 'torchvision']
hidden_imports += collect_submodules('easyocr')
hidden_imports += collect_submodules('ultralytics')
hidden_imports += collect_submodules('torch')

binaries_list = []
binaries_list += collect_dynamic_libs('torch')
binaries_list += collect_dynamic_libs('torchvision')

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
    upx=True,
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
