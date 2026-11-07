"""数据模型。"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .utils import detect_site, human_bytes, human_duration, human_eta, human_speed


STATUS_LABELS = {
    'queued': '排队中',
    'parsing': '解析中',
    'downloading': '下载中',
    'processing': '处理中',
    'completed': '已完成',
    'error': '失败',
    'paused': '已暂停',
    'cancelled': '已取消',
}

ACTIVE_STATUSES = {'parsing', 'downloading', 'processing'}
FINISHED_STATUSES = {'completed', 'error', 'cancelled'}


@dataclass
class FormatInfo:
    format_id: str
    ext: str = ''
    width: int = 0
    height: int = 0
    fps: float = 0
    vcodec: str = ''
    acodec: str = ''
    tbr: float = 0
    abr: float = 0
    filesize: int = 0
    protocol: str = ''
    note: str = ''
    lang: str = ''
    is_audio: bool = False
    is_video: bool = False

    @property
    def resolution(self) -> str:
        if self.is_audio and not self.is_video:
            return '仅音频'
        if self.height:
            suffix = 'P'
            return f'{self.height}{suffix}'
        if self.width:
            return f'{self.width}px'
        return '未知'

    @property
    def codec_short(self) -> str:
        parts = []
        if self.vcodec and self.vcodec != 'none':
            parts.append(self.vcodec.split('.')[0].upper())
        if self.acodec and self.acodec != 'none':
            parts.append(self.acodec.split('.')[0].upper())
        return ' + '.join(parts) or '—'

    @property
    def size_text(self) -> str:
        return human_bytes(self.filesize) if self.filesize else '—'

    @property
    def kind_text(self) -> str:
        if self.is_audio and not self.is_video:
            return '音频'
        return '视频'


@dataclass
class EntryInfo:
    index: int
    id: str = ''
    title: str = ''
    url: str = ''
    duration: float = 0
    uploader: str = ''
    thumbnail: str = ''


@dataclass
class MediaInfo:
    url: str
    kind: str = 'video'
    id: str = ''
    title: str = ''
    description: str = ''
    uploader: str = ''
    uploader_id: str = ''
    thumbnail: str = ''
    duration: float = 0
    extractor: str = ''
    webpage_url: str = ''
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    upload_date: str = ''
    formats: list[FormatInfo] = field(default_factory=list)
    entries: list[EntryInfo] = field(default_factory=list)
    subtitles: dict[str, Any] = field(default_factory=dict)
    is_live: bool = False
    playlist_count: int = 0

    @property
    def site(self) -> tuple[str, str]:
        return detect_site(self.webpage_url or self.url)

    @property
    def duration_text(self) -> str:
        return human_duration(self.duration)

    @property
    def best_thumbnail(self) -> str:
        return self.thumbnail or (self.entries[0].thumbnail if self.entries else '')


@dataclass
class DownloadTask:
    url: str
    mode: str = 'video'
    quality: str = 'best'
    custom_format: str = ''
    playlist: bool = False
    playlist_limit: int = 0
    title: str = ''
    uploader: str = ''
    site: str = ''
    site_color: str = '#8B93A7'
    duration: float = 0
    thumbnail: str = ''
    status: str = 'queued'
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: int | None = None
    filepath: str = ''
    filename: str = ''
    error: str = ''
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created_at: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    started_at: str = ''
    finished_at: str = ''
    playlist_index: int = 0
    playlist_count: int = 0
    selected_format: str = ''
    retries: int = 0
    pause_requested: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.site or self.site == '其他':
            label, color = detect_site(self.url)
            self.site = label
            self.site_color = color

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def display_title(self) -> str:
        return self.title or self.url

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def is_finished(self) -> bool:
        return self.status in FINISHED_STATUSES

    @property
    def progress_text(self) -> str:
        if self.status == 'completed':
            return '100%'
        if self.status in {'error', 'cancelled', 'paused', 'queued'} and not self.progress:
            return '—'
        return f'{max(0.0, min(100.0, self.progress)):.1f}%'

    @property
    def speed_text(self) -> str:
        if self.status == 'completed':
            return human_bytes(self.total_bytes) if self.total_bytes else '完成'
        if self.status == 'processing':
            return '正在合并 / 转码'
        if self.status == 'downloading':
            parts = [human_speed(self.speed)]
            if self.eta:
                parts.append(f'剩余 {human_eta(self.eta)}')
            return ' · '.join(parts)
        if self.status == 'parsing':
            return '正在获取视频信息'
        if self.status == 'queued':
            return '等待下载'
        if self.status == 'paused':
            return f'已暂停 · {human_bytes(self.downloaded_bytes)}'
        if self.status == 'error':
            return self.error or '下载失败'
        return ''

    @property
    def meta_text(self) -> str:
        parts = [self.site or '视频']
        if self.uploader:
            parts.append(self.uploader)
        if self.duration:
            parts.append(human_duration(self.duration))
        if self.playlist_count:
            parts.append(f'合集 {self.playlist_count} 项')
        return '  ·  '.join(parts)

    def apply_info(self, info: dict[str, Any]) -> None:
        """从 yt-dlp 的 info_dict 同步展示信息。"""
        if info.get('title') and not self.title:
            self.title = str(info['title'])
        uploader = info.get('uploader') or info.get('creator') or info.get('channel')
        if uploader and not self.uploader:
            self.uploader = str(uploader)
        if info.get('duration') and not self.duration:
            try:
                self.duration = float(info['duration'])
            except (TypeError, ValueError):
                pass
        if info.get('thumbnail') and not self.thumbnail:
            self.thumbnail = str(info['thumbnail'])
        if info.get('extractor') and (not self.site or self.site == '其他'):
            self.site = str(info['extractor'])
        self.selected_format = self.custom_format or self.selected_format

    def mark(self, status: str, error: str = '') -> None:
        self.status = status
        self.error = error
        if status == 'completed':
            self.finished_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.progress = 100.0
            self.eta = None
            self.speed = 0
        elif status in {'error', 'cancelled'}:
            self.finished_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.speed = 0
            self.eta = None

    def to_history(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title or self.url,
            'site': self.site,
            'site_color': self.site_color,
            'uploader': self.uploader,
            'duration': self.duration,
            'filepath': self.filepath,
            'thumbnail': self.thumbnail,
            'status': self.status,
            'created_at': self.created_at,
            'finished_at': self.finished_at,
            'mode': self.mode,
            'quality': self.quality,
            'custom_format': self.custom_format,
            'playlist': self.playlist,
            'size': self.total_bytes,
        }
