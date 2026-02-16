from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Tuple

APP_NAME = "Ako-ai"

def _appdata_dir() -> str:
    # Roaming AppData preferred for config
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path

def default_config_path() -> str:
    return os.path.join(_appdata_dir(), "config.json")

def default_model_dir() -> str:
    # LocalAppData preferred for large models
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "models")

@dataclass
class AppConfig:
    model_dir: str = ""  # empty => default_model_dir()

    @property
    def effective_model_dir(self) -> str:
        v = (self.model_dir or "").strip()
        return v if v else default_model_dir()

def load_config(path: str | None = None) -> Tuple[AppConfig, str]:
    path = path or default_config_path()
    if not os.path.exists(path):
        return AppConfig(), path
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        cfg = AppConfig(model_dir=str(data.get("model_dir", "") or ""))
        return cfg, path
    except Exception:
        # if corrupt, fall back safely
        return AppConfig(), path

def save_config(cfg: AppConfig, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
