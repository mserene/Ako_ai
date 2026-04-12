from __future__ import annotations

import math
import tkinter as tk
from typing import Callable


BOOT_STEPS = [
    "INITIALIZING INTERFACE",
    "LOADING CORE MODULES",
    "SYNCING WORKSPACE",
    "CHECKING VOICE BRIDGE",
    "CALIBRATING HUD",
    "SYSTEM READY",
]


class HudSplash(tk.Tk):
    def __init__(self, on_done: Callable[[], None] | None = None):
        super().__init__()
        self.on_done = on_done

        self.progress = 0
        self.step_index = 0
        self.scan_angle = 0
        self.ring_phase = 0
        self._done = False

        self.overrideredirect(True)
        self.configure(bg="#02070b")
        self.geometry("980x620")
        self.minsize(980, 620)

        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(
            self,
            width=w,
            height=h,
            bg="#02070b",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value=BOOT_STEPS[0])
        self.progress_var = tk.StringVar(value="000%")
        self.small_var = tk.StringVar(value="ADVANCED BOOT SEQUENCE")

        self._build_static()
        self._tick()
        self.after(220, self._advance_progress)

    def _build_static(self):
        w = 980
        h = 620

        self.canvas.create_rectangle(14, 14, w - 14, h - 14, outline="#173943", width=1)
        self.canvas.create_line(14, 14, 42, 14, fill="#6df7ff", width=2)
        self.canvas.create_line(14, 14, 14, 42, fill="#6df7ff", width=2)
        self.canvas.create_line(w - 42, 14, w - 14, 14, fill="#6df7ff", width=2)
        self.canvas.create_line(w - 14, 14, w - 14, 42, fill="#6df7ff", width=2)
        self.canvas.create_line(14, h - 14, 42, h - 14, fill="#6df7ff", width=2)
        self.canvas.create_line(14, h - 42, 14, h - 14, fill="#6df7ff", width=2)
        self.canvas.create_line(w - 42, h - 14, w - 14, h - 14, fill="#6df7ff", width=2)
        self.canvas.create_line(w - 14, h - 42, w - 14, h - 14, fill="#6df7ff", width=2)

        for gx in range(0, w, 48):
            self.canvas.create_line(gx, 0, gx, h, fill="#0a1f25")
        for gy in range(0, h, 48):
            self.canvas.create_line(0, gy, w, gy, fill="#0a1f25")

        self.canvas.create_text(
            650,
            92,
            textvariable=self.small_var,
            fill="#6fefff",
            font=("Consolas", 10, "bold"),
            anchor="w",
        )
        self.canvas.create_text(
            650,
            134,
            text="HUD LOADING",
            fill="#e7feff",
            font=("Segoe UI", 28, "bold"),
            anchor="w",
        )
        self.canvas.create_text(
            650,
            205,
            text="CURRENT TASK",
            fill="#8ecfd6",
            font=("Consolas", 10),
            anchor="w",
        )
        self.canvas.create_text(
            650,
            238,
            textvariable=self.status_var,
            fill="#e8ffff",
            font=("Consolas", 16, "bold"),
            anchor="w",
        )
        self.canvas.create_text(
            650,
            405,
            text="PROGRESS",
            fill="#8ecfd6",
            font=("Consolas", 10),
            anchor="w",
        )
        self.canvas.create_text(
            870,
            405,
            textvariable=self.progress_var,
            fill="#dfffff",
            font=("Consolas", 11, "bold"),
            anchor="e",
        )

        self.canvas.create_rectangle(650, 425, 890, 439, outline="#28434a", width=1)
        self.progress_fill = self.canvas.create_rectangle(
            651, 426, 651, 438, outline="", fill="#78fff0"
        )

        self.canvas.create_rectangle(650, 460, 890, 560, outline="#28434a", width=1)
        self.log_items = []

        cx, cy = 290, 305
        self.cx = cx
        self.cy = cy

        self.canvas.create_oval(cx - 175, cy - 175, cx + 175, cy + 175, outline="#12313a", width=1)
        self.canvas.create_oval(cx - 145, cy - 145, cx + 145, cy + 145, outline="#143743", width=1)
        self.canvas.create_oval(cx - 115, cy - 115, cx + 115, cy + 115, outline="#18454d", width=1)
        self.canvas.create_line(cx - 190, cy, cx + 190, cy, fill="#153039")
        self.canvas.create_line(cx, cy - 190, cx, cy + 190, fill="#153039")

        self.ring1 = self.canvas.create_arc(
            cx - 170, cy - 170, cx + 170, cy + 170,
            start=10, extent=40, style="arc", outline="#7efff0", width=3
        )
        self.ring2 = self.canvas.create_arc(
            cx - 140, cy - 140, cx + 140, cy + 140,
            start=180, extent=55, style="arc", outline="#9ffcff", width=2
        )
        self.ring3 = self.canvas.create_arc(
            cx - 110, cy - 110, cx + 110, cy + 110,
            start=260, extent=36, style="arc", outline="#5ce8ff", width=2
        )

        self.scan_line = self.canvas.create_line(cx, cy, cx + 150, cy, fill="#7efff0", width=2)

        self.core_outer = self.canvas.create_oval(
            cx - 54, cy - 54, cx + 54, cy + 54, outline="#82fff4", width=2
        )
        self.canvas.create_oval(
            cx - 40, cy - 40, cx + 40, cy + 40, outline="#376f75", width=1
        )
        self.canvas.create_text(cx, cy - 10, text="CORE", fill="#9adce0", font=("Consolas", 10, "bold"))
        self.canvas.create_text(cx, cy + 16, text="AKO", fill="#ecffff", font=("Segoe UI", 20, "bold"))

        self.sweep_y = 70
        self.sweep_line = self.canvas.create_line(40, self.sweep_y, 940, self.sweep_y, fill="#5cf3ff", width=1)

    def _draw_logs(self):
        for item in self.log_items:
            self.canvas.delete(item)
        self.log_items.clear()

        visible = BOOT_STEPS[: self.step_index + 1]
        y = 485
        for i, text in enumerate(visible[-4:]):
            code = 100 + i
            item = self.canvas.create_text(
                664,
                y,
                text=f"[{code}] {text}",
                fill="#d7ffff",
                font=("Consolas", 10),
                anchor="w",
            )
            self.log_items.append(item)
            y += 22

    def _tick(self):
        if self._done:
            return

        self.scan_angle = (self.scan_angle + 4) % 360
        self.ring_phase = (self.ring_phase + 3) % 360
        self.sweep_y += 6
        if self.sweep_y > 570:
            self.sweep_y = 60

        self.canvas.itemconfigure(self.ring1, start=self.ring_phase)
        self.canvas.itemconfigure(self.ring2, start=180 - self.ring_phase)
        self.canvas.itemconfigure(self.ring3, start=260 + self.ring_phase)

        rad = math.radians(self.scan_angle)
        x2 = self.cx + math.cos(rad) * 150
        y2 = self.cy + math.sin(rad) * 150
        self.canvas.coords(self.scan_line, self.cx, self.cy, x2, y2)
        self.canvas.coords(self.sweep_line, 40, self.sweep_y, 940, self.sweep_y)

        pulse = 54 + (math.sin(math.radians(self.ring_phase * 3)) * 4)
        self.canvas.coords(
            self.core_outer,
            self.cx - pulse, self.cy - pulse,
            self.cx + pulse, self.cy + pulse
        )

        self.after(33, self._tick)

    def _advance_progress(self):
        if self._done:
            return

        self.progress = min(self.progress + 2, 100)
        idx = min(int((self.progress / 100) * len(BOOT_STEPS)), len(BOOT_STEPS) - 1)
        self.step_index = idx

        self.status_var.set(BOOT_STEPS[self.step_index])
        self.progress_var.set(f"{self.progress:03d}%")
        end_x = 651 + int(238 * (self.progress / 100))
        self.canvas.coords(self.progress_fill, 651, 426, end_x, 438)
        self._draw_logs()

        if self.progress >= 100:
            self._done = True
            self.after(500, self._finish)
            return

        delay = 90 if self.progress < 80 else 120
        self.after(delay, self._advance_progress)

    def _finish(self):
        self.destroy()
        if self.on_done:
            self.on_done()