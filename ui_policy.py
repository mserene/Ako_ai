# ui_policy.py (룰/키보드 우선)
from __future__ import annotations
from typing import Optional, List

BUTTON_WORDS: List[str] = ["확인", "예", "동의", "다음", "닫기", "취소", "아니오"]

# “텍스트 UI 자동화 1단계”는 클릭보다 키보드가 훨씬 안정적
KEY_FALLBACK = {
    "확인": "enter",
    "예": "enter",
    "동의": "enter",
    "다음": "enter",
    "닫기": "esc",
    "취소": "esc",
    "아니오": "esc",
}

def pick_target(lines: List[str]) -> Optional[str]:
    joined = " ".join(lines)
    for w in BUTTON_WORDS:
        if w in joined:
            return w
    return None

def key_for(target: str) -> Optional[str]:
    return KEY_FALLBACK.get(target)
