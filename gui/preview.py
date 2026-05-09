from __future__ import annotations

import tkinter as tk
from pathlib import Path

from .widgets import (
    ACCENT,
    BORDER,
    CARD_BG,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    _format_size,
    _format_time,
)

PREVIEW_MAX_BYTES = 80 * 1024


def _read_head(file_path: Path, max_lines: int = 60, max_bytes: int = PREVIEW_MAX_BYTES) -> tuple[str, bool]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "(无法读取此文件)", False

    truncated = False
    lines = content.split("\n")
    total = 0
    kept = []
    for line in lines:
        total += len(line.encode("utf-8")) + 1
        if total > max_bytes or len(kept) >= max_lines:
            truncated = True
            break
        kept.append(line)
    return "\n".join(kept), truncated


class PreviewPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1, **kwargs)

        self._header = tk.Frame(self, bg=CARD_BG)
        self._header.pack(fill="x", padx=12, pady=(10, 4))

        self._title_var = tk.StringVar(value="选择文件以预览")
        tk.Label(
            self._header,
            textvariable=self._title_var,
            fg=TEXT_PRIMARY,
            bg=CARD_BG,
            font=("Helvetica", 12, "bold"),
            anchor="w",
        ).pack(side="left")

        self._meta_var = tk.StringVar(value="")
        tk.Label(
            self._header, textvariable=self._meta_var, fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 9), anchor="w"
        ).pack(side="bottom", fill="x", pady=(2, 0))

        sep = tk.Frame(self, height=1, bg=BORDER)
        sep.pack(fill="x", padx=12)

        self._text_frame = tk.Frame(self, bg=CARD_BG)
        self._text_frame.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        self._text = tk.Text(
            self._text_frame,
            wrap="word",
            state="disabled",
            borderwidth=0,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=("Menlo", 10),
            padx=4,
            pady=4,
            cursor="arrow",
        )
        self._text.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(self._text_frame, command=self._text.yview)
        scrollbar.pack(side="right", fill="y")
        self._text.configure(yscrollcommand=scrollbar.set)

        self._truncated_var = tk.StringVar(value="")
        self._truncated_lbl = tk.Label(
            self, textvariable=self._truncated_var, fg="#e67e22", bg=CARD_BG, font=("Helvetica", 9), anchor="w"
        )
        self._truncated_lbl.pack(fill="x", padx=12, pady=(0, 8))

        self._configure_tags()

    def _configure_tags(self):
        self._text.tag_configure("h1", font=("Menlo", 12, "bold"), foreground=ACCENT, spacing1=4, spacing3=2)
        self._text.tag_configure("h2", font=("Menlo", 11, "bold"), foreground=TEXT_PRIMARY, spacing1=4, spacing3=2)
        self._text.tag_configure("h3", font=("Menlo", 10, "bold"), foreground=TEXT_PRIMARY, spacing1=2, spacing3=1)
        self._text.tag_configure("bold", font=("Menlo", 10, "bold"))
        self._text.tag_configure("list", lmargin1=12, lmargin2=20)
        self._text.tag_configure("code", background="#f0f0f0", font=("Menlo", 9))
        self._text.tag_configure("meta", foreground=TEXT_SECONDARY, font=("Menlo", 9))
        self._text.tag_configure("json_key", foreground=ACCENT)

    def show_file(self, file_path: Path, file_name: str = "", is_dir: bool = False, children: list | None = None):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._truncated_var.set("")

        if is_dir:
            self._title_var.set(file_name)
            self._meta_var.set(f"目录 | {len(children or [])} 个文件")
            content = f"📁 {file_name}\n\n"
            for c in children or []:
                content += f"  📄 {c.get('name', '?')}  ({_format_size(c.get('size', 0))})\n"
            self._text.insert("1.0", content, "meta")
        else:
            self._title_var.set(file_name)
            file_size = file_path.stat().st_size

            if file_path.suffix in (".jsonl",):
                self._show_jsonl_preview(file_path, file_name, file_size)
            elif file_path.suffix in (".md",):
                self._show_markdown_preview(file_path, file_name, file_size)
            else:
                self._show_plain_preview(file_path, file_name, file_size)

        self._text.configure(state="disabled")

    def show_session_info(self, info: dict):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._truncated_var.set("")

        thread = info.get("thread_name", "Unknown")
        fname = info.get("name", "?")
        fpath = info.get("path")
        fsize = info.get("size", 0)

        self._title_var.set(thread)
        meta = f"📄 {fname}  |  {_format_size(fsize)}"
        if info.get("updated_at"):
            meta += f"  |  {_format_time(info['updated_at'])}"
        self._meta_var.set(meta)

        if fpath and Path(fpath).exists():
            content, truncated = _read_head(Path(fpath), max_lines=50)
            self._text.insert("1.0", content, "meta")
            if truncated:
                self._truncated_var.set(f"⚠️ 文件较大 ({_format_size(fsize)})，仅展示前 50 行预览")
        else:
            self._text.insert("1.0", "(会话文件未找到)", "meta")

        self._text.configure(state="disabled")

    def show_empty(self, text: str = "选择左侧文件以预览内容"):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._truncated_var.set("")
        self._title_var.set("文件预览")
        self._meta_var.set("")
        self._text.insert("1.0", text, "meta")
        self._text.configure(state="disabled")

    def _show_markdown_preview(self, file_path: Path, file_name: str, file_size: int):
        self._meta_var.set(f"📄 {file_name}  |  {_format_size(file_size)}")

        content, truncated = _read_head(file_path, max_lines=200)
        lines = content.split("\n")
        for line in lines:
            stripped = line.rstrip()
            if stripped.startswith("## "):
                self._text.insert("end", stripped + "\n", "h2")
            elif stripped.startswith("# "):
                self._text.insert("end", stripped + "\n", "h1")
            elif stripped.startswith("### "):
                self._text.insert("end", stripped + "\n", "h3")
            elif stripped.startswith("**") and stripped.endswith("**"):
                self._text.insert("end", stripped + "\n", "bold")
            elif stripped.startswith("- ") or stripped.startswith("* "):
                self._text.insert("end", "  • " + stripped[2:] + "\n", "list")
            elif stripped.startswith("```"):
                self._text.insert("end", stripped + "\n", "code")
            elif stripped.startswith("  ") or stripped.startswith("\t"):
                self._text.insert("end", "  " + stripped.lstrip() + "\n", "code")
            else:
                self._text.insert("end", stripped + "\n")
        if truncated:
            self._truncated_var.set(f"⚠️ 文件较大 ({_format_size(file_size)})，仅展示前半部分预览")

    def _show_jsonl_preview(self, file_path: Path, file_name: str, file_size: int):
        self._meta_var.set(f"📄 {file_name}  |  {_format_size(file_size)}  |  JSONL 会话记录")
        content, truncated = _read_head(file_path, max_lines=60)
        self._text.insert("1.0", content, "meta")
        if truncated:
            self._truncated_var.set(f"⚠️ 文件较大 ({_format_size(file_size)})，仅展示前 60 行预览。选中可导出完整文件。")

    def _show_plain_preview(self, file_path: Path, file_name: str, file_size: int):
        self._meta_var.set(f"📄 {file_name}  |  {_format_size(file_size)}")
        content, truncated = _read_head(file_path, max_lines=200)
        self._text.insert("1.0", content)
        if truncated:
            self._truncated_var.set(f"⚠️ 预览已截断 ({_format_size(file_size)})")
