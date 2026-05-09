import atexit
import os
import threading
import time
from pathlib import Path
from typing import Any

from . import config
from .cloud import (
    list_cloud_versions,
    pull_latest_package,
    push_encrypted_package,
)
from .exporter import export_to_file
from .importer import import_from_file
from .metadata import SyncStatus, compare
from .state import SyncState, get_state_machine
from .watcher import get_watch_manager

LOG_LISTENERS: list = []


def _log(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    line = f"{timestamp}  {message}"
    import contextlib

    for listener in LOG_LISTENERS:
        with contextlib.suppress(Exception):
            listener(line)


def add_log_listener(callback) -> None:
    LOG_LISTENERS.append(callback)


def remove_log_listener(callback) -> None:
    if callback in LOG_LISTENERS:
        LOG_LISTENERS.remove(callback)


def _auto_push() -> None:
    stm = get_state_machine()
    if stm.is_busy():
        return

    try:
        _log("🔍 检测到本地变更，开始自动推送...")
        stm.transition(SyncState.PACKAGING, "自动推送：开始打包")
        memory_path = config.get_memory_path()
        selected_files = config.get_config_value("local", "selected_files") or []
        password = config.get_config_value("security", "encryption_password") or ""

        if not password:
            _log("❌ 未设置加密密码，跳过推送")
            stm.transition(SyncState.ERROR, "未设置加密密码")
            return

        temp_dir = config.CONFIG_DIR / "temp"
        encrypted_path = export_to_file(memory_path, selected_files, password, temp_dir)

        stm.transition(SyncState.UPLOADING, "自动推送：上传到云盘")
        current_ver = config.get_config_value("metadata", "local_version") or 0
        push_encrypted_package(encrypted_path, current_ver)

        encrypted_path.unlink(missing_ok=True)
        _log("✅ 自动推送完成")
        stm.transition(SyncState.SYNCED, "自动推送完成")
    except Exception as e:
        _log(f"❌ 自动推送失败: {e}")
        stm.transition(SyncState.ERROR, str(e))


def _auto_pull() -> None:
    stm = get_state_machine()
    if stm.is_busy():
        return

    try:
        versions = list_cloud_versions()
        result = compare(versions)
        if result["status"] in (SyncStatus.CLOUD_AHEAD.value, SyncStatus.SYNCED.value):
            cloud_version = result["cloud"]["latest_version"]
            local_version = result["local"]["version"]
            if cloud_version > local_version:
                _log(f"🔍 检测到云端新版本 v{cloud_version}，开始自动拉取...")
                do_pull()
    except Exception as e:
        _log(f"⚠️ 自动拉取检查失败: {e}")


def _pull_timer_loop(interval_minutes: int) -> None:
    while getattr(threading.current_thread(), "_daemon_running", True):
        time.sleep(interval_minutes * 60)
        if not getattr(threading.current_thread(), "_daemon_running", True):
            break
        _auto_pull()


def do_push() -> dict[str, Any]:
    stm = get_state_machine()
    try:
        _log("📤 开始推送...")
        stm.transition(SyncState.PACKAGING, "打包记忆中...")
        memory_path = config.get_memory_path()
        selected_files = config.get_config_value("local", "selected_files") or []
        password = config.get_config_value("security", "encryption_password") or ""

        if not password:
            raise ValueError("未设置加密密码，请先运行 codex-memory init")

        temp_dir = config.CONFIG_DIR / "temp"
        encrypted_path = export_to_file(memory_path, selected_files, password, temp_dir)

        stm.transition(SyncState.UPLOADING, "上传到云盘...")
        current_ver = config.get_config_value("metadata", "local_version") or 0
        result = push_encrypted_package(encrypted_path, current_ver)

        encrypted_path.unlink(missing_ok=True)
        _log(f"✅ 推送成功 → 云端 v{current_ver}")
        stm.transition(SyncState.SYNCED, f"推送成功 v{current_ver}")
        return result
    except Exception as e:
        _log(f"❌ 推送失败: {e}")
        stm.transition(SyncState.ERROR, str(e))
        raise


def do_pull() -> dict[str, Any]:
    stm = get_state_machine()
    try:
        _log("📥 开始拉取...")
        stm.transition(SyncState.DOWNLOADING, "从云盘下载...")
        password = config.get_config_value("security", "encryption_password") or ""
        if not password:
            raise ValueError("未设置加密密码")

        temp_dir = config.CONFIG_DIR / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        result = pull_latest_package(temp_dir)

        if not result:
            raise ValueError("云端没有可用的版本")

        stm.transition(SyncState.DECRYPTING, "解密验证中...")
        memory_path = config.get_memory_path()
        imported = import_from_file(result["path"], password, memory_path)

        pkg_path = Path(result["path"])
        pkg_path.unlink(missing_ok=True)

        ver = imported["version"]
        _log(f"✅ 拉取成功 → 本地已更新到 v{ver}")
        stm.transition(SyncState.SYNCED, f"拉取成功 v{ver}")
        return imported
    except Exception as e:
        _log(f"❌ 拉取失败: {e}")
        stm.transition(SyncState.ERROR, str(e))
        raise


def do_sync() -> dict[str, Any]:
    _log("🔄 开始完整同步...")
    pull_result = None
    try:
        versions = list_cloud_versions()
        result = compare(versions)
        if result["status"] in (SyncStatus.CLOUD_AHEAD.value, SyncStatus.CONFLICT.value):
            pull_result = do_pull()
    except Exception:
        pass
    push_result = do_push()
    _log("✅ 完整同步完成")
    return {"pull": pull_result, "push": push_result}


def start_daemon() -> None:
    pid = os.getpid()
    pid_file = config.PID_FILE
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    if pid_file.exists():
        old_pid = int(pid_file.read_text().strip())
        try:
            os.kill(old_pid, 0)
            print(f"守护进程已在运行 (PID: {old_pid})")
            return
        except OSError:
            pass

    pid_file.write_text(str(pid))
    atexit.register(_cleanup_pid)

    config.update_daemon_config(auto_watch=True)
    _log("🟢 守护进程已启动")

    memory_path = config.get_memory_path()
    if memory_path.exists():
        watch_mgr = get_watch_manager()
        watch_mgr.start(memory_path, _auto_push)

    interval = config.get_config_value("daemon", "auto_pull_interval_minutes") or 10
    pull_thread = threading.Thread(target=_pull_timer_loop, args=(interval,), daemon=True)
    pull_thread._daemon_running = True
    pull_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _log("🛑 守护进程收到中断信号")
    finally:
        pull_thread._daemon_running = False
        stop_daemon()


def stop_daemon() -> None:
    watch_mgr = get_watch_manager()
    watch_mgr.stop()
    config.update_daemon_config(auto_watch=False)
    _cleanup_pid()
    _log("🔴 守护进程已停止")


def daemon_status() -> dict[str, Any]:
    pid_file = config.PID_FILE
    running = False
    pid = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            running = True
        except (OSError, ValueError):
            pass

    watch_mgr = get_watch_manager()
    return {
        "running": running or watch_mgr.running,
        "pid": pid,
        "watching": watch_mgr.running,
        "auto_watch": config.get_config_value("daemon", "auto_watch"),
    }


def _cleanup_pid() -> None:
    try:
        if config.PID_FILE.exists():
            config.PID_FILE.unlink()
    except OSError:
        pass
