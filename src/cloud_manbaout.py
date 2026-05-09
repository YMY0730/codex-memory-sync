from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from . import config
from .cloud_base import AuthError, CloudBackend, CloudError, NetworkError
from .utils import hash_file


class ManbaOutBackend(CloudBackend):
    def __init__(self):
        pass

    def _server_url(self) -> str:
        url = config.get_config_value("cloud", "server_url") or "https://manbaout.cn"
        return url.rstrip("/")

    def _token(self) -> str:
        return config.get_config_value("cloud", "token") or ""

    def _sync_path(self) -> str:
        return config.get_config_value("cloud", "sync_path") or "/codex-memories/"

    def _headers(self) -> dict[str, str]:
        token = self._token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        url = f"{self._server_url()}{endpoint}"
        kwargs.setdefault("timeout", 120)
        if "headers" not in kwargs:
            kwargs["headers"] = self._headers()
        try:
            resp = requests.request(method, url, **kwargs)
            return resp
        except requests.ConnectionError as e:
            raise NetworkError(f"无法连接到 {self._server_url()}: {e}") from e
        except requests.Timeout as e:
            raise NetworkError(f"请求超时: {e}") from e
        except requests.RequestException as e:
            raise NetworkError(f"网络错误: {e}") from e

    def login(self, username: str, password: str) -> dict[str, Any]:
        resp = self._request(
            "POST",
            "/api/mobile/login.php",
            json={"username": username, "password": password},
            headers={},
        )
        data = resp.json()
        if not data.get("ok"):
            raise AuthError(data.get("error", "登录失败"))
        token = data.get("token", "")
        if not token:
            raise AuthError("未获取到 Token")
        config.update_cloud_config(
            server_url=self._server_url(),
            username=username,
            token=token,
            token_expires_at=data.get("expires_at", ""),
            sync_path=self._sync_path(),
        )
        return data

    def is_authenticated(self) -> bool:
        try:
            self.test_connection()
            return True
        except Exception:
            return False

    def test_connection(self) -> dict[str, Any]:
        resp = self._request("GET", "/api/mobile/me.php")
        data = resp.json()
        if not data.get("ok"):
            raise AuthError(data.get("error", "Token 无效或已过期"))
        return data

    def list_versions(self) -> list[dict[str, Any]]:
        resp = self._request("GET", "/api/codex_sync/sync.php", params={"path": self._sync_path()})
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "获取版本列表失败"))
        return data.get("versions", [])

    def get_latest_version(self) -> dict[str, Any] | None:
        resp = self._request("GET", "/api/codex_sync/sync.php", params={"path": self._sync_path()})
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "获取最新版本失败"))
        return data.get("latest")

    def list_files_raw(self) -> list[dict[str, Any]]:
        resp = self._request("GET", "/api/mobile/cloud.php", params={"action": "list", "path": self._sync_path()})
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "列出文件失败"))
        return data.get("files", [])

    def upload_file(self, file_path: Path) -> dict[str, Any]:
        if not file_path.exists():
            raise CloudError(f"文件不存在: {file_path}")
        with open(file_path, "rb") as f:
            resp = self._request(
                "POST",
                "/api/mobile/upload.php",
                files={"file": (file_path.name, f, "application/octet-stream")},
                data={"path": self._sync_path()},
            )
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "上传失败"))
        return data.get("file", data)

    def download_file(self, oss_key: str, dest_path: Path) -> Path:
        resp = self._request(
            "GET",
            "/api/mobile/file.php",
            params={"scope": "cloud", "key": oss_key},
            stream=True,
            timeout=300,
        )
        if resp.status_code != 200:
            raise CloudError(f"下载失败: HTTP {resp.status_code}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest_path

    def delete_files(self, keys: list[str]) -> bool:
        resp = self._request(
            "POST",
            "/api/mobile/cloud.php",
            json={"action": "delete", "keys": keys},
        )
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "删除失败"))
        return True

    def find_file_by_filename(self, filename: str) -> str | None:
        files = self.list_files_raw()
        for f in files:
            if f.get("name") == filename:
                return str(f.get("key", ""))
        return None

    def register_version(
        self,
        version: int,
        device: str,
        file_hash: str,
        size: int,
        filename: str,
        expires_days: int = 3,
    ) -> dict[str, Any]:
        resp = self._request(
            "POST",
            "/api/codex_sync/sync.php",
            json={
                "action": "register",
                "path": self._sync_path(),
                "version": version,
                "device": device,
                "hash": file_hash,
                "size": size,
                "filename": filename,
                "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "expires_days": expires_days,
            },
        )
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "注册版本失败"))
        return data

    def unregister_version(self, version: int) -> dict[str, Any]:
        resp = self._request(
            "POST",
            "/api/codex_sync/sync.php",
            json={"action": "unregister", "path": self._sync_path(), "version": version},
        )
        data = resp.json()
        if not data.get("ok"):
            raise CloudError(data.get("error", "注销版本失败"))
        return data

    def push_package(self, file_path: Path, version: int) -> dict[str, Any]:
        file_size = file_path.stat().st_size
        file_hash = hash_file(file_path)
        upload_result = self.upload_file(file_path)
        oss_key = upload_result.get("key", "")
        device = config.get_config_value("metadata", "device_id") or "unknown"
        expires_days = config.get_config_value("cloud", "expires_days") or 3
        self.register_version(
            version=version,
            device=device,
            file_hash=file_hash,
            size=file_size,
            filename=file_path.name,
            expires_days=int(expires_days),
        )
        return {"oss_key": oss_key, "hash": file_hash, "size": file_size, "file": upload_result}

    def pull_package(self, dest_dir: Path) -> dict[str, Any] | None:
        latest = self.get_latest_version()
        if not latest:
            return None
        filename = latest.get("filename", "")
        oss_key = self.find_file_by_filename(filename)
        if not oss_key:
            versions = self.list_versions()
            if versions:
                latest = versions[0]
                filename = latest.get("filename", "")
                oss_key = self.find_file_by_filename(filename)
            if not oss_key:
                raise CloudError(f"云端版本 {filename} 对应的文件不存在")
        dest_path = dest_dir / filename
        self.download_file(oss_key, dest_path)
        return {"path": str(dest_path), "version": latest}
