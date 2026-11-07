"""配置、任务与历史测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fireflydl.config import Settings
from fireflydl.history import HistoryStore
from fireflydl.models import DownloadTask


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            settings = Settings(download_dir=folder, concurrency=99,
                                default_mode='bad', default_quality='bad',
                                filename_template='no-ext').normalized()
            self.assertEqual(settings.concurrency, 6)
            self.assertEqual(settings.default_mode, 'video')
            self.assertEqual(settings.default_quality, 'best')
            self.assertIn('%(ext)s', settings.filename_template)
            settings.save(path)
            loaded = Settings.load(path)
            self.assertEqual(loaded.download_dir, folder)
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['concurrency'], 6)

    def test_cookie_precedence_values(self):
        settings = Settings(cookies_from_browser='edge', cookies_file='').normalized()
        self.assertEqual(settings.cookies_from_browser, 'edge')


class TaskTests(unittest.TestCase):
    def test_mark_completed(self):
        task = DownloadTask(url='https://www.bilibili.com/video/BV1xx', title='T')
        task.progress = 42
        task.mark('completed')
        self.assertEqual(task.status, 'completed')
        self.assertEqual(task.progress, 100)
        self.assertTrue(task.is_finished)
        self.assertEqual(task.progress_text, '100%')

    def test_site_detection(self):
        task = DownloadTask(url='https://www.kuaishou.com/short-video/abc')
        self.assertEqual(task.site, '快手')
        self.assertEqual(task.site_color, '#FF6B35')


class HistoryTests(unittest.TestCase):
    def test_add_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            store = HistoryStore(path)
            task = DownloadTask(url='https://example.com/v', title='A')
            task.mark('completed')
            store.add(task)
            self.assertEqual(len(store.all()), 1)
            self.assertEqual(store.all()[0]['title'], 'A')
            store.remove(task.id)
            self.assertEqual(store.all(), [])

    def test_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            store = HistoryStore(path)
            task = DownloadTask(url='https://example.com/v', title='B')
            task.mark('completed')
            store.add(task)
            again = HistoryStore(path)
            self.assertEqual(again.all()[0]['title'], 'B')


if __name__ == '__main__':
    unittest.main()
