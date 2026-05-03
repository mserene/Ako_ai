from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Callable

from PIL import Image, ImageTk


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


def _resample_filter():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


class LoadingOverlay(tk.Frame):
    """
    고퀄 MP4를 미리 이미지 프레임으로 변환해두고,
    실행 중에는 Pillow + Tkinter로 프레임을 재생하는 로딩 화면.

    cv2/opencv-python 필요 없음.
    """

    def __init__(
        self,
        master: tk.Misc,
        on_done: Callable[[], None] | None = None,
        video_path: str | None = None,
        frames_dir: str | None = None,
        fps: int = 24,
        max_duration_ms: int = 5000,
        max_frames: int = 180,
    ):
        super().__init__(master, bg="black", bd=0, highlightthickness=0)

        self.on_done = on_done
        self.video_path = video_path  # 기존 ako_gui.py 호환용. 직접 재생하지 않음.
        self.fps = max(1, int(fps))
        self.frame_delay_ms = max(1, int(1000 / self.fps))
        self.max_duration_ms = max(500, int(max_duration_ms))
        self.max_frames = max(1, int(max_frames))

        rel_frames_dir = frames_dir or os.path.join("assets", "loading", "frames")
        self.frames_dir = Path(resource_path(rel_frames_dir))

        self._finished = False
        self._after_id: str | None = None
        self._frame_index = 0
        self._started_at: float | None = None
        self._photos: list[ImageTk.PhotoImage] = []

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self.label = tk.Label(self, bg="black", bd=0, highlightthickness=0)
        self.label.pack(fill="both", expand=True)

        self.after(1, self._prepare_and_play)

    def _load_frame_paths(self) -> list[Path]:
        if not self.frames_dir.exists():
            return []

        files: list[Path] = []
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            files.extend(self.frames_dir.glob(pattern))

        return sorted(files)[: self.max_frames]

    def _prepare_and_play(self) -> None:
        if self._finished:
            return

        self.update_idletasks()

        frame_paths = self._load_frame_paths()
        if not frame_paths:
            self._show_fallback()
            self._after_id = self.after(1200, self._finish)
            return

        target_w = max(1, self.winfo_width())
        target_h = max(1, self.winfo_height())

        # 처음에 PhotoImage로 준비해두면 재생 중 디스크 읽기 때문에 버벅이는 걸 줄일 수 있음.
        self._photos.clear()
        for path in frame_paths:
            try:
                img = Image.open(path).convert("RGB")
                img = self._fit_to_canvas(img, target_w, target_h)
                self._photos.append(ImageTk.PhotoImage(img))
            except Exception:
                continue

        if not self._photos:
            self._show_fallback()
            self._after_id = self.after(1200, self._finish)
            return

        self._started_at = time.monotonic()
        self._frame_index = 0
        self._play_next_frame()

    def _fit_to_canvas(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        img_w, img_h = img.size

        scale = min(target_w / img_w, target_h / img_h)
        new_w = max(1, int(img_w * scale))
        new_h = max(1, int(img_h * scale))

        resized = img.resize((new_w, new_h), _resample_filter())

        canvas = Image.new("RGB", (target_w, target_h), "black")
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(resized, (paste_x, paste_y))
        return canvas

    def _play_next_frame(self) -> None:
        if self._finished:
            return

        if self._started_at is not None:
            elapsed_ms = int((time.monotonic() - self._started_at) * 1000)
            if elapsed_ms >= self.max_duration_ms:
                self._finish()
                return

        if self._frame_index >= len(self._photos):
            self._finish()
            return

        self.label.configure(image=self._photos[self._frame_index])
        self._frame_index += 1

        self._after_id = self.after(self.frame_delay_ms, self._play_next_frame)

    def _show_fallback(self) -> None:
        self.label.configure(
            image="",
            text="AKO LOADING...",
            fg="#ab8dff",
            bg="black",
            font=("Segoe UI Semibold", 26, "bold"),
        )

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
