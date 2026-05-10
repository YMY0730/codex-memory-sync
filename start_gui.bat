@echo off
chcp 65001 >nul 2>&1
title Codex Memory Sync GUI
cd /d "%~dp0"
python cli.py gui
pause
