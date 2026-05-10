"""
app_modern.py — CustomTkinter 精美 UI 实现
设计原则：卡片式布局、圆角现代风、清晰的信息层级、流畅的交互动效
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from src import config
from src.chat_parser import parse_jsonl_session
from src.cloud import (
    CloudError,
    is_cloud_configured,
    list_cloud_versions,
    unregister_version,
)
from src.daemon import daemon_status, do_pull, do_push, do_sync
from src.export_local import (
    create_export_zip,
    discover_memories,
    discover_rules,
    discover_sessions,
)
from src.metadata import compare
from src.path_detector import detect_codex_locations
from src.utils import format_size

from .chat_bubble import ChatView

# --- 常量 -------------------------------------------------------------------
HOME_DIR = Path.home()
MEMORIES_DIR = HOME_DIR / ".codex" / "memories"
SESSIONS_DIR = HOME_DIR / ".codex" / "sessions"
RULES_DIR = HOME_DIR / ".codex" / "rules"
SESSION_INDEX = HOME_DIR / ".codex" / "session_index.jsonl"

# --- 颜色配置 ---------------------------------------------------------------
COLORS = {
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#06B6D4",
    "gray_50": "#F9FAFB",
    "gray_100": "#F3F4F6",
    "gray_200": "#E5E7EB",
    "gray_300": "#D1D5DB",
    "gray_400": "#9CA3AF",
    "gray_500": "#6B7280",
    "gray_600": "#4B5563",
    "gray_700": "#374151",
    "gray_800": "#1F2937",
    "gray_900": "#111827",
}


class ModernApp(ctk.CTk):
    """Codex Memory Sync — 现代精美 GUI"""

    def __init__(self):
        super().__init__()

        self.title("Codex Memory Sync")
        self.geometry("1100x750")
        self.minsize(900, 650)

        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))

        # 配置网格权重，让内容可以自适应
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 加载外观设置
        self._load_appearance()

        # 构建 UI（先展示骨架，数据异步加载）
        self._build_header()
        self._build_main_content()
        self._build_status_bar()

        # 本地模式检查
        self._setup_local_mode()

        # 延迟加载数据，确保窗口先显示
        self.after(100, self._refresh_all)

    def _load_appearance(self):
        """加载并应用外观主题"""
        mode = config.get_config_value("appearance", "mode") or "System"
        theme = config.get_config_value("appearance", "color_theme") or "blue"
        ctk.set_appearance_mode(mode)
        ctk.set_default_color_theme(theme)
        self.current_mode = mode

    def _build_header(self):
        """顶部导航栏 — 简洁现代风格"""
        self.header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header.grid_columnconfigure(1, weight=1)

        # Logo 和标题
        logo_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        ctk.CTkLabel(
            logo_frame,
            text="🧠",
            font=ctk.CTkFont(size=28),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_frame,
            text="Codex Memory Sync",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        # 右侧控制区
        controls = ctk.CTkFrame(self.header, fg_color="transparent")
        controls.grid(row=0, column=2, padx=20, pady=10, sticky="e")

        # 主题切换按钮
        self.theme_btn = ctk.CTkButton(
            controls,
            text="🌙" if self.current_mode == "Light" else "☀️",
            width=40,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color=(COLORS["gray_200"], COLORS["gray_700"]),
            command=self._toggle_theme,
        )
        self.theme_btn.pack(side="right", padx=5)

    def _build_main_content(self):
        """主内容区 — 包含标签页"""
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # 创建标签页
        self.tabview = ctk.CTkTabview(
            self.main_frame,
            corner_radius=16,
            segmented_button_selected_color=COLORS["primary"],
            segmented_button_selected_hover_color=COLORS["primary_hover"],
            segmented_button_unselected_color=(COLORS["gray_100"], COLORS["gray_800"]),
            segmented_button_unselected_hover_color=(COLORS["gray_200"], COLORS["gray_700"]),
            text_color=(COLORS["gray_700"], COLORS["gray_200"]),
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=20, pady=(0, 10))

        # 添加标签页
        self.tab_home = self.tabview.add("🏠 首页")
        self.tab_local = self.tabview.add("💻 本地")
        self.tab_cloud = self.tabview.add("☁️ 云端")
        self.tab_bridge = self.tabview.add("🔄 跨工具")
        self.tab_settings = self.tabview.add("⚙️ 设置")

        # 构建各标签页内容
        self._build_home_tab()
        self._build_local_tab()
        self._build_cloud_tab()
        self._build_bridge_tab()
        self._build_settings_tab()

    def _build_home_tab(self):
        """首页 Dashboard — 卡片式信息展示"""
        # 主滚动容器
        container = ctk.CTkScrollableFrame(self.tab_home, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure((0, 1), weight=1)

        # === 第一行：统计卡片 ===
        stats = self._get_local_stats()

        # 记忆文件卡片
        self._create_stat_card(
            container,
            0,
            0,
            icon="📄",
            title="记忆文件",
            count=stats["memory_count"],
            size=format_size(stats["memory_size"]),
            color=COLORS["primary"],
        )

        # 会话记录卡片
        self._create_stat_card(
            container,
            0,
            1,
            icon="💬",
            title="会话记录",
            count=stats["session_count"],
            size=format_size(stats["session_size"]),
            color=COLORS["info"],
        )

        # 规则文件卡片
        self._create_stat_card(
            container,
            1,
            0,
            icon="📋",
            title="规则文件",
            count=stats["rule_count"],
            size=format_size(stats["rule_size"]),
            color=COLORS["success"],
        )

        # 总计卡片
        self._create_stat_card(
            container,
            1,
            1,
            icon="📦",
            title="总计",
            count=stats["total_count"],
            size=format_size(stats["total_size"]),
            color=COLORS["warning"],
            highlight=True,
        )

        # === 云同步状态卡片 ===
        self.cloud_status_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        self.cloud_status_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=15)
        self.cloud_status_card.grid_columnconfigure(0, weight=1)

        self.cloud_status_content = ctk.CTkFrame(self.cloud_status_card, fg_color="transparent")
        self.cloud_status_content.pack(fill="both", expand=True, padx=20, pady=20)

        # === 导出大卡片 ===
        export_card = ctk.CTkFrame(container, corner_radius=16, fg_color=(COLORS["primary"], COLORS["gray_800"]))
        export_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=15)
        export_card.grid_columnconfigure(0, weight=1)

        export_content = ctk.CTkFrame(export_card, fg_color="transparent")
        export_content.pack(fill="both", expand=True, padx=30, pady=30)

        ctk.CTkLabel(
            export_content,
            text="📦",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            export_content,
            text="导出本地压缩包",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
        ).pack()

        ctk.CTkLabel(
            export_content,
            text="一键打包记忆、会话和规则，双击 import.sh 即可在新设备导入",
            font=ctk.CTkFont(size=13),
            text_color=(COLORS["gray_100"], COLORS["gray_300"]),
        ).pack(pady=10)

        ctk.CTkButton(
            export_content,
            text="立即导出 ZIP",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=45,
            corner_radius=12,
            fg_color="white",
            text_color=COLORS["primary"],
            hover_color=COLORS["gray_100"],
            command=self._do_local_export,
        ).pack(pady=15)

        # === 快速操作区 ===
        actions_frame = ctk.CTkFrame(container, fg_color="transparent")
        actions_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=5, pady=10)

        actions = [
            ("🔄 完整同步", self._do_sync, COLORS["primary"]),
            ("📤 推送到云", self._do_push, COLORS["success"]),
            ("📥 从云拉取", self._do_pull, COLORS["info"]),
        ]

        for _, (text, cmd, color) in enumerate(actions):
            btn = ctk.CTkButton(
                actions_frame,
                text=text,
                font=ctk.CTkFont(size=13),
                height=40,
                corner_radius=10,
                fg_color=color,
                hover_color=self._darken_color(color),
                command=cmd,
            )
            btn.pack(side="left", padx=5, expand=True, fill="x")

    def _create_stat_card(self, parent, row, col, icon, title, count, size, color, highlight=False):
        """创建统计卡片"""
        card = ctk.CTkFrame(
            parent,
            corner_radius=16,
            fg_color=("white", COLORS["gray_800"]),
            border_width=2 if highlight else 0,
        )
        if highlight:
            card.configure(border_color=color)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # 图标和标题行
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text=icon,
            font=ctk.CTkFont(size=32),
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=14),
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
        ).pack(side="right")

        # 数字
        ctk.CTkLabel(
            content,
            text=str(count),
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=color,
        ).pack(anchor="w")

        # 大小
        ctk.CTkLabel(
            content,
            text=size,
            font=ctk.CTkFont(size=13),
            text_color=(COLORS["gray_400"], COLORS["gray_500"]),
        ).pack(anchor="w")

    def _build_local_tab(self):
        """本地管理 — 左侧树形文件列表 + 右侧预览（聊天/文本）"""
        main_frame = ctk.CTkFrame(self.tab_local, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=3)
        main_frame.grid_rowconfigure(0, weight=1)

        # ========== 左侧：树形文件列表 ==========
        left_frame = ctk.CTkFrame(main_frame, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(left_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=15, pady=15)

        ctk.CTkLabel(toolbar, text="📁 本地文件", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        ctk.CTkButton(
            toolbar, text="☑ 全选", width=60, height=30, corner_radius=8, command=self._select_all_local
        ).pack(side="right", padx=2)
        ctk.CTkButton(
            toolbar,
            text="☐ 取消",
            width=60,
            height=30,
            corner_radius=8,
            fg_color=(COLORS["gray_200"], COLORS["gray_700"]),
            command=self._deselect_all_local,
        ).pack(side="right", padx=2)

        self.files_scroll = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
        self.files_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))

        self.file_vars: dict[str, ctk.BooleanVar] = {}
        self.file_path_map: dict[str, Path | None] = {}
        self.collapsed: dict[str, bool] = {}

        # ========== 右侧：预览区 ==========
        self.preview_frame = ctk.CTkFrame(main_frame, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.preview_frame.grid_rowconfigure(1, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        # 面包屑导航
        self.breadcrumb_bar = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.breadcrumb_bar.grid(row=0, column=0, sticky="ew", padx=18, pady=15)

        self.back_btn = ctk.CTkButton(
            self.breadcrumb_bar,
            text="← 返回列表",
            width=80,
            height=28,
            corner_radius=6,
            fg_color=(COLORS["gray_200"], COLORS["gray_700"]),
            text_color=(COLORS["gray_700"], COLORS["gray_200"]),
            command=self._go_back_to_tree,
        )

        self.breadcrumb_label = ctk.CTkLabel(
            self.breadcrumb_bar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=(COLORS["gray_400"], COLORS["gray_500"]),
        )

        # 欢迎提示
        self.welcome_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.welcome_frame.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(self.welcome_frame, text="📂", font=ctk.CTkFont(size=64)).pack(pady=(40, 10))
        ctk.CTkLabel(self.welcome_frame, text="选择左侧文件即可预览", font=ctk.CTkFont(size=16, weight="bold")).pack()
        ctk.CTkLabel(
            self.welcome_frame,
            text=".jsonl 会话 → 聊天时间线\n.md / .py / 其他 → 文本预览",
            font=ctk.CTkFont(size=12),
            text_color=(COLORS["gray_400"], COLORS["gray_500"]),
        ).pack(pady=10)

        # 预览容器（初始化隐藏）
        self.content_view: ctk.CTkFrame | None = None
        self.chat_view: ChatView | None = None
        self.text_preview: ctk.CTkTextbox | None = None

        # 底部导出栏
        bottom_bar = ctk.CTkFrame(main_frame, corner_radius=12, fg_color=(COLORS["gray_100"], COLORS["gray_800"]))
        bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=10)

        self.local_status = ctk.CTkLabel(bottom_bar, text="已选择 0 个文件", font=ctk.CTkFont(size=13))
        self.local_status.pack(side="left", padx=20, pady=15)

        ctk.CTkButton(
            bottom_bar,
            text="📦 导出选中",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            corner_radius=10,
            command=self._export_selected_local,
        ).pack(side="right", padx=20, pady=10)

        self._load_local_files()

    def _build_cloud_tab(self):
        """云端同步标签页"""
        if not is_cloud_configured():
            self._build_cloud_setup_view()
        else:
            self._build_cloud_versions_view()

    def _build_cloud_setup_view(self):
        """云端未配置时的引导视图"""
        container = ctk.CTkFrame(self.tab_cloud, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=40, pady=40)

        # 居中卡片
        card = ctk.CTkFrame(container, corner_radius=24, fg_color=("white", COLORS["gray_800"]))
        card.place(relx=0.5, rely=0.5, anchor="center")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(padx=60, pady=60)

        ctk.CTkLabel(
            content,
            text="☁️",
            font=ctk.CTkFont(size=64),
        ).pack()

        ctk.CTkLabel(
            content,
            text="尚未配置云同步",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(pady=15)

        ctk.CTkLabel(
            content,
            text="配置云后端后，可在多台设备间同步记忆和项目上下文",
            font=ctk.CTkFont(size=13),
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
        ).pack()

        # 选项按钮
        options = ctk.CTkFrame(content, fg_color="transparent")
        options.pack(pady=30)

        github_btn = ctk.CTkButton(
            options,
            text="🐙 使用 GitHub",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            width=200,
            corner_radius=12,
            fg_color="#24292e",
            hover_color="#1b1f23",
            command=lambda: self._show_cloud_config("github"),
        )
        github_btn.pack(pady=8)

        manbaout_btn = ctk.CTkButton(
            options,
            text="☁️ 使用 ManbaOut",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            width=200,
            corner_radius=12,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            command=lambda: self._show_cloud_config("manbaout"),
        )
        manbaout_btn.pack(pady=8)

        ctk.CTkButton(
            content,
            text="暂不需要，保持本地模式",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
            hover=False,
            command=lambda: self.tabview.set("🏠 首页"),
        ).pack(pady=10)

    def _build_cloud_versions_view(self):
        """云端已配置时的版本列表视图"""
        # 工具栏
        toolbar = ctk.CTkFrame(self.tab_cloud, corner_radius=12, fg_color=("white", COLORS["gray_800"]))
        toolbar.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            toolbar,
            text="☁️ 云端版本历史",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=20, pady=15)

        ctk.CTkButton(
            toolbar,
            text="🔄 刷新",
            width=80,
            height=32,
            corner_radius=8,
            command=self._refresh_cloud_versions,
        ).pack(side="right", padx=10, pady=10)

        # 版本列表容器
        self.versions_frame = ctk.CTkScrollableFrame(
            self.tab_cloud,
            corner_radius=16,
            fg_color=("white", COLORS["gray_800"]),
        )
        self.versions_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 加载版本列表
        self._refresh_cloud_versions()

    def _build_bridge_tab(self):
        """跨工具同步标签页 — Codex ↔ OpenCode（含复选框选择）"""
        container = ctk.CTkScrollableFrame(self.tab_bridge, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # === Codex → OpenCode ===
        c2o_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        c2o_card.pack(fill="x", pady=8)

        ctk.CTkLabel(c2o_card, text="🧠 Codex → OpenCode", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 4)
        )

        c2o_btns = ctk.CTkFrame(c2o_card, fg_color="transparent")
        c2o_btns.pack(fill="x", padx=20, pady=6)
        for label, action in [("📄 AGENTS.md", "agents"), ("📁 Skills", "skills"), ("🧠 记忆→AGENTS.md", "memories")]:
            ctk.CTkButton(
                c2o_btns,
                text=label,
                font=ctk.CTkFont(size=11),
                height=30,
                corner_radius=8,
                command=lambda a=action: self._bridge_action("c2o", a),
            ).pack(side="left", padx=3)

        # 会话复选框列表
        self.cx_vars: dict[str, ctk.BooleanVar] = {}
        self.cx_frame = ctk.CTkFrame(c2o_card, fg_color="transparent")
        self.cx_frame.pack(fill="x", padx=20, pady=6)
        self._load_cx_checkboxes()

        ctk.CTkButton(
            c2o_card,
            text="📤 导入勾选会话到 OpenCode",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            corner_radius=10,
            command=lambda: self._bridge_import_selected(),
        ).pack(fill="x", padx=20, pady=10)

        # === OpenCode → Codex ===
        o2c_card = ctk.CTkFrame(container, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        o2c_card.pack(fill="x", pady=8)

        ctk.CTkLabel(o2c_card, text="💬 OpenCode → Codex", font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=20, pady=(20, 4)
        )

        o2c_btns = ctk.CTkFrame(o2c_card, fg_color="transparent")
        o2c_btns.pack(fill="x", padx=20, pady=6)
        for label, action in [("📄 AGENTS.md", "agents"), ("📁 Skills", "skills")]:
            ctk.CTkButton(
                o2c_btns,
                text=label,
                font=ctk.CTkFont(size=11),
                height=30,
                corner_radius=8,
                fg_color=COLORS["success"],
                hover_color=self._darken_color(COLORS["success"]),
                command=lambda a=action: self._bridge_action("o2c", a),
            ).pack(side="left", padx=3)

        ctk.CTkButton(
            o2c_card,
            text="📥 导出全部会话到 Codex",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            corner_radius=10,
            fg_color=COLORS["success"],
            hover_color=self._darken_color(COLORS["success"]),
            command=lambda: self._bridge_action("o2c", "sessions"),
        ).pack(fill="x", padx=20, pady=6)
        ctk.CTkButton(
            o2c_card,
            text="🔄 一键全部导出到 Codex",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42,
            corner_radius=10,
            fg_color=COLORS["success"],
            hover_color=self._darken_color(COLORS["success"]),
            command=lambda: self._bridge_action("o2c", "all"),
        ).pack(fill="x", padx=20, pady=(0, 20))

        self.bridge_status = ctk.CTkLabel(
            container, text="", font=ctk.CTkFont(size=12), text_color=(COLORS["gray_400"], COLORS["gray_500"])
        )
        self.bridge_status.pack(pady=10)

    def _load_cx_checkboxes(self):
        """加载 Codex 会话复选框列表"""
        for w in self.cx_frame.winfo_children():
            w.destroy()
        self.cx_vars.clear()

        try:
            from pathlib import Path

            from src.export_local import discover_sessions

            sessions_dir = Path.home() / ".codex" / "sessions"
            idx_path = Path.home() / ".codex" / "session_index.jsonl"
            if not sessions_dir.exists():
                ctk.CTkLabel(self.cx_frame, text="未找到 Codex sessions 目录", font=ctk.CTkFont(size=11)).pack(
                    anchor="w"
                )
                return
            indexed, unindexed = discover_sessions(sessions_dir, idx_path)
            all_sessions = indexed + [
                {"path": p, "name": f"未索引:{p.name}", "thread_name": f"未索引:{p.name}", "size": p.stat().st_size}
                for p in unindexed
            ]

            if not all_sessions:
                ctk.CTkLabel(self.cx_frame, text="没有可导入的会话", font=ctk.CTkFont(size=11)).pack(anchor="w")
                return

            ctk.CTkLabel(
                self.cx_frame, text=f"共 {len(all_sessions)} 个会话（勾选要导入的）", font=ctk.CTkFont(size=11)
            ).pack(anchor="w", pady=(0, 6))

            for s in all_sessions:
                name = s.get("thread_name", s["name"])
                size_str = format_size(s.get("size", 0))
                path_str = str(s["path"])
                var = ctk.BooleanVar(value=False)
                self.cx_vars[path_str] = var
                cb = ctk.CTkCheckBox(
                    self.cx_frame, text=f"{name} ({size_str})", variable=var, font=ctk.CTkFont(size=11)
                )
                cb.pack(anchor="w", padx=5, pady=2)
        except Exception as e:
            ctk.CTkLabel(self.cx_frame, text=f"加载失败: {e}", font=ctk.CTkFont(size=11)).pack(anchor="w")

    def _bridge_import_selected(self):
        """导入勾选的 Codex 会话到 OpenCode"""
        selected = [p for p, v in self.cx_vars.items() if v.get()]
        if not selected:
            from tkinter import messagebox

            messagebox.showinfo("提示", "请先勾选要导入的会话")
            return
        self._bridge_action("c2o", "sessions", session_paths=selected)

    def _bridge_action(self, direction, action, session_paths=None):
        """执行跨工具同步操作"""
        try:
            from src.bridge import (
                codex_all_to_opencode,
                opencode_to_codex,
                sync_agents_md,
                sync_memories_to_opencode,
                sync_skills,
            )

            self.bridge_status.configure(text="⏳ 同步中...", text_color=COLORS["warning"])
            self.update_idletasks()

            if direction == "c2o":
                if action == "agents":
                    r = sync_agents_md("c2o")
                elif action == "skills":
                    r = sync_skills("c2o")
                elif action == "memories":
                    r = sync_memories_to_opencode()
                elif action == "sessions":
                    r = codex_all_to_opencode(session_paths=session_paths)
                else:
                    r = {"error": "未知操作"}
            else:
                if action == "agents":
                    r = sync_agents_md("o2c")
                elif action == "skills":
                    r = sync_skills("o2c")
                elif action == "sessions":
                    r = opencode_to_codex()
                else:
                    r = {"error": "未知操作"}

            import json

            r_text = json.dumps(r, ensure_ascii=False, indent=2)
            self.bridge_status.configure(
                text=f"✅ 完成\n{r_text[:500]}",
                text_color=COLORS["success"],
            )
        except Exception as e:
            self.bridge_status.configure(text=f"❌ 失败: {e}", text_color=COLORS["danger"])

    def _build_settings_tab(self):
        """设置标签页"""
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # === 外观设置 ===
        self._create_setting_card(
            container,
            "🎨 外观设置",
            [
                {
                    "type": "option",
                    "label": "主题模式",
                    "options": ["Light", "Dark", "System"],
                    "current": config.get_config_value("appearance", "mode") or "System",
                    "command": self._change_theme,
                },
                {
                    "type": "option",
                    "label": "强调色",
                    "options": ["blue", "green", "dark-blue"],
                    "current": config.get_config_value("appearance", "color_theme") or "blue",
                    "command": self._change_color_theme,
                },
            ],
        )

        # === Codex 目录位置 ===
        path_card = self._create_setting_card(container, "📂 Codex 目录位置", [])
        path_frame = ctk.CTkFrame(path_card, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=15)

        locs = detect_codex_locations()
        root = locs.get("root")
        self.path_status_label = ctk.CTkLabel(
            path_frame,
            text=f"已检测到: {root}" if root else "⚠️ 未检测到 .codex 目录",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["success"] if root else COLORS["warning"],
        )
        self.path_status_label.pack(side="left")

        ctk.CTkButton(
            path_frame,
            text="🔍 重新扫描",
            width=100,
            height=34,
            corner_radius=8,
            command=self._rescan_codex_path,
        ).pack(side="right")

        # === 云后端设置 ===
        cloud_card = self._create_setting_card(
            container,
            "🗄️ 云后端设置",
            [
                {
                    "type": "option",
                    "label": "后端类型",
                    "options": ["none", "github", "manbaout"],
                    "current": config.get_backend(),
                    "command": self._change_backend,
                },
            ],
        )

        # 动态显示后端配置
        self.backend_config_frame = ctk.CTkFrame(cloud_card, fg_color="transparent")
        self.backend_config_frame.pack(fill="x", padx=20, pady=10)
        self._update_backend_config_ui()

        # === 加密设置 ===
        enc_card = self._create_setting_card(container, "🔒 加密设置", [])

        enc_frame = ctk.CTkFrame(enc_card, fg_color="transparent")
        enc_frame.pack(fill="x", padx=20, pady=15)

        self.enc_entry = ctk.CTkEntry(
            enc_frame,
            placeholder_text="设置加密密码（用于云同步加密）",
            show="●",
            height=40,
            corner_radius=10,
        )
        self.enc_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            enc_frame,
            text="保存",
            width=80,
            height=40,
            corner_radius=10,
            command=self._save_encryption_password,
        ).pack(side="right")

        # === 守护进程设置 ===
        daemon_card = self._create_setting_card(container, "🤖 守护进程", [])

        daemon_frame = ctk.CTkFrame(daemon_card, fg_color="transparent")
        daemon_frame.pack(fill="x", padx=20, pady=15)

        ds = daemon_status()
        self.daemon_switch = ctk.CTkSwitch(
            daemon_frame,
            text="启用自动同步守护进程",
            command=self._toggle_daemon,
        )
        self.daemon_switch.pack(anchor="w")
        if ds.get("running"):
            self.daemon_switch.select()

    def _create_setting_card(self, parent, title, items):
        """创建设置卡片"""
        card = ctk.CTkFrame(parent, corner_radius=16, fg_color=("white", COLORS["gray_800"]))
        card.pack(fill="x", pady=10)

        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(20, 10))

        for item in items:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=10)

            ctk.CTkLabel(
                row,
                text=item["label"],
                font=ctk.CTkFont(size=13),
            ).pack(side="left")

            if item["type"] == "option":
                option = ctk.CTkOptionMenu(
                    row,
                    values=item["options"],
                    command=item["command"],
                    width=150,
                    height=32,
                    corner_radius=8,
                )
                option.set(item["current"])
                option.pack(side="right")

        return card

    def _build_status_bar(self):
        """底部状态栏"""
        self.status_bar = ctk.CTkFrame(
            self, height=40, corner_radius=0, fg_color=(COLORS["gray_100"], COLORS["gray_800"])
        )
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=0, pady=0)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="就绪",
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(side="left", padx=20, pady=10)

        self.status_indicator = ctk.CTkLabel(
            self.status_bar,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["success"],
        )
        self.status_indicator.pack(side="right", padx=20, pady=10)

    # ══════════════════════════════════════════════════════════════════════════
    # 功能方法
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_theme(self):
        """切换明暗主题"""
        if self.current_mode == "Light":
            new_mode = "Dark"
            self.theme_btn.configure(text="☀️")
        else:
            new_mode = "Light"
            self.theme_btn.configure(text="🌙")

        self.current_mode = new_mode
        ctk.set_appearance_mode(new_mode)
        config.set_config_value(new_mode, "appearance", "mode")

    def _load_local_files(self):
        """加载本地文件树"""
        for widget in self.files_scroll.winfo_children():
            widget.destroy()
        self.file_vars.clear()
        self.file_path_map.clear()

        memories = discover_memories(MEMORIES_DIR)
        sessions_idx, sessions_un = discover_sessions(SESSIONS_DIR, SESSION_INDEX)
        rules = discover_rules(RULES_DIR)

        # 记忆文件树
        self._add_tree_section("📁 记忆文件", "memories")
        for item in memories:
            if item.get("is_dir"):
                dir_key = f"memories_{item['name']}"
                self.collapsed[dir_key] = True
                self._add_tree_dir("  📁 " + item["name"] + "/", item["path"], item.get("size", 0), dir_key)
                for child in item.get("children", []):
                    child_key = f"memories_{child['relative']}"
                    self._add_tree_file("      📄 " + child["name"], child["path"], child.get("size", 0), child_key)
            else:
                key = f"memories_{item['relative']}"
                self._add_tree_file("  📄 " + item["name"], item.get("path"), item.get("size", 0), key)

        # 会话记录
        self._add_tree_section("💬 会话记录", "sessions")
        self._add_tree_label(f"    已索引: {len(sessions_idx)} 个", "sessions_indexed")
        for s in sessions_idx:
            key = f"sessions_{s['session_id']}"
            name = s.get("thread_name", s["name"])
            self._add_tree_file(f"      💬 {name}", s.get("path"), s.get("size", 0), key)
        if sessions_un:
            self._add_tree_label(f"    未索引: {len(sessions_un)} 个", "sessions_unindexed")
            for p in sessions_un:
                self._add_tree_file(f"      📄 {p.name}", p, p.stat().st_size, f"sessions_un_{p.name}")

        # 规则文件
        self._add_tree_section("📋 规则文件", "rules")
        for r in rules:
            self._add_tree_file("  📄 " + r["name"], r.get("path"), r.get("size", 0), f"rules_{r['name']}")

    def _add_tree_section(self, text: str, key: str):
        row = ctk.CTkFrame(self.files_scroll, fg_color="transparent", height=32)
        row.pack(fill="x", padx=5, pady=(10, 2))
        row.pack_propagate(False)
        ctk.CTkLabel(
            row,
            text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=(COLORS["gray_600"], COLORS["gray_400"]),
        ).pack(side="left", padx=5)

    def _add_tree_label(self, text: str, key: str):
        row = ctk.CTkFrame(self.files_scroll, fg_color="transparent", height=26)
        row.pack(fill="x", padx=5, pady=0)
        row.pack_propagate(False)
        ctk.CTkLabel(
            row, text=text, font=ctk.CTkFont(size=11), text_color=(COLORS["gray_400"], COLORS["gray_500"])
        ).pack(side="left", padx=5)

    def _add_tree_file(self, name: str, path: Path | None, size: int, key: str):
        row = ctk.CTkFrame(self.files_scroll, fg_color="transparent", height=30)
        row.pack(fill="x", padx=5, pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=False)
        self.file_vars[key] = var
        ctk.CTkCheckBox(row, text="", variable=var, width=24, command=self._update_local_status).pack(
            side="left", padx=(5, 2)
        )

        if path:
            self.file_path_map[key] = path
            lbl = ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11), cursor="hand2", anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=5)
            lbl.bind("<Button-1>", lambda e, p=path, n=name: self._preview_file(p, n))
        else:
            self.file_path_map[key] = None
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=11), anchor="w").pack(
                side="left", fill="x", expand=True, padx=5
            )

        if size:
            ctk.CTkLabel(
                row,
                text=format_size(size),
                font=ctk.CTkFont(size=10),
                text_color=(COLORS["gray_400"], COLORS["gray_500"]),
            ).pack(side="right", padx=5)

    def _add_tree_dir(self, name: str, path: Path | None, size: int, key: str):
        row = ctk.CTkFrame(self.files_scroll, fg_color="transparent", height=30)
        row.pack(fill="x", padx=5, pady=1)
        row.pack_propagate(False)

        var = ctk.BooleanVar(value=False)
        self.file_vars[key] = var
        self.file_path_map[key] = path
        ctk.CTkCheckBox(row, text=name, variable=var, width=24, command=self._update_local_status).pack(
            side="left", padx=(5, 2)
        )

    def _update_local_status(self):
        selected = [k for k, v in self.file_vars.items() if v.get()]
        self.local_status.configure(text=f"已选择 {len(selected)} 个文件")

    def _go_back_to_tree(self):
        """返回文件列表视图"""
        if self.content_view:
            self.content_view.destroy()
            self.content_view = None
        self.chat_view = None
        self.text_preview = None
        self.welcome_frame.grid()
        self.back_btn.pack_forget()
        self.breadcrumb_label.configure(text="")

    def _preview_file(self, path: Path, display_name: str = ""):
        """预览文件 — .jsonl 聊天模式 / 其他文本模式"""
        if not path or not path.exists():
            return

        name = display_name or path.name

        # 隐藏欢迎页
        self.welcome_frame.grid_remove()

        # 销毁旧预览
        if self.content_view:
            self.content_view.destroy()
            self.content_view = None
        self.chat_view = None
        self.text_preview = None

        # 面包屑
        self.back_btn.pack(side="left", padx=(0, 10))
        self.breadcrumb_label.configure(text=name)

        # 创建内容容器
        self.content_view = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.content_view.grid(row=1, column=0, sticky="nsew")
        self.content_view.grid_columnconfigure(0, weight=1)
        self.content_view.grid_rowconfigure(0, weight=1)

        # 判断文件类型
        is_jsonl = path.suffix.lower() == ".jsonl"

        if is_jsonl:
            self._show_chat_preview(path)
        else:
            self._show_text_preview(path)

    def _show_chat_preview(self, path: Path):
        """聊天时间线预览（.jsonl）"""
        messages = parse_jsonl_session(path, max_messages=200)

        if not messages:
            ctk.CTkLabel(
                self.content_view,
                text="该会话没有可解析的消息",
                font=ctk.CTkFont(size=13),
                text_color=(COLORS["gray_400"], COLORS["gray_500"]),
            ).grid(row=0, column=0, padx=30, pady=40)
            return

        # 会话摘要
        summary = ctk.CTkFrame(self.content_view, fg_color=(COLORS["gray_100"], COLORS["gray_800"]), corner_radius=10)
        summary.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        user_count = sum(1 for m in messages if m["kind"] == "message" and m["role"] == "user")
        asst_count = sum(1 for m in messages if m["kind"] == "message" and m["role"] == "assistant")
        think_count = sum(1 for m in messages if m["kind"] == "thinking")
        tool_count = sum(1 for m in messages if m["kind"] == "tool")
        event_count = sum(1 for m in messages if m["kind"] == "event")

        ctk.CTkLabel(
            summary,
            text=f"💬 {len(messages)} 条 · 👤{user_count} · 🤖{asst_count} · 💭{think_count} · 🔧{tool_count} · 📋{event_count}",
            font=ctk.CTkFont(size=11),
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
        ).pack(padx=15, pady=10)

        # 聊天时间线
        self.chat_view = ChatView(self.content_view, height=400)
        self.chat_view.grid(row=1, column=0, sticky="nsew", padx=5)
        self.chat_view.load_session(messages)

    def _show_text_preview(self, path: Path):
        """纯文本预览（.md / .py / 其他）"""
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            if len(content) > 50000:
                content = content[:50000] + "\n\n... (内容已截断)"
        except Exception:
            content = "无法读取此文件"

        self.text_preview = ctk.CTkTextbox(
            self.content_view,
            corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        self.text_preview.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.text_preview.insert("1.0", content)
        self.text_preview.configure(state="disabled")

    def _select_all_local(self):
        for var in self.file_vars.values():
            var.set(True)
        self._update_local_status()

    def _deselect_all_local(self):
        for var in self.file_vars.values():
            var.set(False)
        self._update_local_status()

    def _export_selected_local(self):
        self._do_local_export()

    def _show_cloud_config(self, backend_type):
        """显示云配置对话框"""
        # 简化：直接跳转到设置页
        self.tabview.set("⚙️ 设置")
        config.set_backend(backend_type)
        self._update_backend_config_ui()

    def _refresh_cloud_versions(self):
        """刷新云端版本列表"""
        # 清空现有
        for widget in self.versions_frame.winfo_children():
            widget.destroy()

        try:
            versions = list_cloud_versions()
        except CloudError as e:
            error_label = ctk.CTkLabel(
                self.versions_frame,
                text=f"无法获取版本列表: {e}",
                text_color=COLORS["danger"],
            )
            error_label.pack(pady=20)
            return

        if not versions:
            empty_label = ctk.CTkLabel(
                self.versions_frame,
                text="暂无云端版本",
                font=ctk.CTkFont(size=14),
                text_color=(COLORS["gray_400"], COLORS["gray_500"]),
            )
            empty_label.pack(pady=40)
            return

        for v in versions:
            self._create_version_card(v)

    def _create_version_card(self, version):
        """创建版本卡片"""
        card = ctk.CTkFrame(self.versions_frame, corner_radius=12, fg_color=(COLORS["gray_50"], COLORS["gray_700"]))
        card.pack(fill="x", padx=10, pady=5)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # 版本号和设备
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text=f"v{version.get('version', '?')}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            header,
            text=version.get("device", "unknown"),
            font=ctk.CTkFont(size=12),
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
        ).pack(side="left", padx=10)

        # 信息行
        info_text = f"📅 {version.get('time', '')[:19]}  •  📦 {format_size(version.get('size', 0))}"
        ctk.CTkLabel(
            content,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color=(COLORS["gray_500"], COLORS["gray_400"]),
        ).pack(anchor="w", pady=(5, 0))

        # 操作按钮
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            btn_frame,
            text="📥 下载",
            width=80,
            height=32,
            corner_radius=8,
            command=lambda v=version: self._download_version(v),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame,
            text="🗑 删除",
            width=80,
            height=32,
            corner_radius=8,
            fg_color=COLORS["danger"],
            hover_color=self._darken_color(COLORS["danger"]),
            command=lambda v=version: self._delete_version(v),
        ).pack(side="left", padx=2)

    def _download_version(self, version):
        """下载指定版本"""
        # 简化实现
        messagebox.showinfo("下载", f"正在下载版本 v{version.get('version')}...")

    def _delete_version(self, version):
        """删除指定版本"""
        if messagebox.askyesno("确认", f"确定要删除版本 v{version.get('version')} 吗？"):
            try:
                unregister_version(version.get("version"))
                self._refresh_cloud_versions()
            except CloudError as e:
                messagebox.showerror("错误", str(e))

    def _update_backend_config_ui(self):
        """更新后端配置 UI"""
        for widget in self.backend_config_frame.winfo_children():
            widget.destroy()

        backend = config.get_backend()

        if backend == "github":
            self._build_github_config()
        elif backend == "manbaout":
            self._build_manbaout_config()

    def _build_github_config(self):
        """GitHub 配置 UI"""
        ctk.CTkLabel(
            self.backend_config_frame,
            text="GitHub OAuth 配置",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(10, 5))

        self.gh_client_id = ctk.CTkEntry(
            self.backend_config_frame,
            placeholder_text="Client ID",
            height=36,
            corner_radius=8,
        )
        self.gh_client_id.pack(fill="x", pady=5)

        ctk.CTkButton(
            self.backend_config_frame,
            text="授权 GitHub",
            height=36,
            corner_radius=8,
            command=self._do_github_auth,
        ).pack(fill="x", pady=5)

    def _build_manbaout_config(self):
        """ManbaOut 配置 UI"""
        ctk.CTkLabel(
            self.backend_config_frame,
            text="ManbaOut 账号配置",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(10, 5))

        self.mb_server = ctk.CTkEntry(
            self.backend_config_frame,
            placeholder_text="服务器地址",
            height=36,
            corner_radius=8,
        )
        self.mb_server.insert(0, "https://manbaout.cn")
        self.mb_server.pack(fill="x", pady=3)

        self.mb_username = ctk.CTkEntry(
            self.backend_config_frame,
            placeholder_text="用户名",
            height=36,
            corner_radius=8,
        )
        self.mb_username.pack(fill="x", pady=3)

        self.mb_password = ctk.CTkEntry(
            self.backend_config_frame,
            placeholder_text="密码",
            show="●",
            height=36,
            corner_radius=8,
        )
        self.mb_password.pack(fill="x", pady=3)

        ctk.CTkButton(
            self.backend_config_frame,
            text="登录",
            height=36,
            corner_radius=8,
            command=self._do_manbaout_login,
        ).pack(fill="x", pady=5)

    def _do_github_auth(self):
        """执行 GitHub 授权"""
        # 简化实现
        messagebox.showinfo("授权", "请使用 CLI 执行: codex-memory github auth")

    def _do_manbaout_login(self):
        """执行 ManbaOut 登录"""
        # 简化实现
        messagebox.showinfo("登录", "请使用 CLI 执行: codex-memory init --backend manbaout")

    def _change_theme(self, value):
        """切换主题"""
        ctk.set_appearance_mode(value)
        config.set_config_value(value, "appearance", "mode")
        self.current_mode = value

    def _change_color_theme(self, value):
        """切换强调色"""
        ctk.set_default_color_theme(value)
        config.set_config_value(value, "appearance", "color_theme")

    def _change_backend(self, value):
        """切换后端"""
        config.set_backend(value)
        self._update_backend_config_ui()
        # 刷新云标签页
        for widget in self.tab_cloud.winfo_children():
            widget.destroy()
        self._build_cloud_tab()

    def _save_encryption_password(self):
        """保存加密密码"""
        pwd = self.enc_entry.get()
        if pwd:
            config.update_security(pwd)
            messagebox.showinfo("成功", "加密密码已保存")
        else:
            messagebox.showwarning("警告", "密码不能为空")

    def _toggle_daemon(self):
        """切换守护进程"""
        if self.daemon_switch.get():
            from src.daemon import start_daemon

            start_daemon()
            self.status_label.configure(text="守护进程已启动")
        else:
            from src.daemon import stop_daemon

            stop_daemon()
            self.status_label.configure(text="守护进程已停止")

    def _rescan_codex_path(self):
        """重新扫描 Codex 目录"""
        locs = detect_codex_locations()
        root = locs.get("root")
        if root:
            self.path_status_label.configure(
                text=f"已检测到: {root}",
                text_color=COLORS["success"],
            )
        else:
            self.path_status_label.configure(
                text="⚠️ 未检测到 .codex 目录，请在环境变量 CODEX_HOME 中设置",
                text_color=COLORS["warning"],
            )

    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """加深颜色"""
        hex_color = hex_color.lstrip("#")
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ══════════════════════════════════════════════════════════════════════════
    # 数据接口（保留原有实现）
    # ══════════════════════════════════════════════════════════════════════════

    def _get_local_stats(self) -> dict[str, Any]:
        """获取本地数据统计"""
        try:
            memories = discover_memories(MEMORIES_DIR)
        except Exception:
            memories = []
        try:
            sessions_idx, sessions_un = discover_sessions(SESSIONS_DIR, SESSION_INDEX)
        except Exception:
            sessions_idx, sessions_un = [], []
        try:
            rules = discover_rules(RULES_DIR)
        except Exception:
            rules = []

        def _count_size(items: list[dict]) -> tuple[int, int]:
            total = 0
            count = 0
            for item in items:
                if item.get("is_dir"):
                    for c in item.get("children", []):
                        total += c.get("size", 0)
                        count += 1
                else:
                    total += item.get("size", 0)
                    count += 1
            return count, total

        mc, ms = _count_size(memories)
        sc = len(sessions_idx) + len(sessions_un)
        ss = sum(s.get("size", 0) for s in sessions_idx) + sum(p.stat().st_size for p in sessions_un)
        rc, rs = len(rules), sum(r.get("size", 0) for r in rules)

        return {
            "memory_count": mc,
            "memory_size": ms,
            "session_count": sc,
            "session_size": ss,
            "rule_count": rc,
            "rule_size": rs,
            "total_count": mc + sc + rc,
            "total_size": ms + ss + rs,
        }

    def _get_cloud_status(self) -> dict[str, Any]:
        """获取云端同步状态"""
        if not is_cloud_configured():
            return {
                "configured": False,
                "status": "未配置",
                "local_version": 0,
                "cloud_version": 0,
                "cloud_versions": 0,
                "daemon_running": False,
            }

        try:
            versions = list_cloud_versions()
        except Exception:
            versions = []
        result = compare(versions)
        ds = daemon_status()

        return {
            "configured": True,
            "status": result["status"],
            "local_version": result["local"]["version"],
            "cloud_version": result["cloud"]["latest_version"],
            "cloud_versions": result["cloud"]["total_versions"],
            "daemon_running": bool(ds.get("running")),
        }

    def _do_local_export(self) -> None:
        """导出本地数据为 ZIP 压缩包"""
        stats = self._get_local_stats()
        if stats["total_count"] == 0:
            messagebox.showinfo("提示", "没有可导出的文件")
            return

        ver = config.get_config_value("metadata", "local_version") or 1
        default_name = f"codex-context-v{ver}.zip"

        filepath = filedialog.asksaveasfilename(
            title="导出 Codex 记忆压缩包",
            defaultextension=".zip",
            filetypes=[("ZIP 文件", "*.zip"), ("加密包 (.codex)", "*.codex")],
            initialfile=default_name,
        )
        if not filepath:
            return

        # 询问是否设置密码保护
        password = None
        if messagebox.askyesno("密码保护", "是否为此压缩包设置密码？\n\n设置后，导入时需要输入密码才能解压。"):
            from tkinter import simpledialog

            pwd = simpledialog.askstring("设置密码", "请输入导出密码:", show="●")
            if pwd:
                password = pwd
                filepath = Path(filepath).with_suffix(".codex")

        memories = discover_memories(MEMORIES_DIR)
        sessions_idx, sessions_un = discover_sessions(SESSIONS_DIR, SESSION_INDEX)
        rules = discover_rules(RULES_DIR)

        def _flatten(items: list[dict]) -> list[Path]:
            paths: list[Path] = []
            for item in items:
                if item.get("is_dir"):
                    for c in item.get("children", []):
                        paths.append(c["path"])
                else:
                    paths.append(item["path"])
            return paths

        memory_files = _flatten(memories)
        session_files = [s["path"] for s in sessions_idx] + sessions_un
        rule_files = [r["path"] for r in rules]

        try:
            create_export_zip(
                Path(filepath),
                memory_files,
                session_files,
                rule_files,
                MEMORIES_DIR,
                SESSIONS_DIR,
                RULES_DIR,
                password=password,
            )
            messagebox.showinfo("成功", f"已导出到: {filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def _do_sync(self) -> None:
        """完整同步"""
        if not is_cloud_configured():
            messagebox.showinfo("提示", "请先配置云后端")
            return
        try:
            do_sync()
            messagebox.showinfo("成功", "同步完成")
        except CloudError as e:
            messagebox.showerror("错误", str(e))

    def _do_push(self) -> None:
        """推送"""
        if not is_cloud_configured():
            messagebox.showinfo("提示", "请先配置云后端")
            return
        try:
            do_push()
            messagebox.showinfo("成功", "推送完成")
        except CloudError as e:
            messagebox.showerror("错误", str(e))

    def _do_pull(self) -> None:
        """拉取"""
        if not is_cloud_configured():
            messagebox.showinfo("提示", "请先配置云后端")
            return
        try:
            do_pull()
            messagebox.showinfo("成功", "拉取完成")
        except CloudError as e:
            messagebox.showerror("错误", str(e))

    def _setup_local_mode(self) -> None:
        """首次启动检查"""
        if not is_cloud_configured():
            config.ensure_config_dir()
            config.set_backend("none")

    def _refresh_all(self) -> None:
        """刷新所有数据"""
        # 更新首页统计
        cloud = self._get_cloud_status()

        # 更新状态栏
        if cloud["configured"]:
            status_text = f"v{cloud['local_version']} ← 本地 | ☁️ 云端 v{cloud['cloud_version']}"
            if cloud["daemon_running"]:
                status_text += " | 守护进程运行中"
        else:
            status_text = "本地模式"

        self.status_label.configure(text=status_text)


def main() -> None:
    config.ensure_config_dir()
    app = ModernApp()
    app.mainloop()


if __name__ == "__main__":
    main()
