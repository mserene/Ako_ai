# ui_loop.py
from __future__ import annotations

import hashlib
import logging
import time
import re
from typing import List, Optional, Set, Tuple

import numpy as np
import pyautogui as pag

from ui_vision import grab_screen, ocr_lines

logger = logging.getLogger(__name__)

BUTTON_WORDS: List[str] = ["확인", "예", "동의", "다음", "건너뛰기", "닫기", "취소", "아니오"]

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

DIALOG_HINT_WORDS: List[str] = [
    "설치",
    "업데이트",
    "권한",
    "허용",
    "승인",
    "경고",
    "오류",
    "실패",
    "저장",
    "종료",
    "닫으시겠",
    "취소하시겠",
    "정말",
    "계속",
    "라이선스",
    "사용권",
    "동의함",
    "확인하시겠",
    "삭제",
    "변경",
    "적용",
    "재시작",
    "다시 시작",
    "필요",
    "요청",
    "연결",
]

POSITIVE = {"확인", "예", "동의", "다음", "건너뛰기"}
NEGATIVE = {"닫기", "취소", "아니오"}


def _normalize_text(lines: List[str]) -> Tuple[str, str]:
    joined = " ".join(lines)
    compact = re.sub(r"[^0-9A-Za-z가-힣]", "", joined)
    return joined, compact


def extract_hits(lines: List[str]) -> Set[str]:
    joined, compact = _normalize_text(lines)
    hits = set()
    for word in BUTTON_WORDS:
        if word in joined or word in compact:
            hits.add(word)
    return hits


def has_dialog_context(lines: List[str]) -> bool:
    joined, compact = _normalize_text(lines)
    return any(word in joined or word in compact for word in DIALOG_HINT_WORDS)


def decide_action(lines: List[str]) -> Tuple[Optional[str], Optional[str], str]:
    hits = extract_hits(lines)
    if not hits:
        return None, None, "no_hits"

    context_exists = has_dialog_context(lines)
    if len(hits) == 1 and not context_exists:
        only = next(iter(hits))
        if only in SINGLE_HIT_ALLOW:
            return only, KEY_FOR[only], f"single_hit_allow({only})"
        return None, None, f"single_hit_no_context({only})"

    joined, compact = _normalize_text(lines)

    def ctx_has_any(words: List[str]) -> bool:
        return any(word in joined or word in compact for word in words)

    positive_context = ctx_has_any(
        ["설치", "업데이트", "권한", "허용", "승인", "라이선스", "사용권", "동의", "계속", "다음"]
    )
    negative_context = ctx_has_any(["오류", "실패", "경고", "종료", "닫으시겠", "취소하시겠", "삭제", "정말"])

    priority = ["동의", "다음", "확인", "예", "건너뛰기", "취소", "닫기", "아니오"]
    for target in priority:
        if target not in hits:
            continue

        if target in POSITIVE:
            if positive_context or context_exists:
                return target, KEY_FOR[target], f"positive_ok(ctx_positive={positive_context}, ctx={context_exists})"
            continue

        if target in NEGATIVE:
            if negative_context:
                return target, KEY_FOR[target], f"negative_ok(ctx_negative={negative_context})"
            continue

    return None, None, "gated_skip"


def screen_fingerprint(bgra: np.ndarray) -> str:
    """화면 변화 감지용 경량 해시."""
    try:
        small = bgra[::20, ::20, :3]
        return hashlib.md5(small.tobytes()).hexdigest()
    except Exception as e:
        logger.warning(f"fingerprint 생성 실패: {e}")
        return ""


def crop_regions(bgra: np.ndarray):
    """버튼이 있을 법한 영역만 OCR 대상으로 잘라냄."""
    h, w = bgra.shape[0], bgra.shape[1]
    center = bgra[int(h * 0.22):int(h * 0.88), int(w * 0.18):int(w * 0.82), :]
    br = bgra[int(h * 0.55):int(h * 0.98), int(w * 0.55):int(w * 0.98), :]
    return [center, br]


def ui_mvp_loop(monitor_index: int = 1, interval_sec: float = 0.8):
    """
    MVP 루프:
    - 화면 캡처 → OCR → policy 판단 → 클릭
    - 같은 화면에서 같은 버튼 반복 클릭 방지
    - 에러 발생 시 루프 중단 없이 계속 진행
    """
    logger.info("[UI] MVP loop 시작 (Ctrl+C로 종료)")
    print("[UI] MVP loop 시작 (Ctrl+C로 종료)")

    acted: set = set()
    last_fp = ""
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 10

    while True:
        # 연속 오류가 너무 많으면 잠시 쉬고 카운터 리셋
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.warning(f"[UI] 연속 오류 {consecutive_errors}회 → 3초 대기 후 재시도")
            time.sleep(3.0)
            consecutive_errors = 0

        # 화면 캡처
        try:
            bgra = grab_screen(monitor_index)
        except Exception as e:
            logger.error(f"[UI] 화면 캡처 실패: {e}")
            consecutive_errors += 1
            time.sleep(interval_sec)
            continue

        # 지문 계산
        fp = screen_fingerprint(bgra)
        if fp != last_fp:
            last_fp = fp
            acted = set()  # 화면이 바뀌면 반복 차단 초기화

        # OCR
        lines_all = []
        ocr_failed = False
        for crop in crop_regions(bgra):
            try:
                lines_all.extend(ocr_lines(crop, lang="kor+eng"))
            except Exception as e:
                logger.warning(f"[UI] OCR 실패: {e}")
                ocr_failed = True
                break

        if ocr_failed:
            consecutive_errors += 1
            time.sleep(interval_sec)
            continue

        consecutive_errors = 0  # 성공 시 카운터 리셋

        # 정책 판단
        try:
            target, key, reason = decide_action(lines_all)
        except Exception as e:
            logger.error(f"[UI] decide_action 오류: {e}")
            time.sleep(interval_sec)
            continue

        if not target:
            logger.debug(f"[UI] 버튼 미감지: {reason}")
            time.sleep(interval_sec)
            continue

        # 같은 화면에서 같은 버튼 반복 차단
        act_key = (fp, target)
        if act_key in acted:
            logger.debug(f"[UI] '{target}' 중복 차단")
            time.sleep(interval_sec)
            continue

        # 실행
        try:
            pag.press(key)
            acted.add(act_key)
            msg = f"[UI] '{target}' 감지 → key={key} ({reason})"
            logger.info(msg)
            print(msg)
        except Exception as e:
            logger.error(f"[UI] key press 실패 (key={key}): {e}")

        time.sleep(interval_sec)
