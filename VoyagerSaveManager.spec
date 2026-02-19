# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['save_manager.py'],
    pathex=[],
    binaries=[],
    datas=[('badge.png', '.')],
    hiddenimports=['PIL._tkinter_finder', 'pynput.keyboard._xorg', 'pynput.keyboard._uinput', 'pynput.mouse._xorg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VoyagerSaveManager',
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
