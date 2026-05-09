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
    BORDER,
    CARD_BG,
    RECOMMEND_BG,
    RECOMMEND_BORDER,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARN_BG,
    WARN_BORDER,
    WARNING,
    PrimaryButton,
    SecondaryButton,
    WarningBanner,
)


class WizardWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Codex Memory Sync 设置向导")
        self.geometry("560x560")
        self.resizable(False, False)
        self.configure(bg=BG_COLOR)
        self._parent = parent
        self._step = 0
        self._backend = tk.StringVar(value="github")
        self._polling = False

        self._header = tk.Label(
            self, text="🧠 Codex Memory Sync 设置向导", fg="white", bg=ACCENT, font=("Helvetica", 16, "bold"), pady=14
        )
        self._header.pack(fill="x")

        self._step_label = tk.Label(self, text="", fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Helvetica", 11))
        self._step_label.pack(pady=(8, 0))

        self._content = tk.Frame(self, bg=BG_COLOR)
        self._content.pack(fill="both", expand=True, padx=24, pady=8)

        self._btn_frame = tk.Frame(self, bg=BG_COLOR)
        self._btn_frame.pack(fill="x", padx=24, pady=12)

        self._show_step(0)

    def _show_step(self, step: int):
        for w in self._content.winfo_children():
            w.destroy()
        for w in self._btn_frame.winfo_children():
            w.destroy()
        self._polling = False
        self._step = step

        if step == 0:
            self._show_step_backend()
        elif step == 1:
            self._show_step_encryption()
        elif step == 2:
            self._show_step_files()

    def _show_step_backend(self):
        self._step_label.configure(text="第 1 步：选择存储后端")

        canvas = tk.Canvas(self._content, bg=BG_COLOR, highlightthickness=0)
        scrollbar = tk.Scrollbar(self._content, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_COLOR)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- GitHub Card (Recommended) ---
        gh_outer = tk.Frame(scroll_frame, bg=RECOMMEND_BG, highlightbackground=RECOMMEND_BORDER, highlightthickness=2)
        gh_outer.pack(fill="x", pady=(4, 8))

        tk.Label(gh_outer, text="⭐ 推荐", fg=SUCCESS, bg=RECOMMEND_BG, font=("Helvetica", 10, "bold")).pack(
            anchor="w", padx=14, pady=(8, 0)
        )

        tk.Label(
            gh_outer, text="🐙 GitHub 私有仓库", fg=TEXT_PRIMARY, bg=RECOMMEND_BG, font=("Helvetica", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(2, 4))

        benefits = [
            "• 数据永久保存，不会过期",
            "• 端到端 AES-256 加密",
            "• 免费私有仓库，不限容量",
            "• 通过 OAuth 安全授权，无需密码",
        ]
        for b in benefits:
            tk.Label(
                gh_outer, text=b, fg=TEXT_SECONDARY, bg=RECOMMEND_BG, font=("Helvetica", 10), anchor="w", justify="left"
            ).pack(anchor="w", padx=20)

        self._gh_status_var = tk.StringVar(value="")
        self._gh_auth_btn = PrimaryButton(gh_outer, text="🔑 授权 GitHub", command=self._github_auth)
        self._gh_auth_btn.pack(padx=14, pady=(8, 4), anchor="w")

        self._gh_code_var = tk.StringVar(value="")
        self._gh_code_label = tk.Label(
            gh_outer, textvariable=self._gh_code_var, fg=ACCENT, bg=RECOMMEND_BG, font=("Menlo", 18, "bold")
        )
        self._gh_code_label.pack(pady=(0, 4))

        tk.Label(
            gh_outer, textvariable=self._gh_status_var, fg=TEXT_SECONDARY, bg=RECOMMEND_BG, font=("Helvetica", 10)
        ).pack(anchor="w", padx=14, pady=(0, 4))

        tk.Label(
            gh_outer,
            text="ℹ️ 需要 GitHub OAuth App 的 Client ID",
            fg=TEXT_SECONDARY,
            bg=RECOMMEND_BG,
            font=("Helvetica", 9),
        ).pack(anchor="w", padx=14)
        help_text = (
            "获取方式: GitHub Settings → Developer settings → OAuth Apps → New OAuth App\n"
            "Homepage URL 和 Callback URL 填 http://localhost 即可"
        )
        tk.Label(
            gh_outer, text=help_text, fg="#999", bg=RECOMMEND_BG, font=("Helvetica", 8), anchor="w", justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 2))

        client_frame = tk.Frame(gh_outer, bg=RECOMMEND_BG)
        client_frame.pack(fill="x", padx=14, pady=(2, 12))
        tk.Label(client_frame, text="Client ID:", fg=TEXT_SECONDARY, bg=RECOMMEND_BG, font=("Helvetica", 10)).pack(
            side="left"
        )
        self._client_id_entry = tk.Entry(client_frame, font=("Helvetica", 10), width=35)
        existing_client = config.get_config_value("github", "client_id") or ""
        self._client_id_entry.insert(0, existing_client)
        self._client_id_entry.pack(side="left", padx=4, fill="x", expand=True)

        select_btn = PrimaryButton(gh_outer, text="选这个 →", command=self._select_github)
        select_btn.pack(padx=14, pady=(0, 12), anchor="w")

        self._gh_radiobtn = tk.Radiobutton(
            scroll_frame, text="", variable=self._backend, value="github", bg=BG_COLOR, command=lambda: None
        )
        self._gh_radiobtn.pack(anchor="w")

        # --- ManbaOut Card ---
        mb_outer = tk.Frame(scroll_frame, bg=WARN_BG, highlightbackground=WARN_BORDER, highlightthickness=1)
        mb_outer.pack(fill="x", pady=(8, 4))

        tk.Label(mb_outer, text="⚠️ 实验性", fg=WARNING, bg=WARN_BG, font=("Helvetica", 10, "bold")).pack(
            anchor="w", padx=14, pady=(8, 0)
        )

        tk.Label(
            mb_outer, text="☁️ ManbaOut 云盘 (manbaout.cn)", fg=TEXT_PRIMARY, bg=WARN_BG, font=("Helvetica", 13, "bold")
        ).pack(anchor="w", padx=14, pady=(2, 4))

        WarningBanner(mb_outer, "默认仅保存 3 天，到期自动清理。可在设置中调整期限（最长 365 天）。").pack(
            fill="x", padx=14, pady=(4, 2)
        )
        WarningBanner(mb_outer, "数据经 AES-256 端到端加密，平台无法读取内容。").pack(fill="x", padx=14, pady=(2, 2))

        disclaimer = (
            "免责声明：本平台仅提供加密数据的中转存储服务。因端到端加密，平台无法解密或使用数据。"
            "若未及时续期导致数据被系统清理，平台不承担责任。建议长期使用请选择 GitHub。"
        )
        tk.Label(
            mb_outer,
            text=disclaimer,
            fg="#e67e22",
            bg=WARN_BG,
            font=("Helvetica", 8),
            anchor="w",
            justify="left",
            wraplength=480,
        ).pack(anchor="w", padx=14, pady=(2, 8))

        fields = [
            ("服务器:", "https://manbaout.cn"),
            ("用户名:", ""),
            ("密码:", ""),
        ]
        self._mb_entries = {}
        for _i, (label, default) in enumerate(fields):
            row = tk.Frame(mb_outer, bg=WARN_BG)
            row.pack(fill="x", padx=14, pady=(2, 0))
            tk.Label(row, text=label, fg=TEXT_SECONDARY, bg=WARN_BG, anchor="w", width=8, font=("Helvetica", 10)).pack(
                side="left"
            )
            show = "*" if "密码" in label else ""
            entry = tk.Entry(row, font=("Helvetica", 10), show=show)
            entry.insert(0, default)
            entry.pack(side="left", fill="x", expand=True)
            self._mb_entries[label] = entry

        self._mb_status_var = tk.StringVar(value="")
        tk.Label(mb_outer, textvariable=self._mb_status_var, fg=TEXT_SECONDARY, bg=WARN_BG, font=("Helvetica", 9)).pack(
            anchor="w", padx=14, pady=(4, 0)
        )

        btn_row = tk.Frame(mb_outer, bg=WARN_BG)
        btn_row.pack(fill="x", padx=14, pady=(4, 12))
        PrimaryButton(btn_row, text="🔑 登录", command=self._manbaout_login).pack(side="left", padx=(0, 8))
        SecondaryButton(btn_row, text="选这个 →", command=self._select_manbaout).pack(side="left")

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _github_auth(self):
        client_id = self._client_id_entry.get().strip()
        if not client_id:
            messagebox.showerror("错误", "请先填写 GitHub OAuth App 的 Client ID")
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

        def _poll():
            for _attempt in range(60):
                if not self._polling:
                    return
                try:
                    result = github_auth_poll(client_id, device_code)
                    if result["status"] == "authorized":
                        r = result
                        self.after(0, lambda r=r: self._gh_status_var.set(f"✅ 授权成功 ({r['user']['login']})"))
                        self.after(500, lambda: self._show_step(1))
                        return
                    elif result["status"] == "slow_down":
                        time.sleep(interval * 2)
                    else:
                        time.sleep(interval)
                except AuthError as err:
                    err_msg = str(err)
                    self.after(0, lambda msg=err_msg: self._gh_status_var.set(f"❌ 授权失败: {msg}"))
                    return
                except Exception as err:
                    err_msg = str(err)
                    self.after(0, lambda msg=err_msg: self._gh_status_var.set(f"⚠️ 网络错误: {msg}"))
                    time.sleep(interval)
            self.after(0, lambda: self._gh_status_var.set("⚠️ 授权超时，请重试"))

        import time

        threading.Thread(target=_poll, daemon=True).start()

    def _manbaout_login(self):
        server = self._mb_entries["服务器:"].get().strip()
        username = self._mb_entries["用户名:"].get().strip()
        password = self._mb_entries["密码:"].get().strip()
        if not username or not password:
            messagebox.showerror("错误", "请填写用户名和密码")
            return
        self._mb_status_var.set("正在连接...")
        self.update_idletasks()
        config.set_config_value(server, "cloud", "server_url")
        try:
            manbaout_login(username, password)
            self._mb_status_var.set("✅ 登录成功")
            self.after(1000, lambda: self._show_step(1))
        except AuthError as e:
            self._mb_status_var.set(f"❌ {e}")
        except NetworkError as e:
            self._mb_status_var.set(f"❌ 网络错误: {e}")

    def _select_github(self):
        self._backend.set("github")
        config.set_backend("github")
        token = config.get_config_value("github", "token") or ""
        if token:
            self._show_step(1)
        elif not self._client_id_entry.get().strip():
            messagebox.showinfo("提示", "请先填写 Client ID 并点击'授权 GitHub'")

    def _select_manbaout(self):
        self._backend.set("manbaout")
        config.set_backend("manbaout")
        token = config.get_config_value("cloud", "token") or ""
        if token:
            self._show_step(1)
        else:
            messagebox.showinfo("提示", "请先填写用户名密码并点击'登录'")

    def _show_step_encryption(self):
        self._step_label.configure(text="第 2 步：设置加密密码")
        card = tk.Frame(self._content, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, pady=8)

        tk.Label(
            card, text="设置一个密码用于加密你的记忆文件", fg=TEXT_PRIMARY, bg=CARD_BG, font=("Helvetica", 12, "bold")
        ).pack(padx=16, pady=(16, 4))
        tk.Label(
            card, text="换设备时需要输入相同密码才能解密", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 10)
        ).pack(padx=16, pady=(0, 12))

        pwd_frame = tk.Frame(card, bg=CARD_BG)
        pwd_frame.pack(fill="x", padx=16)
        tk.Label(pwd_frame, text="加密密码:", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 11)).pack(anchor="w")
        self._wiz_pwd1 = tk.Entry(pwd_frame, font=("Helvetica", 11), show="*", width=45)
        self._wiz_pwd1.pack(fill="x", pady=(4, 8))

        tk.Label(pwd_frame, text="确认密码:", fg=TEXT_SECONDARY, bg=CARD_BG, font=("Helvetica", 11)).pack(anchor="w")
        self._wiz_pwd2 = tk.Entry(pwd_frame, font=("Helvetica", 11), show="*", width=45)
        self._wiz_pwd2.pack(fill="x", pady=(4, 8))

        WarningBanner(card, "请务必记住此密码，丢失后无法恢复记忆数据。").pack(fill="x", padx=16, pady=(4, 16))

        SecondaryButton(self._btn_frame, text="← 上一步", command=lambda: self._show_step(0)).pack(side="left")
        PrimaryButton(self._btn_frame, text="下一步 →", command=self._save_pwd_and_next).pack(side="right")

    def _save_pwd_and_next(self):
        p1 = self._wiz_pwd1.get().strip()
        p2 = self._wiz_pwd2.get().strip()
        if not p1:
            messagebox.showerror("错误", "密码不能为空")
            return
        if p1 != p2:
            messagebox.showerror("错误", "两次密码不一致")
            return
        config.update_security(p1)
        self._show_step(2)

    def _show_step_files(self):
        self._step_label.configure(text="第 3 步：选择要同步的记忆文件")
        card = tk.Frame(self._content, bg=CARD_BG, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, pady=8)

        tk.Label(
            card, text="勾选需要跨设备同步的记忆文件", fg=TEXT_PRIMARY, bg=CARD_BG, font=("Helvetica", 12, "bold")
        ).pack(padx=16, pady=(16, 4))

        list_frame = tk.Frame(card, bg=CARD_BG)
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        memory_path = config.get_memory_path()
        default_selected = {"MEMORY.md", "raw_memories.md", "memory_summary.md"}
        self._file_check_vars: dict[str, tk.BooleanVar] = {}

        if memory_path.exists():
            files = sorted(memory_path.iterdir(), key=lambda p: (p.is_dir(), p.name.lower()))
            for f in files:
                if f.name.startswith("."):
                    continue
                var = tk.BooleanVar(value=f.name in default_selected)
                self._file_check_vars[f.name] = var
                name = f.name + ("/" if f.is_dir() else "")
                tk.Checkbutton(
                    list_frame, text=name, variable=var, bg=CARD_BG, font=("Helvetica", 11), anchor="w"
                ).pack(fill="x", pady=2)
        else:
            tk.Label(
                list_frame,
                text="记忆目录暂不存在，后续可在设置中配置",
                fg=TEXT_SECONDARY,
                bg=CARD_BG,
                font=("Helvetica", 10),
            ).pack(pady=16)

        SecondaryButton(self._btn_frame, text="← 上一步", command=lambda: self._show_step(1)).pack(side="left")
        PrimaryButton(self._btn_frame, text="🎉 完成，开始使用", command=self._finish).pack(side="right")

    def _finish(self):
        selected = [name for name, var in self._file_check_vars.items() if var.get()]
        if selected:
            config.update_local_files(selected)
        messagebox.showinfo("设置完成", "Codex Memory Sync 已配置完毕！\n\n现在可以开始同步记忆了。")
        self.destroy()
        self._parent._trigger_refresh()
