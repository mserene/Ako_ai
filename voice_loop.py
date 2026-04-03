# voice_loop.py
# -----------------------------------------------------------------------------
# 마이크 입력을 받아 STT(음성->텍스트) 후 app.run_actions()로 넘기는 루프.
# - faster-whisper(오프라인) 사용
# - WhisperModel을 싱글턴으로 캐싱 → 첫 호출 이후 빠른 응답
# -----------------------------------------------------------------------------
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable


@dataclass
class VoiceConfig:
    device: Optional[int] = None
    samplerate: int = 16000
    min_record_sec: float = 0.6
    max_record_sec: float = 10.0
    silence_sec: float = 0.9
    silence_threshold: float = 0.012
    model: str = "small"
    language: str = "ko"
    wake_word: str = ""
    print_heard_audio_stats: bool = False


# -----------------------------------------------------------------------------
# WhisperModel 싱글턴 캐시
# - 모델명이 바뀔 때만 재로드, 그 외엔 재사용 → 응답 속도 대폭 개선
# -----------------------------------------------------------------------------
_whisper_cache: dict = {}
_whisper_lock = threading.Lock()


def _get_whisper_model(model_name: str):
    """WhisperModel을 캐싱해서 반환. 같은 모델명이면 재사용."""
    with _whisper_lock:
        if model_name not in _whisper_cache:
            try:
                from faster_whisper import WhisperModel
                _whisper_cache[model_name] = WhisperModel(
                    model_name, device="cpu", compute_type="int8"
                )
            except ImportError:
                raise RuntimeError(
                    "faster-whisper가 설치되어 있지 않아요.\n"
                    "pip install faster-whisper"
                )
            except Exception as e:
                raise RuntimeError(f"Whisper 모델 로드 실패({model_name}): {e}")
        return _whisper_cache[model_name]


def clear_whisper_cache():
    """모델 캐시를 비웁니다. 모델을 교체할 때 호출."""
    with _whisper_lock:
        _whisper_cache.clear()


# -----------------------------------------------------------------------------
# 녹음
# -----------------------------------------------------------------------------
def _rms(x) -> float:
    import numpy as np
    if x is None:
        return 0.0
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return 0.0
    return float((np.mean(x * x) + 1e-12) ** 0.5)


def _record_until_silence(cfg: VoiceConfig):
    """sounddevice로 녹음. 무음이 일정 시간 지속되면 종료."""
    import numpy as np
    import sounddevice as sd

    sr = int(cfg.samplerate)
    block = int(sr * 0.2)  # 200ms 단위로 처리

    frames = []
    started = False
    silent_for = 0.0
    total = 0.0

    def _cb(indata, _frames, _time, status):
        nonlocal started, silent_for, total
        mono = indata[:, 0].copy()
        frames.append(mono)
        total += _frames / sr

        level = _rms(mono)
        if cfg.print_heard_audio_stats:
            print(f"[VOICE] rms={level:.4f} total={total:.1f}s")

        if not started:
            if total >= cfg.min_record_sec:
                started = True
            return

        if level < cfg.silence_threshold:
            silent_for += _frames / sr
        else:
            silent_for = 0.0

    try:
        with sd.InputStream(
            samplerate=sr,
            device=cfg.device,
            channels=1,
            dtype="float32",
            blocksize=block,
            callback=_cb,
        ):
            t0 = time.time()
            while True:
                time.sleep(0.05)
                if total >= cfg.max_record_sec:
                    break
                if started and silent_for >= cfg.silence_sec:
                    break
                if time.time() - t0 > cfg.max_record_sec + 2.0:
                    break
    except Exception as e:
        raise RuntimeError(
            f"마이크 녹음 실패: {e}\n"
            "- pip install sounddevice numpy\n"
            "- 마이크 연결 및 기본 장치 설정을 확인하세요."
        )

    if not frames:
        import numpy as np
        return np.zeros((0,), dtype=np.float32)

    import numpy as np
    return np.concatenate(frames, axis=0)


# -----------------------------------------------------------------------------
# STT
# -----------------------------------------------------------------------------
def _transcribe(audio, cfg: VoiceConfig) -> str:
    """캐싱된 WhisperModel로 STT 수행."""
    import numpy as np

    if np.asarray(audio).size == 0:
        return ""

    try:
        model = _get_whisper_model(cfg.model)
    except RuntimeError as e:
        raise RuntimeError(str(e))

    try:
        segments, _ = model.transcribe(
            audio,
            language=(cfg.language or None),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": int(cfg.silence_sec * 1000)},
        )
        return " ".join((seg.text or "").strip() for seg in segments if seg.text and seg.text.strip())
    except Exception as e:
        raise RuntimeError(f"STT 변환 실패: {e}")


# -----------------------------------------------------------------------------
# 공개 API
# -----------------------------------------------------------------------------
def listen_once(cfg: VoiceConfig) -> str:
    """한 번 녹음해서 텍스트로 반환."""
    audio = _record_until_silence(cfg)

    import numpy as np
    if np.asarray(audio).size < int(cfg.samplerate * cfg.min_record_sec):
        return ""

    return _transcribe(audio, cfg)


def _passes_wakeword(text: str, wake: str) -> bool:
    wake = (wake or "").strip().lower()
    if not wake:
        return True
    t = (text or "").strip().lower()
    return t.startswith(wake) or t.startswith(wake + "야") or (wake in t.split())


def _strip_wakeword(text: str, wake_word: str) -> str:
    """웨이크워드를 텍스트 앞에서 제거."""
    if not wake_word:
        return text
    low = text.lower()
    w = wake_word.lower()
    if low.startswith(w):
        text = text[len(wake_word):].lstrip(" ,.!?\t")
    if text.startswith("야"):
        text = text[1:].lstrip()
    return text.strip()


# -----------------------------------------------------------------------------
# CLI 루프
# -----------------------------------------------------------------------------
def voice_actions_loop(cfg: VoiceConfig):
    """무한 루프: 음성 → 텍스트 → actions 실행 (CLI용)"""
    from app import run_actions

    print("[VOICE] 시작: 말하고 잠깐 멈추면 인식합니다. (Ctrl+C 종료)")
    if cfg.wake_word:
        print(f"[VOICE] 웨이크워드: '{cfg.wake_word}'가 포함/시작할 때만 실행")

    # 첫 루프 전에 모델을 미리 로드해서 워밍업
    print(f"[VOICE] 모델 로드 중: {cfg.model} ...")
    try:
        _get_whisper_model(cfg.model)
        print("[VOICE] 모델 준비 완료. 말씀하세요.")
    except RuntimeError as e:
        print(f"[VOICE] 모델 로드 실패: {e}")
        return

    while True:
        try:
            text = listen_once(cfg)
        except RuntimeError as e:
            print(f"[VOICE] 오류: {e}")
            # 폴백: 키보드 입력
            try:
                s = input("[VOICE] (폴백) 텍스트로 명령 입력: ").strip()
                if s:
                    print(run_actions(s))
            except (EOFError, KeyboardInterrupt):
                break
            continue

        text = (text or "").strip()
        if not text:
            continue

        print(f"[VOICE] 인식: {text}")
        if not _passes_wakeword(text, cfg.wake_word):
            continue

        text = _strip_wakeword(text, cfg.wake_word)
        if not text:
            continue

        try:
            result = run_actions(text)
            print(f"[VOICE] 결과: {result}")
        except Exception as e:
            print(f"[VOICE] 명령 실행 오류: {e}")


# -----------------------------------------------------------------------------
# GUI용: stop_event로 중단 가능한 음성 루프
# -----------------------------------------------------------------------------
def gui_voice_loop(
    cfg: VoiceConfig,
    stop_event: threading.Event,
    on_text: Callable[[str], None],
    on_error: Optional[Callable[[str], None]] = None,
):
    """
    GUI에서 별도 스레드로 돌릴 수 있는 음성 루프.
    - stop_event가 set 되면 즉시 종료
    - 텍스트가 인식되면 on_text(text) 호출
    - 오류는 on_error(msg)로 전달
    """
    def _err(msg: str):
        if on_error:
            try:
                on_error(msg)
            except Exception:
                pass

    # 모델 미리 로드 (GUI 스레드를 블로킹하지 않고 여기서 처리)
    try:
        _get_whisper_model(cfg.model)
    except RuntimeError as e:
        _err(str(e))
        return

    while not stop_event.is_set():
        try:
            text = listen_once(cfg)
        except RuntimeError as e:
            _err(str(e))
            time.sleep(0.6)
            continue

        if stop_event.is_set():
            break

        text = (text or "").strip()
        if not text:
            continue

        if not _passes_wakeword(text, cfg.wake_word):
            continue

        text = _strip_wakeword(text, cfg.wake_word)
        if not text:
            continue

        try:
            on_text(text)
        except Exception as e:
            _err(f"콜백 오류: {e}")
            time.sleep(0.2)
