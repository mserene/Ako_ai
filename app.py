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


def run_actions(text: str) -> str:
    # 기존 앱 실행/검색 로직을 그대로 사용
    from command_actions import handle_open_app, handle_search_command, load_app_specs

    specs = load_app_specs()  # app_commands.json (exe 옆) 로드
    r = handle_open_app(text, specs)
    if r:
        return r

    r = handle_search_command(text)
    if r:
        return r

    return "명령을 이해하지 못했어요. 예: '크롬 켜줘', '디스코드 앞으로', '유튜브에서 고양이 검색해줘'"


def run_ui() -> str:
    from ui_loop import ui_mvp_loop
    ui_mvp_loop()
    return "UI 루프 종료"


def main():
    p = argparse.ArgumentParser(prog="ako_ai")
    p.add_argument("--mode", choices=["actions", "ui"], default="actions")
    p.add_argument("--text", default="", help="actions 모드에서 사용할 텍스트 명령")
    args = p.parse_args()

    if args.mode == "actions":
        if not args.text.strip():
            print('예: python app.py --mode=actions --text "크롬 켜줘"')
            print('    또는: python app.py --mode=actions --text "크롬 켜줘"')
            return
        print(run_actions(args.text))
    else:
        print(run_ui())


if __name__ == "__main__":
    main()
