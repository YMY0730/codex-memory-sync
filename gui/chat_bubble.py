"""chat_bubble.py — Codex 聊天气泡组件（CustomTkinter）

支持消息种类:
  - meta:      会话信息条
  - event:     系统事件 (任务开始/结束, developer prompt 折叠)
  - message:   用户/助手对话气泡
  - thinking:  思考过程（折叠）
  - tool:      工具调用卡片
"""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

C = {
    "user_bg": "#2563EB",
    "user_text": "#FFFFFF",
    "assistant_bg": ("#F3F4F6", "#1F2937"),
    "assistant_text": ("#111827", "#F3F4F6"),
    "thinking_bg": ("#FEF3C7", "#713F12"),
    "thinking_text": ("#92400E", "#FDE68A"),
    "tool_bg": ("#DBEAFE", "#1E3A5F"),
    "tool_text": ("#1E40AF", "#93C5FD"),
    "event_bg": ("#F9FAFB", "#111827"),
    "event_text": ("#9CA3AF", "#6B7280"),
    "meta_bg": ("#EEF2FF", "#312E81"),
    "meta_text": ("#4338CA", "#A5B4FC"),
    "ts": ("#9CA3AF", "#6B7280"),
}


class ChatBubble(ctk.CTkFrame):
    """单条聊天气泡 — 根据 kind 渲染不同样式"""

    def __init__(self, parent, msg: dict[str, Any], **kwargs):
        self.msg = msg
        kind = msg.get("kind", "message")
        role = msg.get("role", "")
        text = msg.get("text", "")
        ts = msg.get("timestamp", "")

        # 选择颜色方案
        if kind == "meta":
            bg, fg = C["meta_bg"], C["meta_text"]
        elif kind == "event":
            bg, fg = C["event_bg"], C["event_text"]
        elif kind == "thinking":
            bg, fg = C["thinking_bg"], C["thinking_text"]
        elif kind == "tool":
            bg, fg = C["tool_bg"], C["tool_text"]
        elif role == "user":
            bg, fg = C["user_bg"], C["user_text"]
        else:  # assistant
            bg, fg = C["assistant_bg"], C["assistant_text"]

        super().__init__(parent, corner_radius=10, fg_color=bg, **kwargs)
        self.bg = bg
        self.fg = fg

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=8)

        # 时间戳
        if ts:
            ctk.CTkLabel(
                inner,
                text=ts,
                font=ctk.CTkFont(size=9),
                text_color=C["ts"],
            ).pack(anchor="w" if role != "user" else "e")

        # 正文
        if text:
            display = text[:4000] + ("\n\n..." if len(text) > 4000 else "")
            ctk.CTkLabel(
                inner,
                text=display,
                font=ctk.CTkFont(size=12),
                text_color=fg,
                wraplength=550,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))

    @staticmethod
    def _trim(text: str, n: int) -> str:
        return text[:n] + ("..." if len(text) > n else "")


class ChatView(ctk.CTkScrollableFrame):
    """聊天时间线视图"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._bubbles: list[ChatBubble] = []

    def load_session(self, messages: list[dict[str, Any]]):
        self.clear()
        for msg in messages:
            # Skip developer prompts unless explicitly needed
            # (they're rendered as "事件" with a summary line)
            b = ChatBubble(self, msg)
            if msg.get("role") == "user":
                b.pack(anchor="e", fill="x", pady=3, padx=20)
            else:
                b.pack(anchor="w", fill="x", pady=3, padx=10)
            self._bubbles.append(b)

    def clear(self):
        for b in self._bubbles:
            b.destroy()
        self._bubbles.clear()
