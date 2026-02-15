# ui_tap.py
from __future__ import annotations

from typing import Optional
import time
import pyautogui as pag


def _dir_offsets(direction: Optional[str], w: int, h: int) -> tuple[int, int]:
    if not direction:
        return (0, 0)
    d = direction.replace(" ", "")
    # aliases
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

    dx = 0
    dy = 0

    # 플레이어 클릭은 중앙이 기본, 좌우는 조금 크게, 상하는 조금 작게 움직이기
    step_x = int(w * 0.15)
    step_y = int(h * 0.10)

    if key in ("left", "upleft", "downleft"):
        dx -= step_x
    if key in ("right", "upright", "downright"):
        dx += step_x
    if key in ("up", "upleft", "upright"):
        dy -= step_y
    if key in ("down", "downleft", "downright"):
        dy += step_y

    return dx, dy


def tap_youtube_toggle(direction: Optional[str] = None, backup_k: bool = True) -> bool:
    """유튜브 재생/일시정지 토글.
    - 전체화면: 화면 중앙 클릭이면 거의 항상 토글
    - 창모드: 플레이어가 보이는 상태라면 화면 (0.50w, 0.40h) 근처가 플레이어에 걸릴 확률이 높음

    direction: 왼쪽/오른쪽/위/아래/왼쪽위... (중복 오탐 줄이기용 클릭 지점 이동)
    backup_k: 클릭 후 k 키를 눌러 토글을 한 번 더 시도(포커스가 플레이어에 있을 때만 동작)
    """
    w, h = pag.size()
    base_x = int(w * 0.50)
    base_y = int(h * 0.40)

    dx, dy = _dir_offsets(direction, w, h)
    x = max(10, min(w - 10, base_x + dx))
    y = max(10, min(h - 10, base_y + dy))

    pag.moveTo(x, y, duration=0.05)
    pag.click()

    # 클릭 직후 아주 잠깐 대기 (포커스/오버레이 반응)
    time.sleep(0.10)

    if backup_k:
        # 유튜브 단축키: K (재생/일시정지)
        # 포커스가 플레이어에 있다면 확실하게 토글됨.
        pag.press("k")

    return True
