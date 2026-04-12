from __future__ import annotations

import math
import tkinter as tk
from typing import Callable


BOOT_STEPS = [
    "AKO // LINKING",
    "VOICE // STABLE",
    "MEMORY // SYNCED",
    "AKO IS READY",
]


class HudSplash(tk.Tk):
    def __init__(self, on_done: Callable[[], None] | None = None):
        super().__init__()
        self.on_done = on_done

        self.w = 980
        self.h = 620

        self.progress = 0
        self.phase = 0.0
        self.wave_phase = 0.0
        self.step_index = 0
        self._done = False

        self.overrideredirect(True)
        self.configure(bg="#070a14")
        self.geometry(f"{self.w}x{self.h}")
        self.minsize(self.w, self.h)

        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - self.w) // 2
        y = (sh - self.h) // 2
        self.geometry(f"{self.w}x{self.h}+{x}+{y}")

        self.canvas = tk.Canvas(
            self,
            width=self.w,
            height=self.h,
            bg="#070a14",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.current_status = BOOT_STEPS[0]

        self._build_static()
        self._animate()
        self.after(350, self._advance_progress)

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def _build_static(self):
        w, h = self.w, self.h
        cx, cy = w // 2, h // 2 - 20
        self.cx = cx
        self.cy = cy

        # background layers
        self.canvas.create_rectangle(0, 0, w, h, fill="#070a14", outline="")

        self._draw_background_glow(cx, cy, 250, "#120f24")
        self._draw_background_glow(cx, cy, 180, "#17122d")
        self._draw_background_glow(cx, cy, 110, "#20153a")

        # subtle top/bottom fades
        self.canvas.create_rectangle(0, 0, w, 90, fill="#080c18", outline="")
        self.canvas.create_rectangle(0, h - 90, w, h, fill="#080b17", outline="")

        # decorative thin frame
        self.canvas.create_line(54, 46, w - 54, 46, fill="#171d34", width=1)
        self.canvas.create_line(54, h - 46, w - 54, h - 46, fill="#171d34", width=1)

        # small title
        self.title_text = self.canvas.create_text(
            cx,
            110,
            text="AKO",
            fill="#8d73d9",
            font=("Segoe UI", 10, "bold"),
            anchor="center",
        )

        # central aura
        self.aura_outer = self.canvas.create_oval(
            cx - 130, cy - 130, cx + 130, cy + 130,
            outline="",
            fill="#151028",
        )
        self.aura_mid = self.canvas.create_oval(
            cx - 92, cy - 92, cx + 92, cy + 92,
            outline="",
            fill="#1b1430",
        )
        self.aura_inner = self.canvas.create_oval(
            cx - 58, cy - 58, cx + 58, cy + 58,
            outline="",
            fill="#23183d",
        )

        # AKO letters built separately
        self.letter_a = self.canvas.create_text(
            cx - 82,
            cy,
            text="A",
            fill="#2a2144",
            font=("Segoe UI Semibold", 38, "bold"),
            anchor="center",
        )
        self.letter_k = self.canvas.create_text(
            cx,
            cy,
            text="K",
            fill="#2a2144",
            font=("Segoe UI Semibold", 38, "bold"),
            anchor="center",
        )
        self.letter_o = self.canvas.create_text(
            cx + 82,
            cy,
            text="O",
            fill="#2a2144",
            font=("Segoe UI Semibold", 38, "bold"),
            anchor="center",
        )

        # letter underline fragments
        self.line_a = self.canvas.create_line(
            cx - 110, cy + 42, cx - 56, cy + 42,
            fill="#2a2144", width=2
        )
        self.line_k = self.canvas.create_line(
            cx - 26, cy + 42, cx + 26, cy + 42,
            fill="#2a2144", width=2
        )
        self.line_o = self.canvas.create_line(
            cx + 56, cy + 42, cx + 110, cy + 42,
            fill="#2a2144", width=2
        )

        # soft orbital / symbol wave around AKO
        self.wave_items = []
        self._create_symbol_waves()

        # small status text
        self.status_text = self.canvas.create_text(
            cx,
            cy + 118,
            text=self.current_status,
            fill="#9f8adf",
            font=("Consolas", 11, "bold"),
            anchor="center",
        )

        # ready text, initially hidden
        self.ready_text = self.canvas.create_text(
            cx,
            cy + 154,
            text="",
            fill="#d8d1f5",
            font=("Segoe UI", 14, "bold"),
            anchor="center",
        )

        # minimal bottom indicators
        self.progress_left = self.canvas.create_text(
            cx - 86,
            h - 112,
            text="STATE",
            fill="#5f5b7c",
            font=("Consolas", 10),
            anchor="e",
        )
        self.progress_label = self.canvas.create_text(
            cx - 70,
            h - 112,
            text="00%",
            fill="#b8a9ee",
            font=("Consolas", 10, "bold"),
            anchor="w",
        )

        self.bar_bg = self.canvas.create_line(
            cx - 70, h - 92, cx + 70, h - 92,
            fill="#24263a", width=2
        )
        self.bar_fill = self.canvas.create_line(
            cx - 70, h - 92, cx - 70, h - 92,
            fill="#8e73f0", width=2
        )

    def _draw_background_glow(self, cx: int, cy: int, r: int, color: str):
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill=color, outline=""
        )

    def _create_symbol_waves(self):
        cx, cy = self.cx, self.cy
        base_r = 96

        for i in range(28):
            angle = (360 / 28) * i
            rad = math.radians(angle)
            x1 = cx + math.cos(rad) * (base_r - 6)
            y1 = cy + math.sin(rad) * (base_r - 6)
            x2 = cx + math.cos(rad) * (base_r + 6)
            y2 = cy + math.sin(rad) * (base_r + 6)

            item = self.canvas.create_line(
                x1, y1, x2, y2,
                fill="#211b35",
                width=2,
                capstyle=tk.ROUND,
            )
            self.wave_items.append((item, angle))

    # ------------------------------------------------------------------
    # animation
    # ------------------------------------------------------------------
    def _animate(self):
        if self._done:
            return

        self.phase += 0.06
        self.wave_phase += 3.2

        self._animate_aura()
        self._animate_letters()
        self._animate_symbol_waves()

        self.after(33, self._animate)

    def _animate_aura(self):
        cx, cy = self.cx, self.cy

        pulse1 = math.sin(self.phase) * 5
        pulse2 = math.sin(self.phase * 1.25 + 0.8) * 4
        pulse3 = math.sin(self.phase * 1.5 + 1.7) * 3

        self.canvas.coords(
            self.aura_outer,
            cx - (130 + pulse1), cy - (130 + pulse1),
            cx + (130 + pulse1), cy + (130 + pulse1)
        )
        self.canvas.coords(
            self.aura_mid,
            cx - (92 + pulse2), cy - (92 + pulse2),
            cx + (92 + pulse2), cy + (92 + pulse2)
        )
        self.canvas.coords(
            self.aura_inner,
            cx - (58 + pulse3), cy - (58 + pulse3),
            cx + (58 + pulse3), cy + (58 + pulse3)
        )

        # subtle color breathing
        glow_mix = int(40 + (math.sin(self.phase) + 1) * 12)
        mid_mix = int(52 + (math.sin(self.phase * 1.2) + 1) * 10)
        inner_mix = int(64 + (math.sin(self.phase * 1.4) + 1) * 10)

        self.canvas.itemconfigure(self.aura_outer, fill=self._hex_rgb(18, 12, glow_mix))
        self.canvas.itemconfigure(self.aura_mid, fill=self._hex_rgb(28, 18, mid_mix))
        self.canvas.itemconfigure(self.aura_inner, fill=self._hex_rgb(38, 22, inner_mix))

    def _animate_letters(self):
        # reveal by progress
        # A first, then K, then O, then underline fragments, then final brighten
        p = self.progress

        a_color = self._blend_color("#2a2144", "#c9b6ff", self._segment(p, 5, 35))
        k_color = self._blend_color("#2a2144", "#d7c8ff", self._segment(p, 20, 55))
        o_color = self._blend_color("#2a2144", "#ece4ff", self._segment(p, 38, 72))

        line_a = self._blend_color("#2a2144", "#7e67cf", self._segment(p, 12, 42))
        line_k = self._blend_color("#2a2144", "#8d73f0", self._segment(p, 28, 58))
        line_o = self._blend_color("#2a2144", "#a28bff", self._segment(p, 45, 75))

        self.canvas.itemconfigure(self.letter_a, fill=a_color)
        self.canvas.itemconfigure(self.letter_k, fill=k_color)
        self.canvas.itemconfigure(self.letter_o, fill=o_color)

        self.canvas.itemconfigure(self.line_a, fill=line_a)
        self.canvas.itemconfigure(self.line_k, fill=line_k)
        self.canvas.itemconfigure(self.line_o, fill=line_o)

        # slight floating motion
        a_dy = math.sin(self.phase * 1.3) * 1.5
        k_dy = math.sin(self.phase * 1.2 + 0.8) * 1.2
        o_dy = math.sin(self.phase * 1.4 + 1.6) * 1.5

        self.canvas.coords(self.letter_a, self.cx - 82, self.cy + a_dy)
        self.canvas.coords(self.letter_k, self.cx, self.cy + k_dy)
        self.canvas.coords(self.letter_o, self.cx + 82, self.cy + o_dy)

        self.canvas.coords(self.line_a, self.cx - 110, self.cy + 42 + a_dy, self.cx - 56, self.cy + 42 + a_dy)
        self.canvas.coords(self.line_k, self.cx - 26, self.cy + 42 + k_dy, self.cx + 26, self.cy + 42 + k_dy)
        self.canvas.coords(self.line_o, self.cx + 56, self.cy + 42 + o_dy, self.cx + 110, self.cy + 42 + o_dy)

    def _animate_symbol_waves(self):
        # subtle pulse around symbol
        strength = self._segment(self.progress, 28, 100)

        for item, angle in self.wave_items:
            local = (math.sin(math.radians(angle * 2 + self.wave_phase)) + 1) / 2
            amt = 0.18 + (0.82 * local * strength)

            color = self._blend_color("#211b35", "#8f78ee", amt * 0.7)
            width = 1 if amt < 0.45 else 2

            rad = math.radians(angle)
            r1 = 96 + math.sin(math.radians(self.wave_phase + angle)) * 2
            r2 = 108 + math.sin(math.radians(self.wave_phase * 1.2 + angle * 1.6)) * 3

            x1 = self.cx + math.cos(rad) * r1
            y1 = self.cy + math.sin(rad) * r1
            x2 = self.cx + math.cos(rad) * r2
            y2 = self.cy + math.sin(rad) * r2

            self.canvas.coords(item, x1, y1, x2, y2)
            self.canvas.itemconfigure(item, fill=color, width=width)

    # ------------------------------------------------------------------
    # progress / state
    # ------------------------------------------------------------------
    def _advance_progress(self):
        if self._done:
            return

        self.progress = min(self.progress + 2, 100)

        if self.progress < 30:
            self.step_index = 0
        elif self.progress < 58:
            self.step_index = 1
        elif self.progress < 84:
            self.step_index = 2
        else:
            self.step_index = 3

        self.current_status = BOOT_STEPS[self.step_index]

        self.canvas.itemconfigure(self.status_text, text=self.current_status)
        self.canvas.itemconfigure(self.progress_label, text=f"{self.progress:02d}%")

        end_x = (self.cx - 70) + int(140 * (self.progress / 100))
        self.canvas.coords(self.bar_fill, self.cx - 70, self.h - 92, end_x, self.h - 92)

        if self.progress >= 84:
            alpha = self._segment(self.progress, 84, 100)
            ready_color = self._blend_color("#3a3056", "#ebe2ff", alpha)
            self.canvas.itemconfigure(self.ready_text, text="AKO IS READY", fill=ready_color)

        if self.progress >= 100:
            self._done = True
            self.after(700, self._finish)
            return

        delay = 85 if self.progress < 70 else 105
        self.after(delay, self._advance_progress)

    def _finish(self):
        self.destroy()
        if self.on_done:
            self.on_done()

    # ------------------------------------------------------------------
    # utils
    # ------------------------------------------------------------------
    def _segment(self, value: float, start: float, end: float) -> float:
        if value <= start:
            return 0.0
        if value >= end:
            return 1.0
        return (value - start) / (end - start)

    def _blend_color(self, c1: str, c2: str, t: float) -> str:
        t = max(0.0, min(1.0, t))
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)

        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return self._rgb_to_hex(r, g, b)

    def _hex_to_rgb(self, value: str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        return f"#{r:02x}{g:02x}{b:02x}"

    def _hex_rgb(self, r: int, g: int, b: int) -> str:
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return f"#{r:02x}{g:02x}{b:02x}"