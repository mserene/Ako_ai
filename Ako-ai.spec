# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# 프로젝트 루트
ROOT = os.path.abspath(os.path.dirname(SPEC) if 'SPEC' in dir() else os.getcwd())

# Prefer the active build environment so stale developer venvs do not leak
# package assets into a release build.
def find_site_packages():
    candidates = []

    env_site = os.environ.get("AKO_BUILD_SITE_PACKAGES", "")
    if env_site:
        candidates.append(env_site)

    candidates.extend([
        os.path.join(sys.prefix, "Lib", "site-packages"),
        os.path.join(ROOT, ".build_venv", "Lib", "site-packages"),
    ])

    for p in sys.path:
        if "site-packages" in p and os.path.isdir(p):
            candidates.append(p)

    candidates.extend([
        os.path.join(ROOT, ".venv", "Lib", "site-packages"),
        os.path.join(ROOT, "venv", "Lib", "site-packages"),
    ])

    seen = set()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        key = os.path.normcase(candidate)
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(candidate):
            return candidate
    return ""

SITE_PKG = find_site_packages()

hiddenimports = [
    "ako_gui",
    "command_actions",
    "llm_agent",
    "ui_do",
    "ui_loop",
    "ui_tap",
    "ui_vision",
    "voice_loop",
    *collect_submodules("core"),
    "faster_whisper",
    "ctranslate2",
    "pyautogui",
    "pytesseract",
    "PIL",
    "mss",
    "numpy",
    "sounddevice",
    "requests",
    "ollama",
]

datas = [
    (os.path.join(ROOT, "app_commands.json"), "."),
    (os.path.join(ROOT, "search_sites.json"), "."),
    (os.path.join(ROOT, "llm_agent.py"), "."),
]

ico = os.path.join(ROOT, "assets", "ako.ico")
if os.path.exists(ico):
    datas.append((ico, "assets"))

loading_frames_dir = os.path.join(ROOT, "assets", "loading", "frames")
if os.path.isdir(loading_frames_dir):
    datas.append((loading_frames_dir, "assets/loading/frames"))

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
    console=False,
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
