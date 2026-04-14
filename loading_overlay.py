from __future__ import annotations

import math
import random
import tkinter as tk
from typing import Callable


BOOT_STEPS = [
    "AKO // LINKING",
    "VOICE // STABLE",
    "MEMORY // SYNCED",
    "AKO IS READY",
]


class LoadingOverlay(tk.Frame):
    def __init__(self, master: tk.Misc, on_done: Callable[[], None] | None = None):
        super().__init__(master, bg="#02030a", bd=0)

        self.on_done = on_done
        self.progress = 0.0
        self.phase = 0.0
        self.rot_y = 0.0
        self.rot_x = 0.0
        self._done = False

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self.canvas = tk.Canvas(
            self,
            bg="#02030a",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.shell_particles: list[dict] = []
        self.shell_items: list[int] = []
        self.core_particles: list[dict] = []
        self.core_items: list[int] = []

        self.after(10, self._init_scene)
        self.after(30, self._tick)
        self.after(260, self._advance_progress)

    # ------------------------------------------------------------
    # init / build
    # ------------------------------------------------------------
    def _init_scene(self):
        self.update_idletasks()
        self.w = max(self.winfo_width(), 620)
        self.h = max(self.winfo_height(), 420)

        self.cx = self.w // 2
        self.cy = self.h // 2 - 10

        self._build_scene()

    def _build_scene(self):
        w, h = self.w, self.h
        cx, cy = self.cx, self.cy

        self.canvas.delete("all")

        # base
        self.canvas.create_rectangle(0, 0, w, h, fill="#02030a", outline="")

        # smoother center gradient feel with many layers
        self.bg_layers: list[int] = []
        for i in range(90, 0, -1):
            t = i / 90.0
            rx = int(500 * t)
            ry = int(300 * t)

            # darker outside, bluer/purpler toward center
            r = int(3 + 22 * (1 - t) + 8 * math.sin((1 - t) * 1.4))
            g = int(5 + 16 * (1 - t))
            b = int(12 + 34 * (1 - t) + 26 * (1 - t) * (1 - t))

            # blend in subtle purple toward center
            purple_mix = (1 - t) ** 1.8
            r = int(r + 42 * purple_mix)
            g = int(g + 10 * purple_mix)
            b = int(b + 34 * purple_mix)

            color = self._rgb_to_hex(r, g, b)
            item = self.canvas.create_oval(
                cx - rx, cy - ry, cx + rx, cy + ry,
                fill=color,
                outline="",
            )
            self.bg_layers.append(item)

        # extra central glow
        self.glow_back_1 = self.canvas.create_oval(
            cx - 170, cy - 170, cx + 170, cy + 170,
            fill="#0a1120", outline=""
        )
        self.glow_back_2 = self.canvas.create_oval(
            cx - 120, cy - 120, cx + 120, cy + 120,
            fill="#10152b", outline=""
        )
        self.glow_back_3 = self.canvas.create_oval(
            cx - 78, cy - 78, cx + 78, cy + 78,
            fill="#171938", outline=""
        )

        # ambient background specks
        self.dust_items: list[int] = []
        random.seed(17)
        for _ in range(75):
            x = random.randint(0, w)
            y = random.randint(0, h)
            r = random.choice((1, 1, 1, 2))
            c = random.choice(("#07111d", "#0a1525", "#0e1830", "#11173a", "#191a45"))
            self.dust_items.append(
                self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=c, outline="")
            )

        # sphere shell particles
        self._make_shell_particles()
        for _ in self.shell_particles:
            item = self.canvas.create_oval(0, 0, 0, 0, outline="", fill="#173052")
            self.shell_items.append(item)

        # inner flow particles
        self._make_core_particles()
        for _ in self.core_particles:
            item = self.canvas.create_oval(0, 0, 0, 0, outline="", fill="#2a3c66")
            self.core_items.append(item)

        # AKO glow layers: one word, no fake mask slide
        self.ako_glow_far = self.canvas.create_text(
            cx, cy,
            text="AKO",
            fill="#1f3560",
            font=("Segoe UI Semibold", 42, "bold"),
            anchor="center",
        )
        self.ako_glow_mid = self.canvas.create_text(
            cx, cy,
            text="AKO",
            fill="#2f4f86",
            font=("Segoe UI Semibold", 42, "bold"),
            anchor="center",
        )
        self.ako_main = self.canvas.create_text(
            cx, cy,
            text="AKO",
            fill="#d9f0ff",
            font=("Segoe UI Semibold", 42, "bold"),
            anchor="center",
        )

        # keep initially invisible
        self.canvas.itemconfigure(self.ako_glow_far, state="hidden")
        self.canvas.itemconfigure(self.ako_glow_mid, state="hidden")
        self.canvas.itemconfigure(self.ako_main, state="hidden")

        # status
        self.status_text = self.canvas.create_text(
            cx,
            cy + 126,
            text=BOOT_STEPS[0],
            fill="#9a8fcd",
            font=("Consolas", 11, "bold"),
            anchor="center",
        )

        self.ready_text = self.canvas.create_text(
            cx,
            cy + 160,
            text="",
            fill="#d9e7ff",
            font=("Segoe UI", 13, "bold"),
            anchor="center",
        )

        self.percent_text = self.canvas.create_text(
            cx,
            h - 84,
            text="00%",
            fill="#8fa8ff",
            font=("Consolas", 10, "bold"),
            anchor="center",
        )

        self.bar_bg = self.canvas.create_line(
            cx - 62, h - 62, cx + 62, h - 62,
            fill="#1a1d35",
            width=2,
        )
        self.bar_fill = self.canvas.create_line(
            cx - 62, h - 62, cx - 62, h - 62,
            fill="#9a82ff",
            width=2,
        )

    def _make_shell_particles(self):
        self.shell_particles.clear()
        random.seed(7)

        for _ in range(520):
            u = random.random()
            v = random.random()

            theta = 2 * math.pi * u
            phi = math.acos(2 * v - 1)

            radius = 150 + random.uniform(-12, 12)

            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.cos(phi)
            z = radius * math.sin(phi) * math.sin(theta)

            self.shell_particles.append(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "size": random.uniform(0.8, 2.4),
                    "bias": random.uniform(0.6, 1.4),
                    "seed": random.uniform(0.0, 1000.0),
                }
            )

    def _make_core_particles(self):
        self.core_particles.clear()
        random.seed(11)

        for _ in range(150):
            ang = random.uniform(0, math.tau)
            rr = random.uniform(12, 66)

            self.core_particles.append(
                {
                    "ang": ang,
                    "rad": rr,
                    "seed": random.uniform(0.0, 1000.0),
                    "speed": random.uniform(0.4, 1.1),
                    "size": random.uniform(1.0, 2.8),
                }
            )

    # ------------------------------------------------------------
    # animation
    # ------------------------------------------------------------
    def _tick(self):
        if self._done:
            return

        if not hasattr(self, "cx"):
            self.after(33, self._tick)
            return

        self.phase += 0.045
        self.rot_y += 0.017
        self.rot_x += 0.008

        self._animate_background()
        self._animate_shell_particles()
        self._animate_core_particles()
        self._animate_ako()
        self._animate_ui()

        self.after(33, self._tick)

    def _animate_background(self):
        breathe = (math.sin(self.phase * 0.8) + 1) / 2

        for idx, item in enumerate(self.bg_layers):
            t = idx / max(1, len(self.bg_layers) - 1)
            expand = math.sin(self.phase * 0.55 + t * 2.8) * (0.8 + t * 2.2)

            rx = 500 - idx * (500 / 90)
            ry = 300 - idx * (300 / 90)

            rx2 = rx + expand
            ry2 = ry + expand * 0.55
            self.canvas.coords(
                item,
                self.cx - rx2, self.cy - ry2,
                self.cx + rx2, self.cy + ry2
            )

        # central glow breathing with purple support
        g1 = 170 + math.sin(self.phase * 1.0) * 4
        g2 = 120 + math.sin(self.phase * 1.15 + 0.7) * 3
        g3 = 78 + math.sin(self.phase * 1.3 + 1.2) * 2

        self.canvas.coords(self.glow_back_1, self.cx - g1, self.cy - g1, self.cx + g1, self.cy + g1)
        self.canvas.coords(self.glow_back_2, self.cx - g2, self.cy - g2, self.cx + g2, self.cy + g2)
        self.canvas.coords(self.glow_back_3, self.cx - g3, self.cy - g3, self.cx + g3, self.cy + g3)

        c1 = self._blend("#09111d", "#111a31", 0.45 + 0.25 * breathe)
        c2 = self._blend("#11142a", "#1a1739", 0.35 + 0.35 * breathe)
        c3 = self._blend("#171834", "#281c4d", 0.30 + 0.40 * breathe)

        self.canvas.itemconfigure(self.glow_back_1, fill=c1)
        self.canvas.itemconfigure(self.glow_back_2, fill=c2)
        self.canvas.itemconfigure(self.glow_back_3, fill=c3)

    def _animate_shell_particles(self):
        cx, cy = self.cx, self.cy
        reveal = self._segment(self.progress, 2, 84)
        perspective = 540

        for p, item in zip(self.shell_particles, self.shell_items):
            x = p["x"]
            y = p["y"]
            z = p["z"]

            seed = p["seed"]
            wave = math.sin(self.phase * (1.1 + p["bias"]) + seed * 0.01)
            swirl = math.cos(self.phase * (0.7 + p["bias"] * 0.4) + seed * 0.013)

            # organic shell distortion
            x += wave * 5.0 * reveal
            y += swirl * 4.5 * reveal
            z += math.sin(self.phase * 1.7 + seed * 0.009) * 10.0 * reveal

            # Y rotation
            ry = self.rot_y * p["bias"]
            x1 = x * math.cos(ry) + z * math.sin(ry)
            z1 = -x * math.sin(ry) + z * math.cos(ry)

            # X rotation
            rx = 0.72 + math.sin(self.phase * 0.45) * 0.07 + self.rot_x
            y2 = y * math.cos(rx) - z1 * math.sin(rx)
            z2 = y * math.sin(rx) + z1 * math.cos(rx)

            scale = perspective / (perspective + z2 + 260)
            sx = cx + x1 * scale
            sy = cy + y2 * scale

            depth = max(0.0, min(1.0, (z2 + 200) / 400))
            light = (0.08 + 0.92 * depth) * reveal

            # blue-white with subtle purple support
            c_a = self._blend("#0a1424", "#2a2750", 0.22 + 0.20 * (1 - depth))
            c_b = self._blend(c_a, "#b9f1ff", light)

            size = p["size"] * scale * (0.85 + reveal * 0.9)
            size = max(0.7, min(3.8, size))

            self.canvas.coords(item, sx - size, sy - size, sx + size, sy + size)
            self.canvas.itemconfigure(item, fill=c_b)

    def _animate_core_particles(self):
        cx, cy = self.cx, self.cy
        reveal = self._segment(self.progress, 14, 100)

        for p, item in zip(self.core_particles, self.core_items):
            seed = p["seed"]
            ang = p["ang"] + self.phase * p["speed"] * 0.8 + math.sin(self.phase * 1.4 + seed * 0.01) * 0.22
            rad = p["rad"] + math.sin(self.phase * 2.0 + seed * 0.02) * 10.0

            # give depth by squashing and slight drift
            x = math.cos(ang) * rad
            y = math.sin(ang) * rad * 0.62
            z = math.sin(ang * 1.7 + self.phase * 0.9) * 24

            perspective = 410
            scale = perspective / (perspective + z + 120)
            sx = cx + x * scale
            sy = cy + y * scale

            depth = max(0.0, min(1.0, (z + 24) / 48))
            light = (0.18 + 0.82 * depth) * reveal

            color = self._blend("#231f48", "#d8f0ff", light)
            size = p["size"] * (0.8 + 0.55 * reveal) * scale
            size = max(0.8, min(3.0, size))

            self.canvas.coords(item, sx - size, sy - size, sx + size, sy + size)
            self.canvas.itemconfigure(item, fill=color)

    def _animate_ako(self):
        # not a black mask slide: letters generate from glow/convergence
        reveal = self._segment(self.progress, 32, 88)
        settle = self._segment(self.progress, 60, 100)

        if reveal <= 0:
            self.canvas.itemconfigure(self.ako_glow_far, state="hidden")
            self.canvas.itemconfigure(self.ako_glow_mid, state="hidden")
            self.canvas.itemconfigure(self.ako_main, state="hidden")
            return

        self.canvas.itemconfigure(self.ako_glow_far, state="normal")
        self.canvas.itemconfigure(self.ako_glow_mid, state="normal")
        self.canvas.itemconfigure(self.ako_main, state="normal")

        # letter-by-letter emergence, but visually one joined word
        a_t = min(1.0, reveal / 0.45)
        k_t = min(1.0, max(0.0, (reveal - 0.18) / 0.45))
        o_t = min(1.0, max(0.0, (reveal - 0.36) / 0.45))
        combined = (a_t + k_t + o_t) / 3.0

        # use same word but animate intensity toward left->right completion
        glow_far = self._blend("#11182d", "#3d4e8c", 0.30 + 0.55 * combined)
        glow_mid = self._blend("#17223f", "#7a7dff", 0.24 + 0.68 * combined)
        main_col = self._blend("#23324f", "#edf4ff", 0.12 + 0.88 * settle)

        # shimmer that feels like forming, not sliding
        jitter_x = math.sin(self.phase * 3.0) * (1.0 - settle) * 1.8
        jitter_y = math.sin(self.phase * 2.2 + 0.8) * (1.0 - settle) * 1.2

        self.canvas.coords(self.ako_glow_far, self.cx + jitter_x * 1.2, self.cy + jitter_y * 1.1)
        self.canvas.coords(self.ako_glow_mid, self.cx + jitter_x * 0.7, self.cy + jitter_y * 0.6)
        self.canvas.coords(self.ako_main, self.cx, self.cy)

        self.canvas.itemconfigure(self.ako_glow_far, fill=glow_far)
        self.canvas.itemconfigure(self.ako_glow_mid, fill=glow_mid)
        self.canvas.itemconfigure(self.ako_main, fill=main_col)

        # fake progressive formation by tweaking font brightness over left->right segments
        # plus nearby burst particles impression from core by brightening in sequence
        if a_t < 1 or k_t < 1 or o_t < 1:
            bias = 0.35 + 0.65 * combined
            self.canvas.itemconfigure(self.ako_main, fill=self._blend("#18243d", "#edf4ff", bias * settle + 0.18))

    def _animate_ui(self):
        breathe = (math.sin(self.phase * 0.9) + 1) / 2

        # status
        status_color = self._blend("#7569ad", "#bea7ff", 0.35 + 0.25 * breathe)
        self.canvas.itemconfigure(self.status_text, fill=status_color)

        # bar
        self.canvas.itemconfigure(self.bar_bg, fill=self._blend("#151728", "#231f42", 0.35 + 0.25 * breathe))
        self.canvas.itemconfigure(self.bar_fill, fill=self._blend("#6e6ed8", "#aa8cff", 0.35 + 0.55 * breathe))
        self.canvas.itemconfigure(self.percent_text, fill=self._blend("#7f88d6", "#c6b7ff", 0.35 + 0.50 * breathe))

        # ready text
        if self.progress >= 82:
            t = self._segment(self.progress, 82, 100)
            ready_color = self._blend("#3f4670", "#f0eaff", t)
            self.canvas.itemconfigure(self.ready_text, text="AKO IS READY", fill=ready_color)

    # ------------------------------------------------------------
    # progress / finish
    # ------------------------------------------------------------
    def _advance_progress(self):
        if self._done:
            return

        self.progress = min(self.progress + 2, 100)

        if self.progress < 32:
            idx = 0
        elif self.progress < 58:
            idx = 1
        elif self.progress < 84:
            idx = 2
        else:
            idx = 3

        self.canvas.itemconfigure(self.status_text, text=BOOT_STEPS[idx])
        self.canvas.itemconfigure(self.percent_text, text=f"{int(self.progress):02d}%")

        bar_end = (self.cx - 62) + int(124 * (self.progress / 100.0))
        self.canvas.coords(self.bar_fill, self.cx - 62, self.h - 62, bar_end, self.h - 62)

        if self.progress >= 100:
            self._done = True
            self.after(620, self._finish)
            return

        delay = 76 if self.progress < 70 else 96
        self.after(delay, self._advance_progress)

    def _finish(self):
        self.destroy()
        if self.on_done:
            self.on_done()

    # ------------------------------------------------------------
    # utils
    # ------------------------------------------------------------
    def _segment(self, value: float, start: float, end: float) -> float:
        if value <= start:
            return 0.0
        if value >= end:
            return 1.0
        return (value - start) / (end - start)

    def _blend(self, c1: str, c2: str, t: float) -> str:
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
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return f"#{r:02x}{g:02x}{b:02x}"