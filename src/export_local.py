from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any

from .utils import hash_file


def _encrypt_zip_file(zip_path: Path, password: str) -> Path:
    """用 AES-256-GCM 加密 ZIP 文件，返回加密后路径"""
    import os as _os
    import struct

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    raw = zip_path.read_bytes()
    salt = _os.urandom(16)
    nonce = _os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, raw, None)

    enc_path = zip_path.with_suffix(".codex")
    header = struct.pack(">B", 1) + salt + nonce
    enc_path.write_bytes(header + ciphertext)
    zip_path.unlink(missing_ok=True)
    return enc_path


def build_manifest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": _config_get("metadata", "local_version") or 1,
        "device": _config_get("metadata", "device_id") or "unknown",
        "exported_at": _time_now(),
        "total_files": len(entries),
        "total_size": sum(e.get("size", 0) for e in entries),
        "files": entries,
    }


def _config_get(*keys: str) -> Any:
    try:
        from . import config

        return config.get_config_value(*keys)
    except Exception:
        return ""


def _time_now() -> str:
    import datetime

    return datetime.datetime.now().isoformat()


def create_export_zip(
    output_path: Path,
    memory_files: list[Path],
    session_files: list[Path],
    rule_files: list[Path],
    memory_dir: Path,
    session_dir: Path,
    rule_dir: Path,
    password: str | None = None,
) -> Path:
    entries: list[dict[str, Any]] = []

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _readme(password is not None))
        zf.writestr("import.sh", _import_sh(password is not None))
        zf.writestr("import.bat", _import_bat(password is not None))

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

    if password:
        return _encrypt_zip_file(output_path, password)
    return output_path


def _readme(encrypted: bool = False) -> str:
    extra = ""
    if encrypted:
        extra = "\n⚠️ 此包已加密。导入时需要输入密码解密。\n"
    return f"""Codex Memory Import - 一键导入记忆和上下文
============================================

使用方法:
  macOS / Linux:  双击 import.sh 或在终端运行 bash import.sh
  Windows:        双击 import.bat
{extra}
导入内容:
  memories/   → ~/.codex/memories/     (Codex 记忆文件)
  sessions/   → ~/.codex/sessions/     (会话上下文记录)
  rules/      → ~/.codex/rules/        (规则文件)

防覆盖保护:
  如果目标文件已存在，导入文件会自动重命名为 xxx_imported_日期.ext

manifest.json 中包含每个文件的 SHA256，可用于校验完整性。
"""


def _import_sh(encrypted: bool = False) -> str:
    decrypt_block = ""
    if encrypted:
        decrypt_block = """
echo ""
read -s -p "输入导出时设置的密码: " DECRYPT_PWD
echo ""
echo "🔓 正在解密..."
python3 -c "
import sys,struct,os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
data=open(sys.argv[1],'rb').read()
salt,nonce=data[1:17],data[17:29]
ct=data[29:]
kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=salt,iterations=600000)
key=kdf.derive(sys.argv[2].encode())
aesgcm=AESGCM(key)
plain=aesgcm.decrypt(nonce,ct,None)
open(sys.argv[3],'wb').write(plain)
" "$SCRIPT_DIR/$0" "$DECRYPT_PWD" "$SCRIPT_DIR/__d.zip" 2>/dev/null
if [ $? -ne 0 ] || [ ! -f "$SCRIPT_DIR/__d.zip" ]; then echo "❌ 密码错误"; exit 1; fi
unzip -qo "$SCRIPT_DIR/__d.zip" -d "$SCRIPT_DIR" >/dev/null 2>&1
rm -f "$SCRIPT_DIR/__d.zip"
exit 0
"""
    return f"""#!/bin/bash
set -e
TARGET_MEM="$HOME/.codex/memories"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
{decrypt_block}
import_dir() {{
    local src="$1"; local dest="$2"; local label="$3"
    [ ! -d "$src" ] && return
    echo "$label"
    local n=0; local r=0; local today=$(date +%Y%m%d)
    while IFS= read -r -d '' rel; do
        local s="$src/$rel"; local d="$dest/$rel"
        mkdir -p "$(dirname "$d")"
        if [ -f "$d" ]; then
            local b="${{d##*/}}"; local nm="${{b%.*}}"; local ex="${{b##*.}}"
            [ "$nm" = "$ex" ] && ex=""
            [ -n "$ex" ] && local sf="${{nm}}_imported_${{today}}.${{ex}}" || local sf="${{b}}_imported_${{today}}"
            cp "$s" "$(dirname "$d")/$sf"
            n=$((n+1))
        else
            cp "$s" "$d"; r=$((r+1))
        fi
    done < <(cd "$src" && find . -type f -print0)
    echo "    -> 导入 $r 个"
}}
import_dir "$SCRIPT_DIR/memories" "$TARGET_MEM" "📁 记忆文件:"
import_dir "$SCRIPT_DIR/sessions" "$HOME/.codex/sessions" "📁 会话记录:"
import_dir "$SCRIPT_DIR/rules" "$HOME/.codex/rules" "📁 规则文件:"
echo "完成。"
"""


def _import_bat(encrypted: bool = False) -> str:
    decrypt_block = ""
    if encrypted:
        decrypt_block = """set /p DECRYPT_PWD="输入导出时设置的密码: "
echo 解密中...
python -c "import sys,struct,os;from cryptography.hazmat.primitives.ciphers.aead import AESGCM;from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC;from cryptography.hazmat.primitives import hashes;data=open(sys.argv[1],'rb').read();s,n,ct=data[1:17],data[17:29],data[29:];kdf=PBKDF2HMAC(algorithm=hashes.SHA256(),length=32,salt=s,iterations=600000);key=kdf.derive(sys.argv[2].encode());aesgcm=AESGCM(key);open(sys.argv[3],'wb').write(aesgcm.decrypt(n,ct,None))" "%%~f0" "%%DECRYPT_PWD%%" "%%~dp0__d.zip" 2>nul
if not exist "%%~dp0__d.zip" (echo 密码错误&& pause && exit /b 1)
"""
    return f"""@echo off
setlocal enabledelayedexpansion
{decrypt_block}
set TARGET_MEM=%%USERPROFILE%%\\.codex\\memories
set SCRIPT_DIR=%%~dp0
set NEW=0 && set RENAMED=0
for /f "tokens=2-4 delims=/- " %%a in ('date /t') do set today=%%c%%a%%b
echo Codex Memory Import
echo ======================

if exist "%%SCRIPT_DIR%%memories\\" (
    echo 📁 记忆文件:
    for /r "%%SCRIPT_DIR%%memories" %%f in (*) do (
        set "rel=%%f" && set "rel=!rel:%%SCRIPT_DIR%%memories\\=!"
        set "dest=%%TARGET_MEM%%\\!rel!"
        mkdir "!dest!\\..\\" 2>nul
        if exist "!dest!" (
            set "safe=%%~nf_imported_!today!%%~xf"
            copy "%%f" "%%TARGET_MEM%%\\!safe!" >nul && set /a RENAMED+=1
        ) else (
            copy "%%f" "!dest!" >nul && set /a NEW+=1
        )
    )
    echo.
)
if exist "%%SCRIPT_DIR%%sessions\\" (
    echo 📁 会话记录:
    for /r "%%SCRIPT_DIR%%sessions" %%f in (*) do (
        set "rel=%%f" && set "rel=!rel:%%SCRIPT_DIR%%sessions\\=!"
        set "dest=%%USERPROFILE%%\\.codex\\sessions\\!rel!"
        mkdir "!dest!\\..\\" 2>nul
        if exist "!dest!" ( copy "%%f" "!dest!\\..\\%%~nf_imported_!today!%%~xf" >nul ) else ( copy "%%f" "!dest!" >nul )
    )
    echo.
)
echo 完成。
pause
"""


def discover_sessions(
    sessions_dir: Path,
    index_path: Path,
) -> tuple[list[dict[str, Any]], list[Path]]:
    indexed: dict[str, dict] = {}
    if index_path.exists():
        try:
            for line in index_path.read_text(encoding="utf-8", errors="replace").strip().split("\n"):
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
