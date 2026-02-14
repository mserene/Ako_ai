# app.py
import argparse
from typing import Optional

from command_actions import handle_open_app, handle_search_command, load_app_specs


def run_actions(text: str) -> str:
    specs = load_app_specs()

    # 1) 앱 열기/앞으로
    r = handle_open_app(text, specs)
    if r:
        return r

    # 2) 검색
    r = handle_search_command(text)
    if r:
        return r

    return "명령을 이해하지 못했어요. 예: '크롬 켜줘', '유튜브에서 ~검색해줘'"


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
            print("예: python app.py --mode=actions --text \"크롬 켜줘\"")
            return
        print(run_actions(args.text))
    else:
        print(run_ui())


if __name__ == "__main__":
    main()
