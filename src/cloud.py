from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config
from .cloud_base import AuthError, CloudBackend, CloudError, NetworkError, NoopBackend  # noqa: F401
from .cloud_github import GitHubBackend
from .cloud_manbaout import ManbaOutBackend


def _get_backend() -> CloudBackend:
    backend_type = config.get_config_value("backend") or "none"
    if backend_type == "none":
        return NoopBackend()
    if backend_type == "manbaout":
        return ManbaOutBackend()
    return GitHubBackend()


def list_cloud_versions() -> list[dict[str, Any]]:
    return _get_backend().list_versions()


def get_latest_version() -> dict[str, Any] | None:
    return _get_backend().get_latest_version()


def list_cloud_files() -> list[dict[str, Any]]:
    backend = _get_backend()
    if isinstance(backend, ManbaOutBackend):
        return backend.list_files_raw()
    return []


def upload_file(file_path: str | Path) -> dict[str, Any]:
    return _get_backend().upload_file(Path(file_path))


def download_file(key: str, dest_path: str | Path) -> Path:
    return _get_backend().download_file(key, Path(dest_path))


def delete_files(keys: list[str]) -> bool:
    return _get_backend().delete_files(keys)


def find_file_key_by_filename(filename: str) -> str | None:
    return _get_backend().find_file_by_filename(filename)


def register_version(
    version: int,
    device: str,
    file_hash: str,
    size: int,
    filename: str,
    expires_days: int = 3,
) -> dict[str, Any]:
    return _get_backend().register_version(version, device, file_hash, size, filename, expires_days)


def unregister_version(version: int) -> dict[str, Any]:
    return _get_backend().unregister_version(version)


def push_encrypted_package(file_path: str | Path, version: int) -> dict[str, Any]:
    return _get_backend().push_package(Path(file_path), version)


def pull_latest_package(dest_dir: str | Path) -> dict[str, Any] | None:
    return _get_backend().pull_package(Path(dest_dir))


def test_connection() -> dict[str, Any]:
    return _get_backend().test_connection()


def manbaout_login(username: str, password: str) -> dict[str, Any]:
    config.set_config_value("manbaout", "backend")
    backend = ManbaOutBackend()
    return backend.login(username, password)


def github_auth_start(client_id: str) -> dict[str, Any]:
    config.set_config_value("github", "backend")
    config.set_config_value(client_id, "github", "client_id")
    backend = GitHubBackend()
    return backend.auth_start(client_id)


def github_auth_poll(client_id: str, device_code: str) -> dict[str, Any]:
    backend = GitHubBackend()
    return backend.auth_poll(client_id, device_code)


def get_github_user() -> dict[str, Any]:
    backend = GitHubBackend()
    return backend._get_user()


def is_cloud_configured() -> bool:
    return config.is_cloud_configured()
