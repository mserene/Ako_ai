from __future__ import annotations

import os
import sys
import tkinter as tk
import threading  

from loading_overlay import LoadingOverlay
from core.controller import AkoController


def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)


class RoundIconButton(tk.Canvas):
    def __init__(
        self,
        master,
        command,
        size=42,
        bg="#f2f4ff",
        fg="#0c0f1a",
        hover_bg="#ffffff",
        disabled_bg="#555a70",
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=master.cget("bg"),
            highlightthickness=0,
            bd=0,
        )
        self.command = command
        self.size = size
        self.bg_color = bg
        self.fg_color = fg
        self.hover_bg = hover_bg
        self.disabled_bg = disabled_bg
        self.enabled = True
        self._pressed = False

        self._draw(bg)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self, fill):
        self.delete("all")
        pad = 2
        self.create_oval(
            pad,
            pad,
            self.size - pad,
            self.size - pad,
            fill=fill,
            outline="",
        )
        cx = self.size / 2
        cy = self.size / 2
        self.create_polygon(
            cx - 5, cy - 7,
            cx + 8, cy,
            cx - 5, cy + 7,
            fill=self.fg_color,
            outline="",
        )

    def configure_state(self, enabled: bool):
        self.enabled = enabled
        self._draw(self.bg_color if enabled else self.disabled_bg)

    def _on_enter(self, _event):
        if self.enabled and not self._pressed:
            self._draw(self.hover_bg)

    def _on_leave(self, _event):
        if self.enabled and not self._pressed:
            self._draw(self.bg_color)

    def _on_press(self, _event):
        if self.enabled:
            self._pressed = True
            self._draw(self.hover_bg)

    def _on_release(self, event):
        if not self.enabled:
            return

        inside = 0 <= event.x <= self.size and 0 <= event.y <= self.size
        self._pressed = False
        self._draw(self.hover_bg if inside else self.bg_color)

        if inside and self.command:
            self.command()


class AkoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        try:
            self.iconbitmap(resource_path(os.path.join("assets", "ako.ico")))
        except Exception:
            pass

        self.title("Ako")
        self.geometry("940x680")
        self.minsize(860, 600)
        self.configure(bg="#090b14")

        self.colors = {
            "bg": "#090b14",
            "panel": "#101321",
            "panel_2": "#151a2b",
            "border": "#2a2f4b",
            "text": "#eceefe",
            "muted": "#a7adc9",
            "accent": "#ab8dff",
            "accent_soft": "#241f45",
            "entry_bg": "#23252d",
            "entry_fg": "#f3f4ff",
            "log_bg": "#0c0f1b",
            "chip_on_bg": "#241f45",
            "chip_on_fg": "#ab8dff",
            "chip_off_bg": "#151a2b",
            "chip_off_fg": "#a7adc9",
        }

        self.controller = AkoController(log_fn=self._append_log)
        self.loading_overlay: LoadingOverlay | None = None

        self._placeholder_text = "메시지 입력..."
        self._placeholder_active = True

        self._build_ui()
        self._refresh_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._start_loading_overlay()
        self.deiconify()

    def _start_loading_overlay(self):
        self.loading_overlay = LoadingOverlay(
            self,
            on_done=self._finish_loading_overlay,
            video_path=os.path.join("assets", "loading", "ako_loading.mp4"),
        )

    def _finish_loading_overlay(self):
        self.loading_overlay = None

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
            text="대화 인터페이스",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w", pady=(4, 0))

        tk.Label(
            header_left,
            text="명령도 실행하고 일상대화도 가능한 채팅 화면",
            bg=self.colors["bg"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(6, 0))

        right = tk.Frame(header, bg=self.colors["bg"])
        right.pack(side="right")

        self.power_chip = tk.Label(
            right,
            text="꺼짐",
            bg=self.colors["chip_off_bg"],
            fg=self.colors["chip_off_fg"],
            font=("Segoe UI Semibold", 10),
            padx=16,
            pady=8,
        )
        self.power_chip.pack(side="right")

        self.power_btn = tk.Button(
            right,
            text="전원 켜기",
            command=self._toggle_power,
            bg="#ab8dff",
            fg="#0b0b14",
            activebackground="#bea7ff",
            activeforeground="#0b0b14",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            highlightthickness=0,
        )
        self.power_btn.pack(side="right", padx=(0, 10))

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

        top_info = tk.Frame(main_panel, bg=self.colors["panel"])
        top_info.pack(fill="x", pady=(0, 12))

        self.status_line = tk.Label(
            top_info,
            text="전원 꺼짐",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.status_line.pack(side="left", fill="x", expand=True)

        self.clear_btn = tk.Button(
            top_info,
            text="대화 지우기",
            command=self._clear_log,
            bg="#1b1f34",
            fg="#f3f4ff",
            activebackground="#2a3050",
            activeforeground="#f3f4ff",
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            font=("Segoe UI Semibold", 9),
            cursor="hand2",
            highlightthickness=0,
        )
        self.clear_btn.pack(side="right")

        log_wrap = tk.Frame(
            main_panel,
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
            padx=16,
            pady=16,
            font=("Consolas", 10),
        )
        self.log_text.pack(fill="both", expand=True)

        bottom = tk.Frame(root, bg=self.colors["bg"])
        bottom.pack(fill="x", pady=(14, 0))

        input_shell = tk.Frame(
            bottom,
            bg=self.colors["entry_bg"],
            highlightbackground="#3a3d49",
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=10,
        )
        input_shell.pack(fill="x")

        self.msg_entry = tk.Entry(
            input_shell,
            bg=self.colors["entry_bg"],
            fg=self.colors["muted"],
            insertbackground=self.colors["text"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 12),
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=(2, 10), ipady=6)
        self.msg_entry.bind("<Return>", lambda e: self._send_message())
        self.msg_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.msg_entry.bind("<FocusOut>", self._on_entry_focus_out)

        self._set_placeholder()

        self.send_btn = RoundIconButton(
            input_shell,
            command=self._send_message,
            size=40,
            bg="#f2f4ff",
            fg="#0c0f1a",
            hover_bg="#ffffff",
            disabled_bg="#666b88",
        )
        self.send_btn.pack(side="right")

    def _set_placeholder(self):
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, self._placeholder_text)
        self.msg_entry.configure(fg=self.colors["muted"])
        self._placeholder_active = True

    def _clear_placeholder(self):
        if self._placeholder_active:
            self.msg_entry.delete(0, "end")
            self.msg_entry.configure(fg=self.colors["entry_fg"])
            self._placeholder_active = False

    def _on_entry_focus_in(self, _event):
        self._clear_placeholder()

    def _on_entry_focus_out(self, _event):
        if not self.msg_entry.get().strip():
            self._set_placeholder()

    def _append_log(self, line: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        if hasattr(self.controller, "clear_chat_history"):
            self.controller.clear_chat_history()

    def _toggle_power(self):
        self.controller.toggle_power()
        self._refresh_ui()

    def _send_message(self):
        text = self.msg_entry.get().strip()
        if self._placeholder_active or not text:
            return

        self.msg_entry.delete(0, "end")
        self.msg_entry.configure(fg=self.colors["entry_fg"])
        self._placeholder_active = False

        self._append_log(f"[나] {text}")
        self.status_line.configure(text="메시지 처리 중...")

        self._handle_message(text)
        self.msg_entry.focus_set()

    def _handle_message(self, text: str):
        """명령어는 즉시 처리, 일반 대화는 논블로킹 스트리밍으로 처리."""
        try:
            handled = False
            if hasattr(self.controller, "is_command_text"):
                try:
                    handled = bool(self.controller.is_command_text(text))
                except Exception:
                    handled = False
            else:
                command_hints = [
                    "열어", "켜", "꺼", "실행", "재생", "눌러", "클릭", "검색",
                    "닫아", "삭제", "입력", "가줘", "가자", "해줘",
                ]
                handled = any(k in text for k in command_hints)

            if handled:
                # 명령어: 기존 방식 유지 (이미 빠름)
                self.controller.handle_text_command(text)
                self.status_line.configure(text="명령 실행 완료")
                return

            # 일반 대화: 비동기 스트리밍
            self._start_chat_async(text)

        except Exception as e:
            self._append_log(f"[오류] {e}")
            self.status_line.configure(text="오류 발생")
            self._set_input_enabled(True)

    # ── 스트리밍 대화 관련 메서드 ──────────────────────────────────────────

    def _set_input_enabled(self, enabled: bool):
        """입력창·전송 버튼 활성/비활성 토글."""
        if enabled and self.controller.powered_on:
            self.msg_entry.configure(state="normal")
            self.send_btn.configure_state(True)
            if self._placeholder_active:
                self.msg_entry.configure(fg=self.colors["muted"])
            else:
                self.msg_entry.configure(fg=self.colors["entry_fg"])
        else:
            self.msg_entry.configure(state="disabled")
            self.send_btn.configure_state(False)

    def _start_chat_async(self, text: str):
        """별도 스레드에서 스트리밍 chat을 시작하고 GUI는 즉시 반환."""
        self.status_line.configure(text="[아코] 생각 중...")
        self._set_input_enabled(False)

        # 로그창에 "[아코] " 접두어 미리 삽입해두고 토큰을 이어 붙일 준비
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "[아코] ")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

        threading.Thread(
            target=self._chat_stream_worker,
            args=(text,),
            daemon=True,
            name="AkoChatStream",
        ).start()

    def _chat_stream_worker(self, text: str):
        """백그라운드 스레드: 토큰을 받을 때마다 GUI 업데이트 예약."""
        try:
            for chunk in self.controller.chat_stream(text):
                # after(0, ...) → tkinter 메인 루프에 안전하게 콜백 전달
                self.after(0, self._on_stream_chunk, chunk)
        except Exception as e:
            self.after(0, self._on_stream_error, str(e))
        finally:
            self.after(0, self._on_stream_done)

    def _on_stream_chunk(self, chunk: str):
        """메인 스레드: 토큰 청크를 로그창에 실시간 추가."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", chunk)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _on_stream_done(self):
        """메인 스레드: 스트리밍 완료 후 정리."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self.status_line.configure(text="대기 중")
        self._set_input_enabled(True)
        self.msg_entry.focus_set()

    def _on_stream_error(self, error: str):
        """메인 스레드: 스트림 중 에러 처리."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"\n[오류] {error}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self.status_line.configure(text="오류 발생")
        self._set_input_enabled(True)

    def _refresh_ui(self):
        on = self.controller.powered_on

        self.power_btn.configure(text="전원 끄기" if on else "전원 켜기")

        if not on:
            self.power_chip.configure(
                text="꺼짐",
                bg=self.colors["chip_off_bg"],
                fg=self.colors["chip_off_fg"],
            )
            self.msg_entry.configure(state="disabled")
            self.send_btn.configure_state(False)
            self.status_line.configure(text="전원 꺼짐")
        else:
            self.power_chip.configure(
                text="켜짐",
                bg=self.colors["chip_on_bg"],
                fg=self.colors["chip_on_fg"],
            )
            self.msg_entry.configure(state="normal")
            self.send_btn.configure_state(True)

            if self._placeholder_active:
                self.msg_entry.configure(fg=self.colors["muted"])
            else:
                self.msg_entry.configure(fg=self.colors["entry_fg"])

            if self.status_line.cget("text") in ("전원 꺼짐", "대기 중"):
                self.status_line.configure(text="대기 중")

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
