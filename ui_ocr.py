from __future__ import annotations
from typing import List
import numpy as np

def ocr_lines(bgra: np.ndarray, lang: str = "ko") -> List[str]:
    """Windows OCR(WinRT)로 텍스트 라인 리스트 반환."""
    try:
        import asyncio
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import (
            SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
        )
    except Exception as e:
        raise RuntimeError(
            "Windows OCR(winrt) 패키지가 없어요. 개발 환경에서는 아래 설치 후 다시 실행해줘요.\n"
            "pip install winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging\n"
        ) from e

    def to_software_bitmap(bgra_img: np.ndarray) -> "SoftwareBitmap":
        h, w, _ = bgra_img.shape
        sb = SoftwareBitmap(BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED)
        sb.copy_from_buffer(bgra_img.tobytes())
        return sb

    async def _run():
        engine = OcrEngine.try_create_from_language(Language(lang))
        sb = to_software_bitmap(bgra)
        res = await engine.recognize_async(sb)
        return [line.text for line in res.lines]

    return asyncio.run(_run())
