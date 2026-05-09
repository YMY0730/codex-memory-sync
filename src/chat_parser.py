"""chat_parser.py — 解析 Codex 真实 .jsonl 会话格式

Codex session JSONL line structure:
  {"timestamp":"...", "type":"session_meta", "payload":{...}}
  {"timestamp":"...", "type":"event_msg", "payload":{"type":"task_started",...}}
  {"timestamp":"...", "type":"response_item", "payload":{"type":"message","role":"user|assistant|developer","content":[{"type":"input_text|output_text","text":"..."}]}}
  {"timestamp":"...", "type":"response_item", "payload":{"type":"reasoning","encrypted_content":"..."}}
  {"timestamp":"...", "type":"response_item", "payload":{"type":"function_call",...}}
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_jsonl_session(file_path: Path, max_messages: int = 200) -> list[dict[str, Any]]:
    """解析 Codex .jsonl 会话文件，返回有序消息列表

    Returns:
        list of {
            "kind": "meta" | "event" | "message" | "thinking" | "tool" | "commentary",
            "role": "user" | "assistant" | "developer" | "system" | "",
            "text": str,
            "timestamp": str,
            "raw": dict,
        }
    """
    messages: list[dict[str, Any]] = []
    if not file_path.exists():
        return messages

    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return messages

    lines = raw.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg = _parse_line(obj)
        if msg:
            messages.append(msg)
            if len(messages) >= max_messages:
                break

    return messages


def _parse_line(obj: dict) -> dict | None:
    """解析单行 JSON"""
    line_type = obj.get("type", "")
    payload = obj.get("payload", {})
    ts = obj.get("timestamp", "")

    # 美化时间戳
    ts_display = ts
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts_display = dt.strftime("%H:%M:%S")
    except Exception:
        pass

    # ── session_meta ──
    if line_type == "session_meta":
        sid = payload.get("id", "")[:8]
        cwd = payload.get("cwd", "")
        originator = payload.get("originator", "")
        cli_ver = payload.get("cli_version", "")
        provider = payload.get("model_provider", "unknown")
        return {
            "kind": "meta",
            "role": "",
            "text": f"Session {sid}  |  {originator} v{cli_ver}  |  {provider}  |  {cwd}",
            "timestamp": ts_display,
            "raw": payload,
        }

    # ── event_msg ──
    if line_type == "event_msg":
        event_type = payload.get("type", "")
        if event_type == "task_started":
            return {
                "kind": "event",
                "role": "",
                "text": "🚀 任务开始",
                "timestamp": ts_display,
                "raw": payload,
            }
        elif event_type == "task_ended":
            return {
                "kind": "event",
                "role": "",
                "text": "🏁 任务结束",
                "timestamp": ts_display,
                "raw": payload,
            }
        return None

    # ── response_item ──
    if line_type != "response_item":
        return None

    item_type = payload.get("type", "")

    # ── reasoning / thinking ──
    if item_type == "reasoning":
        summary = payload.get("summary", [])
        enc = payload.get("encrypted_content")
        # 优先取 summary 文本，其次取 content
        summary_text = "\n".join(s.get("text", "") for s in summary if isinstance(s, dict)).strip()
        raw_content = payload.get("content")
        if isinstance(raw_content, list):
            summary_text = _extract_text(raw_content) or summary_text
        if isinstance(raw_content, str) and raw_content.strip():
            summary_text = raw_content.strip()

        if summary_text:
            return {
                "kind": "thinking",
                "role": "assistant",
                "text": summary_text,
                "timestamp": ts_display,
                "raw": payload,
            }
        if enc:
            return {
                "kind": "thinking",
                "role": "assistant",
                "text": f"[思考过程 · 已折叠 · {len(enc)} 字节]",
                "timestamp": ts_display,
                "raw": payload,
            }
        return None

    # ── message ──
    if item_type == "message":
        role = payload.get("role", "").lower()
        content_blocks = payload.get("content", [])
        text = _extract_text(content_blocks)
        if not text.strip():
            return None

        # Developer messages are the system prompt — collapse them
        if role == "developer":
            return {
                "kind": "event",
                "role": "system",
                "text": f"[系统提示 · {len(text)} 字]",
                "timestamp": ts_display,
                "raw": payload,
            }

        # Phase info (commentary before assistant response)
        phase = payload.get("phase", "")
        if phase == "commentary" and role == "assistant":
            return {
                "kind": "message",
                "role": role,
                "text": text,
                "timestamp": ts_display,
                "raw": payload,
            }

        return {
            "kind": "message",
            "role": role,
            "text": text,
            "timestamp": ts_display,
            "raw": payload,
        }

    # ── function_call ──
    if item_type == "function_call":
        name = payload.get("name", payload.get("function_name", "tool"))
        arguments = payload.get("arguments", payload.get("input", ""))
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False, indent=1)
        brief_args = str(arguments)[:200]
        return {
            "kind": "tool",
            "role": "assistant",
            "text": f"🔧 {name}({brief_args}...)",
            "timestamp": ts_display,
            "raw": payload,
        }

    return None


def _extract_text(content: list | str) -> str:
    """从 Codex content 数组中提取文本"""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type", "")
        text = block.get("text", "")
        if block_type in ("input_text", "output_text", "text"):
            parts.append(text)
    return "".join(parts)
