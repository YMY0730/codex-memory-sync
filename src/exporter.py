import hashlib
import io
import json
import os
import struct
import time
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from . import config

PBKDF2_ITERATIONS = 600000
AES_KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12
VERSION_BYTE = 1


def _derive_key(password: str, salt: bytes) -> bytes:
    password_bytes = password.encode("utf-8") if isinstance(password, str) else password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password_bytes)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect_files(memory_dir: Path, selected_files: list[str]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in selected_files:
        full_path = memory_dir / name
        if full_path.is_file():
            with open(full_path, "rb") as f:
                result[name] = f.read()
        elif full_path.is_dir():
            for root, _, files in os.walk(full_path):
                for file in files:
                    rel_path = str(Path(root, file).relative_to(memory_dir))
                    with open(Path(root, file), "rb") as f:
                        result[rel_path] = f.read()
    return result


def package_memories(files: dict[str, bytes], device_id: str, version: int) -> bytes:
    manifest = {
        "version": VERSION_BYTE,
        "device_id": device_id,
        "sync_version": version,
        "timestamp": int(time.time()),
        "files": list(files.keys()),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for name, content in files.items():
            zf.writestr(f"memories/{name}", content)
    return buf.getvalue()


def encrypt(raw_data: bytes, password: str) -> tuple[bytes, str]:
    salt = os.urandom(SALT_LENGTH)
    nonce = os.urandom(NONCE_LENGTH)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, raw_data, None)

    header = struct.pack(">B", VERSION_BYTE) + salt + nonce
    encrypted = header + ciphertext
    file_hash = _hash_bytes(encrypted)
    return encrypted, file_hash


def export(memory_dir: Path, selected_files: list[str], password: str) -> tuple[bytes, str, int]:
    device_id = config.get_config_value("metadata", "device_id") or "unknown"
    current_version = config.get_config_value("metadata", "local_version") or 0
    new_version = current_version + 1

    files = collect_files(memory_dir, selected_files)
    if not files:
        raise ValueError("没有找到可导出的记忆文件")

    raw_package = package_memories(files, device_id, new_version)
    encrypted_data, file_hash = encrypt(raw_package, password)

    config.update_metadata(
        {
            "local_version": new_version,
            "local_hash": file_hash,
            "last_push_version": new_version,
            "last_push_time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    )

    return encrypted_data, file_hash, new_version


def export_to_file(memory_dir: Path, selected_files: list[str], password: str, output_dir: Path) -> Path:
    encrypted_data, file_hash, new_version = export(memory_dir, selected_files, password)

    device_id = config.get_config_value("metadata", "device_id") or "unknown"
    timestamp = time.strftime("%Y%m%dT%H%M%S")
    filename = f"codex-memories-v{new_version}-{timestamp}-{device_id}.enc"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    with open(output_path, "wb") as f:
        f.write(encrypted_data)

    return output_path
