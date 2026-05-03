from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from typing import Callable

import cv2
from PIL import Image, ImageTk


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class LoadingOverlay(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        on_done: Callable[[], None] | None = None,
        video_path: str | None = None,
    ):
        super().__init__(master, bg="black", bd=0, highlightthickness=0)

        self.on_done = on_done
        self.video_path = resource_path(
            video_path or os.path.join("assets", "loading", "ako_loading.mp4")
        )

        self.cap: cv2.VideoCapture | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self._finished = False
        self._after_id: str | None = None
        self.frame_delay_ms = 33

        self.max_duration_sec = 5.0
        self.started_at = time.monotonic()

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self.label = tk.Label(self, bg="black", bd=0, highlightthickness=0)
        self.label.pack(fill="both", expand=True)

        self.bind("<Configure>", self._on_resize)

        self._open_video()
        self._show_first_frame()
        self._after_id = self.after(self.frame_delay_ms, self._play_next_frame)

    def _open_video(self):
        if not os.path.isfile(self.video_path):
            raise FileNotFoundError(f"로딩 영상 파일을 찾지 못했어요: {self.video_path}")

        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"로딩 영상을 열지 못했어요: {self.video_path}")

        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 1:
            fps = 30.0
        self.frame_delay_ms = max(1, int(1000 / fps))

    def _show_first_frame(self):
        if self.cap is None:
            return

        ok, frame = self.cap.read()
        if not ok:
            self._finish()
            return

        self._display_frame(frame)

    def _on_resize(self, _event=None):
        pass

    def _play_next_frame(self):
        if self._finished:
            return

        if time.monotonic() - self.started_at >= self.max_duration_sec:
            self._finish()
            return

        if self.cap is None:
            self._finish()
            return

        ok, frame = self.cap.read()
        if not ok:
            self._finish()
            return

        self._display_frame(frame)
        self._after_id = self.after(self.frame_delay_ms, self._play_next_frame)

    def _display_frame(self, frame):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        target_w = max(1, self.winfo_width())
        target_h = max(1, self.winfo_height())

        h, w = frame.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        canvas = Image.new("RGB", (target_w, target_h), "black")
        img = Image.fromarray(resized)
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        canvas.paste(img, (paste_x, paste_y))

        self.photo = ImageTk.PhotoImage(canvas)
        self.label.configure(image=self.photo)

    def _finish(self):
        if self._finished:
            return
        self._finished = True

        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.destroy()

        if self.on_done:
            self.on_done()