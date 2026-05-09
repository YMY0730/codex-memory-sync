from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import config


class MemoryChangeHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable[[], None]):
        self._callback = callback
        self._last_event = 0.0
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _debounce_seconds(self) -> float:
        return float(config.get_config_value("daemon", "debounce_seconds") or 3)

    def on_any_event(self, event):
        if event.is_directory:
            return
        src = str(event.src_path)
        if src.endswith(".DS_Store") or src.endswith(".tmp") or "___" in src:
            return

        with self._lock:
            now = time.time()
            self._last_event = now
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds(), self._fire)
            self._timer.start()

    def _fire(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        import contextlib

        with contextlib.suppress(Exception):
            self._callback()

    def stop(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


class WatchManager:
    def __init__(self):
        self._observer: Observer | None = None
        self._handler: MemoryChangeHandler | None = None
        self._running = False

    def start(self, path: Path, on_change: Callable[[], None]) -> None:
        if self._running:
            return
        self._handler = MemoryChangeHandler(on_change)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(path), recursive=True)
        self._observer.start()
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        if self._handler:
            self._handler.stop()
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
        self._running = False

    @property
    def running(self) -> bool:
        return self._running


_watch_manager = WatchManager()


def get_watch_manager() -> WatchManager:
    return _watch_manager
