#!/usr/bin/env python3
"""PyInstaller 打包脚本 - macOS / Windows"""

import os
import platform
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")


def build():
    system = platform.system()
    _is_macos = system == "Darwin"

    os.makedirs(DIST_DIR, exist_ok=True)

    common_args = [
        "--noconfirm",
        "--clean",
        "--add-data",
        f"gui{os.pathsep}gui",
        "--add-data",
        f"src{os.pathsep}src",
        "--hidden-import",
        "tkinter",
        "--hidden-import",
        "cryptography",
        "--hidden-import",
        "watchdog",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "pystray",
        "--hidden-import",
        "click",
        "--hidden-import",
        "requests",
        "--collect-all",
        "cryptography",
    ]

    # 1. CLI 单文件二进制
    print("🔨 Building CLI binary...")
    cli_args = (
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "codex-memory",
            "--onefile",
        ]
        + common_args
        + [os.path.join(PROJECT_DIR, "cli.py")]
    )

    subprocess.run(cli_args, cwd=PROJECT_DIR, check=True)
    print("   ✅ CLI binary built\n")

    # 2. macOS GUI .app
    print("🔨 Building macOS GUI .app...")
    gui_args = (
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name",
            "CodexMemorySync",
            "--onedir",
            "--windowed",
            "--osx-bundle-identifier",
            "com.codex.memory-sync",
        ]
        + common_args
        + [os.path.join(PROJECT_DIR, "gui_app.py")]
    )

    subprocess.run(gui_args, cwd=PROJECT_DIR, check=True)

    # 清理 onedir 的裸目录，只保留 .app
    bare_dir = os.path.join(DIST_DIR, "CodexMemorySync")
    if os.path.isdir(bare_dir) and not bare_dir.endswith(".app"):
        shutil.rmtree(bare_dir, ignore_errors=True)

    print("\n✅ Build complete! Output:")
    for name in sorted(os.listdir(DIST_DIR)):
        path = os.path.join(DIST_DIR, name)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"   📄 {name} ({size_mb:.1f}MB)")
        elif os.path.isdir(path):
            size_mb = _dir_size(path) / (1024 * 1024)
            label = "🍎" if name.endswith(".app") else "📁"
            print(f"   {label} {name} ({size_mb:.1f}MB)")

    app = os.path.join(DIST_DIR, "CodexMemorySync.app")
    if os.path.exists(app):
        print(f"\n   双击 {app} 即可启动桌面客户端！")


def _dir_size(path: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return total


if __name__ == "__main__":
    build()
