from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from src import config
from src.cloud import (
    CloudError,
    NetworkError,
    delete_files,
    download_file,
    find_file_key_by_filename,
    list_cloud_versions,
    unregister_version,
)
from src.importer import DecryptError, import_from_file, preview_encrypted

from .widgets import (
    BG_COLOR,
    CARD_BG,
    ERROR,
    TEXT_SECONDARY,
    WARNING,
    PrimaryButton,
    SecondaryButton,
    SectionLabel,
    _format_size,
    _format_time,
    expiry_label,
)


class CloudTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_COLOR)
        self._app = app
        self._versions: list[dict[str, Any]] = []

        SectionLabel(self, text="☁️ 云端记忆版本").pack(fill="x")

        toolbar = tk.Frame(self, bg=BG_COLOR)
        toolbar.pack(fill="x", padx=16, pady=(8, 0))

        PrimaryButton(toolbar, text="🔄 刷新", command=self._refresh).pack(side="left", padx=(0, 8))
        PrimaryButton(toolbar, text="📥 下载选中", command=self._download_selected).pack(side="left", padx=(0, 8))
        SecondaryButton(toolbar, text="🗑 删除选中", command=self._delete_selected).pack(side="left")

        self._backend_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._backend_var, fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Helvetica", 9)).pack(
            side="right"
        )

        self._status_var = tk.StringVar(value="正在加载...")
        status_lbl = tk.Label(
            self, textvariable=self._status_var, fg=TEXT_SECONDARY, bg=BG_COLOR, anchor="w", font=("Helvetica", 10)
        )
        status_lbl.pack(fill="x", padx=16, pady=(4, 0))

        list_frame = tk.Frame(self, bg=CARD_BG)
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        columns = ("version", "time", "device", "size", "expiry", "hash")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=10)
        self._tree.heading("version", text="版本")
        self._tree.heading("time", text="时间")
        self._tree.heading("device", text="来源设备")
        self._tree.heading("size", text="大小")
        self._tree.heading("expiry", text="到期")
        self._tree.heading("hash", text="Hash")

        self._tree.column("version", width=60, anchor="center")
        self._tree.column("time", width=150, anchor="center")
        self._tree.column("device", width=120, anchor="center")
        self._tree.column("size", width=80, anchor="center")
        self._tree.column("expiry", width=90, anchor="center")
        self._tree.column("hash", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", lambda e: self._download_selected())

        self._tree.tag_configure("expired", foreground="#e74c3c")
        self._tree.tag_configure("expiring", foreground="#f39c12")
        self._tree.tag_configure("safe", foreground="#2ecc71")

        self._refresh()

    def _refresh(self):
        backend = config.get_backend()
        self._backend_var.set(f"后端: {'🐙 GitHub' if backend == 'github' else '☁️ ManbaOut'}")

        self._status_var.set("正在加载...")
        self._tree.delete(*self._tree.get_children())
        try:
            self._versions = list_cloud_versions()
            if not self._versions:
                self._status_var.set("云端暂无版本")
            else:
                latest = self._versions[0]
                self._status_var.set(f"共 {len(self._versions)} 个版本，最新: v{latest.get('version', '?')}")
            for v in self._versions:
                ver = f"v{v.get('version', '?')}"
                t = _format_time(v.get("time", ""))
                dev = v.get("device", "?")[:14]
                size = _format_size(v.get("size", 0))
                h = v.get("hash", "")[:10]
                exp_text, exp_color = expiry_label(v.get("expires_at"))
                if exp_color == ERROR:
                    tag = "expired"
                elif exp_color == WARNING or exp_color == "#f39c12":
                    tag = "expiring"
                else:
                    tag = "safe"
                self._tree.insert("", "end", values=(ver, t, dev, size, exp_text, h), tags=(tag,))
        except (CloudError, NetworkError) as e:
            self._status_var.set(f"❌ 加载失败: {e}")
        except Exception as e:
            self._status_var.set(f"❌ {e}")

    def _get_selected(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个版本")
            return None
        idx = self._tree.index(sel[0])
        if 0 <= idx < len(self._versions):
            return self._versions[idx]
        return None

    def _download_selected(self):
        target = self._get_selected()
        if not target:
            return
        self._do_download(target)

    def _do_download(self, target: dict):
        version = target.get("version", 0)
        filename = target.get("filename", "")
        password = config.get_config_value("security", "encryption_password") or ""

        if not password:
            messagebox.showerror("错误", "未设置加密密码，请先在设置中配置")
            return

        self._status_var.set(f"📥 正在下载 v{version}...")
        self.update_idletasks()

        try:
            key = find_file_key_by_filename(filename)
            if not key:
                key = target.get("hash", "")

            temp_dir = config.CONFIG_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            dest = temp_dir / filename

            download_file(key, dest)

            preview = preview_encrypted(dest.read_bytes(), password)
            info = f"版本: v{preview['version']}\n来源设备: {preview['device']}\n文件数: {preview['file_count']}\n\n文件列表:\n"
            for fn, sz in preview["file_sizes"].items():
                info += f"  • {fn} ({_format_size(sz)})\n"

            if messagebox.askyesno("版本详情", info + "\n是否还原到本地记忆目录？"):
                memory_path = config.get_memory_path()
                result = import_from_file(dest, password, memory_path)
                self._status_var.set(f"✅ 已还原 v{version}，{len(result['restored_files'])} 个文件")
                messagebox.showinfo("成功", f"已还原 v{version}\n{len(result['restored_files'])} 个文件")
                self._app._trigger_refresh()
            dest.unlink(missing_ok=True)
        except DecryptError:
            self._status_var.set("❌ 解密失败，密码不正确")
            messagebox.showerror("解密失败", "密码不正确，请检查设置中的加密密码")
        except Exception as e:
            self._status_var.set(f"❌ 下载失败: {e}")
            messagebox.showerror("下载失败", str(e))

    def _delete_selected(self):
        target = self._get_selected()
        if not target:
            return
        version = target.get("version", 0)
        if not messagebox.askyesno("确认删除", f"确定删除云端 v{version}？此操作不可撤销。"):
            return
        try:
            filename = target.get("filename", "")
            key = find_file_key_by_filename(filename)
            if key:
                delete_files([key])
            unregister_version(version)
            self._status_var.set(f"✅ 已删除 v{version}")
            self._refresh()
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
