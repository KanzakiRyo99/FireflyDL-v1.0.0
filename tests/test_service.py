"""服务层纯函数测试（不联网）。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fireflydl.config import Settings
from fireflydl.service import (
    _clean_stale_parts, _is_range_error, base_options, format_selector,
    media_from_info,
)


class SelectorTests(unittest.TestCase):
    def test_audio(self):
        self.assertEqual(format_selector('audio', 'best'), 'bestaudio/best')

    def test_best(self):
        self.assertEqual(format_selector('video', 'best'),
                         'bestvideo*+bestaudio/best')

    def test_height(self):
        selector = format_selector('video', '1080')
        self.assertIn('height<=1080', selector)

    def test_custom(self):
        self.assertEqual(format_selector('video', '1080', '137+140'), '137+140')


class OptionsTests(unittest.TestCase):
    def test_base_options(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(
                download_dir=folder,
                filename_template='%(title)s [%(id)s].%(ext)s',
                cookies_file='',
                cookies_from_browser='',
                proxy='http://127.0.0.1:7890',
                embed_thumbnail=False,
                embed_metadata=False,
                write_subs=False,
            ).normalized()
            options = base_options(settings, selector='best', mode='video', playlist=True,
                                   playlist_limit=5)
            self.assertTrue(options['outtmpl'].startswith(folder))
            self.assertTrue(options['outtmpl'].endswith('%(ext)s'))
            self.assertEqual(options['proxy'], 'http://127.0.0.1:7890')
            self.assertFalse(options['noplaylist'])
            self.assertEqual(options['playlistend'], 5)
            self.assertTrue(Path(folder).is_dir())

    def test_probe_no_download(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(download_dir=folder).normalized()
            options = base_options(settings, probe=True, flat=True)
            self.assertTrue(options['simulate'])
            self.assertEqual(options['extract_flat'], 'in_playlist')


class MediaTests(unittest.TestCase):
    def test_single_video(self):
        info = {
            'id': 'BV1xx',
            'title': '测试视频',
            'uploader': 'UP',
            'duration': 61,
            'webpage_url': 'https://www.bilibili.com/video/BV1xx',
            'formats': [
                {'format_id': '137', 'ext': 'mp4', 'height': 1080,
                 'vcodec': 'avc1', 'acodec': 'none', 'filesize': 1000, 'protocol': 'https'},
                {'format_id': '140', 'ext': 'm4a', 'vcodec': 'none',
                 'acodec': 'mp4a', 'abr': 128, 'protocol': 'https'},
            ],
        }
        media = media_from_info(info, info['webpage_url'])
        self.assertEqual(media.kind, 'video')
        self.assertEqual(media.title, '测试视频')
        self.assertEqual(len(media.formats), 2)
        self.assertEqual(media.formats[0].resolution, '1080P')
        self.assertTrue(media.formats[1].is_audio)

    def test_playlist(self):
        info = {
            '_type': 'playlist',
            'id': 'pl',
            'title': '合集',
            'playlist_count': 2,
            'entries': [
                {'id': '1', 'title': '第一集', 'url': 'https://example.com/1', 'duration': 10},
                {'id': '2', 'title': '第二集', 'webpage_url': 'https://example.com/2'},
            ],
        }
        media = media_from_info(info, 'https://example.com/list')
        self.assertEqual(media.kind, 'playlist')
        self.assertEqual(media.playlist_count, 2)
        self.assertEqual(media.entries[0].title, '第一集')
        self.assertEqual(media.entries[1].url, 'https://example.com/2')


class RangeRecoveryTests(unittest.TestCase):
    def test_range_error_detection(self):
        self.assertTrue(_is_range_error('HTTP Error 416: Requested Range Not Satisfiable'))
        self.assertTrue(_is_range_error('Requested Range Not Satisfiable'))
        self.assertFalse(_is_range_error('HTTP Error 403: Forbidden'))

    def test_clean_only_target_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            target = base / 'video [BV1abc].f30280.m4a.part'
            unrelated = base / 'other [BV9xyz].f30280.m4a.part'
            target.write_bytes(b'x')
            unrelated.write_bytes(b'x')
            removed = _clean_stale_parts(base, str(target.with_suffix('')), 'BV1abc')
            self.assertTrue(removed)
            self.assertFalse(target.exists())
            self.assertTrue(unrelated.exists())


if __name__ == '__main__':
    unittest.main()
