from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import Image, ImageTk


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class LoadingOverlay(tk.Frame):
    """
    MP4를 직접 재생하지 않고, 미리 변환해둔 이미지 프레임을 재생하는 로딩 오버레이.
    cv2/opencv-python 필요 없음.
    """

    def __init__(
        self,
        master: tk.Misc,
        on_done: Callable[[], None] | None = None,
        video_path: str | None = None,
        frames_dir: str | None = None,
        fps: int = 30,
        max_duration_ms: int = 5000,
    ):
        super().__init__(master, bg="black", bd=0, highlightthickness=0)

        self.on_done = on_done
        self.video_path = video_path  # ako_gui.py 호환용. 여기서는 직접 사용하지 않음.
        self.fps = max(1, int(fps))
        self.frame_delay_ms = max(1, int(1000 / self.fps))
        self.max_duration_ms = max(500, int(max_duration_ms))

        self._finished = False
        self._after_id: str | None = None
        self._frame_index = 0
        self._started_ms: int | None = None

        self._frames: list[Path] = []
        self._photo: ImageTk.PhotoImage | None = None
        self._last_size: tuple[int, int] = (0, 0)

        rel_frames_dir = frames_dir or os.path.join("assets", "loading", "frames")
        self.frames_dir = Path(resource_path(rel_frames_dir))

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self.label = tk.Label(self, bg="black", bd=0, highlightthickness=0)
        self.label.pack(fill="both", expand=True)

        self.bind("<Configure>", self._on_resize)

        self._load_frame_list()

        if not self._frames:
            self._show_fallback()
            self._after_id = self.after(1200, self._finish)
            return

        self.after(1, self._play)

    def _load_frame_list(self) -> None:
        if not self.frames_dir.exists():
            return

        patterns = ("*.jpg", "*.jpeg", "*.png", "*.webp")
        files: list[Path] = []
        for pattern in patterns:
            files.extend(self.frames_dir.glob(pattern))

        self._frames = sorted(files)

    def _play(self) -> None:
        if self._finished:
            return

        now_ms = self.winfo_toplevel().tk.call("clock", "milliseconds")
        now_ms = int(now_ms)

        if self._started_ms is None:
            self._started_ms = now_ms

        if now_ms - self._started_ms >= self.max_duration_ms:
            self._finish()
            return

        if self._frame_index >= len(self._frames):
            self._finish()
            return

        self._display_frame(self._frames[self._frame_index])
        self._frame_index += 1

        self._after_id = self.after(self.frame_delay_ms, self._play)

    def _display_frame(self, frame_path: Path) -> None:
        try:
            img = Image.open(frame_path).convert("RGB")
        except Exception:
            return

        target_w = max(1, self.winfo_width())
        target_h = max(1, self.winfo_height())

        img_w, img_h = img.size
        scale = min(target_w / img_w, target_h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (target_w, target_h), "black")
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(img, (paste_x, paste_y))

        self._photo = ImageTk.PhotoImage(canvas)
        self.label.configure(image=self._photo)

    def _on_resize(self, _event=None) -> None:
        # 다음 프레임에서 새 크기로 다시 그려짐.
        pass

    def _show_fallback(self) -> None:
        target_w = max(640, self.winfo_width())
        target_h = max(420, self.winfo_height())

        canvas = Image.new("RGB", (target_w, target_h), "#050712")
        self._photo = ImageTk.PhotoImage(canvas)
        self.label.configure(image=self._photo, text="AKO LOADING...", fg="#ab8dff", font=("Segoe UI", 24, "bold"))

    def _finish(self) -> None:
        if self._finished:
            return

        self._finished = True

        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        try:
            self.destroy()
        finally:
            if self.on_done:
                self.on_done()