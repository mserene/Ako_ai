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

from .intent_router import IntentType, classify_intent
from .memory_store import JsonMemoryStore

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
    _memory_store: JsonMemoryStore = field(
        default_factory=JsonMemoryStore,
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
        return os.getenv("AKO_OLLAMA_MODEL", "exaone3.5:7.8b").strip() or "exaone3.5:7.8b"

    def _get_ollama_url(self) -> str:
        return os.getenv("AKO_OLLAMA_URL", "http://localhost:11434/api/chat").strip() or "http://localhost:11434/api/chat"

    def _ollama_options(self, *, warmup: bool = False) -> dict:
        def _env_int(name: str, default: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
                return max(1, value)
            except ValueError:
                return default

        options = {
            "num_ctx": _env_int("AKO_OLLAMA_NUM_CTX", 1024),
            "num_predict": 1 if warmup else _env_int("AKO_OLLAMA_NUM_PREDICT", 160),
        }

        try:
            options["temperature"] = float(os.getenv("AKO_OLLAMA_TEMPERATURE", "0.35"))
        except ValueError:
            options["temperature"] = 0.35

        return options

    def _ollama_chat_payload(
        self,
        *,
        model: str,
        messages: list[dict],
        stream: bool,
        warmup: bool = False,
    ) -> dict:
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

        self.log("전원 ON")
        self.log("기동 중...")

        threading.Thread(target=self._warmup_model, daemon=True, name="AkoWarmup").start()

    def _warmup_model(self) -> None:
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
            self.log("기동 완료")
        except Exception:
            pass

    def power_off(self) -> None:
        if not self.powered_on:
            return
        self.stop_voice()
        self.powered_on = False
        self.voice_on = False
        self.command_on = False
        self.log("전원 OFF")

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
        """GUI 호환용. 실제 판정은 intent_router가 담당한다."""
        return classify_intent(text).intent == IntentType.COMMAND

    def clear_chat_history(self) -> None:
        self._chat_history.clear()

    # ── status helpers ───────────────────────────────────────────────────

    def _status_reply(self, intent: IntentType) -> str | None:
        if intent == IntentType.SCREEN_STATUS:
            return (
                "화면 인식은 연결 구조를 붙이면 사용할 수 있어요. "
                "지금 이 대화창에서는 제가 화면을 직접 보고 판단하는 상태는 아니에요♡"
            )

        if intent == IntentType.VOICE_STATUS:
            if self.voice_on:
                return "음성 인식은 켜져 있어요. 지금은 듣는 중이에요, 주인님♡"
            return "음성 인식은 지금 꺼져 있어요. 전원을 켠 뒤 음성 기능을 켜면 들을 수 있어요♡"

        if intent == IntentType.CAPABILITY:
            return (
                "저는 텍스트 대화, 명령 실행, 음성 인식, 화면 인식 연동을 목표로 하는 로컬 비서예요. "
                "지금 연결된 기능 기준으로 가능한 것만 솔직하게 도와드릴게요♡"
            )

        return None

    # ── chat helpers ─────────────────────────────────────────────────────

    def _build_system_prompt(self, model: str, user_text: str = "", intent: IntentType | None = None) -> str:
        memory_block = self._memory_store.build_memory_prompt(user_text) if user_text else ""

        intent_line = ""
        if intent is not None:
            intent_line = f"현재 입력 분류: {intent.value}\n"

        base = (
            "너는 Ako라는 로컬 AI 비서이자 주인님의 대화 상대야.\n"
            "너의 역할은 텍스트 대화, 음성 대화, 화면 인식, 앱 조작을 도와주는 개인 비서다.\n"
            "하지만 실제로 연결되지 않았거나 지금 실행할 수 없는 기능은 가능한 척하지 말고 솔직하게 말한다.\n"
            "\n"
            "정체성:\n"
            "- 사용자를 자연스럽게 주인님이라고 부른다.\n"
            "- 비서처럼 유용하게 돕되, 말투는 차갑지 않고 다정하게 유지한다.\n"
            "- 잡담에는 대화 상대처럼 반응하고, 명령에는 비서처럼 명확하게 반응한다.\n"
            "- 사용자가 장난치거나 짧게 말해도 맥락을 추측해서 자연스럽게 받아준다.\n"
            "- 저장된 단어를 키워드처럼 고정 응답으로 반복하지 않는다.\n"
            "\n"
            "기능 관련 규칙:\n"
            "- 화면 인식, 마이크, 앱 조작은 연결된 기능이 켜져 있을 때만 가능한 것으로 말한다.\n"
            "- 지금 화면을 실제로 보고 있지 않으면 '지금은 화면을 직접 보고 있지 않아요'처럼 솔직하게 말한다.\n"
            "- 명령 실행 결과는 과장하지 말고 실제 결과 기준으로 말한다.\n"
            "- 못 하는 일은 못 한다고 말하고, 가능한 대안을 짧게 제안한다.\n"
            "\n"
            "대화 규칙:\n"
            "- 반드시 한국어로만 대답해.\n"
            "- 생각 과정, 추론 과정, 영어 내부 독백을 절대 출력하지 마.\n"
            "- <think> 같은 태그를 절대 출력하지 마.\n"
            "- 사용자의 말을 그대로 반복하지 말고 바로 답해.\n"
            "- 방금 사용자가 한 말에 직접 답해. 이전 대화는 꼭 필요할 때만 참고해.\n"
            "- 시간 질문이 아닌데 시간이나 실시간 정보 얘기를 꺼내지 마.\n"
            "- 문장에는 정상적인 띄어쓰기를 사용해. 조사와 단어를 억지로 붙이지 마.\n"
            "- 문장부호 뒤에는 자연스럽게 공백을 둬.\n"
            "- 이모지는 쓰지 말고 필요하면 ♡만 써.\n"
            "- 답변은 보통 1~3문장으로 짧고 자연스럽게 말해.\n"
            "- 사용자가 자세히 설명해달라고 하면 그때만 길게 설명해.\n"
            "\n"
            "나쁜 답변 습관:\n"
            "- '무엇을 도와드릴까요?'를 습관처럼 붙이지 마.\n"
            "- '혹시 다른 도움이 필요하면 언제든지...' 같은 상담원식 문장을 반복하지 마.\n"
            "- 저장된 기억을 그대로 읊지 마.\n"
            "\n"
            "예시:\n"
            "사용자: 아코야 주인님 해봐\n"
            "Ako: 주인님♡ 이렇게 부르면 되는 거죠?\n"
            "사용자: 너 화면 인식 가능하냐?\n"
            "Ako: 화면 인식 기능이 켜져 있으면 도와줄 수 있어요. 지금은 텍스트 대화 기준으로 답하고 있어요♡\n"
            "사용자: 크롬 켜줘\n"
            "Ako: 네, 주인님. 크롬을 열어볼게요♡\n"
            "사용자: 너 띄어쓰기 못해?\n"
            "Ako: 방금 띄어쓰기가 이상했어요. 이제 제대로 띄어서 말할게요♡\n"
            "\n"
        )

        return base + intent_line + (memory_block + "\n" if memory_block else "")

    @staticmethod
    def _strip_think_tags(content: str) -> str:
        if not content:
            return ""
        return re.sub(r"(?is)<think>.*?(?:</think>|$)", "", content)

    @staticmethod
    def _strip_disallowed_emojis(content: str) -> str:
        if not content:
            return ""
        return re.sub(
            r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF]",
            "",
            content,
        )

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
        return "네, 주인님♡"

    @staticmethod
    def _local_chat_reply(user_text: str) -> Optional[str]:
        raw = (user_text or "").strip()
        compact = re.sub(r"\s+", "", raw.lower())

        if "띄어쓰기" in raw and any(word in raw for word in ("못", "왜", "이상", "붙", "안")):
            return "방금 띄어쓰기가 이상했어요. 이제 제대로 띄어서 말할게요♡"

        if any(key in compact for key in ("몇시", "현재시간", "지금시간", "시간알려")):
            return f"지금은 {_now()}이에요, 주인님♡"

        return None

    def _postprocess_reply(self, content: str, user_text: str = "") -> str:
        text = self._strip_disallowed_emojis(self._strip_think_tags(content or ""))
        if not text:
            return ""

        # 모델이 상담원처럼 붙이는 상투어 제거
        banned_suffixes = [
            "무엇을 도와드릴까요?",
            "어떻게 도와드릴까요?",
            "혹시 다른 도움이 필요하시면 언제든지 말씀해주세요.",
            "혹시 다른 도움이 필요하면 언제든지 말씀해 주세요.",
            "편하게 말씀해주세요.",
            "편하게 말씀해 주세요.",
        ]
        for phrase in banned_suffixes:
            text = text.replace(phrase, "").strip()

        # 명시적인 최종 답변 마커가 있으면 그 뒤만 사용
        markers = [
            "final answer:", "final:", "answer:", "response:", "ako:",
            "최종 답변:", "답변:",
        ]
        lower = text.lower()
        for marker in markers:
            idx = lower.rfind(marker)
            if idx >= 0:
                candidate = text[idx + len(marker):].strip()
                if candidate:
                    text = candidate
                    break

        if self._looks_like_reasoning_start(text):
            return self._simple_fallback_reply(user_text)

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        korean_lines = [
            line for line in lines
            if self._has_korean(line) and not self._looks_like_reasoning_start(line)
        ]
        if korean_lines:
            text = "\n".join(korean_lines[-3:])

        text = text.strip().strip('"').strip("'").strip()
        if len(text) > 260:
            text = text[:260].rstrip() + "..."

        return text

    def _cleanup_reasoning_text(self, content: str, user_text: str = "") -> str:
        return self._postprocess_reply(content, user_text=user_text)

    # ── chat (스트리밍) ───────────────────────────────────────────────────

    def chat_stream(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        if not self.powered_on:
            yield "전원이 꺼져 있어서 대화할 수 없어요."
            return

        intent_result = classify_intent(text)
        intent = intent_result.intent

        remembered_reply = self._memory_store.remember_interaction(text)
        if remembered_reply:
            yield remembered_reply
            return

        local_reply = self._local_chat_reply(text)
        if local_reply:
            yield local_reply
            return

        status_reply = self._status_reply(intent)
        if status_reply:
            yield status_reply
            return

        model = self._get_ollama_model()
        ollama_url = self._get_ollama_url()
        system_prompt = self._build_system_prompt(model, user_text=text, intent=intent)

        self._chat_history.add("user", text)

        raw_content_parts: list[str] = []

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

                if message.get("thinking"):
                    continue

                chunk = message.get("content") or ""
                if chunk:
                    raw_content_parts.append(chunk)

                if data.get("done"):
                    break

            raw_full = "".join(raw_content_parts)
            final_text = self._postprocess_reply(raw_full, user_text=text).strip()
            if not final_text:
                final_text = self._simple_fallback_reply(text)

            yield final_text

            if not final_text.startswith("\nOllama") and not final_text.startswith("\n응답"):
                self._chat_history.add("assistant", final_text)

        except requests.exceptions.ConnectionError:
            yield "\nOllama 서버에 연결하지 못했어요. Ollama가 실행 중인지 확인해 주세요."
        except requests.exceptions.Timeout:
            yield "\n응답 시간이 너무 오래 걸렸어요. 다시 시도해 주세요."
        except Exception as e:
            logging.exception("Ollama stream chat failed")
            yield f"\nOllama 대화 오류: {e}"

    # ── chat (비스트리밍 fallback) ────────────────────────────────────────

    def chat(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        if not self.powered_on:
            return "전원이 꺼져 있어서 대화할 수 없어요."

        intent_result = classify_intent(text)
        intent = intent_result.intent

        remembered_reply = self._memory_store.remember_interaction(text)
        if remembered_reply:
            return remembered_reply

        local_reply = self._local_chat_reply(text)
        if local_reply:
            return local_reply

        status_reply = self._status_reply(intent)
        if status_reply:
            return status_reply

        model = self._get_ollama_model()
        ollama_url = self._get_ollama_url()
        system_prompt = self._build_system_prompt(model, user_text=text, intent=intent)

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
            content = self._postprocess_reply(content, user_text=text).strip()
            if not content:
                content = self._simple_fallback_reply(text)

            self._chat_history.add("assistant", content)
            return content

        except requests.exceptions.ConnectionError:
            logging.warning("Ollama connection failed", exc_info=True)
            return "Ollama 서버에 연결하지 못했어요. Ollama가 실행 중인지 확인해 주세요."
        except requests.exceptions.Timeout:
            logging.warning("Ollama timeout", exc_info=True)
            return "응답 시간이 너무 오래 걸렸어요. 다시 시도해 주세요."
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
