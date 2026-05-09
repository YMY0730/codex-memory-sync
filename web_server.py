"""web_server.py — Codex Memory Sync Web UI (FastAPI)"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from src import config
from src.bridge import (
    codex_all_to_opencode,
    opencode_to_codex,
    read_opencode_db,
    sync_agents_md,
    sync_memories_to_opencode,
    sync_skills,
)
from src.chat_parser import parse_jsonl_session
from src.export_local import (
    create_export_zip,
    discover_memories,
    discover_rules,
    discover_sessions,
)
from src.path_detector import detect_codex_locations
from src.utils import format_size

HOME = Path.home()
CODEX_HOME = HOME / ".codex"

app = FastAPI(title="Codex Memory Sync", version="2.0.0")

# ══════════════════════════════════════════════════════════════════════════════
# API: 数据源
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/stats")
def api_stats():
    """首页统计数据"""
    memories = discover_memories(CODEX_HOME / "memories")
    sessions_idx, sessions_un = discover_sessions(CODEX_HOME / "sessions", CODEX_HOME / "session_index.jsonl")
    rules = discover_rules(CODEX_HOME / "rules")

    def _count(items):
        total = 0
        cnt = 0
        for item in items:
            if item.get("is_dir"):
                for c in item.get("children", []):
                    total += c.get("size", 0)
                    cnt += 1
            else:
                total += item.get("size", 0)
                cnt += 1
        return cnt, total

    mc, ms = _count(memories)
    sc = len(sessions_idx) + len(sessions_un)
    ss = sum(s.get("size", 0) for s in sessions_idx) + sum(p.stat().st_size for p in sessions_un)
    rc, rs = len(rules), sum(r.get("size", 0) for r in rules)

    return {
        "memories": {"count": mc, "size": ms, "size_fmt": format_size(ms)},
        "sessions": {"count": sc, "size": ss, "size_fmt": format_size(ss)},
        "rules": {"count": rc, "size": rs, "size_fmt": format_size(rs)},
        "total": {"count": mc + sc + rc, "size": ms + ss + rs, "size_fmt": format_size(ms + ss + rs)},
        "paths": detect_codex_locations(),
        "backend": config.get_backend(),
    }


@app.get("/api/local/files")
def api_local_files():
    """本地文件列表"""
    memories = discover_memories(CODEX_HOME / "memories")
    sessions_idx, sessions_un = discover_sessions(CODEX_HOME / "sessions", CODEX_HOME / "session_index.jsonl")
    rules = discover_rules(CODEX_HOME / "rules")

    def flatten_memories(items):
        result = []
        for item in items:
            if item.get("is_dir"):
                result.append({"name": f"📁 {item['name']}/", "path": None, "size": item.get("size", 0), "kind": "dir"})
                for c in item.get("children", []):
                    result.append({"name": c["name"], "path": str(c["path"]), "size": c["size"], "kind": "memory"})
            else:
                result.append({"name": item["name"], "path": str(item["path"]), "size": item["size"], "kind": "memory"})
        return result

    return {
        "memories": flatten_memories(memories),
        "sessions": [
            {
                "name": s.get("thread_name", s["name"]),
                "path": str(s["path"]),
                "size": s.get("size", 0),
                "updated": s.get("updated_at", ""),
                "kind": "session",
            }
            for s in sessions_idx
        ]
        + [
            {
                "name": f"未索引: {p.name}",
                "path": str(p),
                "size": p.stat().st_size,
                "updated": "",
                "kind": "session_unindexed",
            }
            for p in sessions_un
        ],
        "rules": [{"name": r["name"], "path": str(r["path"]), "size": r["size"], "kind": "rule"} for r in rules],
    }


@app.get("/api/preview")
def api_preview(path: str = Query(...)):
    fp = Path(path)
    if not fp.exists():
        raise HTTPException(404, "文件不存在")
    is_jsonl = fp.suffix.lower() == ".jsonl"
    if is_jsonl:
        messages = parse_jsonl_session(fp, max_messages=200)
        return {"type": "chat", "messages": messages}
    try:
        content = fp.read_text(encoding="utf-8", errors="replace")
        if len(content) > 100000:
            content = content[:100000] + "\n\n..."
        return {"type": "text", "content": content, "name": fp.name, "size": format_size(fp.stat().st_size)}
    except Exception:
        return {"type": "text", "content": "无法读取此文件", "name": fp.name}


@app.get("/api/opencode/sessions")
def api_opencode_sessions():
    data = read_opencode_db()
    sessions = data.get("sessions", [])
    return [
        {
            "id": s["id"],
            "title": s.get("title", s["id"][:12]),
            "directory": s.get("directory", ""),
            "message_count": len(s.get("messages", [])),
            "created": s.get("time_created", 0),
        }
        for s in sessions
    ]


@app.get("/api/opencode/session/{session_id}")
def api_opencode_session_detail(session_id: str):
    data = read_opencode_db()
    for s in data.get("sessions", []):
        if s["id"] == session_id:
            messages = []
            for msg in s.get("messages", []):
                md = msg.get("data", {}) if isinstance(msg.get("data"), dict) else {}
                role = md.get("role", "assistant") if isinstance(md, dict) else "assistant"
                parts = []
                for p in msg.get("parts", []):
                    pd = p.get("data", {}) if isinstance(p.get("data"), dict) else {}
                    parts.append(
                        {
                            "type": pd.get("type", "text") if isinstance(pd, dict) else "text",
                            "text": pd.get("text", "") if isinstance(pd, dict) else str(pd),
                        }
                    )
                messages.append({"role": role, "parts": parts, "time": msg.get("time_created")})
            return {
                "id": s["id"],
                "title": s.get("title", ""),
                "directory": s.get("directory", ""),
                "messages": messages,
            }
    raise HTTPException(404, "会话未找到")


@app.get("/api/codex/sessions")
def api_codex_sessions():
    idx, unidx = discover_sessions(CODEX_HOME / "sessions", CODEX_HOME / "session_index.jsonl")
    return {
        "indexed": [
            {
                "name": s.get("thread_name", s["name"]),
                "path": str(s["path"]),
                "size": s.get("size", 0),
                "size_fmt": format_size(s.get("size", 0)),
                "updated": s.get("updated_at", ""),
            }
            for s in idx
        ],
        "unindexed": [
            {
                "name": f"未索引: {p.name}",
                "path": str(p),
                "size": p.stat().st_size,
                "size_fmt": format_size(p.stat().st_size),
                "updated": "",
            }
            for p in unidx
        ],
    }


@app.post("/api/bridge/c2o")
def api_bridge_c2o(data: dict[str, Any]):
    action = data.get("action", "")
    if action == "agents":
        return sync_agents_md("c2o")
    if action == "skills":
        return sync_skills("c2o")
    if action == "memories":
        return sync_memories_to_opencode()
    if action == "sessions":
        return codex_all_to_opencode()
    if action == "all":
        return {
            "agents": sync_agents_md("c2o"),
            "skills": sync_skills("c2o"),
            "memories": sync_memories_to_opencode(),
            "sessions": codex_all_to_opencode(),
        }
    return {"error": "未知操作"}


@app.post("/api/bridge/o2c")
def api_bridge_o2c(data: dict[str, Any]):
    action = data.get("action", "")
    session_id = data.get("session_id")
    if action == "agents":
        return sync_agents_md("o2c")
    if action == "skills":
        return sync_skills("o2c")
    if action == "sessions":
        return opencode_to_codex(session_id=session_id)
    if action == "all":
        return opencode_to_codex()
    return {"error": "未知操作"}


@app.post("/api/export")
def api_export(data: dict[str, Any]):
    output = data.get("output", str(HOME / "Desktop" / "codex-context.zip"))
    password = data.get("password")
    filepath = Path(output)
    memories = discover_memories(CODEX_HOME / "memories")
    sessions_idx, sessions_un = discover_sessions(CODEX_HOME / "sessions", CODEX_HOME / "session_index.jsonl")
    rules = discover_rules(CODEX_HOME / "rules")

    def _flat(items):
        paths = []
        for item in items:
            if item.get("is_dir"):
                for c in item.get("children", []):
                    paths.append(c["path"])
            else:
                paths.append(item["path"])
        return paths

    try:
        result = create_export_zip(
            filepath,
            _flat(memories),
            [s["path"] for s in sessions_idx] + sessions_un,
            [r["path"] for r in rules],
            CODEX_HOME / "memories",
            CODEX_HOME / "sessions",
            CODEX_HOME / "rules",
            password=password if password else None,
        )
        return {"ok": True, "path": str(result), "ext": result.suffix}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Frontend
# ══════════════════════════════════════════════════════════════════════════════

_WEB_ROOT = Path(__file__).parent / "static"


@app.get("/")
def index():
    _WEB_ROOT.mkdir(parents=True, exist_ok=True)
    html_file = _WEB_ROOT / "index.html"
    if not html_file.exists():
        return HTMLResponse("<h1>static/index.html not found. Create it to serve the web UI.</h1>")
    return HTMLResponse(html_file.read_text(encoding="utf-8"))


def main():
    import uvicorn

    config.ensure_config_dir()
    print("Codex Memory Sync Web UI → http://127.0.0.1:8899")
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="info")


if __name__ == "__main__":
    main()
