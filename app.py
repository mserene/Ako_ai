# app.py
# 통합 엔트리: ako_ai
from __future__ import annotations

import argparse
import os
import sys

# 배포( PyInstaller one-folder )에서 상대경로가 항상 exe 폴더 기준이 되도록 고정
def _set_workdir_to_appdir() -> str:
    try:
        app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
    except Exception:
        app_dir = os.getcwd()
    if app_dir and os.path.isdir(app_dir):
        os.chdir(app_dir)
    return app_dir

_APP_DIR = _set_workdir_to_appdir()
import re

def _try_youtube_toggle_command(text: str) -> str | None:
    """actions 모드에서 '유튜브 재생 눌러줘', '유튜브 일시정지 눌러줘' 등을 처리.
    - 아이콘 템플릿 없이 플레이어 영역 클릭 + k 백업으로 토글
    """
    s = (text or "").strip()
    if not s:
        return None

    # 유튜브 관련 키워드 + 재생/일시정지/멈춤/정지/토글
    if "유튜브" not in s:
        return None

    # 방향(선택)
    dir_pat = r"(왼쪽\s*위|오른쪽\s*위|왼쪽\s*아래|오른쪽\s*아래|왼쪽|오른쪽|위|아래|좌상|우상|좌하|우하)"
    dm = re.search(dir_pat, s)
    direction = dm.group(0) if dm else None

    # 재생/일시정지 의도
    if re.search(r"(재생|일시\s*정지|일시정지|멈춰|정지|토글)", s) and re.search(r"(눌러\s*줘|눌러줘|해\s*줘|해줘|해\s*줄래|해줄래)", s):
        from ui_tap import youtube_toggle_click_only as tap_youtube_toggle
        tap_youtube_toggle(direction=direction)
        return "유튜브 토글 완료"
    return None


def _try_ui_click_command(text: str) -> str | None:
    """
    actions 모드에서도 '닫기 눌러줘', '오른쪽 위에 있는 닫기 눌러줘' 같은 문장을 처리.
    실패하면 None.
    """
    s = (text or "").strip()
    if not s:
        return None

    # 방향 키워드(공백 포함 허용)
    dir_pat = r"(왼쪽\s*위|오른쪽\s*위|왼쪽\s*아래|오른쪽\s*아래|왼쪽|오른쪽|위|아래|좌상|우상|좌하|우하)"
    # 버튼/대상 텍스트 (가능하면 짧게 잡기)
    # 예: "오른쪽에 있는 닫기 눌러줘" / "닫기 클릭해줘"
    m = re.search(rf"(?:(?P<dir>{dir_pat})\s*(?:에\s*있는|쪽|쪽에\s*있는)?\s*)?(?P<label>.+?)\s*(?:버튼)?\s*(?:눌러\s*줘|눌러줘|클릭\s*해\s*줘|클릭해줘)$", s)
    if not m:
        return None

    direction = m.group("dir")
    label = m.group("label").strip().strip('"').strip("'")
    if not label:
        return None

    from ui_do import do_click_text

    ok = do_click_text(target_text=label, direction=direction or None, monitor_index=1)
    return f"'{label}' 클릭 완료" if ok else f"'{label}'를 화면에서 찾지 못했어요."



def run_actions(text: str) -> str:
    # 0) 유튜브 토글(재생/일시정지) 명령 우선 처리
    yt_r = _try_youtube_toggle_command(text)
    if yt_r:
        return yt_r

    # 1) UI 클릭형 명령(예: '닫기 눌러줘') 우선 처리
    ui_r = _try_ui_click_command(text)
    if ui_r:
        return ui_r

    # 기존 앱 실행/검색 로직을 그대로 사용
    from command_actions import handle_open_app, handle_search_command, load_app_specs

    specs = load_app_specs()  # app_commands.json (exe 옆) 로드
    r = handle_open_app(text, specs)
    if r:
        return r

    r = handle_search_command(text)
    if r:
        return r

    return "명령을 이해하지 못했어요. 예: '크롬 켜줘', '디스코드 앞으로', '유튜브에 고양이 검색해줘'"


def run_ui() -> str:
    from ui_loop import ui_mvp_loop
    ui_mvp_loop()
    return "UI 루프 종료"


def run_do(press: str = "", direction: str = "", timeout_sec: float = 8.0, tap: str = "") -> str:
    if tap:
        from ui_tap import tap_youtube_toggle
        if tap in ("youtube", "youtube_toggle", "yt"):
            tap_youtube_toggle(direction=(direction or None), backup_k=True)
            return "[DO] ok"
        return "[DO] fail"

    from ui_do import do_click_text
    ok = do_click_text(target_text=press, direction=(direction or None), monitor_index=1, timeout_sec=timeout_sec)
    return "[DO] ok" if ok else "[DO] fail"


def main():
    p = argparse.ArgumentParser(prog="ako_ai")
    p.add_argument("--mode", choices=["actions", "ui", "do"], default="actions")
    p.add_argument("--text", default="", help="actions 모드에서 사용할 텍스트 명령")
    p.add_argument("--press", default="", help="do 모드: 클릭할 텍스트 (예: 닫기/취소/확인)")
    p.add_argument("--tap", default="", help="do 모드: 탭/토글 액션 (예: youtube_toggle)")
    p.add_argument("--dir", default="", help="do 모드: 방향(예: 왼쪽/오른쪽/위/아래/왼쪽위/오른쪽아래)")
    p.add_argument("--timeout", type=float, default=8.0, help="do 모드: 찾기 제한 시간(초)")
    args = p.parse_args()

    
    if args.mode == "actions":
        if not args.text.strip():
            print('예: python app.py --mode=actions --text "크롬 켜줘"')
            print('예: python app.py --mode=actions --text "오른쪽에 있는 닫기 눌러줘"')
            print('예: python app.py --mode=actions --text "유튜브 재생 눌러줘"')
            return
        print(run_actions(args.text))

    elif args.mode == "do":
        if not args.press.strip() and not args.tap.strip():
            print('예: python app.py --mode=do --press "닫기"')
            print('예: python app.py --mode=do --press "닫기" --dir "왼쪽"')
            print('예: python app.py --mode=do --tap "youtube_toggle"')
            return
        print(run_do(args.press, direction=args.dir, timeout_sec=args.timeout, tap=args.tap))

    else:
        print(run_ui())



if __name__ == "__main__":
    main()