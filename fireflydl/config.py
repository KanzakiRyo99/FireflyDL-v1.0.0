"""应用设置。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .paths import CONFIG_FILE, default_download_dir
from .utils import atomic_write_json, read_json


COOKIE_BROWSERS = {
    '': '不使用浏览器 Cookie',
    'chrome': 'Chrome',
    'edge': 'Edge',
    'firefox': 'Firefox',
    'brave': 'Brave',
    'chromium': 'Chromium',
    'opera': 'Opera',
    'vivaldi': 'Vivaldi',
    'safari': 'Safari',
}

QUALITY_CHOICES = {
    'best': '最佳画质',
    '2160': '4K / 2160P',
    '1440': '2K / 1440P',
    '1080': '1080P',
    '720': '720P',
    '480': '480P',
    '360': '360P',
}

MODE_CHOICES = {
    'video': '视频 + 音频',
    'audio': '仅音频（MP3）',
}


@dataclass
class Settings:
    download_dir: str = field(default_factory=lambda: str(default_download_dir()))
    concurrency: int = 2
    default_mode: str = 'video'
    default_quality: str = 'best'
    filename_template: str = '%(title).120B [%(id)s].%(ext)s'
    proxy: str = ''
    cookies_from_browser: str = ''
    cookies_file: str = ''
    ffmpeg_path: str = ''
    rate_limit_mb: float = 0
    write_subs: bool = True
    embed_subs: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    playlist: bool = False
    playlist_limit: int = 0
    clipboard_watch: bool = False
    open_folder_when_done: bool = False
    skip_existing: bool = True
    use_archive: bool = False
    subtitle_langs: str = 'zh-Hans,zh-CN,zh-TW,zh,en'
    last_parse_url: str = ''
    window_geometry: str = ''
    sidebar_collapsed: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> 'Settings':
        raw = read_json(path or CONFIG_FILE, {})
        if not isinstance(raw, dict):
            raw = {}
        valid = {f.name for f in fields(cls)}
        values = {key: value for key, value in raw.items() if key in valid}
        settings = cls(**values)
        return settings.normalized()

    def normalized(self) -> 'Settings':
        if not self.download_dir:
            self.download_dir = str(default_download_dir())
        self.download_dir = str(Path(self.download_dir).expanduser())
        try:
            self.concurrency = max(1, min(6, int(self.concurrency)))
        except (TypeError, ValueError):
            self.concurrency = 2
        if self.default_mode not in MODE_CHOICES:
            self.default_mode = 'video'
        if self.default_quality not in QUALITY_CHOICES:
            self.default_quality = 'best'
        if not self.filename_template or '%(ext)s' not in self.filename_template:
            self.filename_template = '%(title).120B [%(id)s].%(ext)s'
        if self.cookies_from_browser not in COOKIE_BROWSERS:
            self.cookies_from_browser = ''
        try:
            self.rate_limit_mb = max(0.0, float(self.rate_limit_mb or 0))
        except (TypeError, ValueError):
            self.rate_limit_mb = 0.0
        try:
            self.playlist_limit = max(0, int(self.playlist_limit or 0))
        except (TypeError, ValueError):
            self.playlist_limit = 0
        self.proxy = (self.proxy or '').strip()
        self.cookies_file = (self.cookies_file or '').strip()
        self.ffmpeg_path = (self.ffmpeg_path or '').strip()
        self.subtitle_langs = (self.subtitle_langs or 'zh-Hans,zh,en').strip()
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def save(self, path: Path | None = None) -> None:
        self.normalized()
        atomic_write_json(path or CONFIG_FILE, self.to_dict())

    @property
    def download_path(self) -> Path:
        return Path(self.download_dir).expanduser()

    @property
    def concurrency_value(self) -> int:
        return max(1, min(6, int(self.concurrency)))

    @property
    def rate_limit_bytes(self) -> int:
        return int(self.rate_limit_mb * 1024 * 1024) if self.rate_limit_mb > 0 else 0
