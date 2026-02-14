# ui_capture.py (화면 캡처 모듈)
import mss
import numpy as np

def grab_screen(monitor_index: int = 1) -> np.ndarray:
    """
    BGRA uint8 이미지(HxWx4) 반환
    monitor_index: 1=메인 모니터
    """
    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        img = np.array(sct.grab(mon))  # BGRA
        return img
