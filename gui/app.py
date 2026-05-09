import tkinter as tk
from tkinter import ttk

from src import config
from src.cloud import CloudError, is_cloud_configured, list_cloud_versions
from src.metadata import SyncStatus, compare

from .tab_cloud import CloudTab
from .tab_local import LocalTab
from .tab_settings import SettingsTab
from .tab_sync import SyncTab
from .widgets import (
    ACCENT,
    BG_COLOR,
    SUCCESS,
    TEXT_SECONDARY,
    StatusBadge,
)
from .wizard import WizardWindow


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.withdraw()

        self.title("Codex Memory Sync")
        self.geometry("780x600")
        self.minsize(680, 480)
        self.configure(bg=BG_COLOR)

        self._check_first_run()

        header = tk.Frame(self, bg=ACCENT, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🧠 Codex Memory Sync", fg="white", bg=ACCENT, font=("Helvetica", 14, "bold")).pack(
            side="left", padx=16, pady=10
        )

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True)

        self._cloud_tab = CloudTab(self._notebook, self)
        self._local_tab = LocalTab(self._notebook, self)
        self._sync_tab = SyncTab(self._notebook, self)
        self._settings_tab = SettingsTab(self._notebook, self)

        self._notebook.add(self._cloud_tab, text="  ☁️ 云端  ")
        self._notebook.add(self._local_tab, text="  💻 本地  ")
        self._notebook.add(self._sync_tab, text="  🔄 同步  ")
        self._notebook.add(self._settings_tab, text="  ⚙️ 设置  ")

        self._status_bar = tk.Frame(self, bg="#e8e8e8", height=28)
        self._status_bar.pack(fill="x", side="bottom")
        self._status_bar.pack_propagate(False)

        self._status_badge = StatusBadge(self._status_bar)
        self._status_badge.pack(side="left", padx=(10, 4), pady=6)

        self._status_text = tk.StringVar(value="就绪")
        tk.Label(
            self._status_bar, textvariable=self._status_text, fg=TEXT_SECONDARY, bg="#e8e8e8", font=("Helvetica", 10)
        ).pack(side="left")

        self._sync_info_var = tk.StringVar(value="")
        tk.Label(
            self._status_bar, textvariable=self._sync_info_var, fg=TEXT_SECONDARY, bg="#e8e8e8", font=("Helvetica", 10)
        ).pack(side="right", padx=10)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._update_status()
        self.after(30000, self._periodic_refresh)

        self.deiconify()

    def _check_first_run(self):
        if config.is_cloud_configured():
            token = config.get_config_value("cloud", "token") or ""
            enc_pwd = config.get_config_value("security", "encryption_password") or ""
            if not token or not enc_pwd:
                wizard = WizardWindow(self)
                wizard.grab_set()
                self.wait_window(wizard)

    def _trigger_refresh(self):
        self._cloud_tab._refresh()
        self._local_tab._refresh()
        self._update_status()

    def _periodic_refresh(self):
        import contextlib

        with contextlib.suppress(Exception):
            self._update_status()
        self.after(30000, self._periodic_refresh)

    def _update_status(self):
        if not is_cloud_configured():
            self._status_badge.set_status("#95a5a6")
            self._status_text.set("本地模式")
            self._sync_info_var.set("未配置云后端")
            return

        try:
            versions = list_cloud_versions()
        except (CloudError, Exception):
            versions = []
        result = compare(versions)

        status = result["status"]
        if status == SyncStatus.SYNCED.value:
            self._status_badge.set_status(SUCCESS)
            self._status_text.set("已同步")
        elif status == SyncStatus.LOCAL_AHEAD.value:
            self._status_badge.set_status("#f39c12")
            self._status_text.set("待推送")
        elif status == SyncStatus.CLOUD_AHEAD.value:
            self._status_badge.set_status("#3498db")
            self._status_text.set("可拉取")
        elif status == SyncStatus.CONFLICT.value:
            self._status_badge.set_status("#e74c3c")
            self._status_text.set("冲突")
        else:
            self._status_badge.set_status("#95a5a6")
            self._status_text.set("未初始化")

        local_ver = result["local"]["version"]
        cloud_ver = result["cloud"]["latest_version"]
        self._sync_info_var.set(f"v{local_ver} ← 本地  |  ☁️ 云端 v{cloud_ver}")

    def _on_close(self):
        minimize = config.get_config_value("daemon", "minimize_to_tray")
        if minimize:
            self.withdraw()
            from .tray import setup_tray

            tray_icon = setup_tray(self)
            if tray_icon:
                import threading

                threading.Thread(target=tray_icon.run, daemon=True).start()
        else:
            self.destroy()


def main():
    app = MainWindow()
    app.mainloop()
