# ui_locate.py
# 화면에서 "텍스트 버튼"을 좌표까지 찾아내기(Tesseract image_to_data 기반)
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import re

import numpy as np
from PIL import Image
import pytesseract

# ui_ocr의 tesseract 경로 해석(동봉된 tools\tesseract\tesseract.exe 우선)
try:
    from ui_ocr import _resolve_tesseract as _resolve_tesseract_cmd  # type: ignore
except Exception:
    _resolve_tesseract_cmd = None


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


def _norm(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    return s


def find_text_boxes(
    bgra: np.ndarray,
    target: str,
    lang: str = "kor+eng",
    conf_min: float = 50.0,
    allow_contains: bool = True,
) -> List[Box]:
    """
    target 텍스트가 포함된 OCR 박스 리스트 반환 (좌표 포함)
    - bgra: HxWx4 (mss 캡처 그대로)
    - conf_min: 낮추면 더 많이 잡히지만 오탐 증가
    """
    if _resolve_tesseract_cmd:
        _resolve_tesseract_cmd()

    target_n = _norm(target)
    if not target_n:
        return []

    # BGRA -> RGB
    rgb = bgra[:, :, :3][:, :, ::-1]
    img = Image.fromarray(rgb)

    data = pytesseract.image_to_data(
        img,
        lang=lang,
        output_type=pytesseract.Output.DICT,
        config="--oem 1 --psm 6",
    )

    boxes: List[Box] = []
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue

        conf_raw = str(data.get("conf", ["-1"] * n)[i]).strip()
        try:
            conf = float(conf_raw) if conf_raw != "-1" else -1.0
        except Exception:
            conf = -1.0
        if conf < conf_min:
            continue

        txt_n = _norm(txt)
        if not txt_n:
            continue

        match = (txt_n == target_n) or (allow_contains and (target_n in txt_n))
        if not match:
            continue

        boxes.append(
            Box(
                text=txt,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                w=int(data["width"][i]),
                h=int(data["height"][i]),
                conf=conf,
            )
        )

    return boxes


def pick_by_direction(boxes: List[Box], direction: Optional[str]) -> Optional[Box]:
    """
    boxes가 여러 개면 방향으로 하나 선택.
    direction 예:
      - 왼쪽/오른쪽/위/아래
      - 왼쪽위/오른쪽위/왼쪽아래/오른쪽아래
      - 좌상/우상/좌하/우하(별칭)
    """
    if not boxes:
        return None

    if not direction:
        # 기본: 신뢰도 가장 높은 것
        return sorted(boxes, key=lambda b: b.conf, reverse=True)[0]

    d = direction.replace(" ", "")
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
    key = aliases.get(d, d)

    if key == "left":
        return min(boxes, key=lambda b: b.cx)
    if key == "right":
        return max(boxes, key=lambda b: b.cx)
    if key == "up":
        return min(boxes, key=lambda b: b.cy)
    if key == "down":
        return max(boxes, key=lambda b: b.cy)
    if key == "upleft":
        return min(boxes, key=lambda b: (b.cx + b.cy))
    if key == "upright":
        return min(boxes, key=lambda b: ((-b.cx) + b.cy))
    if key == "downleft":
        return min(boxes, key=lambda b: (b.cx + (-b.cy)))
    if key == "downright":
        return min(boxes, key=lambda b: ((-b.cx) + (-b.cy)))

    return sorted(boxes, key=lambda b: b.conf, reverse=True)[0]
