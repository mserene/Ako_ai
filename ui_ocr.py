# ui_ocr.py (Tesseract 버전)
from __future__ import annotations
from typing import List
import os
import numpy as np

from PIL import Image
import pytesseract


def _resolve_tesseract():
    """Tesseract 실행 파일과 tessdata 경로를 배포 친화적으로 찾는다.

    우선순위:
      1) 환경변수 TESSERACT_CMD
      2) 프로젝트 동봉 경로: tools/tesseract/tesseract.exe
      3) 시스템 PATH

    tessdata는 동봉 경로가 있으면 TESSDATA_PREFIX로 지정한다.
    """
    # 1) 환경변수로 강제 지정
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        pytesseract.pytesseract.tesseract_cmd = cmd
        return

    base = os.path.dirname(__file__)

    # 2) 프로젝트 동봉 경로
    local_cmd = os.path.join(base, "tools", "tesseract", "tesseract.exe")
    if os.path.exists(local_cmd):
        pytesseract.pytesseract.tesseract_cmd = local_cmd
        local_tessdata = os.path.join(base, "tools", "tesseract", "tessdata")
        if os.path.isdir(local_tessdata):
            os.environ.setdefault("TESSDATA_PREFIX", local_tessdata)
        return

    # 3) PATH에 있으면 pytesseract가 알아서 찾게 둠


def ocr_lines(bgra: np.ndarray, lang: str = "kor+eng") -> List[str]:
    """BGRA(HxWx4) -> 텍스트 라인 리스트

    lang: 한국어 UI면 "kor+eng" 추천.
    """
    _resolve_tesseract()

    # BGRA -> RGB (PIL)
    rgb = bgra[:, :, :3][:, :, ::-1]  # BGR -> RGB
    img = Image.fromarray(rgb)

    # UI 텍스트는 psm 6이 무난
    config = "--oem 1 --psm 6"
    text = pytesseract.image_to_string(img, lang=lang, config=config)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines
