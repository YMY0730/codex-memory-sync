import tkinter as tk
from tkinter import messagebox

from src.daemon import (
    add_log_listener,
    daemon_status,
    do_pull,
    do_push,
    do_sync,
    remove_log_listener,
    start_daemon,
    stop_daemon,
)

from .widgets import (
    BG_COLOR,
    BORDER,
    CARD_BG,
    TEXT_SECONDARY,
    LogLine,
    PrimaryButton,
    SecondaryButton,
    SectionLabel,
)


class SyncTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_COLOR)
        self._app = app
        self._log_widgets: list[LogLine] = []

        SectionLabel(self, text="🔄 同步操作").pack(fill="x")

        btn_card = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        btn_card.pack(fill="x", padx=16, pady=(8, 0))

        btn_row1 = tk.Frame(btn_card, bg=CARD_BG)
        btn_row1.pack(fill="x", padx=12, pady=(12, 6))
        PrimaryButton(btn_row1, text="🔄 完整同步", command=self._do_sync).pack(side="left", padx=(0, 8))
        SecondaryButton(btn_row1, text="📤 仅推送", command=self._do_push).pack(side="left", padx=(0, 8))
        SecondaryButton(btn_row1, text="📥 仅拉取", command=self._do_pull).pack(side="left")

        SectionLabel(self, text="🤖 自动同步").pack(fill="x")

        auto_card = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        auto_card.pack(fill="x", padx=16, pady=(8, 0))

        auto_row = tk.Frame(auto_card, bg=CARD_BG)
        auto_row.pack(fill="x", padx=12, pady=12)

        self._daemon_var = tk.BooleanVar(value=False)
        self._daemon_btn = PrimaryButton(auto_row, text="🟢 开启自动监听", command=self._toggle_daemon)
        self._daemon_btn.pack(side="left", padx=(0, 8))

        self._daemon_status_var = tk.StringVar(value="守护进程未运行")
        tk.Label(
            auto_row,
            textvariable=self._daemon_status_var,
            fg=TEXT_SECONDARY,
            bg=CARD_BG,
            anchor="w",
            font=("Helvetica", 10),
        ).pack(side="left")

        SectionLabel(self, text="📋 同步日志").pack(fill="x")

        log_card = tk.Frame(self, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        log_card.pack(fill="both", expand=True, padx=16, pady=8)

        self._log_canvas = tk.Canvas(log_card, bg=CARD_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(log_card, orient="vertical", command=self._log_canvas.yview)
        self._log_frame = tk.Frame(self._log_canvas, bg=CARD_BG)
        self._log_frame.bind(
            "<Configure>", lambda e: self._log_canvas.configure(scrollregion=self._log_canvas.bbox("all"))
        )
        self._log_canvas.create_window((0, 0), window=self._log_frame, anchor="nw")
        self._log_canvas.configure(yscrollcommand=scrollbar.set)
        self._log_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        add_log_listener(self._on_log)
        self._add_log("📋 同步日志已就绪")
        self._update_daemon_status()

    def _on_log(self, line: str):
        self.after(0, self._add_log, line)

    def _add_log(self, line: str):
        w = LogLine(self._log_frame, text=line)
        w.pack(fill="x")
        self._log_widgets.append(w)
        if len(self._log_widgets) > 200:
            oldest = self._log_widgets.pop(0)
            oldest.destroy()
        self._log_canvas.yview_moveto(1.0)

    def _do_sync(self):
        self._add_log("🔄 开始完整同步...")
        self.update_idletasks()
        try:
            do_sync()
            self._app._trigger_refresh()
        except Exception as e:
            self._add_log(f"❌ 同步失败: {e}")

    def _do_push(self):
        self._add_log("📤 开始推送...")
        self.update_idletasks()
        try:
            do_push()
            self._app._trigger_refresh()
            messagebox.showinfo("推送成功", "记忆已成功推送到云端")
        except Exception as e:
            self._add_log(f"❌ 推送失败: {e}")

    def _do_pull(self):
        self._add_log("📥 开始拉取...")
        self.update_idletasks()
        try:
            do_pull()
            self._app._trigger_refresh()
            messagebox.showinfo("拉取成功", "已从云端拉取最新记忆")
        except Exception as e:
            self._add_log(f"❌ 拉取失败: {e}")

    def _toggle_daemon(self):
        ds = daemon_status()
        if ds["running"]:
            stop_daemon()
            self._add_log("🔴 守护进程已停止")
        else:
            import threading

            t = threading.Thread(target=start_daemon, daemon=True)
            t.start()
            self._add_log("🟢 守护进程已启动")
        self._update_daemon_status()

    def _update_daemon_status(self):
        ds = daemon_status()
        if ds["running"]:
            self._daemon_btn.configure(text="🔴 停止自动监听")
            self._daemon_status_var.set(f"🟢 运行中 (PID: {ds.get('pid', '?')})")
        else:
            self._daemon_btn.configure(text="🟢 开启自动监听")
            self._daemon_status_var.set("🔴 守护进程未运行")

    def destroy(self):
        remove_log_listener(self._on_log)
        super().destroy()
