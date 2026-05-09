from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CloudError(Exception):
    pass


class AuthError(CloudError):
    pass


class NetworkError(CloudError):
    pass


class CloudBackend(ABC):
    """抽象云存储后端"""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        ...

    @abstractmethod
    def list_versions(self) -> list[dict[str, Any]]:
        """列出所有同步版本"""
        ...

    @abstractmethod
    def get_latest_version(self) -> dict[str, Any] | None:
        """获取最新版本"""
        ...

    @abstractmethod
    def upload_file(self, file_path: Path) -> dict[str, Any]:
        """上传文件，返回 {'key': ..., 'name': ...}"""
        ...

    @abstractmethod
    def download_file(self, key: str, dest_path: Path) -> Path:
        """下载文件到目标路径"""
        ...

    @abstractmethod
    def delete_files(self, keys: list[str]) -> bool:
        """删除文件"""
        ...

    @abstractmethod
    def register_version(
        self,
        version: int,
        device: str,
        file_hash: str,
        size: int,
        filename: str,
        expires_days: int = 3,
    ) -> dict[str, Any]:
        """注册新版本到元数据"""
        ...

    @abstractmethod
    def unregister_version(self, version: int) -> dict[str, Any]:
        """从元数据中注销版本"""
        ...

    @abstractmethod
    def push_package(self, file_path: Path, version: int) -> dict[str, Any]:
        """推送加密包：上传 + 注册"""
        ...

    @abstractmethod
    def pull_package(self, dest_dir: Path) -> dict[str, Any] | None:
        """拉取最新加密包：找到 → 下载"""
        ...

    @abstractmethod
    def find_file_by_filename(self, filename: str) -> str | None:
        """根据文件名找到存储 key/hash"""
        ...

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """测试连接"""
        ...
