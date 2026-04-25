from __future__ import annotations

import json
import logging
import os
import requests
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from voice_loop import (
    BootstrapStatus,
    VoiceConfig,
    ensure_whisper_model_async,
    gui_voice_loop,
)

LogFn = Callable[[str], None]


def _run_actions(text: str) -> str:
    from app import run_actions
    return run_actions(text)


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ConversationHistory:
    def __init__(self, max_turns: int = 8):
        self._history = deque(maxlen=max_turns * 2)

    def add(self, role: str, content: str) -> None:
        content = (content or "").strip()
        if not content:
            return
        self._history.append({"role": role, "content": content})

    def get_messages(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}] + list(self._history)

    def clear(self) -> None:
        self._history.clear()


@dataclass
class AkoController:
    log_fn: Optional[LogFn] = None

    powered_on: bool = False
    voice_on: bool = False
    command_on: bool = False

    models_root: str = ""

    logs: list[str] = field(default_factory=list)
    bootstrap_status: BootstrapStatus = field(default_factory=BootstrapStatus)

    _voice_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _voice_stop: Optional[threading.Event] = field(default=None, init=False, repr=False)
    _chat_history: ConversationHistory = field(
        default_factory=lambda: ConversationHistory(max_turns=8),
        init=False,
        repr=False,
    )

    # ── config ───────────────────────────────────────────────────────────

    def set_models_root(self, path: str) -> None:
        self.models_root = (path or "").strip()
        if self.models_root:
            self.log(f"모델 저장 위치 설정: {self.models_root}")
        else:
            self.log("모델 저장 위치 기본값 사용")

    # ── logging ──────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        line = f"[{_now()}] {msg}"
        self.logs.append(line)
        if self.log_fn:
            try:
                self.log_fn(line)
            except Exception:
                logging.exception("GUI log callback failed")

    # ── power ────────────────────────────────────────────────────────────

    def power_on(self) -> None:
        if self.powered_on:
            return
        self.powered_on = True
        self.command_on = True
        self.log("전원 ON")
        # 전원 켜는 시점에 모델을 미리 메모리에 올려둠 → 첫 대화 딜레이 제거
        threading.Thread(target=self._warmup_model, daemon=True, name="AkoWarmup").start()

    def _warmup_model(self) -> None:
        """Ollama 모델을 메모리에 미리 올려두기 위한 더미 요청."""
        model = os.getenv("AKO_OLLAMA_MODEL", "qwen3:4b")
        ollama_url = os.getenv("AKO_OLLAMA_URL", "http://localhost:11434/api/chat")
        try:
            requests.post(
                ollama_url,
                json={
                    "model": model,
                    "stream": False,
                    "messages": [{"role": "user", "content": "안녕"}],
                    "keep_alive": "30m",
                    "options": {"num_predict": 1},  # 토큰 1개만 생성 → 로딩만 하고 즉시 종료
                },
                timeout=60,
            )
            self.log("(모델 워밍업 완료)")
        except Exception:
            pass  # 실패해도 무관, 첫 대화가 살짝 느릴 뿐

    def power_off(self) -> None:
        if not self.powered_on:
            return
        self.stop_voice()
        self.powered_on = False
        self.voice_on = False
        self.command_on = False
        self.log("전원 OFF (모든 기능 정지)")

    def toggle_power(self) -> None:
        if self.powered_on:
            self.power_off()
        else:
            self.power_on()

    # ── command ──────────────────────────────────────────────────────────

    def set_command(self, on: bool) -> None:
        if not self.powered_on:
            self.log("전원이 OFF라서 명령창 설정을 무시했어요.")
            return
        self.command_on = bool(on)
        self.log(f"명령창 {'ON' if self.command_on else 'OFF'}")

    def handle_text_command(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        if not self.powered_on:
            self.log("전원이 OFF라서 입력을 무시했어요.")
            return
        if not self.command_on:
            self.log("명령창이 OFF라서 입력을 무시했어요.")
            return

        try:
            result = _run_actions(text)
        except Exception as e:
            logging.exception("handle_text_command failed")
            self.log(f"[Ako] 오류: {e}")
            return
        self.log(f"[Ako] {result}")

    def is_command_text(self, text: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        keywords = [
            "열어", "켜", "꺼", "실행", "재생", "눌러", "클릭",
            "닫아", "입력", "검색", "삭제", "가줘", "해줘",
            "앞으로", "포커스", "띄워", "찾아줘",
        ]
        return any(k in text for k in keywords)

    def clear_chat_history(self) -> None:
        self._chat_history.clear()

    # ── chat (스트리밍) ───────────────────────────────────────────────────

    def _build_system_prompt(self, model: str) -> str:
        """모델에 맞는 시스템 프롬프트 생성. qwen3 계열만 /nothink 적용."""
        base = (
            "너는 Ako라는 로컬 비서야. "
            "답변은 한국어로 자연스럽고 짧고 친절하게 해. "
            "쓸데없이 길게 말하지 말고, 사용자와 편하게 대화해."
        )
        # qwen3 계열은 /nothink으로 thinking 모드를 끄면 응답이 크게 빨라짐
        if "qwen3" in model.lower():
            return f"/nothink\n{base}"
        return base

    def chat_stream(self, text: str):
        """
        스트리밍 버전 chat. 토큰 청크를 yield한다.
        GUI 스레드에서 직접 호출하지 말고 별도 스레드에서 호출할 것.
        """
        text = (text or "").strip()
        if not text:
            return

        if not self.powered_on:
            yield "전원이 꺼져 있어서 대화할 수 없어요."
            return

        model = os.getenv("AKO_OLLAMA_MODEL", "qwen3:4b")
        ollama_url = os.getenv("AKO_OLLAMA_URL", "http://localhost:11434/api/chat")
        system_prompt = self._build_system_prompt(model)

        self._chat_history.add("user", text)

        collected: list[str] = []
        try:
            resp = requests.post(
                ollama_url,
                json={
                    "model": model,
                    "stream": True,
                    "messages": self._chat_history.get_messages(system_prompt),
                    "keep_alive": "30m",
                },
                timeout=120,
                stream=True,
            )
            resp.raise_for_status()

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                chunk = (data.get("message") or {}).get("content") or ""
                if chunk:
                    collected.append(chunk)
                    yield chunk

                if data.get("done"):
                    break

            # 오류 메시지가 아닌 정상 응답만 히스토리에 저장
            full = "".join(collected).strip()
            if full and not full.startswith("\nOllama") and not full.startswith("\n응답"):
                self._chat_history.add("assistant", full)

        except requests.exceptions.ConnectionError:
            yield "\nOllama 서버에 연결하지 못했어요. Ollama가 실행 중인지 확인해 주세요."
        except requests.exceptions.Timeout:
            yield "\n응답 시간이 너무 오래 걸렸어요. 다시 시도해 주세요."
        except Exception as e:
            logging.exception("Ollama stream chat failed")
            yield f"\nOllama 대화 오류: {e}"

    # ── chat (비스트리밍 fallback) ────────────────────────────────────────

    def chat(self, text: str) -> str:
        """비스트리밍 버전. GUI에서는 chat_stream() 사용 권장."""
        text = (text or "").strip()
        if not text:
            return ""

        if not self.powered_on:
            return "전원이 꺼져 있어서 대화할 수 없어요."

        model = os.getenv("AKO_OLLAMA_MODEL", "qwen3:4b")
        ollama_url = os.getenv("AKO_OLLAMA_URL", "http://localhost:11434/api/chat")
        system_prompt = self._build_system_prompt(model)

        self._chat_history.add("user", text)

        try:
            resp = requests.post(
                ollama_url,
                json={
                    "model": model,
                    "stream": False,
                    "messages": self._chat_history.get_messages(system_prompt),
                    "keep_alive": "30m",  # 5m → 30m
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            content = (data.get("message", {}).get("content") or "").strip()
            if not content:
                return "응답은 왔는데 내용이 비어 있어요."

            self._chat_history.add("assistant", content)
            return content

        except requests.exceptions.ConnectionError:
            logging.warning("Ollama connection failed", exc_info=True)
            return "Ollama 서버에 연결하지 못했어요. Ollama가 실행 중인지 확인해 주세요."
        except requests.exceptions.Timeout:
            logging.warning("Ollama timeout", exc_info=True)
            return "응답 시간이 너무 오래 걸렸어요. 더 가벼운 모델을 쓰거나 다시 시도해 주세요."
        except Exception as e:
            logging.exception("Ollama chat failed")
            return f"Ollama 대화 오류: {e}"

    # ── voice ────────────────────────────────────────────────────────────

    def set_voice(self, on: bool, cfg: Optional[VoiceConfig] = None) -> None:
        if not self.powered_on:
            self.log("전원이 OFF라서 음성 인식 설정을 무시했어요.")
            return
        on = bool(on)
        if on:
            self.start_voice(cfg or VoiceConfig())
        else:
            self.stop_voice()

    def start_voice(self, cfg: VoiceConfig) -> None:
        if not self.powered_on:
            self.log("전원이 OFF라서 음성 인식을 시작할 수 없어요.")
            return
        if self.voice_on and self._voice_thread and self._voice_thread.is_alive():
            return

        self.log(f"음성 인식 준비 중... (model={cfg.model})")
        self.voice_on = False

        def _after_model_ready(model_path: Optional[str]):
            if not self.powered_on:
                return
            if model_path is None:
                self.log("음성 인식 시작 실패: 모델을 준비하지 못했어요. (텍스트 명령창은 사용 가능)")
                self.voice_on = False
                return

            cfg.model = model_path
            self._voice_stop = threading.Event()
            self.voice_on = True
            self.log("음성 인식 ON (듣는 중...)")

            def _on_heard(text: str):
                self.log(f"[나] {text}")
                try:
                    result = _run_actions(text)
                except Exception as e:
                    logging.exception("voice action failed")
                    self.log(f"[Ako] 오류: {e}")
                    return
                self.log(f"[Ako] {result}")

            def _on_error(err: str):
                self.log(f"(음성) {err}")

            t = threading.Thread(
                target=gui_voice_loop,
                args=(cfg, self._voice_stop, _on_heard, _on_error),
                daemon=True,
                name="AkoVoiceLoop",
            )
            self._voice_thread = t
            t.start()

        ensure_whisper_model_async(
            cfg.model,
            log=self.log,
            status=self.bootstrap_status,
            on_done=_after_model_ready,
            models_root=self.models_root,
        )

    def stop_voice(self) -> None:
        if self._voice_stop is not None:
            self._voice_stop.set()
        if self._voice_thread and self._voice_thread.is_alive():
            try:
                self._voice_thread.join(timeout=1.0)
            except Exception:
                logging.exception("voice thread join failed")
        self._voice_thread = None
        self._voice_stop = None
        if self.voice_on:
            self.voice_on = False
            self.log("음성 인식 OFF")
