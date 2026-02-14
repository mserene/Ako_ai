# ui_policy.py
from __future__ import annotations
from typing import List, Optional, Set, Tuple
import re

# 버튼 후보 단어
BUTTON_WORDS: List[str] = ["확인", "예", "동의", "다음", "건너뛰기", "닫기", "취소", "아니오"]

# 키 매핑
KEY_FOR = {
    "확인": "enter",
    "예": "enter",
    "동의": "enter",
    "다음": "enter",
    "건너뛰기": "enter",
    "닫기": "esc",
    "취소": "esc",
    "아니오": "esc",
}

SINGLE_HIT_ALLOW = {"건너뛰기"}

# “대화상자/설치/권한/업데이트/오류” 같은 맥락 단어(이게 있어야 자동 누르도록)
DIALOG_HINT_WORDS: List[str] = [
    "설치", "업데이트", "권한", "허용", "승인", "경고", "오류", "실패",
    "저장", "종료", "닫으시겠", "취소하시겠", "정말", "계속", "라이선스", "사용권", "동의함",
    "확인하시겠", "삭제", "변경", "적용", "재시작", "다시 시작", "필요", "요청", "연결"
]

# 긍정/진행 성격 버튼
POSITIVE = {"확인", "예", "동의", "다음", "건너뛰기"}
# 부정/종료 성격 버튼
NEGATIVE = {"닫기", "취소", "아니오"}

def _normalize_text(lines: List[str]) -> Tuple[str, str]:
    joined = " ".join(lines)
    # 공백/특수문자 제거 버전도 만들어서 OCR 깨짐/띄어쓰기 대응
    compact = re.sub(r"[^0-9A-Za-z가-힣]", "", joined)
    return joined, compact

def extract_hits(lines: List[str]) -> Set[str]:
    joined, compact = _normalize_text(lines)
    hits = set()
    for w in BUTTON_WORDS:
        if (w in joined) or (w in compact):
            hits.add(w)
    return hits

def has_dialog_context(lines: List[str]) -> bool:
    joined, compact = _normalize_text(lines)
    for h in DIALOG_HINT_WORDS:
        if (h in joined) or (h in compact):
            return True
    return False

def decide_action(lines: List[str]) -> Tuple[Optional[str], Optional[str], str]:
    """
    returns: (target_word, key, reason)
    - target_word: 눌러야 할 버튼 단어
    - key: press할 키 ('enter'/'esc')
    - reason: 로그용 이유
    """
    hits = extract_hits(lines)
    if not hits:
        return None, None, "no_hits"

    # 자막/일반 텍스트 오탐 방지:
    # 1) 버튼 단어가 1개만 보이고
    # 2) 대화상자 맥락 단어도 없으면
    # -> 자동으로 누르지 않음
    ctx = has_dialog_context(lines)
    if len(hits) == 1 and not ctx:
        only = next(iter(hits))
        if only in SINGLE_HIT_ALLOW:
            return only, KEY_FOR[only], f"single_hit_allow({only})"
        return None, None, f"single_hit_no_context({only})"


    # “긍정/진행 버튼”은 설치/권한/업데이트 같은 맥락에서만 자동 수행
    # “닫기/취소”는 오류/경고/종료/닫기 질문 같은 맥락에서만 자동 수행
    joined, compact = _normalize_text(lines)

    def ctx_has_any(words: List[str]) -> bool:
        return any((w in joined) or (w in compact) for w in words)

    ctx_positive = ctx_has_any(["설치", "업데이트", "권한", "허용", "승인", "라이선스", "사용권", "동의", "계속", "다음"])
    ctx_negative = ctx_has_any(["오류", "실패", "경고", "종료", "닫으시겠", "취소하시겠", "삭제", "정말"])

    # 우선순위:
    # - 긍정/진행(동의/다음)은 ctx_positive일 때만
    # - 확인/예도 ctx_positive 또는 ctx(일반 맥락)에서만
    # - 닫기/취소는 ctx_negative일 때만 (실수로 ESC 난사 방지)
    priority = ["동의", "다음", "확인", "예", "건너뛰기", "취소", "닫기", "아니오"]
    
    for t in priority:
        if t not in hits:
            continue

        if t in POSITIVE:
            if ctx_positive or ctx:
                return t, KEY_FOR[t], f"positive_ok(ctx_positive={ctx_positive}, ctx={ctx})"
            else:
                continue

        if t in NEGATIVE:
            if ctx_negative:
                return t, KEY_FOR[t], f"negative_ok(ctx_negative={ctx_negative})"
            else:
                continue

    return None, None, "gated_skip"
