# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# 프로젝트 루트
ROOT = os.path.abspath(os.path.dirname(SPEC) if 'SPEC' in dir() else os.getcwd())

# venv 경로 자동 탐지 (하드코딩 제거)
def find_site_packages():
    for candidate in [
        os.path.join(ROOT, ".venv", "Lib", "site-packages"),
        os.path.join(ROOT, "venv", "Lib", "site-packages"),
    ]:
        if os.path.isdir(candidate):
            return candidate
    for p in sys.path:
        if "site-packages" in p and os.path.isdir(p):
            return p
    return ""

SITE_PKG = find_site_packages()

hiddenimports = [
    "ako_gui",
    *collect_submodules("core"),
    "faster_whisper",
    "ctranslate2",
    "pyautogui",
    "pytesseract",
    "PIL",
    "mss",
    "numpy",
    "sounddevice",
]

datas = [
    (os.path.join(ROOT, "app_commands.json"), "."),
    (os.path.join(ROOT, "search_sites.json"), "."),
]

ico = os.path.join(ROOT, "assets", "ako.ico")
if os.path.exists(ico):
    datas.append((ico, "assets"))

if SITE_PKG:
    fw_assets = os.path.join(SITE_PKG, "faster_whisper", "assets")
    fw_vad    = os.path.join(SITE_PKG, "faster_whisper", "vad.py")
    if os.path.isdir(fw_assets):
        datas.append((fw_assets, "faster_whisper/assets"))
    if os.path.isfile(fw_vad):
        datas.append((fw_vad, "faster_whisper"))

tesseract_dir = os.path.join(ROOT, "tools", "tesseract")
if os.path.isdir(tesseract_dir):
    datas.append((tesseract_dir, "tools/tesseract"))

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "tensorflow", "matplotlib", "pandas", "scipy", "IPython"],
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
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    icon=ico if os.path.exists(ico) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Ako-ai",
)
