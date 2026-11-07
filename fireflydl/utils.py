"""通用工具函数。"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .paths import resource_root


ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
URL_RE = re.compile(r'https?://[^\s<>"\'“”‘’]+', re.IGNORECASE)
BV_RE = re.compile(r'(?<![0-9A-Za-z])(BV[0-9A-Za-z]{10})(?![0-9A-Za-z])')
AV_RE = re.compile(r'(?<![0-9A-Za-z])av(\d{1,12})(?![0-9A-Za-z])', re.IGNORECASE)
TRAILING_CHARS = '.,;:!?，。；：！？、）)】]}>》」』'

SITE_LABELS = {
    'bilibili.com': ('B站', '#FB7299'),
    'b23.tv': ('B站', '#FB7299'),
    'douyin.com': ('抖音', '#25F4EE'),
    'iesdouyin.com': ('抖音', '#25F4EE'),
    'kuaishou.com': ('快手', '#FF6B35'),
    'gifshow.com': ('快手', '#FF6B35'),
    'chenzhongtech.com': ('快手', '#FF6B35'),
    'youtube.com': ('YouTube', '#FF4444'),
    'youtu.be': ('YouTube', '#FF4444'),
    'tiktok.com': ('TikTok', '#EE1D52'),
    'weibo.com': ('微博', '#E6162D'),
    'weibo.cn': ('微博', '#E6162D'),
    'xiaohongshu.com': ('小红书', '#FF2442'),
    'xhslink.com': ('小红书', '#FF2442'),
    'twitter.com': ('X', '#E7E9EA'),
    'x.com': ('X', '#E7E9EA'),
    'instagram.com': ('Instagram', '#E1306C'),
    'facebook.com': ('Facebook', '#1877F2'),
    'vimeo.com': ('Vimeo', '#1AB7EA'),
    'twitch.tv': ('Twitch', '#9146FF'),
    'dailymotion.com': ('Dailymotion', '#00AAFF'),
    'acfun.cn': ('AcFun', '#FD4C5B'),
    'iqiyi.com': ('爱奇艺', '#00BE06'),
    'youku.com': ('优酷', '#1F8AFF'),
    'v.qq.com': ('腾讯视频', '#FF6022'),
    'mgtv.com': ('芒果TV', '#FF7100'),
    'douban.com': ('豆瓣', '#2F9B47'),
    'zhihu.com': ('知乎', '#0066FF'),
}

SUPPORTED_HINT = ('B站 / 抖音 / 快手 / YouTube / TikTok / 微博 / 小红书 / X / '
                  'Instagram / Vimeo 等 1700+ 站点')


def strip_ansi(text: Any) -> str:
    return ANSI_RE.sub('', str(text or ''))


def clean_text(text: Any, limit: int = 0) -> str:
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', strip_ansi(text)).strip()
    if limit and len(text) > limit:
        return text[:max(0, limit - 1)] + '…'
    return text


def normalize_urls(text: str) -> list[str]:
    """从分享文案中提取链接，并补全 BV/av 号。"""
    text = (text or '').replace('\u200b', '')
    urls: list[str] = []
    for match in URL_RE.findall(text):
        url = match.rstrip(TRAILING_CHARS)
        if url.lower().startswith(('http://', 'https://')):
            urls.append(url)
    if not urls:
        for bv in BV_RE.findall(text):
            urls.append(f'https://www.bilibili.com/video/{bv}')
        for av in AV_RE.findall(text):
            urls.append(f'https://www.bilibili.com/video/av{av}')
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        key = url.rstrip('/')
        if key not in seen:
            seen.add(key)
            result.append(url)
    return result


def detect_site(url: str) -> tuple[str, str]:
    """返回 (站点中文名, 站点主题色)。"""
    try:
        host = (urlparse(url).hostname or '').lower()
    except ValueError:
        return '其他', '#8B93A7'
    for domain, (label, color) in SITE_LABELS.items():
        if host == domain or host.endswith('.' + domain):
            return label, color
    for domain, (label, color) in SITE_LABELS.items():
        if domain in host:
            return label, color
    return '其他', '#8B93A7'


def human_bytes(size: Any) -> str:
    try:
        value = float(size or 0)
    except (TypeError, ValueError):
        return '—'
    if value <= 0:
        return '—'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f'{int(value)} {units[index]}'
    return f'{value:.1f} {units[index]}'


def human_speed(speed: Any) -> str:
    if not speed:
        return '—'
    return f'{human_bytes(speed)}/s'


def human_count(count: Any) -> str:
    try:
        value = int(count or 0)
    except (TypeError, ValueError):
        return '—'
    if value >= 100_000_000:
        return f'{value / 100_000_000:.1f}亿'
    if value >= 10_000:
        return f'{value / 10_000:.1f}万'
    return str(value)


def human_duration(seconds: Any) -> str:
    try:
        total = int(float(seconds or 0))
    except (TypeError, ValueError):
        return '—'
    if total <= 0:
        return '—'
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def human_eta(seconds: Any) -> str:
    try:
        total = int(float(seconds or 0))
    except (TypeError, ValueError):
        return '—'
    if total <= 0:
        return '—'
    if total < 60:
        return f'{total} 秒'
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f'{minutes} 分 {secs:02d} 秒'
    hours, minutes = divmod(minutes, 60)
    return f'{hours} 小时 {minutes:02d} 分'


def now_text() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def today_text() -> str:
    return datetime.now().strftime('%Y-%m-%d')


def safe_filename(name: str, limit: int = 120) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', clean_text(name))
    name = name.strip().rstrip('.')
    if not name:
        name = 'video'
    if len(name) > limit:
        name = name[:limit - 1] + '…'
    return name


def open_path(path: str | Path, select_file: bool = False) -> bool:
    """在资源管理器中打开目录，或定位到文件。"""
    target = Path(path)
    try:
        if sys.platform.startswith('win'):
            if select_file and target.is_file():
                subprocess.Popen(['explorer', '/select,', str(target)])
            elif target.is_file():
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                target.mkdir(parents=True, exist_ok=True)
                os.startfile(str(target))  # type: ignore[attr-defined]
            return True
        if sys.platform == 'darwin':
            subprocess.Popen(['open', '-R' if select_file else '', str(target)])
            return True
        if target.is_file():
            subprocess.Popen(['xdg-open', str(target.parent)])
        else:
            target.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(['xdg-open', str(target)])
        return True
    except Exception:
        return False


def find_ffmpeg(configured: str = '') -> str:
    candidates: list[Path] = []
    if configured:
        path = Path(configured).expanduser()
        if path.is_dir():
            path = path / ('ffmpeg.exe' if sys.platform.startswith('win') else 'ffmpeg')
        candidates.append(path)
    which = shutil.which('ffmpeg')
    if which:
        candidates.append(Path(which))
    candidates.extend([
        resource_root() / 'bin' / 'ffmpeg.exe',
        Path('C:/ffmpeg/bin/ffmpeg.exe'),
        Path.home() / 'ffmpeg/bin/ffmpeg.exe',
        Path('/usr/bin/ffmpeg'),
        Path('/usr/local/bin/ffmpeg'),
    ])
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return ''


def ffmpeg_version(ffmpeg: str) -> str:
    if not ffmpeg:
        return '未检测到'
    try:
        flags = 0x08000000 if sys.platform.startswith('win') else 0
        output = subprocess.check_output(
            [ffmpeg, '-version'], stderr=subprocess.STDOUT,
            timeout=8, creationflags=flags,
        ).decode('utf-8', 'replace')
        first = output.splitlines()[0] if output else ''
        match = re.search(r'ffmpeg version\s+(\S+)', first)
        return match.group(1) if match else '已找到'
    except Exception:
        return '已找到'


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.stem + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def friendly_error(error: Any) -> str:
    """把 yt-dlp / 网络异常翻译成用户能行动的提示。"""
    raw = clean_text(error)
    lower = raw.lower()
    if not raw:
        return '未知错误，请查看日志'
    if 'fresh cookies' in lower or ('cookies' in lower and 'needed' in lower):
        return '该站点需要 Cookie 验证。请到「设置 → 登录凭证」导入浏览器 Cookie 后重试。'
    if 'sign in to confirm' in lower or 'not a bot' in lower:
        return '站点触发了人机验证。请导入浏览器 Cookie，或更换网络 / 配置代理后重试。'
    if 'ffprobe' in lower and ('not found' in lower or 'not installed' in lower or 'unable' in lower):
        return '未找到 ffprobe。某些封面/字幕嵌入操作需要它，请安装完整版 ffmpeg。'
    if 'ffmpeg' in lower and ('not found' in lower or 'not installed' in lower or 'unable' in lower):
        return '未找到 ffmpeg，无法合并音视频。请安装 ffmpeg 并在「设置」中指定路径。'
    if 'timed out' in lower or 'timeout' in lower or 'timedout' in lower:
        return '网络连接超时。请检查网络，或在「设置」中配置代理后重试。'
    if 'connection' in lower or 'network is unreachable' in lower or 'getaddrinfo' in lower:
        return '网络连接失败。请检查网络，或在「设置」中配置代理后重试。'
    if 'http error 416' in lower or 'range not satisfiable' in lower:
        return '断点续传位置失效（416）。应用会尝试清理失效分片并重新下载；如仍失败，请删除同名 .part 文件后重试。'
    if 'http error 403' in lower or '403 forbidden' in lower:
        return '服务器拒绝访问（403）。可能需要 Cookie、代理，或链接已过期。'
    if 'http error 404' in lower or 'not found' in lower:
        return '页面不存在或视频已被删除（404）。'
    if 'private video' in lower or 'private' in lower:
        return '该视频为私密内容，需要登录且有访问权限。'
    if 'members-only' in lower or 'paid' in lower or 'premium' in lower:
        return '该视频仅限会员 / 付费用户观看，当前账号无权访问。'
    if 'geo' in lower and ('restrict' in lower or 'block' in lower):
        return '该视频存在地区限制，请更换网络或使用相应地区的代理。'
    if 'unsupported url' in lower:
        return '暂不支持该链接。请确认链接完整，或更新 yt-dlp 后重试。'
    if 'requested format' in lower or 'format is not available' in lower:
        return '所选清晰度 / 格式不可用，请换一个清晰度或选择「最佳」。'
    if 'no space left' in lower or 'disk full' in lower:
        return '磁盘空间不足，请清理空间或更换下载目录。'
    if 'ssl' in lower or 'certificate' in lower:
        return 'SSL 证书校验失败。请检查系统时间、代理设置或网络环境。'
    if 'unsupported' in lower and 'python' in lower:
        return 'yt-dlp 版本过旧，请在「设置」中更新 yt-dlp。'
    if 'cancelled' in lower or 'canceled' in lower:
        return '下载已取消。'
    return clean_text(raw, 300)


def truncate_middle(text: str, length: int = 56) -> str:
    text = clean_text(text)
    if len(text) <= length:
        return text
    head = max(1, length // 2 - 1)
    tail = max(1, length - head - 1)
    return text[:head] + '…' + text[-tail:]


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f'{path.stem} ({index}){path.suffix}')
        if not candidate.exists():
            return candidate
    return path


def open_url(url: str) -> None:
    import webbrowser
    webbrowser.open(url, new=2)


def iter_chunks(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    chunk: list[Any] = []
    for item in items:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
