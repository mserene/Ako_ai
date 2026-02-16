from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict


def default_config_path() -> str:
    # Per-user config path
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    cfg_dir = os.path.join(appdata, "Ako-ai")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "config.json")


def default_model_dir() -> str:
    # Safe, per-user default for model storage
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(local, "Ako-ai", "models")


def is_writable_dir(path: str) -> bool:
    # Best-effort write check for a directory
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, ".ako_write_test")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False


@dataclass
class AppConfig:
    # User-selected model storage directory (optional).
    # If empty or not writable, the app falls back to default_model_dir().
    model_dir: str = ""

    @property
    def effective_model_dir(self) -> str:
        p = (self.model_dir or "").strip()
        if p and is_writable_dir(p):
            return p
        return default_model_dir()


def load_config(path: str | None = None) -> tuple[AppConfig, str]:
    path = path or default_config_path()
    if not os.path.exists(path):
        return AppConfig(), path
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        cfg = AppConfig(model_dir=str(data.get("model_dir", "") or ""))
        return cfg, path
    except Exception:
        # If config is corrupted, fall back safely.
        return AppConfig(), path


def save_config(cfg: AppConfig, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
