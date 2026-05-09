"""web_server.py — Codex Memory Sync Web UI (FastAPI)"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

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
        ],
        "rules": [{"name": r["name"], "path": str(r["path"]), "size": r["size"], "kind": "rule"} for r in rules],
    }


@app.get("/api/preview")
def api_preview(path: str = Query(...)):
    """文件预览"""
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
    """OpenCode 会话列表"""
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
    """OpenCode 单条会话详情（含消息）"""
    data = read_opencode_db()
    for s in data.get("sessions", []):
        if s["id"] == session_id:
            messages = []
            for msg in s.get("messages", []):
                msg_data = msg.get("data", {}) if isinstance(msg.get("data"), dict) else {}
                role = msg_data.get("role", "assistant") if isinstance(msg_data, dict) else "assistant"
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
    """Codex 已索引会话列表"""
    from src.export_local import discover_sessions

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
        "unindexed_count": len(unidx),
    }


# ══════════════════════════════════════════════════════════════════════════════
# API: Bridge 操作
# ══════════════════════════════════════════════════════════════════════════════


@app.post("/api/bridge/c2o")
def api_bridge_c2o(data: dict[str, Any]):
    """Codex → OpenCode 同步"""
    action = data.get("action", "")

    if action == "agents":
        return sync_agents_md("c2o")
    elif action == "skills":
        return sync_skills("c2o")
    elif action == "memories":
        return sync_memories_to_opencode()
    elif action == "sessions":
        return codex_all_to_opencode()
    elif action == "all":
        return {
            "agents": sync_agents_md("c2o"),
            "skills": sync_skills("c2o"),
            "memories": sync_memories_to_opencode(),
            "sessions": codex_all_to_opencode(),
        }
    return {"error": "未知操作"}


@app.post("/api/bridge/o2c")
def api_bridge_o2c(data: dict[str, Any]):
    """OpenCode → Codex 同步"""
    action = data.get("action", "")
    session_id = data.get("session_id")

    if action == "agents":
        return sync_agents_md("o2c")
    elif action == "skills":
        return sync_skills("o2c")
    elif action == "sessions":
        return opencode_to_codex(session_id=session_id)
    elif action == "all":
        return opencode_to_codex()
    return {"error": "未知操作"}


# ══════════════════════════════════════════════════════════════════════════════
# API: 导出
# ══════════════════════════════════════════════════════════════════════════════


@app.post("/api/export")
def api_export(data: dict[str, Any]):
    """本地导出"""
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
# 前端页面
# ══════════════════════════════════════════════════════════════════════════════

WEB_UI = """
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Codex Memory Sync</title>
<style>
:root{--bg:#f8fafc;--card:#fff;--text:#1e293b;--text2:#64748b;--accent:#3b82f6;--accent2:#2563eb;--green:#10b981;--amber:#f59e0b;--red:#ef4444;--border:#e2e8f0;--hover:#f1f5f9;--chat-user:#eff6ff;--chat-asst:#fff;--nav-bg:#1e293b;--nav-text:#e2e8f0;--shadow:0 1px 3px rgba(0,0,0,.08);--radius:12px}
[data-theme="dark"]{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--text2:#94a3b8;--accent:#60a5fa;--green:#34d399;--amber:#fbbf24;--border:#334155;--hover:#1e293b;--chat-user:#1e3a5f;--chat-asst:#1e293b;--shadow:0 1px 3px rgba(0,0,0,.3)}
*{margin:0;padding:0;box-sizing:border-box}
body{font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh}
nav{width:220px;background:var(--nav-bg);color:var(--nav-text);padding:24px 0;display:flex;flex-direction:column;position:fixed;height:100vh;z-index:10}
nav .logo{padding:0 20px 24px;font-size:18px;font-weight:700;letter-spacing:-.5px}
nav .logo span{color:var(--accent)}
nav a{display:block;padding:10px 20px;color:var(--nav-text);text-decoration:none;font-size:14px;border-left:3px solid transparent;transition:.15s}
nav a:hover,nav a.active{background:rgba(255,255,255,.08);border-left-color:var(--accent)}
nav .theme-btn{padding:10px 20px;margin-top:auto;color:var(--nav-text);background:none;border:none;cursor:pointer;font-size:14px;text-align:left}
main{margin-left:220px;flex:1;padding:32px;max-width:1200px}
h2{font-size:22px;margin-bottom:20px;font-weight:700}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:32px}
.stat-card{background:var(--card);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow);border:1px solid var(--border);transition:transform .15s}
.stat-card:hover{transform:translateY(-2px)}
.stat-card .icon{font-size:28px;margin-bottom:8px}
.stat-card .num{font-size:28px;font-weight:700;color:var(--accent)}
.stat-card .label{font-size:12px;color:var(--text2);margin-top:4px}
.card{background:var(--card);border-radius:var(--radius);padding:24px;box-shadow:var(--shadow);border:1px solid var(--border);margin-bottom:20px}
.split{display:grid;grid-template-columns:300px 1fr;gap:20px}
.file-list{max-height:500px;overflow-y:auto}
.file-item{display:flex;align-items:center;padding:8px 12px;cursor:pointer;border-radius:8px;font-size:13px;gap:8px;transition:.1s}
.file-item:hover{background:var(--hover)}
.file-item .name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file-item .size{color:var(--text2);font-size:11px;white-space:nowrap}
.chat-container{max-height:500px;overflow-y:auto;padding:12px}
.chat-msg{margin-bottom:12px;padding:12px 16px;border-radius:12px;font-size:13px;line-height:1.5;position:relative}
.chat-msg.user{background:var(--chat-user);margin-left:40px;border:1px solid var(--accent);border-radius:12px 4px 12px 12px}
.chat-msg.assistant{background:var(--chat-asst);margin-right:40px;border:1px solid var(--border);border-radius:4px 12px 12px 12px}
.chat-msg .role{font-size:10px;font-weight:600;text-transform:uppercase;margin-bottom:4px}
.chat-msg.user .role{color:var(--accent)}
.chat-msg.assistant .role{color:var(--text2)}
.chat-msg.meta,.chat-msg.event,.chat-msg.thinking,.chat-msg.tool{font-size:11px;color:var(--text2);padding:6px 12px;border-radius:8px;margin-bottom:8px;background:var(--hover)}
.chat-msg.thinking{color:var(--amber);cursor:pointer}
.chat-msg.tool{color:var(--accent);font-family:monospace}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;border:none;cursor:pointer;font-size:13px;font-weight:500;transition:.15s;text-decoration:none}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent2)}
.btn-green{background:var(--green);color:#fff}
.btn-red{background:var(--red);color:#fff}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-outline:hover{background:var(--hover)}
.btn-sm{padding:4px 10px;font-size:11px}
.bridge-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.bridge-arrow{display:flex;align-items:center;justify-content:center;font-size:32px;color:var(--accent)}
input,select{width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--card);color:var(--text);margin-bottom:8px}
.progress{width:100%;height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin:12px 0}
.progress-bar{height:100%;background:var(--accent);transition:width .3s}
.toast{position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:8px;font-size:13px;z-index:100;opacity:0;transform:translateY(-10px);transition:.3s}
.toast.show{opacity:1;transform:translateY(0)}
.toast.success{background:var(--green);color:#fff}
.toast.error{background:var(--red);color:#fff}
.empty{text-align:center;padding:40px;color:var(--text2)}
.empty .big{font-size:48px;margin-bottom:8px}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.4);z-index:50;align-items:center;justify-content:center}
.modal.show{display:flex}
.modal-content{background:var(--card);padding:32px;border-radius:16px;max-width:500px;width:90%}
@media(max-width:768px){nav{width:60px}nav a,nav .logo{font-size:0;padding:10px}main{margin-left:60px;padding:16px}.split{grid-template-columns:1fr}.bridge-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<nav>
<div class="logo"><span>🧠</span>Codex Sync</div>
<a href="#home" class="active" data-page="home">🏠 仪表盘</a>
<a href="#local" data-page="local">💻 本地文件</a>
<a href="#sessions" data-page="sessions">💬 会话浏览</a>
<a href="#bridge" data-page="bridge">🔄 跨工具同步</a>
<a href="#export" data-page="export">📦 导出</a>
<button class="theme-btn" onclick="toggleTheme()">🌙 暗色模式</button>
</nav>

<main id="main"></main>
<div id="toast" class="toast"></div>

<script>
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const main = $('#main');
const toast = $('#toast');

let theme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', theme);

function toggleTheme() {
    theme = theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    $('.theme-btn').textContent = theme === 'light' ? '🌙 暗色模式' : '☀️ 亮色模式';
}
document.addEventListener('DOMContentLoaded', () => {
    $('.theme-btn').textContent = theme === 'light' ? '🌙 暗色模式' : '☀️ 亮色模式';
});

async function api(url, opts) {
    const r = await fetch(url, {...opts, headers: {'Content-Type':'application/json',...opts?.headers}});
    return r.json();
}

function showToast(msg, type='success') {
    toast.textContent = msg; toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove('show'), 2500);
}

// Navigation
$$('nav a[data-page]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    $$('nav a').forEach(x => x.classList.remove('active'));
    a.classList.add('active');
    loadPage(a.dataset.page);
    history.pushState(null, '', '#' + a.dataset.page);
}));

window.addEventListener('popstate', () => {
    const page = location.hash.slice(1) || 'home';
    loadPage(page);
    $$('nav a').forEach(a => a.classList.toggle('active', a.dataset.page === page));
});

async function loadPage(page) {
    main.innerHTML = '<div class="empty"><div class="big">⏳</div>加载中...</div>';
    switch(page) {
        case 'home': await loadDashboard(); break;
        case 'local': await loadLocal(); break;
        case 'sessions': await loadSessions(); break;
        case 'bridge': await loadBridge(); break;
        case 'export': await loadExport(); break;
    }
}

// Dashboard
async function loadDashboard() {
    const stats = await api('/api/stats');
    main.innerHTML = `
    <h2>🏠 仪表盘</h2>
    <div class="stats">
      <div class="stat-card"><div class="icon">📄</div><div class="num">${stats.memories.count}</div><div class="label">记忆文件 · ${stats.memories.size_fmt}</div></div>
      <div class="stat-card"><div class="icon">💬</div><div class="num">${stats.sessions.count}</div><div class="label">会话记录 · ${stats.sessions.size_fmt}</div></div>
      <div class="stat-card"><div class="icon">📋</div><div class="num">${stats.rules.count}</div><div class="label">规则文件 · ${stats.rules.size_fmt}</div></div>
      <div class="stat-card"><div class="icon">📦</div><div class="num">${stats.total.count}</div><div class="label">总计 · ${stats.total.size_fmt}</div></div>
    </div>
    <div class="card">
      <b>Codex 目录</b>
      <p style="color:var(--text2);margin-top:8px;font-size:13px">${stats.paths.root || '⚠️ 未检测到  .codex 目录，请设置 CODEX_HOME 环境变量'}</p>
    </div>
    <div class="card">
      <b>后端模式</b>
      <p style="margin-top:8px;font-size:13px">${stats.backend === 'none' ? '💻 本地模式' : `☁️ ${stats.backend}`}</p>
      <button class="btn btn-primary" onclick="loadPage('bridge')" style="margin-top:12px">🔄 跨工具同步</button>
      <button class="btn btn-outline" onclick="loadPage('export')" style="margin-top:12px;margin-left:8px">📦 快速导出</button>
    </div>`;
}

// Local files
async function loadLocal() {
    const data = await api('/api/local/files');
    main.innerHTML = `
    <h2>💻 本地文件</h2>
    <div class="split">
      <div class="card" style="padding:16px">
        <div class="file-list" id="fileList">
          ${renderFileGroup('📁 记忆文件', data.memories)}
          ${renderFileGroup('💬 会话记录', data.sessions)}
          ${renderFileGroup('📋 规则文件', data.rules)}
        </div>
      </div>
      <div class="card" style="padding:16px">
        <div id="previewArea"><div class="empty"><div class="big">👁️</div>点击左侧文件预览</div></div>
      </div>
    </div>`;
}

function renderFileGroup(title, items) {
    if (!items || !items.length) return '';
    return `<div style="font-weight:700;font-size:12px;color:var(--text2);padding:8px 4px">${title}</div>` +
        items.map(f => `
      <div class="file-item" onclick="previewFile('${f.path}','${f.kind || ''}')">
        <span>${f.name}</span>
        <span class="size">${formatBytes(f.size)}</span>
      </div>`).join('');
}

async function previewFile(path, kind) {
    const area = $('#previewArea');
    area.innerHTML = '<div class="empty"><div class="big">⏳</div></div>';
    try {
        const data = await api('/api/preview?path=' + encodeURIComponent(path));
        if (data.type === 'chat') {
            area.innerHTML = `<div style="font-size:11px;color:var(--text2);margin-bottom:8px">💬 ${data.messages.length} 条消息</div>
            <div class="chat-container">${data.messages.map(m => renderChatMsg(m)).join('')}</div>`;
        } else {
            area.innerHTML = `<div style="font-size:11px;color:var(--text2);margin-bottom:8px">📄 ${data.name} · ${data.size}</div>
            <pre style="white-space:pre-wrap;font-size:12px;font-family:monospace;max-height:500px;overflow-y:auto;padding:12px;background:var(--hover);border-radius:8px">${escapeHtml(data.content)}</pre>`;
        }
    } catch(e) { area.innerHTML = '<div class="empty"><div class="big">❌</div>预览失败</div>'; }
}

function renderChatMsg(m) {
    if (m.kind === 'meta') return `<div class="chat-msg meta">📋 ${escapeHtml(m.text)}</div>`;
    if (m.kind === 'event') return `<div class="chat-msg event">${escapeHtml(m.text)}</div>`;
    if (m.kind === 'thinking') return `<div class="chat-msg thinking" title="思考过程">💭 ${escapeHtml(m.text.substring(0,200))}</div>`;
    if (m.kind === 'tool') return `<div class="chat-msg tool">🔧 ${escapeHtml(m.text.substring(0,200))}</div>`;
    const role = m.role === 'user' ? 'user' : 'assistant';
    return `<div class="chat-msg ${role}"><div class="role">${role}${m.timestamp ? ' · '+m.timestamp : ''}</div>${escapeHtml(m.text)}</div>`;
}

// Sessions browser
async function loadSessions() {
    try {
        const [codex, opencode] = await Promise.all([api('/api/codex/sessions'), api('/api/opencode/sessions')]);
        main.innerHTML = `
        <h2>💬 会话浏览</h2>
        <div class="bridge-grid">
          <div class="card">
            <b>🧠 Codex 会话 (${codex.indexed.length} 个)</b>
            <div class="file-list" style="max-height:400px;margin-top:12px">
              ${codex.indexed.map((s,i) => `
                <div class="file-item" onclick="previewCodexSession('${s.path.replace(/\\\\/g,'\\\\')}')">
                  <span class="name">${s.name}</span>
                  <span class="size">${s.size_fmt}</span>
                </div>`).join('')}
              ${codex.unindexed_count ? `<div style="font-size:11px;color:var(--text2);padding:8px">+${codex.unindexed_count} 个未索引</div>` : ''}
            </div>
          </div>
          <div class="card">
            <b>💬 OpenCode 会话 (${(opencode||[]).length} 个)</b>
            <div class="file-list" style="max-height:400px;margin-top:12px">
              ${(opencode||[]).map(s => `
                <div class="file-item" onclick="loadOpenCodeSession('${s.id}')">
                  <span class="name">${s.title}</span>
                  <span class="size">${s.message_count} msg</span>
                </div>`).join('')}
            </div>
          </div>
        </div>`;
    } catch(e) { main.innerHTML = '<div class="card"><div class="empty"><div class="big">⚠️</div>加载失败</div></div>'; }
}

// Bridge
async function loadBridge() {
    const [codex, opencode] = await Promise.all([
        api('/api/codex/sessions').catch(()=>({indexed:[],unindexed_count:0})),
        api('/api/opencode/sessions').catch(()=>[])
    ]);
    main.innerHTML = `
    <h2>🔄 跨工具同步</h2>
    <div class="bridge-grid">
      <div class="card">
        <b>🧠 Codex</b>
        <p style="font-size:12px;color:var(--text2)">${codex.indexed.length} 个已索引会话</p>
        <div style="margin:12px 0">
          <button class="btn btn-primary btn-sm" onclick="bridgeAction('c2o','agents')">📄 AGENTS.md</button>
          <button class="btn btn-primary btn-sm" onclick="bridgeAction('c2o','skills')">📁 Skills</button>
          <button class="btn btn-primary btn-sm" onclick="bridgeAction('c2o','memories')">🧠 记忆</button>
        </div>
        <button class="btn btn-primary" onclick="bridgeAction('c2o','sessions')" style="width:100%">📤 导入全部会话到 OpenCode</button>
        <button class="btn btn-primary" onclick="bridgeAction('c2o','all')" style="width:100%;margin-top:8px">🚀 一键全部导入</button>
      </div>
      <div class="card">
        <b>💬 OpenCode</b>
        <p style="font-size:12px;color:var(--text2)">${(opencode||[]).length} 个会话</p>
        <div style="margin:12px 0">
          <button class="btn btn-green btn-sm" onclick="bridgeAction('o2c','agents')">📄 AGENTS.md</button>
          <button class="btn btn-green btn-sm" onclick="bridgeAction('o2c','skills')">📁 Skills</button>
        </div>
        <select id="ocSession" style="margin-bottom:8px">
          <option value="">-- 选择会话 --</option>
          ${(opencode||[]).map(s => `<option value="${s.id}">${s.title} (${s.message_count} msg)</option>`).join('')}
        </select>
        <button class="btn btn-green" onclick="bridgeAction('o2c','sessions')" style="width:100%">📥 导出到 Codex</button>
        <button class="btn btn-green" onclick="bridgeAction('o2c','all')" style="width:100%;margin-top:8px">🔄 一键全部导入 Codex</button>
      </div>
    </div>
    <div id="bridgeProgress" class="progress" style="display:none"><div class="progress-bar" style="width:0"></div></div>
    <div id="bridgeResult" class="card" style="display:none;margin-top:16px;font-size:12px"></div>`;
}

async function bridgeAction(dir, action) {
    const progress = $('#bridgeProgress');
    const result = $('#bridgeResult');
    progress.style.display = 'block';
    progress.querySelector('.progress-bar').style.width = '30%';
    result.style.display = 'none';
    try {
        const sessionId = $('#ocSession')?.value;
        const r = await api('/api/bridge/' + dir, {method:'POST', body:JSON.stringify({action, session_id: sessionId || undefined})});
        progress.querySelector('.progress-bar').style.width = '100%';
        result.style.display = 'block';
        result.innerHTML = `<pre style="white-space:pre-wrap;font-size:12px">${JSON.stringify(r, null, 2)}</pre>`;
        showToast('同步完成!');
    } catch(e) {
        result.style.display = 'block';
        result.innerHTML = `<span style="color:var(--red)">${e.message}</span>`;
        showToast('同步失败', 'error');
    }
    setTimeout(() => { progress.style.display = 'none'; }, 1000);
}

// Export
async function loadExport() {
    const stats = await api('/api/stats');
    main.innerHTML = `
    <h2>📦 导出压缩包</h2>
    <div class="card">
      <p>总文件: <b>${stats.total.count}</b> 个, 总计: <b>${stats.total.size_fmt}</b></p>
      <div style="margin:16px 0">
        <input id="exportPath" placeholder="保存路径 (默认: 桌面/codex-context.zip)" value="${stats.paths.root ? stats.paths.root : ''}/../codex-context.zip">
      </div>
      <div style="margin:16px 0">
        <input id="exportPwd" type="password" placeholder="加密密码 (可选, 留空则不加密)">
      </div>
      <button class="btn btn-primary" onclick="doExport()" style="margin-top:8px">📦 开始导出</button>
      <div id="exportProgress" class="progress" style="display:none;margin-top:12px"><div class="progress-bar" style="width:0"></div></div>
    </div>`;
}

async function doExport() {
    const p = $('#exportPath').value;
    const pwd = $('#exportPwd').value;
    const prog = $('#exportProgress');
    prog.style.display = 'block';
    prog.querySelector('.progress-bar').style.width = '40%';
    const r = await api('/api/export', {method:'POST', body:JSON.stringify({output:p, password:pwd||null})});
    prog.querySelector('.progress-bar').style.width = '100%';
    if (r.ok) {
        showToast('导出成功: ' + r.path);
    } else {
        showToast('导出失败: ' + r.error, 'error');
    }
}

function formatBytes(b) { return b ? (b<1024?b+'B':(b/1024).toFixed(1)+'KB') : ''; }
function escapeHtml(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

// Load initial page
loadPage(location.hash.slice(1) || 'home');
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return HTMLResponse(WEB_UI)


@app.get("/favicon.ico")
def favicon():
    return FileResponse(Path(__file__).parent / "gui" / "__init__.py")  # dummy


def main():
    import uvicorn

    config.ensure_config_dir()
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="info")


if __name__ == "__main__":
    main()
