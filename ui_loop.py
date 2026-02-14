# ui_loop.py
from __future__ import annotations
import time
import hashlib
import numpy as np
import pyautogui as pag

from ui_capture import grab_screen
from ui_ocr import ocr_lines
from ui_policy import decide_action

def screen_fingerprint(bgra: np.ndarray) -> str:
    """
    화면이 '같은지' 판단하기 위한 가벼운 지문.
    너무 정밀할 필요 없어서 다운샘플로 빠르게 만듭니다.
    """
    # BGRA -> BGR 일부만 샘플링
    small = bgra[::20, ::20, :3]  # 빠른 샘플링
    return hashlib.md5(small.tobytes()).hexdigest()

def crop_regions(bgra: np.ndarray):
    """
    버튼이 있을 법한 영역만 OCR 대상으로 사용.
    - 중앙 팝업 영역(대화상자)
    - 우하단 영역(확인/취소/다음 버튼이 자주 있음)
    """
    h, w = bgra.shape[0], bgra.shape[1]

    # 중앙 팝업: 화면 가운데 큰 박스
    center = bgra[int(h*0.22):int(h*0.88), int(w*0.18):int(w*0.82), :]

    # 우하단: 버튼들이 몰리는 곳 (유튜브 자막(하단 중앙) 회피에 도움)
    br = bgra[int(h*0.55):int(h*0.98), int(w*0.55):int(w*0.98), :]

    return [center, br]

def ui_mvp_loop(monitor_index: int = 1, interval_sec: float = 0.8):
    """
    MVP 루프:
    - 화면 캡처
    - (중앙/우하단) OCR
    - policy에서 '정말로 눌러도 되는지' 결정
    - 같은 화면에서 같은 행동 반복 금지
    """
    print("[UI] MVP loop 시작 (Ctrl+C로 종료)")

    acted = set()  # (fingerprint, target_word)
    last_fp = None
    stable_count = 0

    while True:
        bgra = grab_screen(monitor_index)
        fp = screen_fingerprint(bgra)

        # 화면이 바뀌면(지문이 바뀌면) 반복 차단 기록 일부를 리셋
        if fp == last_fp:
            stable_count += 1
        else:
            stable_count = 0
            last_fp = fp
            # 화면 전환 시 과거 기록을 너무 오래 들고 있으면 못 누를 수 있어,
            # 최소한만 유지하고 정리합니다.
            # (화면 전환이 일어났다면 이전 화면의 acted는 의미가 줄어듦)
            acted = set()

        # OCR은 버튼 있을 법한 ROI만 수행
        lines_all = []
        for crop in crop_regions(bgra):
            try:
                lines_all.extend(ocr_lines(crop, lang="kor+eng"))
            except Exception as e:
                # OCR 실패해도 루프는 계속
                print(f"[UI] OCR error: {e}")
                lines_all = []
                break

        target, key, reason = decide_action(lines_all)

        if not target:
            # 너무 스팸이면 interval 조절하거나 여기 출력 줄여도 됨
            print(f"[UI] 버튼 단어 미감지 / skip ({reason})")
            time.sleep(interval_sec)
            continue

        # 같은 화면에서 같은 행동 반복 차단
        act_key = (fp, target)
        if act_key in acted:
            print(f"[UI] '{target}' 감지(같은 화면 재실행 차단) → skip")
            time.sleep(interval_sec)
            continue

        # 실행
        try:
            pag.press(key)
            acted.add(act_key)
            print(f"[UI] '{target}' 감지 → key={key} ({reason})")
        except Exception as e:
            print(f"[UI] key press 실패: {e}")

        time.sleep(interval_sec)
