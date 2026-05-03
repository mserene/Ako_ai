from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class IntentType(str, Enum):
    CHAT = "chat"
    COMMAND = "command"
    MEMORY_UPDATE = "memory_update"
    SCREEN_STATUS = "screen_status"
    VOICE_STATUS = "voice_status"
    CAPABILITY = "capability"
    META = "meta"


@dataclass(frozen=True)
class IntentResult:
    intent: IntentType
    confidence: float = 0.5
    reason: str = ""


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _looks_like_memory_update(text: str, compact: str) -> bool:
    if not text:
        return False

    # 사용자가 의미/교정/취향을 명시적으로 알려주는 경우만 memory update로 본다.
    memory_markers = (
        "기억해", "기억해둬", "잊지마", "뜻이야", "의미야", "라고 말한건",
        "라고 말하는건", "라고 부르는건", "이라고 말한건", "이라고 부르는건",
        "다음부터", "앞으로", "이렇게 이해해", "이렇게 받아들여",
    )
    if _has_any(text, memory_markers):
        return True

    # 나는 ~ 좋아해/싫어해 같은 취향
    if re.search(r"나는\s+.+?(좋아해|싫어해|선호해|별로야|불편해)$", text):
        return True

    return False


def _looks_like_screen_status(text: str, compact: str) -> bool:
    screen_words = ("화면", "스크린", "모니터", "창", "ocr", "인식")
    status_words = ("보여", "볼수", "볼 수", "인식", "가능", "켜져", "상태", "보고있", "보고 있")
    return _has_any(text, screen_words) and _has_any(text, status_words)


def _looks_like_voice_status(text: str, compact: str) -> bool:
    voice_words = ("마이크", "음성", "목소리", "듣고", "듣는", "stt", "녹음")
    status_words = ("가능", "켜져", "상태", "듣고있", "듣고 있", "인식", "되냐", "돼")
    return _has_any(text, voice_words) and _has_any(text, status_words)


def _looks_like_capability(text: str, compact: str) -> bool:
    capability_words = ("뭐할수", "뭐 할 수", "할수있", "할 수 있", "기능", "가능한", "할줄", "할 줄")
    if _has_any(compact, tuple(w.replace(" ", "") for w in capability_words)):
        return True
    return _has_any(text, capability_words)


def _looks_like_real_command(text: str, compact: str) -> bool:
    """앱/화면 조작으로 넘겨도 되는 문장인지 판단한다.

    원칙:
    - '해봐', '말해봐', '불러봐' 같은 대화 요청은 command가 아니다.
    - 실제 앱/화면/버튼/검색/입력/창 조작이 명확할 때만 command.
    """

    # 대화 요청으로 봐야 하는 표현
    chat_like = (
        "말해봐", "불러봐", "따라해", "따라 해", "주인님 해봐", "대답해봐",
        "생각해봐", "설명해봐", "어떻게 생각", "뭐라고 생각",
    )
    if _has_any(text, chat_like):
        return False

    # 명확한 조작 대상
    app_targets = (
        "크롬", "chrome", "유튜브", "youtube", "디스코드", "discord", "카카오톡",
        "메모장", "계산기", "스포티파이", "spotify", "치지직", "브라우저",
        "탐색기", "파일", "폴더", "창", "탭", "버튼", "링크", "주소창",
    )
    action_words = (
        "열어", "켜줘", "켜", "꺼줘", "꺼", "실행", "재생", "일시정지",
        "눌러", "클릭", "닫아", "입력", "검색", "삭제", "가줘", "이동",
        "앞으로", "포커스", "띄워", "최소화", "최대화",
    )

    if _has_any(text, app_targets) and _has_any(text, action_words):
        return True

    # 위치 + 클릭/누르기 계열은 화면 조작으로 본다.
    positions = ("왼쪽", "오른쪽", "위", "아래", "중앙", "가운데", "상단", "하단")
    if _has_any(text, positions) and _has_any(text, ("눌러", "클릭", "터치")):
        return True

    # 검색은 검색어가 있는 경우 command로 봐도 됨.
    if "검색" in text and len(text) >= 4:
        return True

    return False


def classify_intent(text: str) -> IntentResult:
    raw = (text or "").strip()
    compact = _compact(raw)

    if not raw:
        return IntentResult(IntentType.CHAT, 0.1, "empty")

    if _looks_like_memory_update(raw, compact):
        return IntentResult(IntentType.MEMORY_UPDATE, 0.95, "explicit memory/correction marker")

    if _looks_like_screen_status(raw, compact):
        return IntentResult(IntentType.SCREEN_STATUS, 0.88, "screen status/capability question")

    if _looks_like_voice_status(raw, compact):
        return IntentResult(IntentType.VOICE_STATUS, 0.88, "voice status/capability question")

    if _looks_like_capability(raw, compact):
        return IntentResult(IntentType.CAPABILITY, 0.78, "capability question")

    if _looks_like_real_command(raw, compact):
        return IntentResult(IntentType.COMMAND, 0.86, "clear app/screen action command")

    return IntentResult(IntentType.CHAT, 0.65, "default chat")
