from __future__ import annotations

import json
import logging
import os
import re
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

    # ── Ollama config ────────────────────────────────────────────────────

    def _get_ollama_model(self) -> str:
        # qwen3는 일부 환경에서 thinking을 content로 직접 출력하는 경우가 있어서
        # 빠른 일반 대화 기본값은 exaone3.5:2.4b로 둔다.
        return os.getenv("AKO_OLLAMA_MODEL", "exaone3.5:2.4b").strip() or "exaone3.5:2.4b"

    def _get_ollama_url(self) -> str:
        return os.getenv("AKO_OLLAMA_URL", "http://localhost:11434/api/chat").strip() or "http://localhost:11434/api/chat"

    def _ollama_options(self, *, warmup: bool = False) -> dict:
        """짧은 일반 대화를 빠르게 처리하기 위한 Ollama options.

        환경변수로 조절 가능:
        - AKO_OLLAMA_NUM_CTX: 기본 512
        - AKO_OLLAMA_NUM_PREDICT: 기본 64, 워밍업은 1
        - AKO_OLLAMA_TEMPERATURE: 기본 0.2
        """
        def _env_int(name: str, default: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
                return max(1, value)
            except ValueError:
                return default

        options = {
            "num_ctx": _env_int("AKO_OLLAMA_NUM_CTX", 512),
            "num_predict": 1 if warmup else _env_int("AKO_OLLAMA_NUM_PREDICT", 64),
        }

        try:
            options["temperature"] = float(os.getenv("AKO_OLLAMA_TEMPERATURE", "0.2"))
        except ValueError:
            options["temperature"] = 0.2

        return options

    def _ollama_chat_payload(
        self,
        *,
        model: str,
        messages: list[dict],
        stream: bool,
        warmup: bool = False,
    ) -> dict:
        """Ollama /api/chat 요청 본문 생성.

        thinking 제어는 Ollama 최신 API 기준 최상위 think=False로 처리한다.
        options 안에 넣으면 무시될 수 있으니 반드시 최상위에 둔다.
        """
        payload = {
            "model": model,
            "stream": stream,
            "messages": messages,
            "keep_alive": "30m",
            "options": self._ollama_options(warmup=warmup),
        }

        disable_think = os.getenv("AKO_OLLAMA_DISABLE_THINK", "true").lower() not in {
            "0", "false", "no", "off",
        }
        if disable_think:
            payload["think"] = False

        return payload

    # ── power ────────────────────────────────────────────────────────────

    def power_on(self) -> None:
        if self.powered_on:
            return
        self.powered_on = True
        self.command_on = True
        model = self._get_ollama_model()
        self.log(f"전원 ON (대화 모델: {model})")
        # 전원 켜는 시점에 모델을 미리 메모리에 올려둠 → 첫 대화 딜레이 제거
        threading.Thread(target=self._warmup_model, daemon=True, name="AkoWarmup").start()

    def _warmup_model(self) -> None:
        """Ollama 모델을 메모리에 미리 올려두기 위한 더미 요청."""
        model = self._get_ollama_model()
        ollama_url = self._get_ollama_url()
        try:
            requests.post(
                ollama_url,
                json=self._ollama_chat_payload(
                    model=model,
                    stream=False,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt(model)},
                        {"role": "user", "content": "안녕"},
                    ],
                    warmup=True,
                ),
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

    # ── chat helpers ─────────────────────────────────────────────────────

    def _build_system_prompt(self, model: str) -> str:
        """모델에 맞는 시스템 프롬프트 생성."""
        return (
            "너는 Ako라는 로컬 비서야.\n"
            "규칙:\n"
            "- 반드시 한국어로만 대답해.\n"
            "- 생각 과정, 추론 과정, 영어 내부 독백을 절대 출력하지 마.\n"
            "- 사용자의 말을 분석하거나 다시 해석하지 마.\n"
            "- 사용자의 말을 따라 적거나 되묻지 말고 바로 답해.\n"
            "- 문장에는 정상적인 띄어쓰기를 사용해. 조사와 단어를 억지로 붙이지 마.\n"
            "- 문장부호 뒤에는 자연스럽게 공백을 둬.\n"
            "- 즉시 최종 답변만 짧고 자연스럽게 말해.\n"
            "- 인사에는 한 문장으로 짧게 인사해.\n"
            "예시:\n"
            "사용자: ㅎㅇ\n"
            "Ako: 안녕, 주인님♡\n"
            "사용자: 하이\n"
            "Ako: 하이, 주인님♡\n"
            "사용자: 너 띄어쓰기 못해?\n"
            "Ako: 방금 띄어쓰기가 이상했어요. 이제 제대로 띄어서 말할게요♡\n"
        )

    @staticmethod
    def _strip_think_tags(content: str) -> str:
        """모델이 실수로 <think>...</think>를 content에 섞어 보낼 때 제거.

        스트리밍 청크에 쓰이므로 앞뒤 공백을 보존해야 한다.
        여기서 strip()을 해버리면 "좋은 저녁"이 "좋은저녁"처럼 붙는다.
        """
        if not content:
            return ""

        return re.sub(r"(?is)<think>.*?(?:</think>|$)", "", content)

    @staticmethod
    def _looks_like_reasoning_start(text: str) -> bool:
        s = (text or "").lstrip().lower()
        if not s:
            return False

        starts = (
            "okay", "ok,", "the user", "user asked", "i need", "i should",
            "let me", "first,", "hmm", "wait,", "we need", "this is",
            "they want", "since the user", "as ako",
        )
        return any(s.startswith(p) for p in starts)

    @staticmethod
    def _has_korean(text: str) -> bool:
        return any("가" <= ch <= "힣" for ch in text or "")

    @staticmethod
    def _simple_fallback_reply(user_text: str) -> str:
        """reasoning만 생성되고 최종 답변이 없을 때 최소한 이상한 영어 독백은 숨긴다."""
        t = (user_text or "").strip().lower()

        greetings = {"ㅎㅇ", "하이", "안녕", "안뇽", "hello", "hi", "hey", "ㅎㅇㅎㅇ"}
        if t in greetings or t.replace(" ", "") in greetings:
            return "안녕, 주인님♡"

        thanks = {"ㄳ", "ㄱㅅ", "감사", "고마워", "땡큐", "thanks", "thank you"}
        if t in thanks:
            return "천만에요, 주인님♡"

        return "네, 주인님♡"

    @staticmethod
    def _local_chat_reply(user_text: str) -> Optional[str]:
        """LLM보다 정확하고 빠른 짧은 로컬 응답.

        시간 질문이나 방금 출력 품질 관련 질문은 모델에 맡기면
        되묻거나 헛소리할 수 있어서 Python에서 바로 처리한다.
        """
        raw = (user_text or "").strip()
        compact = re.sub(r"\s+", "", raw.lower())

        greetings = {"ㅎㅇ", "ㅎㅇㅎㅇ", "하이", "안녕", "안뇽", "hi", "hello", "hey"}
        if compact in greetings:
            return "안녕, 주인님♡"

        if "띄어쓰기" in raw and any(word in raw for word in ("못", "왜", "이상", "붙", "안")):
            return "방금 띄어쓰기가 이상했어요. 이제 제대로 띄어서 말할게요♡"

        if any(key in compact for key in ("몇시", "현재시간", "지금시간", "시간알려")):
            return f"지금은 {_now()}이에요, 주인님♡"

        return None

    def _cleanup_reasoning_text(self, content: str, user_text: str = "") -> str:
        """content에 영어 reasoning이 섞여 들어온 경우 최종 답변만 남기려고 시도."""
        text = self._strip_think_tags(content or "")
        if not text:
            return ""

        # 명시적인 최종 답변 마커가 있으면 그 뒤만 사용
        markers = [
            "final answer:",
            "final:",
            "answer:",
            "response:",
            "ako:",
            "최종 답변:",
            "답변:",
        ]
        lower = text.lower()
        for marker in markers:
            idx = lower.rfind(marker)
            if idx >= 0:
                candidate = text[idx + len(marker):].strip()
                if candidate:
                    text = candidate
                    break

        # 여전히 영어 reasoning 시작이면 사용자에게 보여주지 않는다.
        if self._looks_like_reasoning_start(text):
            return self._simple_fallback_reply(user_text)

        # 영어 reasoning 문장이 섞여 있고 한국어 문장이 뒤에 있는 경우 마지막 한국어 줄 위주로 사용
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        korean_lines = [
            line for line in lines
            if self._has_korean(line) and not self._looks_like_reasoning_start(line)
        ]
        if korean_lines:
            text = korean_lines[-1]

        # 너무 긴 응답은 짧은 대화 앱에 맞게 앞부분만 남김
        text = text.strip().strip('"').strip("'").strip()
        if len(text) > 240:
            text = text[:240].rstrip() + "..."

        return text

    # ── chat (스트리밍) ───────────────────────────────────────────────────

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

        local_reply = self._local_chat_reply(text)
        if local_reply:
            self._chat_history.add("user", text)
            self._chat_history.add("assistant", local_reply)
            yield local_reply
            return

        model = self._get_ollama_model()
        ollama_url = self._get_ollama_url()
        system_prompt = self._build_system_prompt(model)

        self._chat_history.add("user", text)

        collected: list[str] = []
        raw_content_parts: list[str] = []
        initial_probe = ""
        suppress_reasoning_stream = False

        try:
            resp = requests.post(
                ollama_url,
                json=self._ollama_chat_payload(
                    model=model,
                    stream=True,
                    messages=self._chat_history.get_messages(system_prompt),
                ),
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

                message = data.get("message") or {}

                # thinking 필드는 무조건 버림
                if message.get("thinking"):
                    continue

                chunk = message.get("content") or ""
                if chunk:
                    raw_content_parts.append(chunk)

                    # 첫 부분을 조금 모아서 reasoning 시작인지 판단한다.
                    if len(initial_probe) < 80:
                        initial_probe += chunk

                    if self._looks_like_reasoning_start(initial_probe):
                        suppress_reasoning_stream = True

                    if suppress_reasoning_stream:
                        # reasoning으로 시작한 응답은 중간 chunk를 GUI에 내보내지 않고
                        # done 이후 정리한 최종 답변만 한 번 출력한다.
                        pass
                    else:
                        cleaned_chunk = self._strip_think_tags(chunk)
                        if cleaned_chunk:
                            collected.append(cleaned_chunk)
                            yield cleaned_chunk

                if data.get("done"):
                    eval_count = data.get("eval_count")
                    if isinstance(eval_count, int) and eval_count > 200:
                        self.log(
                            f"(Ollama 경고) eval_count={eval_count}: 응답이 길거나 reasoning이 발생했을 수 있어요. "
                            "모델을 exaone3.5:2.4b 또는 gemma3:4b로 쓰는 걸 권장해요."
                        )
                    break

            raw_full = "".join(raw_content_parts).strip()

            if suppress_reasoning_stream:
                final_text = self._cleanup_reasoning_text(raw_full, user_text=text).strip()
                if final_text:
                    collected = [final_text]
                    yield final_text

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

        local_reply = self._local_chat_reply(text)
        if local_reply:
            self._chat_history.add("user", text)
            self._chat_history.add("assistant", local_reply)
            return local_reply

        model = self._get_ollama_model()
        ollama_url = self._get_ollama_url()
        system_prompt = self._build_system_prompt(model)

        self._chat_history.add("user", text)

        try:
            resp = requests.post(
                ollama_url,
                json=self._ollama_chat_payload(
                    model=model,
                    stream=False,
                    messages=self._chat_history.get_messages(system_prompt),
                ),
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data.get("message", {}).get("content") or ""
            content = self._cleanup_reasoning_text(content, user_text=text).strip()
            if not content:
                content = self._simple_fallback_reply(text)

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
