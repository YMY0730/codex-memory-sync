from __future__ import annotations

import json
import struct
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from . import config

PBKDF2_ITERATIONS = 600000
AES_KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12
VERSION_BYTE = 1


class DecryptError(Exception):
    pass


class VerifyError(Exception):
    pass


def _derive_key(password: str, salt: bytes) -> bytes:
    password_bytes = password.encode("utf-8") if isinstance(password, str) else password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password_bytes)


def decrypt(encrypted_data: bytes, password: str) -> bytes:
    if len(encrypted_data) < 1 + SALT_LENGTH + NONCE_LENGTH:
        raise DecryptError("加密数据长度不足")

    pos = 0
    version = struct.unpack(">B", encrypted_data[pos : pos + 1])[0]
    pos += 1
    if version != VERSION_BYTE:
        raise DecryptError(f"不支持的加密版本: {version}")

    salt = encrypted_data[pos : pos + SALT_LENGTH]
    pos += SALT_LENGTH
    nonce = encrypted_data[pos : pos + NONCE_LENGTH]
    pos += NONCE_LENGTH
    ciphertext = encrypted_data[pos:]

    try:
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext
    except Exception as e:
        raise DecryptError(f"解密失败，密码可能不正确: {e}") from e


def verify(encrypted_data: bytes, password: str) -> bool:
    try:
        decrypt(encrypted_data, password)
        return True
    except DecryptError:
        return False


def unpack_package(raw_data: bytes) -> dict[str, Any]:
    buf = BytesIO(raw_data)
    try:
        with zipfile.ZipFile(buf, "r") as zf:
            manifest_bytes = zf.read("manifest.json")
            manifest = json.loads(manifest_bytes.decode("utf-8"))

            files: dict[str, bytes] = {}
            for name in zf.namelist():
                if name.startswith("memories/"):
                    rel_name = name[len("memories/") :]
                    files[rel_name] = zf.read(name)

            return {"manifest": manifest, "files": files}
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
        raise DecryptError(f"解包失败: {e}") from e


def restore_files(files: dict[str, bytes], memory_dir: Path) -> list[str]:
    restored: list[str] = []
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    for name, content in files.items():
        dest_path = memory_dir / name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(content)
        restored.append(name)

    return restored


def import_encrypted(encrypted_data: bytes, password: str, memory_dir: Path) -> dict[str, Any]:
    plaintext = decrypt(encrypted_data, password)
    package = unpack_package(plaintext)
    manifest = package["manifest"]
    files = package["files"]

    restored = restore_files(files, memory_dir)

    sync_version = manifest.get("sync_version", 0)
    source_device = manifest.get("device_id", "unknown")

    config.update_metadata(
        {
            "local_version": sync_version,
            "last_pull_version": sync_version,
            "last_pull_time": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    )

    return {
        "manifest": manifest,
        "restored_files": restored,
        "source_device": source_device,
        "version": sync_version,
    }


def import_from_file(file_path: str | Path, password: str, memory_dir: Path) -> dict[str, Any]:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "rb") as f:
        encrypted_data = f.read()

    return import_encrypted(encrypted_data, password, memory_dir)


def preview_encrypted(encrypted_data: bytes, password: str) -> dict[str, Any]:
    plaintext = decrypt(encrypted_data, password)
    package = unpack_package(plaintext)
    manifest = package["manifest"]
    files = package["files"]
    return {
        "version": manifest.get("sync_version", 0),
        "device": manifest.get("device_id", "unknown"),
        "timestamp": manifest.get("timestamp", 0),
        "file_count": len(files),
        "file_list": list(files.keys()),
        "file_sizes": {name: len(content) for name, content in files.items()},
    }
