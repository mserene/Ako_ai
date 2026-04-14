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
        super().__init__(master, bg="#02040a", bd=0)

        self.on_done = on_done
        self.progress = 0.0
        self.phase = 0.0
        self.rot = 0.0
        self._done = False

        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

        self.canvas = tk.Canvas(
            self,
            bg="#02040a",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.particles: list[dict] = []
        self.particle_items: list[int] = []

        self.after(10, self._init_scene)
        self.after(30, self._tick)
        self.after(260, self._advance_progress)

    # ------------------------------------------------------------
    # setup
    # ------------------------------------------------------------
    def _init_scene(self):
        self.update_idletasks()
        self.w = max(self.winfo_width(), 620)
        self.h = max(self.winfo_height(), 420)

        self.cx = self.w // 2
        self.cy = self.h // 2 - 8

        self._build_scene()

    def _build_scene(self):
        w, h = self.w, self.h
        cx, cy = self.cx, self.cy

        self.canvas.delete("all")

        self.canvas.create_rectangle(0, 0, w, h, fill="#02040a", outline="")
        self.canvas.create_rectangle(0, 0, w, h, fill="#05070f", outline="")

        self.glow_layers: list[int] = []
        glow = [
            (420, "#030611"),
            (380, "#040816"),
            (340, "#050a1a"),
            (300, "#060c1e"),
            (265, "#071023"),
            (230, "#081328"),
            (200, "#0a1730"),
            (175, "#0b1a37"),
            (150, "#0d1d3d"),
            (126, "#102246"),
            (104, "#132952"),
            (84,  "#16315d"),
            (66,  "#1a3b6d"),
            (50,  "#1f467a"),
        ]
        for r, color in glow:
            item = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=color,
                outline="",
            )
            self.glow_layers.append(item)

        self.outer_ring = self.canvas.create_oval(
            cx - 165, cy - 165, cx + 165, cy + 165,
            outline="#63d4ff",
            width=2,
        )
        self.inner_ring = self.canvas.create_oval(
            cx - 82, cy - 82, cx + 82, cy + 82,
            outline="#315ff4",
            width=2,
        )

        self.canvas.create_oval(
            cx - 184, cy - 184, cx + 184, cy + 184,
            outline="#0d2035",
            width=1,
        )

        self._make_particles()

        for _ in self.particles:
            item = self.canvas.create_oval(0, 0, 0, 0, outline="", fill="#163050")
            self.particle_items.append(item)

        self.ako_text = self.canvas.create_text(
            cx,
            cy,
            text="AKO",
            fill="#dff6ff",
            font=("Segoe UI Semibold", 42, "bold"),
            anchor="center",
        )
        self.ako_glow = self.canvas.create_text(
            cx,
            cy,
            text="AKO",
            fill="#66ccff",
            font=("Segoe UI Semibold", 42, "bold"),
            anchor="center",
        )
        self.canvas.tag_lower(self.ako_glow, self.ako_text)

        x1, y1, x2, y2 = self.canvas.bbox(self.ako_text)
        pad = 12
        self.text_bbox = (x1 - pad, y1 - pad, x2 + pad, y2 + pad)
        self.text_mask = self.canvas.create_rectangle(
            x1 - pad, y1 - pad, x2 + pad, y2 + pad,
            fill="#02040a",
            outline="",
        )

        self.status_text = self.canvas.create_text(
            cx,
            cy + 122,
            text=BOOT_STEPS[0],
            fill="#86bde0",
            font=("Consolas", 11, "bold"),
            anchor="center",
        )

        self.ready_text = self.canvas.create_text(
            cx,
            cy + 154,
            text="",
            fill="#cfefff",
            font=("Segoe UI", 13, "bold"),
            anchor="center",
        )

        self.percent_text = self.canvas.create_text(
            cx,
            h - 86,
            text="00%",
            fill="#7fc8ff",
            font=("Consolas", 10, "bold"),
            anchor="center",
        )

        self.bar_bg = self.canvas.create_line(
            cx - 62, h - 64, cx + 62, h - 64,
            fill="#0f2134",
            width=2,
        )
        self.bar_fill = self.canvas.create_line(
            cx - 62, h - 64, cx - 62, h - 64,
            fill="#75d7ff",
            width=2,
        )

        self.dust = []
        for _ in range(45):
            dx = random.randint(0, w)
            dy = random.randint(0, h)
            r = random.choice((1, 1, 1, 2))
            c = random.choice(("#061220", "#0b1930", "#10203b", "#173058"))
            self.dust.append(
                self.canvas.create_oval(dx - r, dy - r, dx + r, dy + r, outline="", fill=c)
            )

    def _make_particles(self):
        self.particles.clear()
        random.seed(7)

        for _ in range(240):
            u = random.random()
            v = random.random()

            theta = 2 * math.pi * u
            phi = math.acos(2 * v - 1)

            radius = 155 + random.uniform(-8, 8)

            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.cos(phi)
            z = radius * math.sin(phi) * math.sin(theta)

            self.particles.append(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "size": random.uniform(1.0, 2.6),
                    "bias": random.uniform(0.75, 1.25),
                }
            )

    # ------------------------------------------------------------
    # animation
    # ------------------------------------------------------------
    def _tick(self):
        if not hasattr(self, "canvas") or not hasattr(self, "particles"):
            self.after(33, self._tick)
            return

        if self._done:
            return

        self.phase += 0.045
        self.rot += 0.018

        self._animate_rings()
        self._animate_particles()
        self._animate_text_reveal()
        self._animate_glow()

        self.after(33, self._tick)

    def _animate_rings(self):
        cx, cy = self.cx, self.cy

        outer_pulse = math.sin(self.phase * 1.2) * 2.5
        inner_pulse = math.sin(self.phase * 1.6 + 0.7) * 1.5

        self.canvas.coords(
            self.outer_ring,
            cx - (165 + outer_pulse), cy - (165 + outer_pulse),
            cx + (165 + outer_pulse), cy + (165 + outer_pulse),
        )
        self.canvas.coords(
            self.inner_ring,
            cx - (82 + inner_pulse), cy - (82 + inner_pulse),
            cx + (82 + inner_pulse), cy + (82 + inner_pulse),
        )

        t = 0.55 + 0.45 * ((math.sin(self.phase) + 1) / 2)
        outer = self._blend("#2f5d86", "#c7f5ff", t)
        inner = self._blend("#233c8c", "#4e8bff", 0.45 + 0.4 * ((math.sin(self.phase * 1.3) + 1) / 2))

        self.canvas.itemconfigure(self.outer_ring, outline=outer)
        self.canvas.itemconfigure(self.inner_ring, outline=inner)

    def _animate_particles(self):
        cx, cy = self.cx, self.cy
        perspective = 520
        reveal = self._segment(self.progress, 4, 72)

        for p, item in zip(self.particles, self.particle_items):
            x = p["x"]
            y = p["y"]
            z = p["z"]

            ry = self.rot * p["bias"]
            x1 = x * math.cos(ry) + z * math.sin(ry)
            z1 = -x * math.sin(ry) + z * math.cos(ry)

            wobble = math.sin(self.phase * 2.1 + x1 * 0.02 + y * 0.02) * 10.0 * reveal
            z1 += wobble

            rx = 0.65 + math.sin(self.phase * 0.7) * 0.04
            y2 = y * math.cos(rx) - z1 * math.sin(rx)
            z2 = y * math.sin(rx) + z1 * math.cos(rx)

            scale = perspective / (perspective + z2 + 260)
            sx = cx + x1 * scale
            sy = cy + y2 * scale

            depth = max(0.0, min(1.0, (z2 + 190) / 380))
            light = 0.15 + 0.85 * depth * reveal

            size = p["size"] * scale * (0.8 + 0.5 * reveal)
            size = max(0.8, min(3.2, size))

            color = self._blend("#0b1830", "#82e7ff", light)

            self.canvas.coords(item, sx - size, sy - size, sx + size, sy + size)
            self.canvas.itemconfigure(item, fill=color)

    def _animate_text_reveal(self):
        x1, y1, x2, y2 = self.text_bbox
        t = self._segment(self.progress, 34, 86)

        cover_left = x1 + (x2 - x1) * t
        self.canvas.coords(self.text_mask, cover_left, y1, x2, y2)

        glow_mix = self._segment(self.progress, 52, 100)
        self.canvas.itemconfigure(self.ako_glow, fill=self._blend("#0e2540", "#66d8ff", glow_mix))
        self.canvas.itemconfigure(self.ako_text, fill=self._blend("#163150", "#e8fbff", glow_mix))

        offset = math.sin(self.phase * 2.4) * 1.2
        self.canvas.coords(self.ako_glow, self.cx, self.cy + offset)
        self.canvas.coords(self.ako_text, self.cx, self.cy)

    def _animate_glow(self):
        breathe = (math.sin(self.phase * 0.9) + 1) / 2

        ring_color = self._blend("#061120", "#0f2a48", 0.35 + 0.45 * breathe)
        self.canvas.itemconfigure(self.bar_bg, fill=ring_color)

        if self.progress >= 84:
            ready_mix = self._segment(self.progress, 84, 100)
            ready_color = self._blend("#17324f", "#dff8ff", ready_mix)
            self.canvas.itemconfigure(self.ready_text, text="AKO IS READY", fill=ready_color)

    # ------------------------------------------------------------
    # progress
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
        self.canvas.coords(self.bar_fill, self.cx - 62, self.h - 64, bar_end, self.h - 64)

        if self.progress >= 100:
            self._done = True
            self.after(500, self._finish)
            return

        delay = 75 if self.progress < 70 else 95
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
        return f"#{r:02x}{g:02x}{b:02x}"

    def _hex_to_rgb(self, value: str):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))