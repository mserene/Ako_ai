from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PATCH_DIR = ROOT / "_patch_files"


def backup_file(path: Path) -> None:
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[BACKUP] {path.name} -> {backup.name}")


def copy_patch_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        backup_file(dst)
    shutil.copy2(src, dst)
    print(f"[OK] {dst.relative_to(ROOT)} 생성/교체")


def ensure_dirs() -> None:
    (ROOT / "assets" / "loading" / "frames").mkdir(parents=True, exist_ok=True)
    print("[OK] assets/loading/frames 폴더 확인")


def patch_loading_overlay() -> None:
    copy_patch_file(PATCH_DIR / "loading_overlay.py", ROOT / "loading_overlay.py")


def patch_core_init() -> None:
    copy_patch_file(PATCH_DIR / "core" / "__init__.py", ROOT / "core" / "__init__.py")


def patch_ako_gui() -> None:
    path = ROOT / "ako_gui.py"
    if not path.exists():
        print("[SKIP] ako_gui.py 없음")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    if "from loading_overlay import LoadingOverlay" not in text:
        if "from core.controller import AkoController" in text:
            text = text.replace(
                "from core.controller import AkoController",
                "from loading_overlay import LoadingOverlay\nfrom core.controller import AkoController",
                1,
            )
        else:
            text = text.replace(
                "import threading",
                "import threading\n\nfrom loading_overlay import LoadingOverlay",
                1,
            )

    if "self.loading_overlay:" not in text:
        text = text.replace(
            "self.controller = AkoController(log_fn=self._append_log)",
            "self.controller = AkoController(log_fn=self._append_log)\n"
            "        self.loading_overlay: LoadingOverlay | None = None",
            1,
        )

    if "self._start_loading_overlay()" not in text:
        text = text.replace(
            "        self.deiconify()",
            "        self.deiconify()\n"
            "        self.update_idletasks()\n"
            "        self._start_loading_overlay()",
            1,
        )

    if "def _start_loading_overlay(self):" not in text:
        method = (
            "\n"
            "    def _start_loading_overlay(self):\n"
            "        self.loading_overlay = LoadingOverlay(\n"
            "            self,\n"
            "            on_done=self._finish_loading_overlay,\n"
            "            frames_dir=str(Path(\"assets\") / \"loading\" / \"frames\"),\n"
            "            fps=24,\n"
            "            max_duration_ms=5000,\n"
            "            max_frames=180,\n"
            "        )\n"
            "\n"
            "    def _finish_loading_overlay(self):\n"
            "        self.loading_overlay = None\n"
            "\n"
        )

        if "from pathlib import Path" not in text:
            text = text.replace("import threading", "import threading\nfrom pathlib import Path", 1)

        if "    def _build_ui(self):" in text:
            text = text.replace("    def _build_ui(self):", method + "    def _build_ui(self):", 1)
        else:
            print("[WARN] _build_ui 위치를 못 찾아서 로딩 메서드 자동 삽입 실패")

    if text != original:
        backup_file(path)
        path.write_text(text, encoding="utf-8")
        print("[OK] ako_gui.py 로딩 오버레이 연결")
    else:
        print("[OK] ako_gui.py 변경 필요 없음")


def patch_spec() -> None:
    path = ROOT / "Ako-ai.spec"
    if not path.exists():
        print("[SKIP] Ako-ai.spec 없음")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    if "loading_frames_dir" not in text:
        needle = (
            "ico = os.path.join(ROOT, \"assets\", \"ako.ico\")\n"
            "if os.path.exists(ico):\n"
            "    datas.append((ico, \"assets\"))\n"
        )
        insert = needle + (
            "\n"
            "loading_frames_dir = os.path.join(ROOT, \"assets\", \"loading\", \"frames\")\n"
            "if os.path.isdir(loading_frames_dir):\n"
            "    datas.append((loading_frames_dir, \"assets/loading/frames\"))\n"
        )
        if needle in text:
            text = text.replace(needle, insert, 1)
        else:
            print("[WARN] ico 블록을 못 찾았습니다. Ako-ai.spec는 수동 확인이 필요할 수 있어요.")

    if text != original:
        backup_file(path)
        path.write_text(text, encoding="utf-8")
        print("[OK] Ako-ai.spec 프레임 폴더 포함")
    else:
        print("[OK] Ako-ai.spec 변경 필요 없음")


def main() -> None:
    ensure_dirs()
    patch_loading_overlay()
    patch_core_init()
    patch_ako_gui()
    patch_spec()

    print()
    print("패치 완료.")
    print()
    print("다음 명령으로 프레임을 다시 뽑으세요:")
    print(r"Remove-Item assets\loading\frames\frame_*.jpg -ErrorAction SilentlyContinue")
    print(r"ffmpeg -y -ss 0 -t 5 -i assets\loading\ako_loading.mp4 -vf ""fps=24,scale=940:-2"" -q:v 3 assets\loading\frames\frame_%03d.jpg")
    print()
    print("그다음 실행:")
    print(r"python app.py --mode=gui")


if __name__ == "__main__":
    main()
