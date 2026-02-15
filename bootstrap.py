from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Optional

LogFn = Callable[[str], None]

def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

def get_app_name() -> str:
    return "Ako"

def get_user_data_dir() -> str:
    # Windows 우선: %LOCALAPPDATA%\Ako
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(local, get_app_name())
    os.makedirs(path, exist_ok=True)
    return path

def get_models_dir() -> str:
    path = os.path.join(get_user_data_dir(), "models")
    os.makedirs(path, exist_ok=True)
    return path

@dataclass
class BootstrapStatus:
    ready: bool = False
    downloading: bool = False
    last_error: str = ""

def ensure_whisper_model(
    model: str,
    log: Optional[LogFn] = None,
    force: bool = False,
) -> str:
    """
    faster-whisper CTranslate2 모델을 사용자 데이터 폴더에 준비한다.
    - 이미 존재하면 스킵
    - 없으면 HuggingFace에서 다운로드 (faster_whisper.utils.download_model 사용)
    반환: 로컬 모델 경로
    """
    model = (model or "small").strip()
    models_dir = get_models_dir()
    out_dir = os.path.join(models_dir, model.replace("/", "_"))
    # 모델이 이미 준비되었는지 간단히 확인
    model_bin = os.path.join(out_dir, "model.bin")
    if not force and os.path.isfile(model_bin):
        if log:
            log(f"(부트스트랩) 모델 이미 존재: {out_dir}")
        return out_dir

    if log:
        log(f"(부트스트랩) 모델 다운로드 준비: {model} -> {out_dir}")

    try:
        from faster_whisper.utils import download_model
    except Exception as e:
        raise RuntimeError(f"faster-whisper를 불러올 수 없어요: {e}")

    # download_model이 내부적으로 huggingface_hub.snapshot_download를 사용
    try:
        download_model(model, output_dir=out_dir, local_files_only=False)
    except Exception as e:
        raise RuntimeError(f"모델 다운로드 실패: {e}")

    if not os.path.isfile(model_bin):
        raise RuntimeError("다운로드가 끝났는데 model.bin을 찾지 못했어요.")

    if log:
        log(f"(부트스트랩) 모델 준비 완료: {out_dir}")
    return out_dir

def ensure_whisper_model_async(
    model: str,
    log: Optional[LogFn],
    status: BootstrapStatus,
    on_done: Optional[Callable[[Optional[str]], None]] = None,
) -> None:
    """
    GUI가 멈추지 않도록 백그라운드 스레드에서 모델을 준비한다.
    """
    def _task():
        status.downloading = True
        status.last_error = ""
        try:
            path = ensure_whisper_model(model, log=log)
            status.ready = True
            if on_done:
                on_done(path)
        except Exception as e:
            status.ready = False
            status.last_error = str(e)
            if log:
                log(f"(부트스트랩) 오류: {e}")
            if on_done:
                on_done(None)
        finally:
            status.downloading = False

    threading.Thread(target=_task, daemon=True, name="AkoBootstrap").start()
