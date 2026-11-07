"""FireflyDL 的 yt-dlp 快手扩展。

yt-dlp 上游目前没有稳定的 kuaishou.com 提取器（见 yt-dlp issue #14010 / #14024）。
快手移动分享页会把视频信息放在 ``window.INIT_STATE`` 中，本模块负责把其中的
HLS / 直链转换成 yt-dlp 可以直接下载的 formats。

这个目录是 yt-dlp 的插件命名空间：``yt_dlp_plugins/extractor``。
只要项目根目录在 sys.path 中，yt-dlp 启动时会自动加载这里。
"""

from __future__ import annotations

import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    int_or_none,
    str_or_none,
    traverse_obj,
    unified_timestamp,
    url_or_none,
)


class KuaishouFireflyIE(InfoExtractor):
    IE_NAME = 'kuaishou:firefly'
    IE_DESC = '快手（FireflyDL 扩展）'
    _VALID_URL = (
        r'https?://(?:(?:www|v|m)\.)?(?:kuaishou\.com|chenzhongtech\.com|gifshow\.com)/'
        r'(?:(?:short-video|fw/photo|photo|f)/)?(?P<id>[^/?#&]+)'
    )

    _TESTS = [{
        'url': 'https://www.kuaishou.com/short-video/3x25msbsnncn8cs',
        'info_dict': {
            'id': '5229805182084287773',
            'ext': 'mp4',
            'title': str,
            'uploader': str,
        },
        'params': {'skip_download': True},
    }]

    _ANDROID_UA = (
        'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
    )
    _DESKTOP_UA = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )

    @staticmethod
    def _walk(value):
        """深度遍历 INIT_STATE，产出所有字典。"""
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from KuaishouFireflyIE._walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from KuaishouFireflyIE._walk(child)

    def _find_photo(self, state, video_id):
        candidates = []
        for obj in self._walk(state):
            if not isinstance(obj, dict):
                continue
            if any(k in obj for k in ('manifest', 'mainMvUrls', 'playUrl', 'photoId')):
                if obj.get('manifest') or obj.get('mainMvUrls') or obj.get('playUrl'):
                    candidates.append(obj)
        if not candidates:
            return None

        # photoId 可能是数字或字符串；优先选与 URL / 短链跳转后 ID 一致的。
        def score(photo):
            pid = str_or_none(photo.get('photoId')) or ''
            share_info = str(photo.get('share_info') or '')
            points = int(bool(photo.get('manifest')))
            if video_id and pid == str(video_id):
                points += 5
            if video_id and video_id in share_info:
                points += 10
            return points

        candidates.sort(key=score, reverse=True)
        return candidates[0]

    def _real_extract(self, url):
        display_id = self._match_id(url)
        headers = {
            'User-Agent': self._ANDROID_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.6',
            'Referer': 'https://www.kuaishou.com/',
        }

        urlh = self._request_webpage(
            url, display_id,
            note='下载快手分享页',
            headers=headers,
        )
        final_url = urlh.url
        webpage = urlh.read().decode('utf-8', 'replace')
        id_match = re.search(r'/(?:fw/photo|short-video|photo)/([^/?#&]+)', final_url)
        video_id = id_match.group(1) if id_match else display_id

        state = self._search_json(
            r'window\.INIT_STATE\s*=', webpage, '快手 INIT_STATE', video_id,
            end_pattern=r'</script>', default=None,
        )
        if not state:
            # 分享页结构偶尔变化，保留一个兜底，避免直接失败。
            state = self._search_json(
                r'window\.__APOLLO_STATE__\s*=', webpage, '快手 APOLLO_STATE',
                video_id, end_pattern=r'</script>', default=None,
            )

        photo = self._find_photo(state, video_id) if state else None
        if not photo:
            if '验证' in webpage or 'verify' in webpage.lower()[:5000]:
                raise ExtractorError(
                    '快手要求人机验证，请稍后重试，或在设置中导入浏览器 Cookie',
                    expected=True,
                )
            raise ExtractorError(
                '快手页面中未找到视频数据，可能是分享链接失效或快手改版；'
                '可尝试更新 yt-dlp 或导入浏览器 Cookie',
                expected=True,
            )

        video_id = str_or_none(photo.get('photoId')) or video_id
        caption = (photo.get('caption') or '').strip()
        title = caption or f'快手视频 {video_id}'
        uploader = photo.get('userName') or photo.get('user_name')
        duration = photo.get('duration')
        if duration is not None:
            duration = float(duration)
            if duration > 1000:  # 快手使用毫秒
                duration /= 1000

        cover_urls = traverse_obj(photo, ('coverUrls', ..., 'url'), default=[])
        thumbnail = next((u for u in cover_urls if url_or_none(u)), None)
        if not thumbnail:
            thumbnail = traverse_obj(photo, ('webpCoverUrls', 0, 'url'), default=None)

        formats = []
        seen_urls = set()

        manifest = photo.get('manifest') or {}
        for adaptation in traverse_obj(manifest, ('adaptationSet', lambda _, v: isinstance(v, dict)), default=[]):
            for rep in traverse_obj(adaptation, ('representation', lambda _, v: isinstance(v, dict)), default=[]):
                media_url = url_or_none(rep.get('url'))
                if not media_url or media_url in seen_urls:
                    continue
                seen_urls.add(media_url)
                height = int_or_none(rep.get('height')) or int_or_none(adaptation.get('height'))
                width = int_or_none(rep.get('width')) or int_or_none(adaptation.get('width'))
                vcodec_raw = (rep.get('videoCodec') or '').lower()
                vcodec = 'hev1.1.6.L120' if 'hevc' in vcodec_raw or 'h265' in vcodec_raw else 'avc1.64001F'
                is_hls = '.m3u8' in media_url.lower()
                quality = rep.get('qualityType') or rep.get('qualityLabel') or (
                    f'{height}p' if height else None)
                formats.append({
                    'format_id': 'hls-%s-%s' % (
                        height or rep.get('id') or len(formats), 'hevc' if 'hevc' in vcodec_raw else 'avc'),
                    'url': media_url,
                    'ext': 'mp4',
                    'protocol': 'm3u8_native' if is_hls else 'https',
                    'width': width,
                    'height': height,
                    'vcodec': vcodec,
                    'acodec': 'mp4a.40.2',
                    'tbr': int_or_none(rep.get('avgBitrate')),
                    'format_note': quality,
                    'http_headers': {
                        'User-Agent': self._ANDROID_UA,
                        'Referer': 'https://www.kuaishou.com/',
                    },
                })

        # 直链 mp4 通常是 CDN 上的原始文件，作为 HLS 之外的兜底。
        for index, item in enumerate(traverse_obj(photo, ('mainMvUrls', lambda _, v: isinstance(v, dict)), default=[])):
            media_url = url_or_none(item.get('url'))
            if not media_url or media_url in seen_urls:
                continue
            seen_urls.add(media_url)
            height = int_or_none(photo.get('height'))
            width = int_or_none(photo.get('width'))
            formats.append({
                'format_id': 'direct' if index == 0 else f'direct-{index}',
                'url': media_url,
                'ext': 'mp4',
                'width': width,
                'height': height,
                'vcodec': 'avc1.64001F',
                'acodec': 'mp4a.40.2',
                'format_note': '直链',
                'http_headers': {
                    'User-Agent': self._ANDROID_UA,
                    'Referer': 'https://www.kuaishou.com/',
                },
            })

        if not formats:
            # 兼容少量仍保留 playUrl 的旧版页面。
            for key in ('playUrl', 'videoUrl', 'srcNoMark'):
                media_url = url_or_none(photo.get(key))
                if media_url:
                    formats.append({
                        'format_id': key,
                        'url': media_url,
                        'ext': 'mp4',
                        'vcodec': 'avc1.64001F',
                        'acodec': 'mp4a.40.2',
                        'http_headers': {'User-Agent': self._ANDROID_UA},
                    })
        if not formats:
            raise ExtractorError('快手中未找到可下载的视频地址', expected=True)

        return {
            'id': video_id,
            'title': title,
            'description': caption,
            'uploader': uploader,
            'uploader_id': str_or_none(photo.get('userId')),
            'duration': duration,
            'thumbnail': thumbnail,
            'timestamp': (
                unified_timestamp(photo.get('timestamp'))
                if isinstance(photo.get('timestamp'), str)
                else int_or_none(photo.get('timestamp'))
            ),
            'view_count': int_or_none(photo.get('viewCount')),
            'like_count': int_or_none(photo.get('likeCount')),
            'comment_count': int_or_none(photo.get('commentCount')),
            'repost_count': int_or_none(photo.get('forwardCount')),
            'formats': formats,
            'http_headers': {
                'User-Agent': self._ANDROID_UA,
                'Referer': 'https://www.kuaishou.com/',
            },
            'webpage_url': final_url,
        }
