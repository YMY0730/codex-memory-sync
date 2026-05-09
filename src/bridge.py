"""bridge.py — Codex ↔ OpenCode 双向转换引擎

Codex 数据格式:  JSONL 文件, sessions/YYYY/MM/<id>.jsonl, session_index.jsonl
OpenCode 数据格式: SQLite (opencode.db), tables: session/message/part

映射:
  Codex session_meta                    → OpenCode session 表
  Codex response_item(message)          → OpenCode message + part(text)
  Codex response_item(reasoning)        → OpenCode message + part(reasoning)
  Codex response_item(function_call)    → OpenCode message + part(tool)
  Codex event_msg(task_start/end)       → 跳过
"""

from __future__ import annotations

import contextlib
import json
import shutil
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# ══════════════════════════════════════════════════════════════════════════════
# 路径检测
# ══════════════════════════════════════════════════════════════════════════════


def _codex_root() -> Path | None:
    """检测 Codex 根目录"""
    home = Path.home()
    for loc in [home / ".codex"]:
        if loc.exists():
            return loc
    return None


def _codex_sessions_dir() -> Path | None:
    root = _codex_root()
    if root:
        p = root / "sessions"
        if p.exists():
            return p
    return None


def _codex_memories_dir() -> Path | None:
    root = _codex_root()
    if root:
        p = root / "memories"
        if p.exists():
            return p
    return None


def _codex_skills_dir() -> Path | None:
    root = _codex_root()
    if root:
        p = root / "skills"
        if p.exists():
            return p
    return None


def _codex_agents_md() -> Path | None:
    root = _codex_root()
    if root:
        p = root / "AGENTS.md"
        if p.exists():
            return p
    return None


def _opencode_db_path() -> Path | None:
    """检测 OpenCode SQLite 数据库"""
    home = Path.home()
    for loc in [
        home / ".local" / "share" / "opencode" / "opencode.db",
    ]:
        if loc.exists():
            return loc
    return None


def _opencode_agents_md_dir() -> Path | None:
    """OpenCode AGENTS.md 目录"""
    home = Path.home()
    loc = home / ".config" / "opencode"
    loc.mkdir(parents=True, exist_ok=True)
    return loc


# ══════════════════════════════════════════════════════════════════════════════
# OpenCode SQLite 读取
# ══════════════════════════════════════════════════════════════════════════════


def read_opencode_db(db_path: Path | None = None) -> dict[str, Any]:
    """读取 OpenCode SQLite，返回结构化数据"""
    if db_path is None:
        db_path = _opencode_db_path()
    if not db_path or not db_path.exists():
        return {"error": "未找到 opencode.db", "sessions": [], "messages": {}}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    sessions = []
    for row in c.execute("SELECT * FROM session ORDER BY time_created DESC"):
        s = dict(row)
        s["messages"] = _read_messages_with_parts(c, s["id"])
        sessions.append(s)

    conn.close()
    return {"sessions": sessions, "db_path": str(db_path)}


def _read_messages_with_parts(cursor, session_id: str) -> list[dict]:
    messages = []
    for mrow in cursor.execute("SELECT * FROM message WHERE session_id = ? ORDER BY time_created", (session_id,)):
        msg = dict(mrow)
        with contextlib.suppress(json.JSONDecodeError):
            msg["data"] = json.loads(msg["data"]) if isinstance(msg["data"], str) else msg["data"]
        msg["parts"] = []
        for prow in cursor.execute("SELECT * FROM part WHERE message_id = ? ORDER BY time_created", (msg["id"],)):
            p = dict(prow)
            with contextlib.suppress(json.JSONDecodeError):
                p["data"] = json.loads(p["data"]) if isinstance(p["data"], str) else p["data"]
            msg["parts"].append(p)
        messages.append(msg)
    return messages


# ══════════════════════════════════════════════════════════════════════════════
# Codex → OpenCode 转换
# ══════════════════════════════════════════════════════════════════════════════


def codex_to_opencode(codex_session_path: Path, opencode_db_path: Path, title: str = "") -> dict[str, Any]:
    """将单条 Codex 会话 JSONL 导入 OpenCode SQLite"""
    from .chat_parser import parse_jsonl_session

    if not opencode_db_path.exists():
        return {"error": f"opencode.db 未找到: {opencode_db_path}"}
    if not codex_session_path.exists():
        return {"error": f"Codex 会话文件未找到: {codex_session_path}"}

    messages = parse_jsonl_session(codex_session_path, max_messages=500)
    if not messages:
        return {"error": "无法解析 Codex 会话", "ok": False}

    # 提取 session_meta 信息
    meta_text = next((m for m in messages if m["kind"] == "meta"), None)
    if not title:
        title = f"Codex Import - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    conn = sqlite3.connect(str(opencode_db_path))
    c = conn.cursor()
    session_id = f"ses_{uuid.uuid4().hex[:24]}"
    now = int(time.time() * 1000)
    directory = _extract_cwd(meta_text) or str(Path.home())

    # 创建 session
    c.execute(
        "INSERT INTO session (id, project_id, title, directory, time_created, time_updated, slug, version) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (session_id, "global", title, directory, now, now, f"codex-import-{now}", "imported"),
    )

    # 插入消息和 parts
    msg_count = 0
    for msg in messages:
        if msg["kind"] not in ("message", "thinking", "tool"):
            continue

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        role = msg.get("role", "assistant")
        text = msg.get("text", "")

        # message 行
        msg_data = json.dumps({"role": role}, ensure_ascii=False)
        c.execute(
            "INSERT INTO message (id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?)",
            (msg_id, session_id, now + msg_count, now + msg_count, msg_data),
        )

        # part 行
        part_type = "text"
        if msg["kind"] == "thinking":
            part_type = "reasoning"
        elif msg["kind"] == "tool":
            part_type = "tool"

        part_id = f"prt_{uuid.uuid4().hex[:24]}"
        part_data = json.dumps({"type": part_type, "text": text}, ensure_ascii=False)
        c.execute(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) VALUES (?,?,?,?,?,?)",
            (part_id, msg_id, session_id, now + msg_count, now + msg_count, part_data),
        )
        msg_count += 1

    conn.commit()
    conn.close()
    return {"ok": True, "session_id": session_id, "message_count": msg_count, "title": title}


def codex_all_to_opencode(
    opencode_db_path: str | Path | None = None,
    sessions_dir: str | Path | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """批量导入：Codex 所有已索引会话 → OpenCode"""
    from .export_local import discover_sessions

    if opencode_db_path is None:
        opencode_db_path = _opencode_db_path()
    if isinstance(opencode_db_path, str):
        opencode_db_path = Path(opencode_db_path)
    if not opencode_db_path or not opencode_db_path.exists():
        return [{"error": "opencode.db 未找到", "count": 0}]

    if sessions_dir is None:
        sessions_dir = _codex_sessions_dir()
    if isinstance(sessions_dir, str):
        sessions_dir = Path(sessions_dir)
    if not sessions_dir or not sessions_dir.exists():
        return [{"error": "未找到 Codex sessions 目录", "count": 0}]

    index_path = sessions_dir.parent / "session_index.jsonl"
    indexed, unindexed = discover_sessions(sessions_dir, index_path)

    results = []
    for s in indexed:
        thread_name = s.get("thread_name", s["name"])
        r = codex_to_opencode(s["path"], opencode_db_path, title=thread_name if not dry_run else thread_name)
        results.append(r)

    return results


def _extract_cwd(meta_msg: dict | None) -> str | None:
    """从 meta 消息中提取工作目录"""
    if not meta_msg:
        return None
    text = meta_msg.get("text", "")
    # 格式: "Session xxx | Codex Desktop v0.118 | openai | D:\path"
    parts = text.rsplit("|", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return None


# ══════════════════════════════════════════════════════════════════════════════
# OpenCode → Codex 转换
# ══════════════════════════════════════════════════════════════════════════════


def opencode_to_codex(
    db_path: str | Path | None = None,
    session_id: str | None = None,
    codex_sessions_dir: str | Path | None = None,
    dry_run: bool = False,
) -> list[dict]:
    """将 OpenCode 会话导出为 Codex JSONL 格式"""
    if db_path is None:
        db_path = _opencode_db_path()
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not db_path or not db_path.exists():
        return [{"error": "opencode.db 未找到", "count": 0}]

    data = read_opencode_db(db_path)
    sessions = data.get("sessions", [])
    if session_id:
        sessions = [s for s in sessions if s["id"] == session_id]
    if not sessions:
        return [{"error": "没有找到会话", "count": 0}]

    if codex_sessions_dir is None:
        codex_sessions_dir = _codex_sessions_dir()
    if codex_sessions_dir is None:
        home = Path.home()
        codex_sessions_dir = home / ".codex" / "sessions"
    if isinstance(codex_sessions_dir, str):
        codex_sessions_dir = Path(codex_sessions_dir)

    results = []
    for session in sessions:
        lines = _build_codex_jsonl_lines(session)
        if dry_run:
            results.append(
                {"session_id": session["id"], "title": session.get("title", ""), "lines": len(lines), "dry_run": True}
            )
            continue

        # 写入 Codex JSONL
        ts = datetime.fromtimestamp(session["time_created"] / 1000)
        month_dir = codex_sessions_dir / str(ts.year) / f"{ts.month:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)
        filename = f"rollout-{ts.strftime('%Y-%m-%d')}T{ts.strftime('%H-%M-%S')}-{session['id']}.jsonl"
        filepath = month_dir / filename
        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        results.append(
            {"session_id": session["id"], "title": session.get("title", ""), "lines": len(lines), "path": str(filepath)}
        )

    return results


def _build_codex_jsonl_lines(session: dict) -> list[str]:
    """构建 Codex 格式的 JSONL 行"""
    lines = []
    ts = datetime.fromtimestamp(session["time_created"] / 1000).isoformat()

    # session_meta
    meta = {
        "timestamp": ts + "Z",
        "type": "session_meta",
        "payload": {
            "id": session["id"],
            "timestamp": ts + "Z",
            "cwd": session.get("directory", ""),
            "originator": "OpenCode Import",
            "cli_version": session.get("version", "imported"),
            "source": "bridge",
            "model_provider": "openai",
        },
    }
    lines.append(json.dumps(meta, ensure_ascii=False))

    # task_started
    lines.append(
        json.dumps(
            {
                "timestamp": ts + "Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": f"{uuid.uuid4()}",
                    "model_context_window": 200000,
                    "collaboration_mode_kind": "default",
                },
            },
            ensure_ascii=False,
        )
    )

    # messages
    for msg in session.get("messages", []):
        ts2 = datetime.fromtimestamp(msg["time_created"] / 1000).isoformat()
        role = msg.get("data", {}).get("role", "assistant") if isinstance(msg.get("data"), dict) else "assistant"

        for part in msg.get("parts", []):
            part_data = part.get("data", {})
            part_type = part_data.get("type", "text") if isinstance(part_data, dict) else "text"
            part_text = part_data.get("text", "") if isinstance(part_data, dict) else str(part_data)

            if part_type == "text":
                content_type = "input_text" if role == "user" else "output_text"
                lines.append(
                    json.dumps(
                        {
                            "timestamp": ts2 + "Z",
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": role,
                                "content": [{"type": content_type, "text": part_text}],
                            },
                        },
                        ensure_ascii=False,
                    )
                )
            elif part_type == "reasoning":
                lines.append(
                    json.dumps(
                        {
                            "timestamp": ts2 + "Z",
                            "type": "response_item",
                            "payload": {
                                "type": "reasoning",
                                "content": [{"type": "text", "text": part_text}],
                                "encrypted_content": None,
                            },
                        },
                        ensure_ascii=False,
                    )
                )
            elif part_type == "step-start":
                lines.append(
                    json.dumps(
                        {
                            "timestamp": ts2 + "Z",
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "assistant",
                                "content": [{"type": "output_text", "text": f"[Step: {part_text}]"}],
                            },
                        },
                        ensure_ascii=False,
                    )
                )

    # task_ended
    lines.append(
        json.dumps(
            {
                "timestamp": ts + "Z",
                "type": "event_msg",
                "payload": {"type": "task_ended"},
            },
            ensure_ascii=False,
        )
    )

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# AGENTS.md + Skills 双向同步
# ══════════════════════════════════════════════════════════════════════════════


def sync_agents_md(direction: str = "c2o") -> dict[str, Any]:
    """同步 AGENTS.md: c2o (Codex→OpenCode) 或 o2c (OpenCode→Codex)"""
    codex_agents = _codex_agents_md()
    opencode_dir = _opencode_agents_md_dir()
    opencode_agents = opencode_dir / "AGENTS.md" if opencode_dir else None

    if direction == "c2o":
        if not codex_agents:
            return {"ok": False, "error": "未找到 Codex AGENTS.md"}
        if opencode_agents and opencode_agents.exists():
            existing = opencode_agents.read_text(encoding="utf-8")
            new_content = codex_agents.read_text(encoding="utf-8")
            if existing == new_content:
                return {"ok": True, "action": "skipped", "reason": "内容相同"}
        shutil.copy2(str(codex_agents), str(opencode_agents))
        return {"ok": True, "action": "copied", "from": str(codex_agents), "to": str(opencode_agents)}

    elif direction == "o2c":
        codex_root = _codex_root()
        if not codex_root:
            return {"ok": False, "error": "未找到 Codex 目录"}
        if not opencode_agents or not opencode_agents.exists():
            return {"ok": False, "error": "未找到 OpenCode AGENTS.md"}
        dest = codex_root / "AGENTS.md"
        if dest.exists() and dest.read_text(encoding="utf-8") == opencode_agents.read_text(encoding="utf-8"):
            return {"ok": True, "action": "skipped", "reason": "内容相同"}
        shutil.copy2(opencode_agents, dest)
        return {"ok": True, "action": "copied", "from": str(opencode_agents), "to": str(dest)}

    return {"ok": False, "error": f"未知方向: {direction}"}


def sync_skills(direction: str = "c2o") -> list[dict]:
    """同步 Skills 目录: c2o (Codex→OpenCode) 或 o2c (OpenCode→Codex)"""
    codex_skills = _codex_skills_dir()
    opencode_skills = Path.home() / ".config" / "opencode" / "skills"

    if direction == "c2o":
        if not codex_skills:
            return [{"error": "未找到 Codex skills 目录"}]
        opencode_skills.mkdir(parents=True, exist_ok=True)
        results = []
        for item in codex_skills.iterdir():
            dest = opencode_skills / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(item, dest)
                results.append({"name": item.name, "ok": True, "action": "copied" if not dest.exists() else "updated"})
            elif item.is_file():
                shutil.copy2(item, dest)
                results.append({"name": item.name, "ok": True, "action": "copied"})
        return results

    elif direction == "o2c":
        codex_root = _codex_root()
        if not codex_root:
            return [{"error": "未找到 Codex 目录"}]
        codex_skills_dest = codex_root / "skills"
        codex_skills_dest.mkdir(parents=True, exist_ok=True)
        if not opencode_skills.exists():
            return [{"error": "未找到 OpenCode skills 目录"}]
        results = []
        for item in opencode_skills.iterdir():
            dest = codex_skills_dest / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(item, dest)
            elif item.is_file():
                shutil.copy2(item, dest)
            results.append({"name": item.name, "ok": True, "action": "copied"})
        return results

    return [{"error": f"未知方向: {direction}"}]


def sync_memories_to_opencode() -> dict[str, Any]:
    """将 Codex memories/*.md 追加到 OpenCode AGENTS.md"""
    mem_dir = _codex_memories_dir()
    opencode_dir = _opencode_agents_md_dir()
    if not mem_dir or not opencode_dir:
        return {"ok": False, "error": "未找到必需目录"}

    md_files = sorted(mem_dir.rglob("*.md"))
    if not md_files:
        return {"ok": True, "action": "no_files"}

    append_text = "\n\n<!-- Codex Memory Sync: imported memories -->\n"
    for fp in md_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
            append_text += f"\n## {fp.name}\n\n{content}\n"
        except Exception:
            pass

    agents_md = opencode_dir / "AGENTS.md"
    existing = agents_md.read_text(encoding="utf-8", errors="replace") if agents_md.exists() else ""
    # 避免重复追加
    if "Codex Memory Sync: imported memories" in existing:
        # 移除旧内容再追加
        idx = existing.find("<!-- Codex Memory Sync: imported memories -->")
        existing = existing[:idx].rstrip()

    agents_md.write_text(existing + append_text, encoding="utf-8")
    return {"ok": True, "files": len(md_files), "to": str(agents_md)}


def _ensure_timestamp(ts: Any) -> str:
    """将时间戳转为 ISO 格式字符串"""
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts / 1000).isoformat()
        except (ValueError, OSError):
            pass
    if isinstance(ts, str):
        return ts.replace("Z", "+00:00").replace(" ", "T")
    return datetime.now().isoformat()
