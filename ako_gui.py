from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from loading_overlay import LoadingOverlay
from core.controller import AkoController
from voice_loop import VoiceConfig


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        master,
        text,
        command,
        width=124,
        height=42,
        radius=18,
        bg="#1b1f34",
        fg="#f3f4ff",
        hover_bg="#2a3050",
        active_bg="#ab8dff",
        active_fg="#0b0b14",
        font=("Segoe UI Semibold", 10),
        disabled_bg="#171a27",
        disabled_fg="#666b88",
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            bg=master.cget("bg"),
            highlightthickness=0,
            bd=0,
        )
        self.command = command
        self._text = text
        self._width = width
        self._height = height
        self._radius = radius
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._active_bg = active_bg
        self._active_fg = active_fg
        self._font = font
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._enabled = True
        self._pressed = False

        self._draw(self._bg, self._fg)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _draw(self, fill, text_fill):
        self.delete("all")
        self._rounded_rect(
            2, 2,
            self._width - 2,
            self._height - 2,
            self._radius,
            fill=fill,
            outline="",
        )
        self.create_text(
            self._width // 2,
            self._height // 2,
            text=self._text,
            fill=text_fill,
            font=self._font,
        )

    def configure_state(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self._draw(self._bg, self._fg)
        else:
            self._draw(self._disabled_bg, self._disabled_fg)

    def configure_text(self, text: str):
        self._text = text
        if self._enabled:
            self._draw(self._bg, self._fg)
        else:
            self._draw(self._disabled_bg, self._disabled_fg)

    def _on_enter(self, _event):
        if self._enabled and not self._pressed:
            self._draw(self._hover_bg, self._fg)

    def _on_leave(self, _event):
        if self._enabled and not self._pressed:
            self._draw(self._bg, self._fg)

    def _on_press(self, _event):
        if self._enabled:
            self._pressed = True
            self._draw(self._active_bg, self._active_fg)

    def _on_release(self, event):
        if not self._enabled:
            return

        inside = 0 <= event.x <= self._width and 0 <= event.y <= self._height
        self._pressed = False

        if inside:
            self._draw(self._hover_bg, self._fg)
            if self.command:
                self.command()
        else:
            self._draw(self._bg, self._fg)


class AkoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        try:
            self.iconbitmap(resource_path(os.path.join("assets", "ako.ico")))
        except Exception:
            pass

        self.title("Ako")
        self.geometry("920x640")
        self.minsize(820, 560)
        self.configure(bg="#090b14")

        self.colors = {
            "bg": "#090b14",
            "panel": "#101321",
            "panel_2": "#14182a",
            "border": "#2a2f4b",
            "text": "#eceefe",
            "muted": "#a7adc9",
            "accent": "#ab8dff",
            "accent_soft": "#241f45",
            "button_bg": "#1b1f34",
            "button_hover": "#2a3050",
            "button_fg": "#f3f4ff",
            "entry_bg": "#0f1322",
            "entry_fg": "#f2f4ff",
            "log_bg": "#0c0f1b",
        }

        self.controller = AkoController(log_fn=self._append_log)
        self.loading_overlay: LoadingOverlay | None = None

        self._build_ui()
        self._refresh_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._start_loading_overlay()
        self.deiconify()

    # ------------------------------------------------------------------
    # loading overlay
    # ------------------------------------------------------------------
    def _start_loading_overlay(self):
        self.loading_overlay = LoadingOverlay(
            self,
            on_done=self._finish_loading_overlay,
            video_path=os.path.join("assets", "loading", "ako_loading.mp4"),
        )

    def _finish_loading_overlay(self):
        self.loading_overlay = None

    # ------------------------------------------------------------------
    # ui
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = tk.Frame(self, bg=self.colors["bg"], padx=18, pady=18)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg=self.colors["bg"])
        header.pack(fill="x")

        header_left = tk.Frame(header, bg=self.colors["bg"])
        header_left.pack(side="left", fill="x", expand=True)

        tk.Label(
            header_left,
            text="AKO",
            bg=self.colors["bg"],
            fg=self.colors["accent"],
            font=("Segoe UI Semibold", 10),
        ).pack(anchor="w")

        tk.Label(
            header_left,
            text="명령 인터페이스",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            header_left,
            text="전원을 켜고 명령을 입력하면 바로 응답합니다",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(6, 0))

        self.power_chip = tk.Label(
            header,
            text="꺼짐",
            bg=self.colors["panel_2"],
            fg=self.colors["muted"],
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
        )
        self.power_chip.pack(side="right")

        main_panel = tk.Frame(
            root,
            bg=self.colors["panel"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            bd=0,
            padx=18,
            pady=18,
        )
        main_panel.pack(fill="both", expand=True, pady=(16, 0))

        top_row = tk.Frame(main_panel, bg=self.colors["panel"])
        top_row.pack(fill="x")

        self.power_btn = RoundedButton(
            top_row,
            text="전원 켜기",
            command=self._toggle_power,
            width=130,
            height=44,
            radius=20,
            bg=self.colors["accent"],
            fg="#0b0b14",
            hover_bg="#bea7ff",
            active_bg="#8f6fff",
            active_fg="#0b0b14",
        )
        self.power_btn.pack(side="left")

        self.status_line = tk.Label(
            top_row,
            text="전원 꺼짐",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.status_line.pack(side="left", padx=(14, 0), fill="x", expand=True)

        command_box = tk.Frame(main_panel, bg=self.colors["panel"])
        command_box.pack(fill="x", pady=(18, 16))

        tk.Label(
            command_box,
            text="명령 입력",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(0, 6))

        entry_row = tk.Frame(command_box, bg=self.colors["panel"])
        entry_row.pack(fill="x")

        self.cmd_entry = tk.Entry(
            entry_row,
            bg=self.colors["entry_bg"],
            fg=self.colors["entry_fg"],
            insertbackground=self.colors["accent"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            font=("Segoe UI", 11),
        )
        self.cmd_entry.pack(side="left", fill="x", expand=True, ipady=10)
        self.cmd_entry.bind("<Return>", lambda e: self._send_command())

        self.send_btn = RoundedButton(
            entry_row,
            text="보내기",
            command=self._send_command,
            width=118,
            height=44,
            radius=20,
            bg=self.colors["button_bg"],
            fg=self.colors["button_fg"],
            hover_bg=self.colors["button_hover"],
            active_bg=self.colors["accent"],
            active_fg="#0b0b14",
        )
        self.send_btn.pack(side="left", padx=(10, 0))

        tk.Label(
            command_box,
            text="예: 크롬 켜줘 / 유튜브 재생 눌러줘 / 오른쪽에 있는 닫기 눌러줘",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(10, 0))

        log_section = tk.Frame(main_panel, bg=self.colors["panel"])
        log_section.pack(fill="both", expand=True)

        log_header = tk.Frame(log_section, bg=self.colors["panel"])
        log_header.pack(fill="x", pady=(0, 6))

        tk.Label(
            log_header,
            text="응답 창",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")

        self.clear_log_btn = RoundedButton(
            log_header,
            text="지우기",
            command=self._clear_log,
            width=86,
            height=36,
            radius=16,
            bg=self.colors["button_bg"],
            fg=self.colors["button_fg"],
            hover_bg=self.colors["button_hover"],
            active_bg=self.colors["accent"],
            active_fg="#0b0b14",
            font=("Segoe UI Semibold", 9),
        )
        self.clear_log_btn.pack(side="right")

        log_wrap = tk.Frame(
            log_section,
            bg=self.colors["log_bg"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            bd=0,
        )
        log_wrap.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            state="disabled",
            bg=self.colors["log_bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            selectbackground=self.colors["accent_soft"],
            relief="flat",
            bd=0,
            padx=14,
            pady=14,
            font=("Consolas", 10),
        )
        self.log_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def _append_log(self, line: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _toggle_power(self):
        self.controller.toggle_power()
        self._refresh_ui()

    def _send_command(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return

        self.cmd_entry.delete(0, "end")
        self._append_log(f"[나] {text}")
        self.status_line.configure(text="명령 처리 중...")
        self.controller.handle_text_command(text)
        self._refresh_ui()
        self.status_line.configure(text="대기 중")

    def _refresh_ui(self):
        on = self.controller.powered_on

        self.power_btn.configure_text("전원 끄기" if on else "전원 켜기")

        cmd_enabled = on and self.controller.command_on
        entry_state = "normal" if cmd_enabled else "disabled"
        self.cmd_entry.configure(state=entry_state)
        self.send_btn.configure_state(cmd_enabled)
        self.clear_log_btn.configure_state(True)

        if not on:
            self.power_chip.configure(
                text="꺼짐",
                bg=self.colors["panel_2"],
                fg=self.colors["muted"],
            )
            self.power_btn.configure_state(True)
            self.status_line.configure(text="전원 꺼짐")
        else:
            self.power_chip.configure(
                text="켜짐",
                bg=self.colors["accent_soft"],
                fg=self.colors["accent"],
            )
            self.power_btn.configure_state(True)
            if self.status_line.cget("text") in ("대기 중", "전원 꺼짐"):
                self.status_line.configure(text="준비 완료")

    def _on_close(self):
        try:
            self.controller.power_off()
        except Exception:
            pass
        self.destroy()


def main():
    app = AkoGUI()
    app.mainloop()


if __name__ == "__main__":
    main()