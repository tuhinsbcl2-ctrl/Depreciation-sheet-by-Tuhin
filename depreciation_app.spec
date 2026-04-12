# -*- mode: python ; coding: utf-8 -*-
#
# depreciation_app.spec — PyInstaller spec file for the Depreciation Calculator
#
# Usage
# -----
#   pip install pyinstaller
#   pyinstaller depreciation_app.spec
#
# The resulting executable is written to dist/DepreciationCalculator/
# Run dist/DepreciationCalculator/DepreciationCalculator.exe (Windows)
#        dist/DepreciationCalculator/DepreciationCalculator       (macOS/Linux)

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.filedialog",
    ],
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
    [],
    exclude_binaries=True,
    name="DepreciationCalculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # no CMD window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,            # set icon="app.ico" if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DepreciationCalculator",
)
