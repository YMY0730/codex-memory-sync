from enum import Enum
from typing import Any

from . import config


class SyncStatus(Enum):
    SYNCED = "synced"
    LOCAL_AHEAD = "local_ahead"
    CLOUD_AHEAD = "cloud_ahead"
    CONFLICT = "conflict"
    UNINITIALIZED = "uninitialized"


def get_local_info() -> dict[str, Any]:
    return {
        "version": config.get_config_value("metadata", "local_version") or 0,
        "hash": config.get_config_value("metadata", "local_hash") or "",
        "last_push_version": config.get_config_value("metadata", "last_push_version") or 0,
        "last_push_time": config.get_config_value("metadata", "last_push_time") or "",
        "last_pull_version": config.get_config_value("metadata", "last_pull_version") or 0,
        "last_pull_time": config.get_config_value("metadata", "last_pull_time") or "",
        "device_id": config.get_config_value("metadata", "device_id") or "",
    }


def get_cloud_info(versions: list[dict[str, Any]]) -> dict[str, Any]:
    if not versions:
        return {"latest_version": 0, "latest_hash": "", "total_versions": 0, "versions": []}
    latest = versions[0]
    return {
        "latest_version": latest.get("version", 0),
        "latest_hash": latest.get("hash", ""),
        "latest_device": latest.get("device", ""),
        "latest_time": latest.get("time", ""),
        "total_versions": len(versions),
        "versions": versions,
    }


def compare(cloud_versions: list[dict[str, Any]]) -> dict[str, Any]:
    local = get_local_info()
    cloud = get_cloud_info(cloud_versions)

    local_version = local["version"]
    local_hash = local["hash"]
    cloud_version = cloud["latest_version"]
    cloud_hash = cloud["latest_hash"]

    if local_version == 0 and cloud_version == 0:
        status = SyncStatus.UNINITIALIZED
    elif local_version == 0 and cloud_version > 0:
        status = SyncStatus.CLOUD_AHEAD
    elif local_version > 0 and cloud_version == 0:
        status = SyncStatus.LOCAL_AHEAD
    elif local_version == cloud_version:
        status = SyncStatus.CONFLICT if local_hash and cloud_hash and local_hash != cloud_hash else SyncStatus.SYNCED
    elif local_version > cloud_version:
        status = SyncStatus.LOCAL_AHEAD
    else:
        status = SyncStatus.CLOUD_AHEAD

    return {
        "status": status.value,
        "local": local,
        "cloud": cloud,
    }
