# voice_loop.py
# -----------------------------------------------------------------------------
# 마이크 입력을 받아 STT(음성->텍스트) 후 app.run_actions()로 넘기는 루프.
# - 기본은 faster-whisper(오프라인) 사용을 시도
# - 의존성이 없으면 에러 메시지와 함께 텍스트 입력 폴백을 제공
# -----------------------------------------------------------------------------
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class VoiceConfig:
    device: Optional[int] = None          # sounddevice 입력 장치 인덱스
    samplerate: int = 16000
    min_record_sec: float = 0.6
    max_record_sec: float = 10.0
    silence_sec: float = 0.9              # 이만큼 조용하면 종료
    silence_threshold: float = 0.012      # RMS 기준(환경에 따라 조절)
    model: str = "small"                 # faster-whisper 모델명/경로
    language: str = "ko"                 # "ko", "en" 등
    wake_word: str = ""                 # 예: "아코" / "ako" (비우면 항상 처리)
    print_heard_audio_stats: bool = False


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
    block = int(sr * 0.2)  # 200ms

    frames = []
    started = False
    silent_for = 0.0
    total = 0.0

    def _cb(indata, _frames, _time, status):
        nonlocal started, silent_for, total
        if status:
            # 드라이버 경고 정도는 무시
            pass
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

        # 녹음 시작 이후에만 무음 체크
        if level < cfg.silence_threshold:
            silent_for += _frames / sr
        else:
            silent_for = 0.0

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

    if not frames:
        return np.zeros((0,), dtype=np.float32)
    return np.concatenate(frames, axis=0)


def _transcribe_faster_whisper(audio, cfg: VoiceConfig) -> str:
    """faster-whisper가 있으면 그걸로 오프라인 STT."""
    from faster_whisper import WhisperModel

    model = WhisperModel(cfg.model, device="auto", compute_type="auto")

    # faster-whisper는 numpy float32 mono / sample_rate 전달 가능
    segments, info = model.transcribe(
        audio,
        language=(cfg.language or None),
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": int(cfg.silence_sec * 1000)},
    )

    text_parts = []
    for seg in segments:
        t = (seg.text or "").strip()
        if t:
            text_parts.append(t)
    return " ".join(text_parts).strip()


def listen_once(cfg: VoiceConfig) -> str:
    """한 번 녹음해서 텍스트로 반환."""
    try:
        audio = _record_until_silence(cfg)
    except Exception as e:
        raise RuntimeError(
            "마이크 녹음에 실패했어요.\n"
            "- pip install sounddevice numpy\n"
            "- Windows면 'pip install pipwin' 후 'pipwin install pyaudio' 같은 우회가 필요할 수 있어요.\n"
            f"원인: {e}"
        )

    # 너무 짧은 입력이면 무시
    try:
        import numpy as np

        if np.asarray(audio).size < int(cfg.samplerate * cfg.min_record_sec):
            return ""
    except Exception:
        pass

    try:
        return _transcribe_faster_whisper(audio, cfg)
    except Exception as e:
        raise RuntimeError(
            "STT(음성 인식)에 실패했어요.\n"
            "오프라인 STT는 faster-whisper를 추천해요:\n"
            "- pip install faster-whisper\n"
            "- (CUDA 사용 시) torch 설치 상태에 따라 추가 설정이 필요할 수 있어요.\n"
            f"원인: {e}"
        )


def _passes_wakeword(text: str, wake: str) -> bool:
    wake = (wake or "").strip().lower()
    if not wake:
        return True
    t = (text or "").strip().lower()
    # '아코 ...', '아코야 ...', 'ako ...'
    return t.startswith(wake) or t.startswith(wake + "야") or (wake in t.split())


def voice_actions_loop(cfg: VoiceConfig):
    """무한 루프: 음성 -> 텍스트 -> actions 실행"""
    from app import run_actions

    print("[VOICE] 시작: 말하고 잠깐 멈추면 인식합니다. (Ctrl+C 종료)")
    if cfg.wake_word:
        print(f"[VOICE] 웨이크워드: '{cfg.wake_word}'가 포함/시작할 때만 실행")

    while True:
        try:
            text = listen_once(cfg)
        except RuntimeError as e:
            print(str(e))
            # 폴백: 키보드 입력
            s = input("[VOICE] (폴백) 텍스트로 명령 입력: ").strip()
            if not s:
                continue
            print(run_actions(s))
            continue

        text = (text or "").strip()
        if not text:
            continue

        print(f"[VOICE] 인식: {text}")
        if not _passes_wakeword(text, cfg.wake_word):
            continue

        # 웨이크워드가 붙어있으면 제거
        if cfg.wake_word:
            low = text.lower()
            w = cfg.wake_word.lower()
            if low.startswith(w):
                text = text[len(cfg.wake_word):].lstrip(" ,.!?\t")
            if text.startswith("야"):
                text = text[1:].lstrip()

        if not text:
            continue

        result = run_actions(text)
        print(f"[VOICE] 결과: {result}")

