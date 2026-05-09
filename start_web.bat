@echo off
chcp 65001 >nul 2>&1
title Codex Memory Sync
echo ========================================
echo   🧠 Codex Memory Sync Web UI
echo ========================================
echo.
echo   Open http://127.0.0.1:8899 in browser
echo   Press Ctrl+C to stop
echo.
cd /d "%~dp0"
python web_server.py
pause
