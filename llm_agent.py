from __future__ import annotations

import json
import logging
import os
import re
from collections import deque
from typing import Deque, Optional


def _ollama_chat(messages: list[dict], model: str = "exaone3.5:7.8b", timeout: int = 30) -> str:
    try:
        import ollama  # type: ignore
        resp = ollama.chat(model=model, messages=messages)
        return resp["message"]["content"].strip()
    except ImportError:
        pass

    try:
        import requests  # type: ignore
        base_url = os.getenv("AKO_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        resp = requests.post(
            f"{base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[LLM 오류] Ollama 연결 실패: {e}\nOllama가 실행 중인지 확인해줘요. (ollama serve)"


_TOOLS_DESC = """
당신은 사용자의 PC를 도와주는 AI 어시스턴트 'Ako'입니다.
사용자의 입력을 분석해서 아래 중 하나로 응답하세요.

[툴 목록]
1. open_app: 앱 실행 또는 앞으로 띄우기
2. search: 웹/앱 검색
3. ui_click: 화면의 버튼/텍스트 클릭
4. youtube_toggle: 유튜브 재생/일시정지 토글
5. chat: 위 툴에 해당하지 않는 일상 대화, 질문, 잡담

[응답 형식]
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.
툴 사용 시:
{"tool": "툴이름", "text": "원본 사용자 입력 그대로"}
일상 대화 시:
{"tool": "chat", "reply": "자연스러운 한국어 응답"}
"""


class ConversationHistory:
    def __init__(self, max_turns: int = 10):
        self._history: Deque[dict[str, str]] = deque(maxlen=max_turns * 2)

    def add(self, role: str, content: str) -> None:
        content = (content or "").strip()
        if not content:
            return
        self._history.append({"role": role, "content": content})

    def get_messages(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}, *list(self._history)]

    def clear(self) -> None:
        self._history.clear()


class AkoAgent:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("AKO_AGENT_MODEL", "exaone3.5:7.8b")
        self.history = ConversationHistory(max_turns=10)

    def _parse_response(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logging.warning("LLM JSON 파싱 실패: %s", cleaned)
        return {"tool": "chat", "reply": raw.strip()}

    def run(self, user_input: str) -> str:
        user_input = (user_input or "").strip()
        if not user_input:
            return "명령이 비어 있어요."

        self.history.add("user", user_input)
        messages = self.history.get_messages(_TOOLS_DESC)
        raw = _ollama_chat(messages, model=self.model)
        parsed = self._parse_response(raw)
        tool = parsed.get("tool", "chat")
        result = self._dispatch(tool, parsed, user_input)
        self.history.add("assistant", result)
        return result

    def _dispatch(self, tool: str, parsed: dict, original_text: str) -> str:
        try:
            from command_actions import (
                handle_open_app,
                handle_search_command,
                handle_ui_click,
                handle_youtube_toggle,
                load_app_specs,
            )
        except ImportError as e:
            logging.exception("명령 모듈 로드 실패")
            return f"명령 모듈 로드 실패: {e}"

        text = parsed.get("text", original_text)

        if tool == "open_app":
            specs = load_app_specs()
            result = handle_open_app(text, specs)
            return result or "앱을 찾지 못했어요. app_commands.json에 등록된 앱인지 확인해줘요."
        if tool == "search":
            return handle_search_command(text) or "검색어를 이해하지 못했어요."
        if tool == "ui_click":
            return handle_ui_click(text) or "클릭할 대상을 화면에서 찾지 못했어요."
        if tool == "youtube_toggle":
            result = handle_youtube_toggle(text)
            if result:
                return result
            try:
                from ui_tap import youtube_toggle_click_only
                youtube_toggle_click_only(direction=None)
                return "유튜브 토글 완료"
            except Exception as e:
                logging.exception("유튜브 토글 실패")
                return f"유튜브 토글 실패: {e}"
        if tool == "chat":
            return parsed.get("reply", "...")
        return f"알 수 없는 툴: {tool}"

    def clear_history(self) -> None:
        self.history.clear()


_agent_instance: Optional[AkoAgent] = None


def get_agent(model: str | None = None) -> AkoAgent:
    global _agent_instance
    wanted_model = model or os.getenv("AKO_AGENT_MODEL", "exaone3.5:7.8b")
    if _agent_instance is None or _agent_instance.model != wanted_model:
        _agent_instance = AkoAgent(model=wanted_model)
    return _agent_instance


def run_agent(user_input: str, model: str | None = None) -> str:
    return get_agent(model).run(user_input)
