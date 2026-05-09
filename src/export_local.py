from __future__ import annotations

import hashlib
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any

from . import config
from .utils import hash_file


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _import_sh() -> str:
    return r"""#!/bin/bash
set -e
TARGET_MEM="$HOME/.codex/memories"
TARGET_SESS="$HOME/.codex/sessions"
TARGET_RULES="$HOME/.codex/rules"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NEW=0
RENAMED=0
today=$(date +%Y%m%d)

echo "🧠 Codex Memory Import"
echo "======================"
echo ""

import_dir() {
    local src_dir="$1"
    local dest_dir="$2"
    local label="$3"
    if [ ! -d "$src_dir" ]; then
        return
    fi
    echo "$label"
    local _new=0
    local _renamed=0
    while IFS= read -r -d '' rel; do
        local src="$src_dir/$rel"
        local dest="$dest_dir/$rel"
        mkdir -p "$(dirname "$dest")"
        if [ -f "$dest" ]; then
            local base="${dest##*/}"
            local name="${base%.*}"
            local ext="${base##*.}"
            [ "$name" = "$ext" ] && ext=""
            if [ -n "$ext" ]; then
                local safe="${name}_imported_${today}.${ext}"
            else
                local safe="${base}_imported_${today}"
            fi
            cp "$src" "$(dirname "$dest")/$safe"
            echo "⚠️   $rel → $(basename "$dest") 已重命名为 $safe"
            _renamed=$((_renamed + 1))
        else
            cp "$src" "$dest"
            echo "✅   $rel"
            _new=$((_new + 1))
        fi
    done < <(cd "$src_dir" && find . -type f -print0)
    echo "    → 新增 $_new，重命名 $_renamed"
    echo ""
}

import_dir "$SCRIPT_DIR/memories" "$TARGET_MEM" "📁 记忆文件:"
import_dir "$SCRIPT_DIR/sessions" "$TARGET_SESS" "📁 会话记录:"
import_dir "$SCRIPT_DIR/rules" "$TARGET_RULES" "📁 规则文件:"

echo "======================"
echo "完成。打开 Codex 即可使用导入的上下文。"
"""
    return _import_sh


def _import_bat() -> str:
    return r"""@echo off
setlocal enabledelayedexpansion
set TARGET_MEM=%USERPROFILE%\.codex\memories
set TARGET_SESS=%USERPROFILE%\.codex\sessions
set TARGET_RULES=%USERPROFILE%\.codex\rules
set SCRIPT_DIR=%~dp0
set NEW=0
set RENAMED=0

for /f "tokens=2-4 delims=/- " %%a in ('date /t') do set today=%%c%%a%%b

echo Codex Memory Import
echo ======================
echo.

if exist "%SCRIPT_DIR%memories\" (
    echo 📁 记忆文件:
    for /r "%SCRIPT_DIR%memories" %%f in (*) do (
        set "rel=%%f"
        set "rel=!rel:%SCRIPT_DIR%memories\=!"
        set "dest=%TARGET_MEM%\!rel!"
        if not exist "!dest!\\..\\" mkdir "!dest!\\..\\" 2>nul
        if exist "!dest!" (
            set "name=%%~nf"
            set "ext=%%~xf"
            set "safe=!name!_imported_!today!!ext!"
            copy "%%f" "%TARGET_MEM%\!safe!" >nul
            echo ⚠️  !rel! -^> !safe! ^(原文件已存在^)
            set /a RENAMED+=1
        ) else (
            copy "%%f" "!dest!" >nul
            echo ✅ !rel!
            set /a NEW+=1
        )
    )
    echo.
)

if exist "%SCRIPT_DIR%sessions\" (
    echo 📁 会话记录:
    for /r "%SCRIPT_DIR%sessions" %%f in (*) do (
        set "rel=%%f"
        set "rel=!rel:%SCRIPT_DIR%sessions\=!"
        set "dest=%TARGET_SESS%\!rel!"
        if not exist "!dest!\\..\\" mkdir "!dest!\\..\\" 2>nul
        if exist "!dest!" (
            set "name=%%~nf"
            set "ext=%%~xf"
            set "safe=!name!_imported_!today!!ext!"
            copy "%%f" "%TARGET_SESS%\!safe!" >nul
            echo ⚠️  !rel! -^> !safe! ^(原文件已存在^)
            set /a RENAMED+=1
        ) else (
            copy "%%f" "!dest!" >nul
            echo ✅ !rel!
            set /a NEW+=1
        )
    )
    echo.
)

if exist "%SCRIPT_DIR%rules\" (
    echo 📁 规则文件:
    for /r "%SCRIPT_DIR%rules" %%f in (*) do (
        set "rel=%%f"
        set "rel=!rel:%SCRIPT_DIR%rules\=!"
        set "dest=%TARGET_RULES%\!rel!"
        if not exist "!dest!\\..\\" mkdir "!dest!\\..\\" 2>nul
        if exist "!dest!" (
            set "name=%%~nf"
            set "ext=%%~xf"
            set "safe=!name!_imported_!today!!ext!"
            copy "%%f" "%TARGET_RULES%\!safe!" >nul
            echo ⚠️  !rel! -^> !safe! ^(原文件已存在^)
            set /a RENAMED+=1
        ) else (
            copy "%%f" "!dest!" >nul
            echo ✅ !rel!
            set /a NEW+=1
        )
    )
    echo.
)

echo ======================
echo ✅ 新增 !NEW! 个文件
if !RENAMED! gtr 0 echo ⚠️  !RENAMED! 个文件因目标已存在，已重命名（原文件未修改）
echo.
echo 完成。
pause
"""
    return _import_bat


def _readme() -> str:
    return """Codex Memory Import - 一键导入记忆和上下文
============================================

使用方法:
  macOS / Linux:  双击 import.sh 或在终端运行 bash import.sh
  Windows:        双击 import.bat

导入内容:
  memories/   → ~/.codex/memories/     (Codex 记忆文件)
  sessions/   → ~/.codex/sessions/     (会话上下文记录)
  rules/      → ~/.codex/rules/        (规则文件)

防覆盖保护:
  如果目标文件已存在，导入文件会自动重命名为 xxx_imported_日期.ext
  原有文件不会被修改或删除。

manifest.json 中包含每个文件的 SHA256，可用于校验完整性。
"""


def build_manifest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": config.get_config_value("metadata", "local_version") or 1,
        "device": config.get_config_value("metadata", "device_id") or "unknown",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_files": len(entries),
        "total_size": sum(e.get("size", 0) for e in entries),
        "files": entries,
    }


def create_export_zip(
    output_path: Path,
    memory_files: list[Path],
    session_files: list[Path],
    rule_files: list[Path],
    memory_dir: Path,
    session_dir: Path,
    rule_dir: Path,
) -> Path:
    entries: list[dict[str, Any]] = []

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Readme
        zf.writestr("README.txt", _readme())

        # Import scripts
        zf.writestr("import.sh", _import_sh())
        zf.writestr("import.bat", _import_bat())

        # Memory files
        if memory_files:
            for fp in memory_files:
                arcname = str(Path("memories") / fp.relative_to(memory_dir))
                sha = hash_file(fp)
                entries.append(
                    {
                        "path": arcname,
                        "sha256": sha,
                        "size": fp.stat().st_size,
                        "source": str(fp),
                        "type": "memory",
                    }
                )
                zf.write(fp, arcname)

        # Session files
        if session_files:
            for fp in session_files:
                arcname = str(Path("sessions") / fp.relative_to(session_dir))
                sha = hash_file(fp)
                entries.append(
                    {
                        "path": arcname,
                        "sha256": sha,
                        "size": fp.stat().st_size,
                        "source": str(fp),
                        "type": "session",
                    }
                )
                zf.write(fp, arcname)

        # Rule files
        if rule_files:
            for fp in rule_files:
                arcname = str(Path("rules") / fp.relative_to(rule_dir))
                sha = hash_file(fp)
                entries.append(
                    {
                        "path": arcname,
                        "sha256": sha,
                        "size": fp.stat().st_size,
                        "source": str(fp),
                        "type": "rule",
                    }
                )
                zf.write(fp, arcname)

        # Manifest
        manifest = build_manifest(entries)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    return output_path


def discover_sessions(
    sessions_dir: Path,
    index_path: Path,
) -> tuple[list[dict[str, Any]], list[Path]]:
    indexed: dict[str, dict] = {}
    if index_path.exists():
        try:
            for line in index_path.read_text().strip().split("\n"):
                if line.strip():
                    entry = json.loads(line)
                    indexed[entry["id"]] = {
                        "thread_name": entry.get("thread_name", ""),
                        "updated_at": entry.get("updated_at", ""),
                    }
        except (json.JSONDecodeError, OSError):
            pass

    indexed_files: list[dict[str, Any]] = []
    unindexed_files: list[Path] = []

    if not sessions_dir.exists():
        return indexed_files, unindexed_files

    for root, _, files in os.walk(sessions_dir):
        for fname in sorted(files):
            if not fname.endswith(".jsonl"):
                continue
            fp = Path(root) / fname

            session_id = _extract_session_id(fname)
            info = indexed.get(session_id, {}) if session_id else {}
            thread_name = info.get("thread_name", "")

            if thread_name:
                indexed_files.append(
                    {
                        "path": fp,
                        "name": fname,
                        "session_id": session_id,
                        "thread_name": thread_name,
                        "size": fp.stat().st_size,
                        "updated_at": info.get("updated_at", ""),
                        "relative": str(fp.relative_to(sessions_dir)),
                    }
                )
            else:
                unindexed_files.append(fp)

    indexed_files.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    unindexed_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return indexed_files, unindexed_files


def _extract_session_id(filename: str) -> str | None:
    parts = filename.replace(".jsonl", "").split("-")
    if len(parts) >= 11:
        return "-".join(parts[6:])
    return None


def discover_memories(memory_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not memory_dir.exists():
        return result

    for item in sorted(memory_dir.iterdir(), key=lambda p: (p.is_dir(), p.name.lower())):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            children = []
            for child in sorted(item.iterdir()):
                if child.is_file() and not child.name.startswith("."):
                    children.append(
                        {
                            "path": child,
                            "name": child.name,
                            "size": child.stat().st_size,
                            "mtime": child.stat().st_mtime,
                            "relative": str(child.relative_to(memory_dir)),
                        }
                    )
            if children:
                result.append(
                    {
                        "path": item,
                        "name": item.name + "/",
                        "is_dir": True,
                        "children": children,
                        "size": sum(c["size"] for c in children),
                    }
                )
        else:
            result.append(
                {
                    "path": item,
                    "name": item.name,
                    "is_dir": False,
                    "size": item.stat().st_size,
                    "mtime": item.stat().st_mtime,
                    "relative": item.name,
                }
            )
    return result


def discover_rules(rules_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not rules_dir.exists():
        return result
    for item in sorted(rules_dir.iterdir()):
        if item.name.startswith(".") or item.is_dir():
            continue
        result.append(
            {
                "path": item,
                "name": item.name,
                "size": item.stat().st_size,
                "mtime": item.stat().st_mtime,
            }
        )
    return result
