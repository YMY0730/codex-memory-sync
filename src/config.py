from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "backend": "github",
    "cloud": {
        "server_url": "https://manbaout.cn",
        "username": "",
        "token": "",
        "token_expires_at": "",
        "sync_path": "/codex-memories/",
        "expires_days": 3,
    },
    "github": {
        "client_id": "",
        "token": "",
        "repo": "codex-memory-backup",
        "owner": "",
    },
    "security": {
        "encryption_password": "",
    },
    "local": {
        "memory_path": str(Path.home() / ".codex" / "memories"),
        "selected_files": ["MEMORY.md", "raw_memories.md", "memory_summary.md"],
    },
    "daemon": {
        "auto_watch": False,
        "debounce_seconds": 3,
        "auto_pull_interval_minutes": 10,
        "start_on_boot": False,
        "minimize_to_tray": True,
    },
    "metadata": {
        "device_id": platform.node() or "unknown-device",
        "local_version": 0,
        "local_hash": "",
        "last_push_version": 0,
        "last_push_time": "",
        "last_pull_version": 0,
        "last_pull_time": "",
    },
}

CONFIG_DIR = Path.home() / ".codex-memory-sync"
CONFIG_FILE = CONFIG_DIR / "config.json"
PID_FILE = CONFIG_DIR / "daemon.pid"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        merged = _deep_merge(DEFAULT_CONFIG, data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config_dict: dict[str, Any]) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=2, ensure_ascii=False)


def get_config_value(*keys: str) -> Any:
    config_dict = load_config()
    result = config_dict
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, {})
        else:
            return None
    return result


def set_config_value(value: Any, *keys: str) -> None:
    config_dict = load_config()
    target = config_dict
    for key in keys[:-1]:
        if key not in target or not isinstance(target[key], dict):
            target[key] = {}
        target = target[key]
    target[keys[-1]] = value
    save_config(config_dict)


def get_backend() -> str:
    return get_config_value("backend") or "github"


def set_backend(backend: str) -> None:
    set_config_value(backend, "backend")


def update_cloud_config(server_url: str, username: str, token: str, token_expires_at: str, sync_path: str) -> None:
    config_dict = load_config()
    config_dict["cloud"].update(
        {
            "server_url": server_url,
            "username": username,
            "token": token,
            "token_expires_at": token_expires_at,
            "sync_path": sync_path,
        }
    )
    save_config(config_dict)


def update_security(encryption_password: str) -> None:
    config_dict = load_config()
    config_dict["security"]["encryption_password"] = encryption_password
    save_config(config_dict)


def update_local_files(selected_files: list[str]) -> None:
    config_dict = load_config()
    config_dict["local"]["selected_files"] = selected_files
    save_config(config_dict)


def update_daemon_config(**kwargs: Any) -> None:
    config_dict = load_config()
    for key, value in kwargs.items():
        if key in config_dict["daemon"]:
            config_dict["daemon"][key] = value
    save_config(config_dict)


def update_metadata(metadata: dict[str, Any]) -> None:
    config_dict = load_config()
    config_dict["metadata"].update(metadata)
    save_config(config_dict)


def update_manbaout_expiry(days: int) -> None:
    set_config_value(int(days), "cloud", "expires_days")


def update_github_config(client_id: str = "", token: str = "", owner: str = "", repo: str = "") -> None:
    config_dict = load_config()
    if client_id:
        config_dict["github"]["client_id"] = client_id
    if token:
        config_dict["github"]["token"] = token
    if owner:
        config_dict["github"]["owner"] = owner
    if repo:
        config_dict["github"]["repo"] = repo
    save_config(config_dict)


def get_memory_path() -> Path:
    path_str = get_config_value("local", "memory_path")
    return Path(path_str).expanduser().resolve()


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
