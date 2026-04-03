# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations
import os
from PyInstaller.utils.hooks import collect_submodules

# Project root (this .spec file sits in the project root)
ROOT = os.path.abspath(os.getcwd())  # fallback when __file__ is not defined during spec exec

# Ensure local modules are discoverable
pathex = [ROOT]

# Force-include local modules that PyInstaller might miss in some setups
hiddenimports = [
    "ako_gui",
    # local packages
    *collect_submodules("core"),
]

# Files that must live next to the executable at runtime
datas = [
    ("ako_gui.py", "."),
    ("app_commands.json", "."),
    ("search_sites.json", "."),
    ('assets\\ako.ico', 'assets'),
    (r".venv\Lib\site-packages\faster_whisper\assets", r"faster_whisper\assets"),
    (r".venv\Lib\site-packages\faster_whisper\vad.py", r"faster_whisper"),
]

a = Analysis(
    ["app.py"],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ako-ai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # reduce AV false positives
    console=True,        # keep console for debugging (can be switched later)
    disable_windowed_traceback=False,
    icon=r"assets\ako.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,           # reduce AV false positives
    upx_exclude=[],
    name="Ako-ai",
)
