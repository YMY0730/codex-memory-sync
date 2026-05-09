import tkinter as tk
from tkinter import messagebox

from .widgets import BG_COLOR, CARD_BG, TEXT_PRIMARY, TEXT_SECONDARY


def show_about(parent):
    messagebox.showinfo(
        "关于",
        "Codex Memory Sync v1.0.0\n\n"
        "跨设备 Codex 记忆同步工具\n\n"
        "功能:\n"
        "  • 加密打包本地 Codex 记忆\n"
        "  • 上传到 ManbaOut 云盘\n"
        "  • 换设备一键下载还原\n"
        "  • 守护进程自动同步\n\n"
        "云盘: manbaout.cn\n",
    )


def show_conflict_dialog(parent, local_info: dict, cloud_info: dict) -> str:
    dialog = tk.Toplevel(parent)
    dialog.title("同步冲突")
    dialog.geometry("480x340")
    dialog.resizable(False, False)
    dialog.configure(bg=BG_COLOR)
    dialog.transient(parent)
    dialog.grab_set()

    result = tk.StringVar(value="cancel")

    tk.Label(dialog, text="⚠️ 同步冲突", fg="#e74c3c", bg=BG_COLOR, font=("Helvetica", 14, "bold")).pack(pady=(16, 4))
    tk.Label(
        dialog, text="本地和云端都有新版本，内容不同。", fg=TEXT_SECONDARY, bg=BG_COLOR, font=("Helvetica", 10)
    ).pack()

    local_card = tk.Frame(dialog, bg=CARD_BG, highlightbackground="#e0e0e0", highlightthickness=1)
    local_card.pack(fill="x", padx=24, pady=(12, 4))

    tk.Label(
        local_card,
        text=f"💻 本地版本 v{local_info.get('version', '?')}",
        fg=TEXT_PRIMARY,
        bg=CARD_BG,
        font=("Helvetica", 11, "bold"),
    ).pack(padx=12, pady=(8, 2), anchor="w")
    tk.Label(
        local_card,
        text=f"设备: {local_info.get('device_id', '?')}",
        fg=TEXT_SECONDARY,
        bg=CARD_BG,
        font=("Helvetica", 10),
    ).pack(padx=12, anchor="w")
    tk.Label(
        local_card,
        text=f"Hash: {local_info.get('hash', '?')[:16]}...",
        fg=TEXT_SECONDARY,
        bg=CARD_BG,
        font=("Helvetica", 10),
    ).pack(padx=12, pady=(0, 8), anchor="w")

    cloud_card = tk.Frame(dialog, bg=CARD_BG, highlightbackground="#e0e0e0", highlightthickness=1)
    cloud_card.pack(fill="x", padx=24, pady=4)

    tk.Label(
        cloud_card,
        text=f"☁️ 云端版本 v{cloud_info.get('latest_version', '?')}",
        fg=TEXT_PRIMARY,
        bg=CARD_BG,
        font=("Helvetica", 11, "bold"),
    ).pack(padx=12, pady=(8, 2), anchor="w")
    tk.Label(
        cloud_card,
        text=f"设备: {cloud_info.get('latest_device', '?')}",
        fg=TEXT_SECONDARY,
        bg=CARD_BG,
        font=("Helvetica", 10),
    ).pack(padx=12, anchor="w")
    tk.Label(
        cloud_card,
        text=f"Hash: {cloud_info.get('latest_hash', '?')[:16]}...",
        fg=TEXT_SECONDARY,
        bg=CARD_BG,
        font=("Helvetica", 10),
    ).pack(padx=12, pady=(0, 8), anchor="w")

    btn_frame = tk.Frame(dialog, bg=BG_COLOR)
    btn_frame.pack(fill="x", padx=24, pady=(12, 16))

    def _choose(action):
        result.set(action)
        dialog.destroy()

    tk.Button(
        btn_frame,
        text="保留本地",
        bg="#3498db",
        fg="white",
        font=("Helvetica", 11),
        relief="flat",
        padx=16,
        pady=6,
        cursor="hand2",
        command=lambda: _choose("keep_local"),
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_frame,
        text="保留云端",
        bg="#2ecc71",
        fg="white",
        font=("Helvetica", 11),
        relief="flat",
        padx=16,
        pady=6,
        cursor="hand2",
        command=lambda: _choose("keep_cloud"),
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_frame,
        text="取消",
        bg="#95a5a6",
        fg="white",
        font=("Helvetica", 11),
        relief="flat",
        padx=16,
        pady=6,
        cursor="hand2",
        command=lambda: _choose("cancel"),
    ).pack(side="left")

    dialog.wait_window()
    return result.get()
