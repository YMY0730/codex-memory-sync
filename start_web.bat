@echo off
title Codex Memory Sync
echo ========================================
echo   🧠 Codex Memory Sync Web UI
echo ========================================
echo.
echo   打开浏览器访问: http://127.0.0.1:8899
echo   按 Ctrl+C 停止服务器
echo.
cd /d "%~dp0"
python web_server.py
pause
