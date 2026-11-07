"""下载历史持久化。"""

from __future__ import annotations

import threading
from typing import Any

from .models import DownloadTask
from .paths import HISTORY_FILE
from .utils import atomic_write_json, read_json


class HistoryStore:
    def __init__(self, path=HISTORY_FILE, limit: int = 500):
        self.path = path
        self.limit = limit
        self._lock = threading.RLock()
        data = read_json(path, [])
        self._items: list[dict[str, Any]] = data if isinstance(data, list) else []

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)

    def add(self, task: DownloadTask) -> None:
        item = task.to_history()
        with self._lock:
            self._items = [entry for entry in self._items if entry.get('id') != item.get('id')]
            self._items.insert(0, item)
            self._items = self._items[:self.limit]
            self.save()

    def remove(self, record_id: str) -> None:
        with self._lock:
            self._items = [entry for entry in self._items if entry.get('id') != record_id]
            self.save()

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self.save()

    def save(self) -> None:
        try:
            atomic_write_json(self.path, self._items)
        except OSError:
            pass
