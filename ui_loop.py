from __future__ import annotations
import time
import pyautogui as pag

from ui_capture import grab_screen
from ui_ocr import ocr_lines
from ui_policy import pick_target, key_for

def ui_mvp_loop(monitor_index: int = 1, interval_sec: float = 0.8):
    """
    MVP: 화면 OCR로 '확인/취소/닫기/다음/동의' 같은 단어가 보이면
    키보드(Enter/Esc)로 먼저 처리하는 루프.
    """
    print("[UI] MVP loop 시작 (Ctrl+C로 종료)")
    while True:
        bgra = grab_screen(monitor_index)
        lines = ocr_lines(bgra, lang="ko")

        target = pick_target(lines)
        if target:
            k = key_for(target)
            if k:
                pag.press(k)
                print(f"[UI] '{target}' 감지 → key={k}")
            else:
                print(f"[UI] '{target}' 감지(키 룰 없음)")
        # 너무 시끄러우면 아래 줄을 주석 처리해도 됨
        # else:
        #     print("[UI] 버튼 단어 미감지")

        time.sleep(interval_sec)
