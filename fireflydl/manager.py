"""下载队列调度器。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Callable

from . import service
from .config import Settings
from .history import HistoryStore
from .models import DownloadTask
from .utils import normalize_urls


EventCallback = Callable[[str, DownloadTask | None, str], None]


class DownloadManager:
    """线程池式下载队列。

    所有对 GUI 的通知都通过 ``emit`` 发出，GUI 必须把它放入线程安全队列，
    再回到 Tk 主线程更新界面。
    """

    def __init__(self, settings_getter: Callable[[], Settings], emit: EventCallback,
                 history: HistoryStore | None = None):
        self._settings_getter = settings_getter
        self._emit = emit
        self.history = history or HistoryStore()
        self._lock = threading.RLock()
        self._tasks: OrderedDict[str, DownloadTask] = OrderedDict()
        self._active: set[str] = set()
        self._removed: set[str] = set()
        self._closed = False
        self._threads: dict[str, threading.Thread] = {}

    @property
    def settings(self) -> Settings:
        return self._settings_getter()

    def tasks(self) -> list[DownloadTask]:
        with self._lock:
            return list(self._tasks.values())

    def get(self, task_id: str) -> DownloadTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def count(self, *statuses: str) -> int:
        with self._lock:
            return sum(1 for task in self._tasks.values() if task.status in statuses)

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def add_urls(
        self,
        text: str,
        *,
        mode: str = 'video',
        quality: str = 'best',
        custom_format: str = '',
        playlist: bool = False,
        playlist_limit: int = 0,
    ) -> list[DownloadTask]:
        urls = normalize_urls(text)
        created: list[DownloadTask] = []
        with self._lock:
            for url in urls:
                task = DownloadTask(
                    url=url,
                    mode=mode,
                    quality=quality,
                    custom_format=custom_format,
                    playlist=playlist,
                    playlist_limit=playlist_limit,
                )
                self._tasks[task.id] = task
                created.append(task)
        for task in created:
            self._emit('added', task, '')
        if created:
            self._pump()
        return created

    def add_task(self, task: DownloadTask) -> DownloadTask:
        with self._lock:
            self._tasks[task.id] = task
        self._emit('added', task, '')
        self._pump()
        return task

    def _pump(self) -> None:
        if self._closed:
            return
        started: list[DownloadTask] = []
        with self._lock:
            concurrency = self.settings.concurrency_value
            if len(self._active) >= concurrency:
                return
            for task in self._tasks.values():
                if len(self._active) >= concurrency:
                    break
                if task.status != 'queued' or task.id in self._active:
                    continue
                self._active.add(task.id)
                thread = threading.Thread(
                    target=self._run_task, args=(task,),
                    name=f'fireflydl-{task.id}', daemon=True,
                )
                self._threads[task.id] = thread
                started.append(task)
                thread.start()
        for task in started:
            self._emit('status', task, '')

    def _run_task(self, task: DownloadTask) -> None:
        logger = lambda message: self._emit('log', task, message)

        def service_emit(kind: str, current: DownloadTask) -> None:
            with self._lock:
                if current.id in self._removed:
                    return
            self._emit(kind, current, '')

        try:
            result = service.run_download(task, self.settings, service_emit, logger)
        except Exception as exc:
            from .utils import friendly_error
            task.mark('error', friendly_error(exc))
            self._emit('status', task, '')
            result = service.DownloadResult(False, error=task.error)
        with self._lock:
            removed = task.id in self._removed
            self._active.discard(task.id)
            self._threads.pop(task.id, None)
        if result.success:
            if not removed:
                self.history.add(task)
                self._emit('completed', task, task.filepath)
        elif result.paused:
            if not removed:
                self._emit('paused', task, '')
        elif result.cancelled:
            if not removed:
                self._emit('cancelled', task, '')
        else:
            if not removed:
                self._emit('failed', task, result.error)
        self._pump()

    def pause(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status == 'queued':
                task.status = 'paused'
                self._emit('status', task, '')
                return True
            if task.id in self._active:
                task.pause_requested = True
                task.cancel_event.set()
                self._emit('status', task, '')
                return True
        return False

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status in {'queued', 'paused'}:
                task.status = 'cancelled'
                task.cancel_event.set()
                self._emit('status', task, '')
                return True
            if task.id in self._active:
                task.pause_requested = False
                task.cancel_event.set()
                self._emit('status', task, '')
                return True
        return False

    def resume(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status not in {'paused', 'cancelled', 'error'}:
                return False
            task.cancel_event.clear()
            task.pause_requested = False
            task.status = 'queued'
            task.error = ''
            task.finished_at = ''
            task.retries += 1
            if task.retries > 1:
                task.progress = 0.0
                task.downloaded_bytes = 0
            self._emit('status', task, '')
        self._pump()
        return True

    def retry(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.is_active:
                return False
            task.cancel_event.clear()
            task.pause_requested = False
            task.status = 'queued'
            task.error = ''
            task.progress = 0.0
            task.speed = 0
            task.eta = None
            task.finished_at = ''
            task.retries += 1
            self._emit('status', task, '')
        self._pump()
        return True

    def remove(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.is_active:
                task.cancel_event.set()
                self._removed.add(task_id)
            self._tasks.pop(task_id, None)
        self._emit('removed', task, '')
        return True

    def clear_finished(self) -> int:
        with self._lock:
            ids = [
                task_id for task_id, task in self._tasks.items()
                if task.status in {'completed', 'error', 'cancelled'}
            ]
            for task_id in ids:
                task = self._tasks.pop(task_id)
                self._emit('removed', task, '')
            return len(ids)

    def pause_all(self) -> int:
        count = 0
        for task in self.tasks():
            if task.status in {'queued', 'downloading', 'parsing'}:
                count += int(self.pause(task.id))
        return count

    def resume_all(self) -> int:
        count = 0
        for task in self.tasks():
            if task.status in {'paused', 'error', 'cancelled'}:
                count += int(self.resume(task.id))
        return count

    def set_concurrency(self, value: int) -> None:
        with self._lock:
            self.settings.concurrency = max(1, min(6, int(value)))
        self._pump()

    def shutdown(self) -> None:
        self._closed = True
        for task in self.tasks():
            if task.is_active:
                task.cancel_event.set()
        for thread in list(self._threads.values()):
            thread.join(timeout=0.8)
