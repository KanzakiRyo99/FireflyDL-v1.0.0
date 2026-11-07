"""通用工具测试。"""

from __future__ import annotations

import unittest

from fireflydl.utils import (
    detect_site, friendly_error, human_bytes, human_count, human_duration,
    normalize_urls, safe_filename,
)


class UrlTests(unittest.TestCase):
    def test_share_text(self):
        text = ('3.14 复制打开抖音，看看【作者的作品】 '
                'https://v.douyin.com/iAbCdEf/ 复制此链接，打开Dou音搜索')
        self.assertEqual(normalize_urls(text), ['https://v.douyin.com/iAbCdEf/'])

    def test_multiple_and_dedupe(self):
        text = ('https://www.bilibili.com/video/BV1GJ411x7h7，\n'
                'https://www.bilibili.com/video/BV1GJ411x7h7/\n'
                'https://youtu.be/dQw4w9WgXcQ')
        urls = normalize_urls(text)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], 'https://www.bilibili.com/video/BV1GJ411x7h7')

    def test_bv_and_av(self):
        self.assertEqual(normalize_urls('看看 BV1GJ411x7h7 这个视频'),
                         ['https://www.bilibili.com/video/BV1GJ411x7h7'])
        self.assertEqual(normalize_urls('av170001'),
                         ['https://www.bilibili.com/video/av170001'])

    def test_no_url(self):
        self.assertEqual(normalize_urls('普通文本'), [])


class SiteTests(unittest.TestCase):
    def test_sites(self):
        self.assertEqual(detect_site('https://www.bilibili.com/video/x')[0], 'B站')
        self.assertEqual(detect_site('https://v.kuaishou.com/abc')[0], '快手')
        self.assertEqual(detect_site('https://youtu.be/abc')[0], 'YouTube')
        self.assertEqual(detect_site('https://example.com/a')[0], '其他')


class FormatTests(unittest.TestCase):
    def test_human_bytes(self):
        self.assertEqual(human_bytes(0), '—')
        self.assertEqual(human_bytes(512), '512 B')
        self.assertEqual(human_bytes(1536), '1.5 KB')
        self.assertEqual(human_bytes(1024 ** 3), '1.0 GB')

    def test_duration(self):
        self.assertEqual(human_duration(0), '—')
        self.assertEqual(human_duration(65), '01:05')
        self.assertEqual(human_duration(3661), '1:01:01')

    def test_count(self):
        self.assertEqual(human_count(999), '999')
        self.assertEqual(human_count(12345), '1.2万')
        self.assertEqual(human_count(123456789), '1.2亿')

    def test_safe_filename(self):
        self.assertEqual(safe_filename('a<b>:c?.mp4'), 'a_b__c_.mp4')
        self.assertEqual(safe_filename('...'), 'video')


class ErrorTests(unittest.TestCase):
    def test_cookie_hint(self):
        message = friendly_error('ERROR: Fresh cookies (not necessarily logged in) are needed')
        self.assertIn('Cookie', message)

    def test_timeout_hint(self):
        self.assertIn('超时', friendly_error('Unable to download webpage: timed out'))
        self.assertIn('代理', friendly_error('Connection refused'))

    def test_ffmpeg_hint(self):
        self.assertIn('ffmpeg', friendly_error('ERROR: ffmpeg not found. Please install'))

    def test_range_hint(self):
        self.assertIn('416', friendly_error('HTTP Error 416: Requested Range Not Satisfiable'))


if __name__ == '__main__':
    unittest.main()
