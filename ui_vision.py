from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional

import mss
import numpy as np
from PIL import Image
import pytesseract


def grab_screen(monitor_index: int = 1) -> np.ndarray:
    """BGRA uint8 이미지(HxWx4) 반환. monitor_index: 1=메인 모니터."""
    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        return np.array(sct.grab(mon))


def _resolve_tesseract() -> None:
    """동봉된 Tesseract 또는 시스템 PATH의 Tesseract를 사용한다."""
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        pytesseract.pytesseract.tesseract_cmd = cmd
        return

    base = os.path.dirname(__file__)
    local_cmd = os.path.join(base, "tools", "tesseract", "tesseract.exe")
    if os.path.exists(local_cmd):
        pytesseract.pytesseract.tesseract_cmd = local_cmd
        local_tessdata = os.path.join(base, "tools", "tesseract", "tessdata")
        if os.path.isdir(local_tessdata):
            os.environ.setdefault("TESSDATA_PREFIX", local_tessdata)


def ocr_lines(bgra: np.ndarray, lang: str = "kor+eng") -> List[str]:
    """BGRA(HxWx4) 이미지를 OCR해 텍스트 라인 리스트로 반환한다."""
    _resolve_tesseract()
    rgb = bgra[:, :, :3][:, :, ::-1]
    img = Image.fromarray(rgb)
    text = pytesseract.image_to_string(img, lang=lang, config="--oem 1 --psm 6")
    return [line.strip() for line in text.splitlines() if line.strip()]


@dataclass
class Box:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def find_text_boxes(
    bgra: np.ndarray,
    target: str,
    lang: str = "kor+eng",
    conf_min: float = 50.0,
    allow_contains: bool = True,
) -> List[Box]:
    """
    target 텍스트가 포함된 OCR 박스 리스트 반환 (좌표 포함).
    - bgra: HxWx4 (mss 캡처 그대로)
    - conf_min: 낮추면 더 많이 잡히지만 오탐 증가
    """
    _resolve_tesseract()

    target_n = _norm(target)
    if not target_n:
        return []

    rgb = bgra[:, :, :3][:, :, ::-1]
    img = Image.fromarray(rgb)
    data = pytesseract.image_to_data(
        img,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config="--oem 1 --psm 6",
    )

    boxes: List[Box] = []
    count = len(data.get("text", []))
    for index in range(count):
        raw_text = (data["text"][index] or "").strip()
        if not raw_text:
            continue

        conf_raw = str(data.get("conf", ["-1"] * count)[index]).strip()
        try:
            confidence = float(conf_raw) if conf_raw != "-1" else -1.0
        except Exception:
            confidence = -1.0
        if confidence < conf_min:
            continue

        normalized_text = _norm(raw_text)
        if not normalized_text:
            continue

        matches = normalized_text == target_n or (
            allow_contains and target_n in normalized_text
        )
        if not matches:
            continue

        boxes.append(
            Box(
                text=raw_text,
                x=int(data["left"][index]),
                y=int(data["top"][index]),
                w=int(data["width"][index]),
                h=int(data["height"][index]),
                conf=confidence,
            )
        )

    return boxes


def pick_by_direction(boxes: List[Box], direction: Optional[str]) -> Optional[Box]:
    """
    boxes가 여러 개면 방향으로 하나 선택한다.
    direction 예:
      - 왼쪽/오른쪽/위/아래
      - 왼쪽위/오른쪽위/왼쪽아래/오른쪽아래
      - 좌상/우상/좌하/우하
    """
    if not boxes:
        return None

    if not direction:
        return max(boxes, key=lambda box: box.conf)

    aliases = {
        "좌": "left",
        "왼쪽": "left",
        "우": "right",
        "오른쪽": "right",
        "상": "up",
        "위": "up",
        "하": "down",
        "아래": "down",
        "좌상": "upleft",
        "좌상단": "upleft",
        "왼쪽위": "upleft",
        "우상": "upright",
        "우상단": "upright",
        "오른쪽위": "upright",
        "좌하": "downleft",
        "좌하단": "downleft",
        "왼쪽아래": "downleft",
        "우하": "downright",
        "우하단": "downright",
        "오른쪽아래": "downright",
    }
    key = aliases.get(direction.replace(" ", ""), direction)

    if key == "left":
        return min(boxes, key=lambda box: box.cx)
    if key == "right":
        return max(boxes, key=lambda box: box.cx)
    if key == "up":
        return min(boxes, key=lambda box: box.cy)
    if key == "down":
        return max(boxes, key=lambda box: box.cy)
    if key == "upleft":
        return min(boxes, key=lambda box: box.cx + box.cy)
    if key == "upright":
        return min(boxes, key=lambda box: (-box.cx) + box.cy)
    if key == "downleft":
        return min(boxes, key=lambda box: box.cx - box.cy)
    if key == "downright":
        return min(boxes, key=lambda box: (-box.cx) - box.cy)

    return max(boxes, key=lambda box: box.conf)
