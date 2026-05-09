from __future__ import annotations

import tkinter as tk
from typing import Any

from src.utils import format_size, format_time

BG_COLOR = "#f5f5f5"
CARD_BG = "#ffffff"
ACCENT = "#4a90d9"
ACCENT_HOVER = "#357abd"
TEXT_PRIMARY = "#1a1a1a"
TEXT_SECONDARY = "#666666"
SUCCESS = "#2ecc71"
WARNING = "#f39c12"
ERROR = "#e74c3c"
BORDER = "#e0e0e0"
WARN_BG = "#fef9e7"
WARN_BORDER = "#f9e79f"
RECOMMEND_BORDER = "#2ecc71"
RECOMMEND_BG = "#eafaf1"


_format_size = format_size
_format_time = format_time


def expiry_label(expires_at: str | None) -> tuple[str, str]:
    if not expires_at:
        return "✅ 永久", SUCCESS
    import datetime

    try:
        dt_str = expires_at[:19]
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        now = datetime.datetime.now()
        delta = dt - now
        if delta.total_seconds() <= 0:
            return "🔴 已过期", ERROR
        days = delta.days
        if days <= 3:
            return f"⚠️ {days}天后", WARNING
        if days <= 7:
            return f"🟡 {days}天后", "#f39c12"
        return f"🟢 {days}天后", SUCCESS
    except Exception:
        return "-", TEXT_SECONDARY


class StatusBadge(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=12, height=12, highlightthickness=0, **kwargs)
        self._color = SUCCESS
        self._draw()

    def set_status(self, color: str):
        self._color = color
        self._draw()

    def _draw(self):
        self.delete("all")
        self.create_oval(1, 1, 11, 11, fill=self._color, outline="")


class ProgressBar(tk.Frame):
    def __init__(self, parent, width=300, height=6, **kwargs):
        super().__init__(parent, **kwargs)
        self._width = width
        self._height = height
        self._canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0, bg=BORDER)
        self._canvas.pack()
        self._bar = self._canvas.create_rectangle(0, 0, 0, height, fill=ACCENT, width=0)

    def set_progress(self, pct: float):
        w = int(self._width * min(max(pct, 0), 1))
        self._canvas.coords(self._bar, 0, 0, w, self._height)

    def set_indeterminate(self):
        self._canvas.coords(self._bar, 0, 0, self._width // 3, self._height)


class LogLine(tk.Frame):
    def __init__(self, parent, text: str, **kwargs):
        super().__init__(parent, bg=CARD_BG, **kwargs)
        lbl = tk.Label(self, text=text, fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w", font=("Menlo", 10))
        lbl.pack(side="left", fill="x", padx=8)


class WarningBanner(tk.Frame):
    def __init__(self, parent, text: str, icon: str = "⚠️", **kwargs):
        super().__init__(parent, bg=WARN_BG, highlightbackground=WARN_BORDER, highlightthickness=1, **kwargs)
        inner = tk.Frame(self, bg=WARN_BG)
        inner.pack(fill="x", padx=12, pady=10)
        tk.Label(inner, text=icon, fg=TEXT_PRIMARY, bg=WARN_BG, font=("Helvetica", 12)).pack(side="left", padx=(0, 8))
        tk.Label(
            inner, text=text, fg=TEXT_SECONDARY, bg=WARN_BG, font=("Helvetica", 10), anchor="w", justify="left"
        ).pack(side="left", fill="x")


class SectionLabel(tk.Frame):
    def __init__(self, parent, text: str, **kwargs):
        super().__init__(parent, bg=BG_COLOR, **kwargs)
        lbl = tk.Label(self, text=text, fg=TEXT_PRIMARY, bg=BG_COLOR, anchor="w", font=("Helvetica", 11, "bold"))
        lbl.pack(side="left", padx=16, pady=(12, 4))


class Card(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1, **kwargs)


class PrimaryButton(tk.Button):
    def __init__(self, parent: tk.Widget, text: str, command: Any = None, **kwargs: Any) -> None:
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_HOVER,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Helvetica", 11),
            **kwargs,
        )


class SecondaryButton(tk.Button):
    def __init__(self, parent: tk.Widget, text: str, command: Any = None, **kwargs: Any) -> None:
        super().__init__(
            parent,
            text=text,
            command=command,
            bg="white",
            fg=TEXT_PRIMARY,
            activebackground="#e8e8e8",
            activeforeground=TEXT_PRIMARY,
            relief="solid",
            bd=1,
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Helvetica", 11),
            **kwargs,
        )


class DangerButton(tk.Button):
    def __init__(self, parent: tk.Widget, text: str, command: Any = None, **kwargs: Any) -> None:
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=ERROR,
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            font=("Helvetica", 11),
            **kwargs,
        )
