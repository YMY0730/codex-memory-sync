from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

from . import config
from .cloud_base import AuthError, CloudBackend, CloudError, NetworkError
from .utils import hash_file

GITHUB_API_BASE = "https://api.github.com"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"


class GitHubBackend(CloudBackend):
    def __init__(self):
        pass

    def _token(self) -> str:
        return config.get_config_value("github", "token") or ""

    def _client_id(self) -> str:
        return config.get_config_value("github", "client_id") or ""

    def _repo(self) -> str:
        return config.get_config_value("github", "repo") or "codex-memory-backup"

    def _owner(self) -> str:
        return config.get_config_value("github", "owner") or ""

    def _api_headers(self) -> dict[str, str]:
        token = self._token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "codex-memory-sync",
        }

    def _api(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{GITHUB_API_BASE}{path}"
        kwargs.setdefault("headers", self._api_headers())
        kwargs.setdefault("timeout", 60)
        try:
            resp = requests.request(method, url, **kwargs)
            return resp
        except requests.ConnectionError as e:
            raise NetworkError(f"无法连接到 GitHub: {e}") from e
        except requests.Timeout as e:
            raise NetworkError(f"请求超时: {e}") from e
        except requests.RequestException as e:
            raise NetworkError(f"网络错误: {e}") from e

    def auth_start(self, client_id: str) -> dict[str, Any]:
        resp = requests.post(
            GITHUB_DEVICE_CODE_URL,
            json={"client_id": client_id, "scope": "repo"},
            headers={"Accept": "application/json"},
            timeout=30,
        )
        data = resp.json()
        if "error" in data:
            raise AuthError(data.get("error_description", data["error"]))
        return {
            "device_code": data["device_code"],
            "user_code": data["user_code"],
            "verification_url": data["verification_uri"],
            "interval": data.get("interval", 5),
        }

    def auth_poll(self, client_id: str, device_code: str) -> dict[str, Any]:
        resp = requests.post(
            GITHUB_ACCESS_TOKEN_URL,
            json={
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        data = resp.json()
        if "error" in data:
            if data["error"] == "authorization_pending":
                return {"status": "pending"}
            elif data["error"] == "slow_down":
                return {"status": "slow_down"}
            raise AuthError(data.get("error_description", data["error"]))
        token = data.get("access_token", "")
        if not token:
            raise AuthError("未获取到 access_token")

        config.set_config_value(client_id, "github", "client_id")
        config.set_config_value(token, "github", "token")

        user_info = self._get_user()
        config.set_config_value(user_info["login"], "github", "owner")
        return {"status": "authorized", "token": token, "user": user_info}

    def _get_user(self) -> dict[str, Any]:
        resp = self._api("GET", "/user")
        data = resp.json()
        if "login" not in data:
            raise AuthError("获取用户信息失败")
        return {"login": data["login"], "name": data.get("name", ""), "avatar": data.get("avatar_url", "")}

    def is_authenticated(self) -> bool:
        token = self._token()
        if not token:
            return False
        try:
            self._get_user()
            return True
        except Exception:
            return False

    def test_connection(self) -> dict[str, Any]:
        return self._get_user()

    def _ensure_repo(self) -> dict[str, Any]:
        owner = self._owner()
        repo = self._repo()
        resp = self._api("GET", f"/repos/{owner}/{repo}")
        if resp.status_code == 200:
            return resp.json()
        resp = self._api(
            "POST",
            "/user/repos",
            json={"name": repo, "private": True, "auto_init": True},
        )
        if resp.status_code not in (201, 422):
            raise CloudError(f"创建仓库失败: {resp.json().get('message', '')}")
        return resp.json()

    def _contents_path(self, filename: str = "") -> str:
        return f"codex-memories/{filename}" if filename else "codex-memories"

    def _meta_key(self) -> str:
        return "codex-memories/metadata.json"

    def _read_metadata(self) -> dict[str, Any]:
        owner = self._owner()
        repo = self._repo()
        resp = self._api("GET", f"/repos/{owner}/{repo}/contents/{self._meta_key()}")
        if resp.status_code == 404:
            return {"versions": []}
        if resp.status_code != 200:
            raise CloudError(f"读取元数据失败: HTTP {resp.status_code}")
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)

    def _write_metadata(self, metadata: dict[str, Any]) -> None:
        owner = self._owner()
        repo = self._repo()
        sha = None
        resp = self._api("GET", f"/repos/{owner}/{repo}/contents/{self._meta_key()}")
        if resp.status_code == 200:
            sha = resp.json().get("sha")

        content = json.dumps(metadata, ensure_ascii=False, indent=2)
        body = {
            "message": f"Update metadata v{metadata.get('versions', [{}])[-1].get('version', '?') if metadata.get('versions') else 'init'}",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if sha:
            body["sha"] = sha

        resp = self._api("PUT", f"/repos/{owner}/{repo}/contents/{self._meta_key()}", json=body)
        if resp.status_code not in (200, 201):
            raise CloudError(f"写入元数据失败: {resp.json().get('message', '')}")

    def list_versions(self) -> list[dict[str, Any]]:
        self._ensure_repo()
        try:
            meta = self._read_metadata()
            versions = meta.get("versions", [])
            versions.sort(key=lambda v: v.get("version", 0), reverse=True)
            return versions
        except CloudError:
            raise
        except Exception as e:
            raise CloudError(f"获取版本列表失败: {e}") from e

    def get_latest_version(self) -> dict[str, Any] | None:
        versions = self.list_versions()
        return versions[0] if versions else None

    def upload_file(self, file_path: Path) -> dict[str, Any]:
        self._ensure_repo()
        owner = self._owner()
        repo = self._repo()
        file_path = Path(file_path)
        if not file_path.exists():
            raise CloudError(f"文件不存在: {file_path}")

        content = file_path.read_bytes()
        github_path = f"{self._contents_path(file_path.name)}"

        resp = self._api(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{github_path}",
            json={
                "message": f"Upload {file_path.name}",
                "content": base64.b64encode(content).decode("ascii"),
            },
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise CloudError(f"上传失败: {data.get('message', '')}")
        return {
            "key": data["content"]["sha"],
            "name": file_path.name,
            "path": data["content"]["path"],
            "sha": data["content"]["sha"],
        }

    def download_file(self, key: str, dest_path: Path) -> Path:
        owner = self._owner()
        repo = self._repo()
        github_path = f"{self._contents_path(Path(dest_path).name)}"

        resp = self._api("GET", f"/repos/{owner}/{repo}/contents/{github_path}")
        if resp.status_code != 200:
            raise CloudError(f"下载失败: HTTP {resp.status_code}")
        data = resp.json()
        content = base64.b64decode(data["content"])
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(content)
        return dest_path

    def delete_files(self, keys: list[str]) -> bool:
        owner = self._owner()
        repo = self._repo()
        for key in keys:
            github_path = (
                f"{self._contents_path()}/{key}/metadata.json" if "/" not in key else f"{self._contents_path()}/{key}"
            )
            resp = self._api("GET", f"/repos/{owner}/{repo}/contents/{github_path}")
            if resp.status_code != 200:
                continue
            sha = resp.json().get("sha", "")
            resp = self._api(
                "DELETE",
                f"/repos/{owner}/{repo}/contents/{github_path}",
                json={"message": f"Delete {key}", "sha": sha},
            )
        return True

    def find_file_by_filename(self, filename: str) -> str | None:
        owner = self._owner()
        repo = self._repo()
        github_path = f"{self._contents_path(filename)}"
        resp = self._api("GET", f"/repos/{owner}/{repo}/contents/{github_path}")
        if resp.status_code == 200:
            return resp.json().get("sha", "")
        return None

    def register_version(
        self,
        version: int,
        device: str,
        file_hash: str,
        size: int,
        filename: str,
        expires_days: int = 0,
    ) -> dict[str, Any]:
        self._ensure_repo()
        meta = self._read_metadata()
        meta["versions"].append(
            {
                "version": version,
                "device": device,
                "hash": file_hash,
                "size": size,
                "filename": filename,
                "path": self._sync_path(),
                "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "expires_at": None,
            }
        )
        self._write_metadata(meta)
        return {"ok": True, "version": version}

    def unregister_version(self, version: int) -> dict[str, Any]:
        meta = self._read_metadata()
        path = self._sync_path()
        old_count = len(meta["versions"])
        meta["versions"] = [v for v in meta["versions"] if not (v.get("version") == version and v.get("path") == path)]
        removed = old_count - len(meta["versions"])
        self._write_metadata(meta)
        return {"ok": True, "version": version, "removed": removed}

    def push_package(self, file_path: Path, version: int) -> dict[str, Any]:
        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        file_hash = hash_file(file_path)
        upload_result = self.upload_file(file_path)
        device = config.get_config_value("metadata", "device_id") or "unknown"
        self.register_version(
            version=version,
            device=device,
            file_hash=file_hash,
            size=file_size,
            filename=file_path.name,
            expires_days=0,
        )
        return {"key": upload_result.get("sha", ""), "hash": file_hash, "size": file_size, "file": upload_result}

    def pull_package(self, dest_dir: Path) -> dict[str, Any] | None:
        latest = self.get_latest_version()
        if not latest:
            return None
        filename = latest.get("filename", "")
        key = latest.get("hash", "") or self.find_file_by_filename(filename)
        if not key:
            versions = self.list_versions()
            if versions:
                latest = versions[0]
                filename = latest.get("filename", "")
                key = latest.get("hash", "")
        if not key:
            raise CloudError(f"无法找到版本 {latest.get('version', '?')} 对应的文件")
        dest_path = dest_dir / filename
        self.download_file(key, dest_path)
        return {"path": str(dest_path), "version": latest}

    def _sync_path(self) -> str:
        return config.get_config_value("cloud", "sync_path") or "/codex-memories/"
