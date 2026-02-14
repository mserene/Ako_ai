# ui_do.py
# "지금 화면에서 ~ 눌러줘" 같은 1회성 상호작용 실행
from __future__ import annotations

from typing import Optional, List
import time

import pyautogui as pag

from ui_capture import grab_screen
from ui_locate import find_text_boxes, pick_by_direction


def _crop_regions(bgra, mode: str = "center+br") -> List:
    """
    너무 넓게 OCR하면 느려질 수 있어서 기본은 중앙/우하단만 봅니다.
    mode:
      - "full": 전체
      - "center+br": 중앙 팝업 + 우하단
      - "bottom": 하단만
    """
    if mode == "full":
        return [bgra]

    h, w = bgra.shape[0], bgra.shape[1]
    regions = []

    if mode in ("center+br", "center"):
        center = bgra[int(h * 0.22):int(h * 0.88), int(w * 0.18):int(w * 0.82), :]
        regions.append(center)

    if mode in ("center+br", "br"):
        br = bgra[int(h * 0.55):int(h * 0.98), int(w * 0.55):int(w * 0.98), :]
        regions.append(br)

    if mode == "bottom":
        bottom = bgra[int(h * 0.65):, :, :]
        regions.append(bottom)

    return regions or [bgra]


def click_box(box, base_left: int = 0, base_top: int = 0):
    """
    box 좌표는 'crop 내부 좌표'일 수 있어서, base_left/base_top을 더해 실제 화면 좌표로 변환
    """
    x = int(base_left + box.cx)
    y = int(base_top + box.cy)
    pag.moveTo(x, y, duration=0.05)
    pag.click()


def do_click_text(
    target_text: str,
    direction: Optional[str] = None,
    monitor_index: int = 1,
    lang: str = "kor+eng",
    timeout_sec: float = 8.0,
    conf_min: float = 50.0,
    roi_mode: str = "center+br",
) -> bool:
    """
    화면에서 target_text를 찾아 "클릭" 1회 수행.
    여러 개면 direction으로 선택.
    - monitor_index는 1(메인) 고정 사용 권장.
    """
    t0 = time.time()

    while time.time() - t0 < timeout_sec:
        bgra = grab_screen(monitor_index)
        h, w = bgra.shape[0], bgra.shape[1]

        # ROI별로 탐색: 찾자마자 클릭하고 종료
        regions = _crop_regions(bgra, mode=roi_mode)

        # 각 crop의 원점 오프셋 계산 (crop을 만든 방식과 동일해야 함)
        offsets = []
        if roi_mode == "full":
            offsets = [(0, 0)]
        elif roi_mode == "bottom":
            offsets = [(0, int(h * 0.65))]
        else:
            # center + br (기본)
            offsets = [
                (int(w * 0.18), int(h * 0.22)),  # center
                (int(w * 0.55), int(h * 0.55)),  # br
            ][: len(regions)]

        all_boxes = []
        all_offsets = []
        for crop, (ox, oy) in zip(regions, offsets):
            boxes = find_text_boxes(crop, target_text, lang=lang, conf_min=conf_min)
            for b in boxes:
                all_boxes.append(b)
                all_offsets.append((ox, oy))

        if all_boxes:
            chosen = pick_by_direction(all_boxes, direction)
            # chosen의 인덱스로 offset을 함께 꺼내기
            idx = all_boxes.index(chosen)
            ox, oy = all_offsets[idx]
            click_box(chosen, base_left=ox, base_top=oy)
            return True

        time.sleep(0.25)

    return False
