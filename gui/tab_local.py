from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src import config
from src.cloud import is_cloud_configured, list_cloud_versions
from src.export_local import (
    create_export_zip,
    discover_memories,
    discover_rules,
    discover_sessions,
)
from src.metadata import SyncStatus, compare

from .preview import PreviewPanel
from .widgets import (
    BG_COLOR,
    CARD_BG,
    TEXT_SECONDARY,
    PrimaryButton,
    SecondaryButton,
    SectionLabel,
    _format_size,
)

CODE_DIR = Path.home() / ".codex"
MEMORIES_DIR = CODE_DIR / "memories"
SESSIONS_DIR = CODE_DIR / "sessions"
SESSION_INDEX = CODE_DIR / "session_index.jsonl"
RULES_DIR = CODE_DIR / "rules"


class LocalTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_COLOR)
        self._app = app

        # Selection state: path_str -> True/False
        self._selected: dict[str, bool] = {}
        # Node id -> data mapping
        self._node_data: dict[str, dict] = {}

        SectionLabel(self, text="💻 本地数据").pack(fill="x")

        toolbar = tk.Frame(self, bg=BG_COLOR)
        toolbar.pack(fill="x", padx=16, pady=(8, 0))
        PrimaryButton(toolbar, text="☑ 全选", command=self._select_all).pack(side="left", padx=(0, 4))
        SecondaryButton(toolbar, text="☐ 取消全选", command=self._deselect_all).pack(side="left", padx=(0, 4))
        SecondaryButton(toolbar, text="🔄 刷新", command=self._refresh).pack(side="left")

        self._total_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._total_var, fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Helvetica", 10)).pack(
            side="right"
        )

        # Main split pane
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG_COLOR, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=16, pady=8)

        # Left: file tree
        left = tk.Frame(paned, bg=CARD_BG)
        left.configure(width=280)

        tree_frame = tk.Frame(left, bg=CARD_BG)
        tree_frame.pack(fill="both", expand=True)

        self._tree = ttk.Treeview(tree_frame, columns=("size",), show="tree", selectmode="browse")
        self._tree.heading("#0", text="文件")
        self._tree.column("#0", width=220)
        self._tree.column("size", width=80, anchor="e")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<space>", self._toggle_selection)
        self._tree.bind("<Double-1>", self._toggle_selection)

        # Right: preview
        right_frame = tk.Frame(paned, bg=CARD_BG)
        self._preview = PreviewPanel(right_frame)
        self._preview.pack(fill="both", expand=True, padx=0, pady=0)

        paned.add(left, minsize=200)
        paned.add(right_frame, minsize=300)

        # Bottom
        bottom = tk.Frame(self, bg=BG_COLOR)
        bottom.pack(fill="x", padx=16, pady=(0, 8))

        self._status_var = tk.StringVar(value="")
        tk.Label(
            bottom, textvariable=self._status_var, fg=TEXT_SECONDARY, bg=BG_COLOR, anchor="w", font=("Helvetica", 10)
        ).pack(side="left", fill="x", expand=True)

        PrimaryButton(bottom, text="📦 导出选中", command=self._export_selected).pack(side="right")

        self._refresh()

    def _refresh(self):
        self._tree.delete(*self._tree.get_children())
        self._selected.clear()
        self._node_data.clear()

        self._add_memories()
        self._add_sessions()
        self._add_rules()
        self._update_totals()

        try:
            versions = list_cloud_versions() if is_cloud_configured() else []
        except Exception:
            versions = []
        result = compare(versions)
        status_labels = {
            SyncStatus.SYNCED.value: "✅ 已同步",
            SyncStatus.LOCAL_AHEAD.value: "🟡 待推送",
            SyncStatus.CLOUD_AHEAD.value: "🔵 可拉取",
            SyncStatus.CONFLICT.value: "🔴 冲突",
            SyncStatus.UNINITIALIZED.value: "⚪ 本地模式",
        }
        self._status_var.set(
            f"{status_labels.get(result['status'], '')} | 本地 v{result['local']['version']} | 云端 v{result['cloud']['latest_version']}"
        )

    def _add_memories(self):
        items = discover_memories(MEMORIES_DIR)
        if not items:
            return

        mem_root = self._tree.insert("", "end", text="📁 记忆文件 (~/.codex/memories/)", open=True, tags=("section",))
        default_selected = {"MEMORY.md", "raw_memories.md", "memory_summary.md"}

        for item in items:
            if item.get("is_dir"):
                dir_id = self._tree.insert(mem_root, "end", text=f"📁 {item['name']}", open=True)
                self._node_data[dir_id] = {"type": "dir", "data": item}
                self._selected[dir_id] = False
                for child in item.get("children", []):
                    ch_id = self._tree.insert(
                        dir_id, "end", text=f"☐ {child['name']}", values=(_format_size(child["size"]),)
                    )
                    self._node_data[ch_id] = {"type": "memory", "data": child, "path": child["path"]}
                    is_sel = child.get("name", "") in default_selected or child.get("relative", "") in default_selected
                    self._selected[ch_id] = is_sel
            else:
                fid = self._tree.insert(mem_root, "end", text=f"☐ {item['name']}", values=(_format_size(item["size"]),))
                self._node_data[fid] = {"type": "memory", "data": item, "path": item["path"]}
                is_sel = item.get("name", "") in default_selected
                self._selected[fid] = is_sel

        self._sync_tree_checkmarks(mem_root)

    def _add_sessions(self):
        indexed, unindexed = discover_sessions(SESSIONS_DIR, SESSION_INDEX)
        total_sessions = len(indexed) + len(unindexed)
        if total_sessions == 0:
            return

        total_size = sum(s["size"] for s in indexed) + sum(p.stat().st_size for p in unindexed)
        sess_root = self._tree.insert(
            "", "end", text=f"📁 会话记录 (~/.codex/sessions/ — {_format_size(total_size)})", open=False
        )

        for s in indexed:
            thread = s.get("thread_name", "Unknown")
            fname = s.get("name", "?")
            _ = fname
            size = s["size"]
            size_warn = " ⚠️" if size > 10 * 1024 * 1024 else ""
            sid = self._tree.insert(sess_root, "end", text=f"☐ {thread}{size_warn}", values=(_format_size(size),))
            self._node_data[sid] = {"type": "session", "data": s, "path": s["path"]}
            self._selected[sid] = False

        if unindexed:
            un_root = self._tree.insert(sess_root, "end", text="📁 未索引会话", open=False)
            for p in unindexed:
                uid = self._tree.insert(
                    un_root, "end", text=f"☐ {p.parent.name}/{p.name}", values=(_format_size(p.stat().st_size),)
                )
                self._node_data[uid] = {
                    "type": "session",
                    "data": {
                        "name": p.name,
                        "path": p,
                        "size": p.stat().st_size,
                        "thread_name": f"(未索引) {p.parent.name}/{p.name}",
                        "updated_at": "",
                    },
                    "path": p,
                }
                self._selected[uid] = False

    def _add_rules(self):
        items = discover_rules(RULES_DIR)
        if not items:
            return
        rules_root = self._tree.insert("", "end", text="📁 规则文件 (~/.codex/rules/)", open=False)
        for item in items:
            rid = self._tree.insert(rules_root, "end", text=f"☐ {item['name']}", values=(_format_size(item["size"]),))
            self._node_data[rid] = {"type": "rule", "data": item, "path": item["path"]}
            self._selected[rid] = False

    def _on_tree_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        node_id = sel[0]
        node = self._node_data.get(node_id)
        if not node:
            return

        ntype = node.get("type", "")
        data = node.get("data", {})

        if ntype == "dir":
            self._preview.show_file(
                file_path=data.get("path", Path()),
                file_name=data.get("name", ""),
                is_dir=True,
                children=data.get("children", []),
            )
        elif ntype in ("memory",):
            self._preview.show_file(
                file_path=data.get("path", Path()),
                file_name=data.get("name", ""),
            )
        elif ntype == "session":
            self._preview.show_session_info(data)
        elif ntype == "rule":
            self._preview.show_file(
                file_path=data.get("path", Path()),
                file_name=data.get("name", ""),
            )
        else:
            self._preview.show_empty()

    def _toggle_selection(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return
        node_id = sel[0]
        cur = self._selected.get(node_id, False)
        self._selected[node_id] = not cur
        self._update_totals()

        # Update tree text
        node = self._node_data.get(node_id)
        if node:
            icon = "☑" if self._selected[node_id] else "☐"
            ntype = node.get("type", "")
            data = node.get("data", {})
            if ntype == "session":
                thread = data.get("thread_name", "")
                size = data.get("size", 0)
                size_warn = " ⚠️" if size > 10 * 1024 * 1024 else ""
                self._tree.item(node_id, text=f"{icon} {thread}{size_warn}")
            elif ntype == "dir":
                self._tree.item(node_id, text=f"📁 {data.get('name', '')}")
                for child_id in self._tree.get_children(node_id):
                    ch = self._node_data.get(child_id)
                    if ch:
                        self._sync_single_checkmark(child_id, ch)
            else:
                self._tree.item(node_id, text=f"{icon} {data.get('name', '?')}")

    def _sync_tree_checkmarks(self, parent_id):
        for child_id in self._tree.get_children(parent_id):
            node = self._node_data.get(child_id)
            if node and node.get("type") == "dir":
                self._sync_tree_checkmarks(child_id)
            else:
                self._sync_single_checkmark(child_id, node)

    def _sync_single_checkmark(self, node_id, node):
        if not node:
            return
        icon = "☑" if self._selected.get(node_id, False) else "☐"
        data = node.get("data", {})
        name = data.get("name", "?")
        self._tree.item(node_id, text=f"{icon} {name}")

    def _select_all(self):
        for node_id in self._node_data:
            if self._node_data[node_id].get("type") != "dir":
                self._selected[node_id] = True
        for root_id in self._tree.get_children(""):
            self._sync_tree_checkmarks(root_id)
        self._update_totals()

    def _deselect_all(self):
        for node_id in self._selected:
            self._selected[node_id] = False
        for root_id in self._tree.get_children(""):
            self._sync_tree_checkmarks(root_id)
        self._update_totals()

    def _update_totals(self):
        count = 0
        total_bytes = 0
        for node_id, sel in self._selected.items():
            if not sel:
                continue
            node = self._node_data.get(node_id)
            if not node:
                continue
            if node.get("type") == "dir":
                continue
            count += 1
            data = node.get("data", {})
            total_bytes += data.get("size", 0)
        self._total_var.set(f"已选 {count} 个文件，共 {_format_size(total_bytes)}")

    def _export_selected(self):
        memory_files: list[Path] = []
        session_files: list[Path] = []
        rule_files: list[Path] = []

        for node_id, sel in self._selected.items():
            if not sel:
                continue
            node = self._node_data.get(node_id)
            if not node or node.get("type") == "dir":
                continue
            ntype = node.get("type")
            path = node.get("path")
            if not path or not path.exists():
                continue
            if ntype == "memory":
                memory_files.append(path)
            elif ntype == "session":
                session_files.append(path)
            elif ntype == "rule":
                rule_files.append(path)

        if not memory_files and not session_files and not rule_files:
            messagebox.showinfo("提示", "请先选择要导出的文件")
            return

        total = sum(f.stat().st_size for f in memory_files + session_files + rule_files)
        default_name = f"codex-context-v{config.get_config_value('metadata', 'local_version') or 1}.zip"
        output = filedialog.asksaveasfilename(
            title="导出压缩包",
            defaultextension=".zip",
            filetypes=[("ZIP 压缩包", "*.zip")],
            initialfile=default_name,
        )
        if not output:
            return

        try:
            path = create_export_zip(
                Path(output),
                memory_files,
                session_files,
                rule_files,
                MEMORIES_DIR,
                SESSIONS_DIR,
                RULES_DIR,
            )
            messagebox.showinfo(
                "导出成功",
                f"✅ 已导出 {len(memory_files) + len(session_files) + len(rule_files)} 个文件\n"
                f"📦 {path.name} ({_format_size(total)})\n\n"
                f"将 zip 发送到其他设备，解压后双击 import.sh 即可导入",
            )
        except Exception as e:
            messagebox.showerror("导出失败", str(e))
