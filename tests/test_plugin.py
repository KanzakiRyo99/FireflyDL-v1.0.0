"""快手 yt-dlp 扩展测试。"""

from __future__ import annotations

import unittest


class KuaishouPluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fireflydl import ensure_plugin_path
        ensure_plugin_path()
        from yt_dlp_plugins.extractor.kuaishou import KuaishouFireflyIE
        cls.ie = KuaishouFireflyIE
        cls.instance = KuaishouFireflyIE()

    def test_urls(self):
        for url in (
            'https://www.kuaishou.com/short-video/3x25msbsnncn8cs',
            'https://v.kuaishou.com/abcDef',
            'https://m.gifshow.com/fw/photo/3x25msbsnncn8cs',
            'https://www.chenzhongtech.com/short-video/abc',
        ):
            self.assertTrue(self.instance.suitable(url), url)

    def test_match_id(self):
        self.assertEqual(
            self.instance._match_id('https://www.kuaishou.com/short-video/3x25msbsnncn8cs'),
            '3x25msbsnncn8cs',
        )

    def test_walk(self):
        state = {'a': {'photoId': '1'}, 'b': [{'photoId': '2'}]}
        found = [obj.get('photoId') for obj in self.instance._walk(state)]
        self.assertIn('1', found)
        self.assertIn('2', found)


if __name__ == '__main__':
    unittest.main()
