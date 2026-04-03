# llm_agent.py
# -----------------------------------------------------------------------------
# Ollama(exaone3.5) 기반 에이전트
# - 사용자 입력을 받아 의도를 파악하고 적절한 툴을 호출하거나 일상 대화를 반환한다.
# - 실제 OS 동작은 command_actions.py가 담당한다.
# -----------------------------------------------------------------------------
from __future__ import annotations

import json
import re
from typing import Optional

# ---------------------------------------------------------------------------
# Ollama 클라이언트 (ollama 패키지 없으면 requests로 fallback)
# ---------------------------------------------------------------------------
def _ollama_chat(messages: list[dict], model: str = "exaone3.5:7.8b", timeout: int = 30) -> str:
    """Ollama /api/chat 엔드포인트를 호출하고 assistant 응답 텍스트를 반환한다."""
    try:
        import ollama  # type: ignore
        resp = ollama.chat(model=model, messages=messages)
        return resp["message"]["content"].strip()
    except ImportError:
        pass

    # ollama 패키지 없으면 requests로 직접 호출
    try:
        import requests  # type: ignore
        resp = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception as e:
        return f"[LLM 오류] Ollama 연결 실패: {e}\nOllama가 실행 중인지 확인해줘요. (ollama serve)"


# ---------------------------------------------------------------------------
# 툴 정의 — LLM에게 알려줄 사용 가능한 액션 목록
# ---------------------------------------------------------------------------
_TOOLS_DESC = """
당신은 사용자의 PC를 도와주는 AI 어시스턴트 'Ako'입니다.
사용자의 입력을 분석해서 아래 중 하나로 응답하세요.

[툴 목록]
1. open_app: 앱 실행 또는 앞으로 띄우기
   - 예: "크롬 켜줘", "디스코드 앞으로", "스팀 열어줘"

2. search: 웹/앱 검색
   - 예: "유튜브에서 고양이 검색해줘", "구글에서 날씨 찾아줘", "네이버에서 뉴스 검색해줘"

3. ui_click: 화면의 버튼/텍스트 클릭
   - 예: "닫기 눌러줘", "오른쪽 위에 있는 확인 눌러줘"

4. youtube_toggle: 유튜브 재생/일시정지 토글
   - 예: "유튜브 재생해줘", "유튜브 멈춰줘", "유튜브 일시정지"

5. chat: 위 툴에 해당하지 않는 일상 대화, 질문, 잡담
   - 예: "안녕", "오늘 날씨 어때?", "넌 뭘 할 수 있어?"

[응답 형식]
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.

툴 사용 시:
{"tool": "툴이름", "text": "원본 사용자 입력 그대로"}

일상 대화 시:
{"tool": "chat", "reply": "자연스러운 한국어 응답"}

[사용 가능한 앱]
디스코드, 카카오톡, 크롬, 스포티파이, 스팀, 코드(VSCode), 라이엇 클라이언트, 롤, 발로란트, 메모장, OBS, 그림판, 계산기

[사용 가능한 검색 사이트]
구글, 네이버, 유튜브, 위키, 스포티파이, 챗지피티
"""


# ---------------------------------------------------------------------------
# 대화 기록 관리
# ---------------------------------------------------------------------------
class ConversationHistory:
    """간단한 인메모리 대화 기록. 최대 N턴 유지."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._history: list[dict] = []

    def add(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        # 최대 턴 수 초과 시 오래된 것부터 제거 (system 메시지는 유지)
        while len(self._history) > self.max_turns * 2:
            self._history.pop(0)

    def get_messages(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}] + self._history

    def clear(self) -> None:
        self._history.clear()


# ---------------------------------------------------------------------------
# 메인 에이전트 클래스
# ---------------------------------------------------------------------------
class AkoAgent:
    def __init__(self, model: str = "exaone3.5:7.8b"):
        self.model = model
        self.history = ConversationHistory(max_turns=10)

    def _parse_response(self, raw: str) -> dict:
        """LLM 응답에서 JSON을 추출한다. 파싱 실패 시 chat으로 fallback."""
        # 코드블록 제거
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

        # JSON 부분만 추출 시도
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 파싱 실패 → 그냥 대화 응답으로 처리
        return {"tool": "chat", "reply": raw.strip()}

    def run(self, user_input: str) -> str:
        """
        사용자 입력을 받아 처리하고 결과 문자열을 반환한다.
        - 툴 액션이면 command_actions.py의 함수를 호출한다.
        - 일상 대화면 LLM 응답을 그대로 반환한다.
        """
        user_input = (user_input or "").strip()
        if not user_input:
            return "명령이 비어 있어요."

        # 대화 기록에 사용자 입력 추가
        self.history.add("user", user_input)

        # LLM 호출
        messages = self.history.get_messages(_TOOLS_DESC)
        raw = _ollama_chat(messages, model=self.model)

        # 응답 파싱
        parsed = self._parse_response(raw)
        tool = parsed.get("tool", "chat")

        result = self._dispatch(tool, parsed, user_input)

        # 대화 기록에 어시스턴트 응답 추가
        self.history.add("assistant", result)
        return result

    def _dispatch(self, tool: str, parsed: dict, original_text: str) -> str:
        """툴 이름에 따라 command_actions.py 함수를 호출한다."""
        try:
            from command_actions import (
                handle_open_app,
                handle_search_command,
                handle_ui_click,
                handle_youtube_toggle,
                load_app_specs,
            )
        except ImportError as e:
            return f"명령 모듈 로드 실패: {e}"

        # LLM이 원본 텍스트를 그대로 넘겨줬을 때 사용
        text = parsed.get("text", original_text)

        if tool == "open_app":
            specs = load_app_specs()
            result = handle_open_app(text, specs)
            if result:
                return result
            # LLM이 open_app으로 판단했지만 매칭 실패 → 앱 이름 직접 추출 시도
            return f"앱을 찾지 못했어요. app_commands.json에 등록된 앱인지 확인해줘요."

        elif tool == "search":
            result = handle_search_command(text)
            if result:
                return result
            return "검색어를 이해하지 못했어요."

        elif tool == "ui_click":
            result = handle_ui_click(text)
            if result:
                return result
            return "클릭할 대상을 화면에서 찾지 못했어요."

        elif tool == "youtube_toggle":
            result = handle_youtube_toggle(text)
            if result:
                return result
            # youtube_toggle은 텍스트 매칭이 엄격해서 직접 호출
            try:
                from ui_tap import youtube_toggle_click_only
                youtube_toggle_click_only(direction=None)
                return "유튜브 토글 완료"
            except Exception as e:
                return f"유튜브 토글 실패: {e}"

        elif tool == "chat":
            return parsed.get("reply", "...")

        else:
            return f"알 수 없는 툴: {tool}"

    def clear_history(self) -> None:
        self.history.clear()


# ---------------------------------------------------------------------------
# 싱글톤 — 앱 전체에서 하나의 에이전트 인스턴스 공유
# ---------------------------------------------------------------------------
_agent_instance: Optional[AkoAgent] = None


def get_agent(model: str = "exaone3.5:7.8b") -> AkoAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AkoAgent(model=model)
    return _agent_instance


def run_agent(user_input: str, model: str = "exaone3.5:7.8b") -> str:
    """외부에서 간단하게 호출할 수 있는 진입점."""
    return get_agent(model).run(user_input)
