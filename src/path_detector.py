"""path_detector.py — 跨设备自动检测 Codex 目录位置"""

from __future__ import annotations

import os
from pathlib import Path


def detect_codex_root() -> Path | None:
    r"""自动检测 .codex 目录位置，按优先级：
    1. $CODEX_HOME 环境变量
    2. Windows: %USERPROFILE%\.codex
    3. Linux/Mac: ~/.codex
    """
    # 1. 环境变量
    env_root = os.environ.get("CODEX_HOME", "").strip()
    if env_root:
        p = Path(env_root)
        if p.exists() and p.is_dir():
            return p.resolve()

    # 2. Windows
    if os.name == "nt":
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            p = Path(userprofile) / ".codex"
            if p.exists() and p.is_dir():
                return p.resolve()

    # 3. Linux/Mac home
    home = Path.home()
    p = home / ".codex"
    if p.exists() and p.is_dir():
        return p.resolve()

    return None


def detect_codex_locations() -> dict[str, Path | None]:
    """返回完整路径映射"""
    root = detect_codex_root()
    if root is None:
        return {
            "root": None,
            "memories": None,
            "sessions": None,
            "rules": None,
            "index": None,
        }
    return {
        "root": root,
        "memories": root / "memories",
        "sessions": root / "sessions",
        "rules": root / "rules",
        "index": root / "session_index.jsonl",
    }
