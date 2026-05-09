from __future__ import annotations

import datetime
import hashlib
from pathlib import Path


def hash_file(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def format_size(size: int) -> str:
    n: float = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(n) < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n:.0f}B"
        n /= 1024
    return f"{n:.1f}TB"


def format_time(ts_str: str) -> str:
    if not ts_str:
        return "-"
    try:
        ts = float(ts_str)
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(ts_str)[:16].replace("T", " ")
