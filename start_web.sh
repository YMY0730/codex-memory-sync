#!/bin/bash
# Codex Memory Sync — Web UI 一键启动脚本 (macOS / Linux)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  🧠 Codex Memory Sync Web UI"
echo "========================================"
echo ""
echo "  打开浏览器访问: http://127.0.0.1:8899"
echo "  按 Ctrl+C 停止服务器"
echo ""

python3 web_server.py 2>/dev/null || python web_server.py
