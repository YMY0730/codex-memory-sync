import threading
from enum import Enum
from typing import Callable


class SyncState(Enum):
    IDLE = "idle"
    PACKAGING = "packaging"
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    DECRYPTING = "decrypting"
    RESTORING = "restoring"
    ERROR = "error"
    SYNCED = "synced"


class SyncStateMachine:
    def __init__(self):
        self._state = SyncState.IDLE
        self._lock = threading.Lock()
        self._listeners: list[Callable[[SyncState, SyncState, str], None]] = []

    @property
    def state(self) -> SyncState:
        with self._lock:
            return self._state

    def transition(self, new_state: SyncState, message: str = "") -> None:
        with self._lock:
            old_state = self._state
            self._state = new_state
        import contextlib

        for listener in self._listeners:
            with contextlib.suppress(Exception):
                listener(old_state, new_state, message)

    def on_change(self, callback: Callable[[SyncState, SyncState, str], None]) -> None:
        self._listeners.append(callback)

    def is_busy(self) -> bool:
        state = self.state
        return state in {
            SyncState.PACKAGING,
            SyncState.UPLOADING,
            SyncState.DOWNLOADING,
            SyncState.DECRYPTING,
            SyncState.RESTORING,
        }

    def is_error(self) -> bool:
        return self.state == SyncState.ERROR


_global_machine = SyncStateMachine()


def get_state_machine() -> SyncStateMachine:
    return _global_machine
