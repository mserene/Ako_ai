from __future__ import annotations

import tkinter as tk
import os
import sys
from tkinter import ttk, filedialog, messagebox

from core.controller import AkoController
from core.config import load_config, save_config, is_writable_dir
from voice_loop import VoiceConfig


def resource_path(rel_path: str) -> str:
    """PyInstaller(onedir/onefile) 모두 대응"""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class AkoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            self.iconbitmap(resource_path(os.path.join("assets", "ako.ico")))
        except Exception:
            pass
        self.title("Ako")
        self.geometry("620x420")
        self.minsize(620, 420)

        self.controller = AkoController(log_fn=self._append_log)

        # load persistent config
        self.cfg, self.cfg_path = load_config()
        self.controller.set_models_root(self.cfg.effective_model_dir)

        # ---------- styles ----------
        try:
            style = ttk.Style(self)
            if "vista" in style.theme_names():
                style.theme_use("vista")
        except Exception:
            pass

        # ---------- layout ----------
        self._build_top()
        self._build_modes()
        self._build_command()
        self._build_log()

        self._refresh_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- model dir handlers ---- (중복 제거: 단일 구현으로 통합)
    def on_change_model_dir(self):
        chosen = filedialog.askdirectory(title="모델 저장 폴더 선택")
        if not chosen:
            return

        # 선택 폴더 검증 (쓰기 불가면 config 건드리지 않고 기본값 유지)
        if not is_writable_dir(chosen):
            messagebox.showerror("폴더 오류", "선택한 폴더에 저장할 수 없어요.\n기본 경로를 계속 사용할게요.")
            self._append_log(f"[MODEL] 적용 실패(쓰기 불가): {chosen}")
            if hasattr(self, "model_path_var"):
                self.model_path_var.set(self.cfg.effective_model_dir)
            return

        # 저장 + 적용
        self.cfg.model_dir = chosen
        save_config(self.cfg, self.cfg_path)

        eff = self.cfg.effective_model_dir
        self.controller.set_models_root(eff)
        if hasattr(self, "model_path_var"):
            self.model_path_var.set(eff)

        self._append_log(f"[MODEL] 저장 위치 변경: {eff}")
        self._refresh_ui()

    def on_reset_model_dir(self):
        self.cfg.model_dir = ""
        save_config(self.cfg, self.cfg_path)

        eff = self.cfg.effective_model_dir
        self.controller.set_models_root(eff)
        if hasattr(self, "model_path_var"):
            self.model_path_var.set(eff)

        self._append_log(f"[MODEL] 기본값으로 재설정: {eff}")
        self._refresh_ui()

    # ---------------- UI blocks ----------------
    def _build_top(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        self.power_var = tk.StringVar(value="OFF")
        ttk.Label(top, text="전원:", font=("Segoe UI", 12)).pack(side="left")
        self.power_badge = ttk.Label(top, textvariable=self.power_var, font=("Segoe UI", 12, "bold"))
        self.power_badge.pack(side="left", padx=(8, 16))

        self.power_btn = ttk.Button(top, text="전원 켜기", command=self._toggle_power)
        self.power_btn.pack(side="right")

    def _build_modes(self):
        box = ttk.LabelFrame(self, text="기능 스위치", padding=12)
        box.pack(fill="x", padx=12, pady=(0, 10))

        self.voice_var = tk.BooleanVar(value=False)
        self.cmd_var = tk.BooleanVar(value=False)

        self.voice_chk = ttk.Checkbutton(box, text="음성 인식", variable=self.voice_var, command=self._toggle_voice)
        self.voice_chk.pack(side="left")

        self.cmd_chk = ttk.Checkbutton(box, text="명령창(채팅)", variable=self.cmd_var, command=self._toggle_cmd)
        self.cmd_chk.pack(side="left", padx=(16, 0))

        # 음성 옵션
        opt = ttk.Frame(box)
        opt.pack(side="right")

        ttk.Label(opt, text="Wake:").pack(side="left")
        self.wake_entry = ttk.Entry(opt, width=10)
        self.wake_entry.insert(0, "아코")
        self.wake_entry.pack(side="left", padx=(6, 12))

        ttk.Label(opt, text="Model:").pack(side="left")
        self.model_entry = ttk.Entry(opt, width=10)
        self.model_entry.insert(0, "small")
        self.model_entry.pack(side="left", padx=(6, 0))

        # 모델 저장 위치
        path_row = ttk.Frame(box)
        path_row.pack(fill="x", pady=(10, 0))
        ttk.Label(path_row, text="모델 저장 위치:").pack(side="left")
        self.model_path_var = tk.StringVar(value=self.cfg.effective_model_dir)
        ttk.Label(path_row, textvariable=self.model_path_var).pack(side="left", padx=(8, 8), fill="x", expand=True)
        ttk.Button(path_row, text="변경", command=self.on_change_model_dir).pack(side="right", padx=(6, 0))
        ttk.Button(path_row, text="기본값", command=self.on_reset_model_dir).pack(side="right", padx=(6, 0))

    def _build_command(self):
        box = ttk.LabelFrame(self, text="명령 입력", padding=12)
        box.pack(fill="x", padx=12, pady=(0, 10))

        row = ttk.Frame(box)
        row.pack(fill="x")

        self.cmd_entry = ttk.Entry(row)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda e: self._send_command())

        self.send_btn = ttk.Button(row, text="보내기", command=self._send_command)
        self.send_btn.pack(side="left", padx=(8, 0))

        self.hint = ttk.Label(box, text="예: 크롬 켜줘 / 유튜브 재생 눌러줘 / 오른쪽에 있는 닫기 눌러줘")
        self.hint.pack(anchor="w", pady=(8, 0))

    def _build_log(self):
        box = ttk.LabelFrame(self, text="로그", padding=12)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log_text = tk.Text(box, wrap="word", height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        btns = ttk.Frame(box)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="로그 지우기", command=self._clear_log).pack(side="right")

    # ---------------- actions ----------------
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
        if not self.controller.powered_on:
            self.voice_var.set(False)
            self.cmd_var.set(False)
        else:
            self.cmd_var.set(True)
        self._refresh_ui()

    def _toggle_voice(self):
        if self.voice_var.get():
            cfg = VoiceConfig(
                wake_word=self.wake_entry.get().strip(),
                model=self.model_entry.get().strip() or "small",
                language="ko",
            )
            self.controller.set_voice(True, cfg=cfg)
        else:
            self.controller.set_voice(False)
        self._refresh_ui()

    def _toggle_cmd(self):
        self.controller.set_command(bool(self.cmd_var.get()))
        self._refresh_ui()

    def _send_command(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return
        self.cmd_entry.delete(0, "end")
        self._append_log(f"[나] {text}")
        self.controller.handle_text_command(text)
        self._refresh_ui()

    def _refresh_ui(self):
        on = self.controller.powered_on
        self.power_var.set("ON" if on else "OFF")
        self.power_btn.configure(text="전원 끄기" if on else "전원 켜기")

        state = "normal" if on else "disabled"
        self.voice_chk.configure(state=state)
        self.cmd_chk.configure(state=state)
        self.wake_entry.configure(state=state)
        self.model_entry.configure(state=state)

        cmd_state = "normal" if (on and self.controller.command_on) else "disabled"
        self.cmd_entry.configure(state=cmd_state)
        self.send_btn.configure(state=cmd_state)

        if not on:
            self.voice_var.set(False)
            self.cmd_var.set(False)
        else:
            self.voice_var.set(bool(self.controller.voice_on))
            self.cmd_var.set(bool(self.controller.command_on))

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
