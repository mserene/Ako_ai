# ui_do.py
# "지금 화면에서 ~ 눌러줘" 같은 1회성 상호작용 실행
from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

import pyautogui as pag

from ui_vision import find_text_boxes, grab_screen, pick_by_direction

logger = logging.getLogger(__name__)


def _crop_regions(bgra, mode: str = "center+br") -> Tuple[List, List[Tuple[int, int]]]:
    """
    OCR 대상 영역을 잘라서 반환. (crop 리스트, 각 crop의 화면 원점 오프셋 리스트)

    mode:
      - "full"      : 전체 화면
      - "center+br" : 중앙 팝업 + 우하단 (기본)
      - "bottom"    : 하단만
    """
    h, w = bgra.shape[0], bgra.shape[1]

    if mode == "full":
        return [bgra], [(0, 0)]

    if mode == "bottom":
        bottom = bgra[int(h * 0.65):, :, :]
        return [bottom], [(0, int(h * 0.65))]

    # center + br (기본)
    center = bgra[int(h * 0.22):int(h * 0.88), int(w * 0.18):int(w * 0.82), :]
    br = bgra[int(h * 0.55):int(h * 0.98), int(w * 0.55):int(w * 0.98), :]
    offsets = [
        (int(w * 0.18), int(h * 0.22)),
        (int(w * 0.55), int(h * 0.55)),
    ]
    return [center, br], offsets


def click_box(box, base_left: int = 0, base_top: int = 0):
    """
    box 좌표(crop 내부 좌표)를 실제 화면 좌표로 변환해서 클릭.
    """
    x = int(base_left + box.cx)
    y = int(base_top + box.cy)
    try:
        pag.moveTo(x, y, duration=0.05)
        pag.click()
        logger.debug(f"클릭: ({x}, {y}) '{box.text}'")
    except Exception as e:
        logger.warning(f"클릭 실패 ({x}, {y}): {e}")
        raise


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
    화면에서 target_text를 찾아 클릭 1회 수행.
    여러 개 발견 시 direction으로 선택.

    반환: 성공 여부
    """
    if not target_text or not target_text.strip():
        logger.warning("do_click_text: target_text가 비어 있음")
        return False

    t0 = time.time()
    attempt = 0

    while time.time() - t0 < timeout_sec:
        attempt += 1
        try:
            bgra = grab_screen(monitor_index)
        except Exception as e:
            logger.error(f"화면 캡처 실패: {e}")
            time.sleep(0.5)
            continue

        try:
            regions, offsets = _crop_regions(bgra, mode=roi_mode)
        except Exception as e:
            logger.error(f"crop 실패: {e}")
            time.sleep(0.5)
            continue

        all_boxes = []
        all_offsets = []

        for crop, (ox, oy) in zip(regions, offsets):
            try:
                boxes = find_text_boxes(crop, target_text, lang=lang, conf_min=conf_min)
                for b in boxes:
                    all_boxes.append(b)
                    all_offsets.append((ox, oy))
            except Exception as e:
                logger.warning(f"OCR 실패 (offset={ox},{oy}): {e}")
                continue

        if all_boxes:
            chosen = pick_by_direction(all_boxes, direction)
            if chosen is None:
                logger.warning("pick_by_direction이 None 반환")
                time.sleep(0.25)
                continue

            idx = all_boxes.index(chosen)
            ox, oy = all_offsets[idx]

            try:
                click_box(chosen, base_left=ox, base_top=oy)
                return True
            except Exception as e:
                logger.error(f"클릭 실행 실패: {e}")
                return False

        logger.debug(f"[{attempt}] '{target_text}' 미발견, 재시도...")
        time.sleep(0.25)

    logger.info(f"do_click_text: '{target_text}' {timeout_sec}초 내 미발견")
    return False
