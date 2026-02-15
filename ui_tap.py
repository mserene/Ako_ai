# ui_tap.py
from __future__ import annotations
from typing import Optional, Tuple
import pyautogui as pag

# NOTE:
# - Click-only implementation (no 'k' fallback) to avoid double-toggle.
# - Designed to work in both YouTube fullscreen and windowed layouts assuming player is visible.

def _dir_offset(direction: Optional[str], w: int, h: int) -> Tuple[int, int]:
    '''
    방향에 따라 클릭 지점을 살짝 이동.
    w,h 는 기준이 되는 화면 크기(주 모니터 기준).
    '''
    if not direction:
        return (0, 0)
    d = direction.replace(" ", "")
    aliases = {
        "좌": "left", "왼쪽": "left",
        "우": "right", "오른쪽": "right",
        "위": "up", "상": "up",
        "아래": "down", "하": "down",
        "왼쪽위": "upleft", "좌상": "upleft", "좌상단": "upleft",
        "오른쪽위": "upright", "우상": "upright", "우상단": "upright",
        "왼쪽아래": "downleft", "좌하": "downleft", "좌하단": "downleft",
        "오른쪽아래": "downright", "우하": "downright", "우하단": "downright",
    }
    key = aliases.get(d, d)

    dx = int(w * 0.12)
    dy = int(h * 0.08)

    if key == "left": return (-dx, 0)
    if key == "right": return (dx, 0)
    if key == "up": return (0, -dy)
    if key == "down": return (0, dy)
    if key == "upleft": return (-dx, -dy)
    if key == "upright": return (dx, -dy)
    if key == "downleft": return (-dx, dy)
    if key == "downright": return (dx, dy)
    return (0, 0)

def youtube_toggle_click_only(direction: Optional[str] = None, move_duration: float = 0.05) -> None:
    '''
    유튜브 재생/일시정지 토글: 클릭 1회만 수행 (K 백업 없음)

    - 기본 클릭 지점: 화면 기준 (0.50w, 0.40h)
    - direction이 있으면 그 방향으로 살짝 이동
    '''
    w, h = pag.size()

    x = int(w * 0.50)
    y = int(h * 0.40)

    ox, oy = _dir_offset(direction, w, h)
    x += ox
    y += oy

    pag.moveTo(x, y, duration=move_duration)
    pag.click()
