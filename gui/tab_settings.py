from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

from src import config
from src.cloud import (
    AuthError,
    NetworkError,
    github_auth_poll,
    github_auth_start,
    manbaout_login,
)

from .widgets import (
    ACCENT,
    BG_COLOR,
    CARD_BG,
    TEXT_SECONDARY,
    WARN_BG,
    WARN_BORDER,
    Card,
    PrimaryButton,
    SectionLabel,
    WarningBanner,
)


class SettingsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_COLOR)
        self._app = app
        self._polling = False

        canvas = tk.Canvas(self, bg=BG_COLOR, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._scroll_frame = tk.Frame(canvas, bg=BG_COLOR)
        self._scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_backend_section()
        self._build_cloud_section()
        self._build_github_section()
        self._build_encryption_section()
        self._build_daemon_section()

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self._refresh_visibility()

    def _build_backend_section(self):
        SectionLabel(self._scroll_frame, text="🗄️ 存储后端").pack(fill="x")

        card = Card(self._scroll_frame)
        card.pack(fill="x", padx=16, pady=(8, 0))

        self._backend_var = tk.StringVar(value=config.get_backend())
        btn_frame = tk.Frame(card, bg=CARD_BG)
        btn_frame.pack(fill="x", padx=12, pady=12)

        gh_btn = tk.Radiobutton(
            btn_frame,
            text="🐙 GitHub 私有仓库 (推荐)",
            variable=self._backend_var,
            value="github",
            bg=CARD_BG,
            font=("Helvetica", 11),
            command=self._on_backend_change,
        )
        gh_btn.pack(anchor="w", pady=2)

        mb_btn = tk.Radiobutton(
            btn_frame,
            text="☁️ ManbaOut 云盘",
            variable=self._backend_var,
            value="manbaout",
            bg=CARD_BG,
            font=("Helvetica", 11),
            command=self._on_backend_change,
        )
        mb_btn.pack(anchor="w", pady=2)

        self._manbaout_warning_frame = tk.Frame(card, bg=WARN_BG, highlightbackground=WARN_BORDER, highlightthickness=1)

    def _build_cloud_section(self):
        self._cloud_section = tk.Frame(self._scroll_frame, bg=BG_COLOR)
        self._cloud_section.pack(fill="x")

        SectionLabel(self._cloud_section, text="☁️ ManbaOut 配置").pack(fill="x")

        card = Card(self._cloud_section)
        card.pack(fill="x", padx=16, pady=(8, 0))

        fields = [
            ("服务器地址:", "server_url"),
            ("用户名:", "username"),
            ("云盘路径:", "sync_path"),
        ]
        self._cloud_entries: dict[str, tk.Entry] = {}
        for i, (label, key) in enumerate(fields):
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill="x", padx=12, pady=(8 if i == 0 else 4, 0))
            tk.Label(row, text=label, fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w", width=14, font=("Helvetica", 11)).pack(
                side="left"
            )
            val = config.get_config_value("cloud", key) or ""
            entry = tk.Entry(row, font=("Helvetica", 11), width=35)
            entry.insert(0, val)
            entry.pack(side="left", fill="x", expand=True)
            self._cloud_entries[key] = entry

        pwd_row = tk.Frame(card, bg=CARD_BG)
        pwd_row.pack(fill="x", padx=12, pady=4)
        tk.Label(
            pwd_row, text="密码:", fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w", width=14, font=("Helvetica", 11)
        ).pack(side="left")
        self._cloud_pwd = tk.Entry(pwd_row, font=("Helvetica", 11), width=35, show="*")
        self._cloud_pwd.pack(side="left", fill="x", expand=True)

        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", padx=12, pady=(4, 12))
        PrimaryButton(btn_row, text="🔑 登录并保存", command=self._cloud_login).pack(side="left", padx=(0, 8))
        self._cloud_status = tk.StringVar(value="")
        tk.Label(btn_row, textvariable=self._cloud_status, fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 10)).pack(
            side="left"
        )

        # Retention setting
        exp_frame = tk.Frame(card, bg=CARD_BG)
        exp_frame.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(
            exp_frame, text="保存期限:", fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w", width=14, font=("Helvetica", 11)
        ).pack(side="left")
        self._expiry_var = tk.StringVar(value=str(config.get_config_value("cloud", "expires_days") or 3))
        exp_entry = tk.Entry(exp_frame, textvariable=self._expiry_var, width=6, font=("Helvetica", 11))
        exp_entry.pack(side="left")
        tk.Label(exp_frame, text="天  (1 ~ 365)", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 10)).pack(
            side="left", padx=4
        )
        PrimaryButton(exp_frame, text="💾 保存", command=self._save_expiry).pack(side="left", padx=(8, 0))

        # Warning banner
        WarningBanner(card, "默认仅保存 3 天，到期自动清理。临时中转不建议长期依赖。").pack(
            fill="x", padx=12, pady=(0, 4)
        )

        disclaimer = (
            "免责声明：平台仅提供加密数据中转，因端到端加密无法解密或使用数据。"
            "若未及时续期导致数据被清理，平台不承担责任。建议长期使用请选 GitHub。"
        )
        tk.Label(
            card,
            text=disclaimer,
            fg="#e67e22",
            bg=CARD_BG,
            font=("Helvetica", 8),
            anchor="w",
            justify="left",
            wraplength=460,
        ).pack(anchor="w", padx=12, pady=(0, 12))

    def _build_github_section(self):
        self._github_section = tk.Frame(self._scroll_frame, bg=BG_COLOR)
        self._github_section.pack(fill="x")

        SectionLabel(self._github_section, text="🐙 GitHub 配置").pack(fill="x")

        card = Card(self._github_section)
        card.pack(fill="x", padx=16, pady=(8, 0))

        tk.Label(card, text="Client ID:", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 11)).pack(
            anchor="w", padx=12, pady=(12, 2)
        )
        self._gh_client_entry = tk.Entry(card, font=("Helvetica", 11), width=45)
        existing = config.get_config_value("github", "client_id") or ""
        self._gh_client_entry.insert(0, existing)
        self._gh_client_entry.pack(fill="x", padx=12)

        help_text = (
            "获取: GitHub Settings → Developer settings → OAuth Apps → New OAuth App\n"
            "Homepage URL / Callback URL 填 http://localhost"
        )
        tk.Label(card, text=help_text, fg="#999", bg=CARD_BG, font=("Helvetica", 8), anchor="w", justify="left").pack(
            anchor="w", padx=12, pady=(2, 8)
        )

        btn_row = tk.Frame(card, bg=CARD_BG)
        btn_row.pack(fill="x", padx=12, pady=(0, 8))
        self._gh_auth_btn = PrimaryButton(btn_row, text="🔑 授权 GitHub", command=self._github_auth)
        self._gh_auth_btn.pack(side="left", padx=(0, 8))
        self._gh_status_var = tk.StringVar(value="")
        tk.Label(btn_row, textvariable=self._gh_status_var, fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 10)).pack(
            side="left"
        )

        self._gh_code_var = tk.StringVar(value="")
        self._gh_code_label = tk.Label(
            card, textvariable=self._gh_code_var, fg=ACCENT, bg=CARD_BG, font=("Menlo", 16, "bold")
        )
        self._gh_code_label.pack(pady=(0, 8))

    def _build_encryption_section(self):
        SectionLabel(self._scroll_frame, text="🔒 加密设置").pack(fill="x")

        card = Card(self._scroll_frame)
        card.pack(fill="x", padx=16, pady=(8, 0))

        row = tk.Frame(card, bg=CARD_BG)
        row.pack(fill="x", padx=12, pady=12)
        tk.Label(
            row, text="加密密码:", fg=TEXT_SECONDARY, bg=CARD_BG, anchor="w", width=14, font=("Helvetica", 11)
        ).pack(side="left")
        self._enc_entry = tk.Entry(row, font=("Helvetica", 11), width=35, show="*")
        current_pwd = config.get_config_value("security", "encryption_password") or ""
        self._enc_entry.insert(0, current_pwd)
        self._enc_entry.pack(side="left", fill="x", expand=True)
        PrimaryButton(row, text="💾 保存", command=self._save_encryption).pack(side="left", padx=4)

    def _build_daemon_section(self):
        SectionLabel(self._scroll_frame, text="⚙️ 守护进程").pack(fill="x")

        card = Card(self._scroll_frame)
        card.pack(fill="x", padx=16, pady=(8, 0))

        self._boot_var = tk.BooleanVar(value=config.get_config_value("daemon", "start_on_boot"))
        row1 = tk.Frame(card, bg=CARD_BG)
        row1.pack(fill="x", padx=12, pady=(12, 4))
        tk.Checkbutton(row1, text="开机自启", variable=self._boot_var, bg=CARD_BG, command=self._save_daemon).pack(
            side="left"
        )

        self._tray_var = tk.BooleanVar(value=config.get_config_value("daemon", "minimize_to_tray"))
        row2 = tk.Frame(card, bg=CARD_BG)
        row2.pack(fill="x", padx=12, pady=(0, 4))
        tk.Checkbutton(
            row2, text="关闭窗口时最小化到托盘", variable=self._tray_var, bg=CARD_BG, command=self._save_daemon
        ).pack(side="left")

        debounce_row = tk.Frame(card, bg=CARD_BG)
        debounce_row.pack(fill="x", padx=12, pady=(4, 12))
        tk.Label(debounce_row, text="监听防抖(秒):", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 11)).pack(
            side="left"
        )
        self._debounce_var = tk.StringVar(value=str(config.get_config_value("daemon", "debounce_seconds") or 3))
        tk.Entry(debounce_row, textvariable=self._debounce_var, width=6, font=("Helvetica", 11)).pack(
            side="left", padx=4
        )
        tk.Label(debounce_row, text="检查间隔(分):", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 11)).pack(
            side="left", padx=(16, 0)
        )
        self._interval_var = tk.StringVar(
            value=str(config.get_config_value("daemon", "auto_pull_interval_minutes") or 10)
        )
        tk.Entry(debounce_row, textvariable=self._interval_var, width=6, font=("Helvetica", 11)).pack(
            side="left", padx=4
        )
        PrimaryButton(debounce_row, text="💾 保存", command=self._save_daemon).pack(side="left", padx=(16, 0))

    def _refresh_visibility(self):
        backend = config.get_backend()
        if backend == "github":
            self._cloud_section.pack_forget()
            self._github_section.pack(
                after=self._scroll_frame.winfo_children()[
                    self._scroll_frame.winfo_children().index(
                        [c for c in self._scroll_frame.winfo_children() if isinstance(c, tk.Frame)][0]
                    )
                ],
                fill="x",
            )
        else:
            self._github_section.pack_forget()

    def _on_backend_change(self):
        backend = self._backend_var.get()
        config.set_backend(backend)
        self._refresh_visibility()

    def _cloud_login(self):
        server = self._cloud_entries["server_url"].get().strip()
        username = self._cloud_entries["username"].get().strip()
        password = self._cloud_pwd.get().strip()
        sync_path = self._cloud_entries["sync_path"].get().strip()
        if not username or not password:
            messagebox.showerror("错误", "请填写用户名和密码")
            return
        config.set_config_value(server, "cloud", "server_url")
        config.set_config_value(sync_path or "/codex-memories/", "cloud", "sync_path")
        self._cloud_status.set("正在连接...")
        self.update_idletasks()
        try:
            manbaout_login(username, password)
            config.set_backend("manbaout")
            self._backend_var.set("manbaout")
            self._refresh_visibility()
            self._cloud_status.set("✅ 连接成功")
            self._app._trigger_refresh()
        except AuthError as e:
            self._cloud_status.set(f"❌ {e}")
        except NetworkError:
            self._cloud_status.set("❌ 网络错误")

    def _save_expiry(self):
        try:
            days = int(self._expiry_var.get())
            if days < 1 or days > 365:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入 1 ~ 365 之间的数字")
            return
        config.update_manbaout_expiry(days)
        messagebox.showinfo("成功", f"保存期限已设为 {days} 天")

    def _github_auth(self):
        client_id = self._gh_client_entry.get().strip()
        if not client_id:
            messagebox.showerror("错误", "请先填写 Client ID")
            return
        self._gh_status_var.set("正在获取授权码...")
        self.update_idletasks()
        try:
            result = github_auth_start(client_id)
            self._gh_code_var.set(result["user_code"])
            self._gh_status_var.set("请在浏览器中输入上面的验证码")
            webbrowser.open(result["verification_url"])
            self._poll_github_token(client_id, result["device_code"], result["interval"])
        except AuthError as e:
            self._gh_status_var.set(f"❌ {e}")
        except NetworkError as e:
            self._gh_status_var.set(f"❌ 网络错误: {e}")

    def _poll_github_token(self, client_id: str, device_code: str, interval: int):
        if self._polling:
            return
        self._polling = True
        import time

        def _poll():
            for _ in range(60):
                if not self._polling:
                    return
                try:
                    result = github_auth_poll(client_id, device_code)
                    if result["status"] == "authorized":
                        r = result
                        self.after(0, lambda r=r: self._gh_status_var.set(f"✅ 授权成功 ({r['user']['login']})"))
                        config.set_backend("github")
                        self.after(0, lambda: self._backend_var.set("github"))
                        self.after(100, self._refresh_visibility)
                        self.after(500, self._app._trigger_refresh)
                        return
                except AuthError as err:
                    err_msg = str(err)
                    self.after(0, lambda msg=err_msg: self._gh_status_var.set(f"❌ 授权失败: {msg}"))
                    return
                except Exception as err:
                    err_msg = str(err)
                    self.after(0, lambda msg=err_msg: self._gh_status_var.set(f"⚠️ 网络错误: {msg}"))
                time.sleep(interval)
            self.after(0, lambda: self._gh_status_var.set("⚠️ 授权超时，请重试"))

        threading.Thread(target=_poll, daemon=True).start()

    def _save_encryption(self):
        pwd = self._enc_entry.get().strip()
        if not pwd:
            messagebox.showerror("错误", "加密密码不能为空")
            return
        config.update_security(pwd)
        messagebox.showinfo("成功", "加密密码已保存")

    def _save_daemon(self):
        try:
            debounce = int(self._debounce_var.get())
            interval = int(self._interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效数字")
            return
        config.update_daemon_config(
            debounce_seconds=debounce,
            auto_pull_interval_minutes=interval,
            start_on_boot=self._boot_var.get(),
            minimize_to_tray=self._tray_var.get(),
        )
        messagebox.showinfo("成功", "守护进程设置已保存")

    def destroy(self):
        self._polling = False
        super().destroy()
