"""yt-dlp 封装：页面解析、格式整理与下载执行。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import ensure_plugin_path

ensure_plugin_path()

try:
    import yt_dlp
    from yt_dlp.utils import DownloadCancelled, DownloadError
    YTDLP_AVAILABLE = True
    YTDLP_IMPORT_ERROR = ''
except Exception as exc:  # pragma: no cover - 依赖缺失时给出友好提示
    yt_dlp = None  # type: ignore[assignment]
    DownloadCancelled = Exception  # type: ignore[assignment,misc]
    DownloadError = Exception  # type: ignore[assignment,misc]
    YTDLP_AVAILABLE = False
    YTDLP_IMPORT_ERROR = str(exc)

from .config import Settings
from .models import DownloadTask, EntryInfo, FormatInfo, MediaInfo
from .paths import ARCHIVE_FILE, DATA_DIR
from .utils import clean_text, find_ffmpeg, friendly_error


EventCallback = Callable[[str, DownloadTask], None]
LogCallback = Callable[[str], None]


@dataclass
class DownloadResult:
    success: bool
    filepath: str = ''
    error: str = ''
    cancelled: bool = False
    paused: bool = False


class YdlLogger:
    """把 yt-dlp 日志转给 GUI 日志页，同时收集错误用于提示。"""

    def __init__(self, sink: LogCallback | None = None):
        self.sink = sink
        self.messages: list[str] = []

    def _write(self, level: str, message: Any) -> None:
        text = clean_text(message)
        if not text or text.startswith('[debug]'):
            return
        if 'Deprecated Feature: Support for Python version' in text:
            return
        line = f'[{level}] {text}'
        self.messages.append(line)
        if len(self.messages) > 200:
            del self.messages[:100]
        if self.sink:
            self.sink(line)

    def debug(self, message: Any) -> None:
        text = clean_text(message)
        if text.startswith('[debug] '):
            text = text[8:]
        self._write('调试', text)

    def info(self, message: Any) -> None:
        self._write('信息', message)

    def warning(self, message: Any) -> None:
        self._write('警告', message)

    def error(self, message: Any) -> None:
        self._write('错误', message)


def available() -> bool:
    return YTDLP_AVAILABLE


def version() -> str:
    if not YTDLP_AVAILABLE:
        return '未安装'
    try:
        from yt_dlp.version import __version__
        return __version__
    except Exception:
        return '未知'


def format_selector(mode: str, quality: str, custom_format: str = '') -> str:
    custom = (custom_format or '').strip()
    if custom:
        return custom
    if mode == 'audio':
        return 'bestaudio/best'
    if quality and str(quality).isdigit():
        height = int(quality)
        return (
            f'bestvideo[height<={height}]+bestaudio/'
            f'best[height<={height}]/'
            f'bestvideo[height<={height}]+bestaudio/best'
        )
    return 'bestvideo*+bestaudio/best'


def _cookie_options(settings: Settings) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if settings.cookies_file:
        cookie_path = Path(settings.cookies_file).expanduser()
        if cookie_path.is_file():
            options['cookiefile'] = str(cookie_path)
    elif settings.cookies_from_browser:
        options['cookiesfrombrowser'] = (settings.cookies_from_browser,)
    return options


def _ffmpeg_options(settings: Settings) -> dict[str, Any]:
    ffmpeg = find_ffmpeg(settings.ffmpeg_path)
    # yt-dlp 需要同目录下的 ffprobe，指向目录比只指向 ffmpeg.exe 更稳妥。
    return {'ffmpeg_location': str(Path(ffmpeg).parent)} if ffmpeg else {}


def _postprocessors(settings: Settings, mode: str, ffmpeg: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """返回 (postprocessors, 额外 ydl 选项)。"""
    extra: dict[str, Any] = {}
    processors: list[dict[str, Any]] = []
    if not ffmpeg:
        return processors, extra

    if mode == 'audio':
        processors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        })

    if settings.embed_metadata:
        processors.append({'key': 'FFmpegMetadata', 'add_metadata': True})
    if settings.embed_thumbnail:
        processors.append({'key': 'EmbedThumbnail'})
        extra['writethumbnail'] = True
    if settings.write_subs:
        extra['writesubtitles'] = True
        extra['writeautomaticsub'] = True
        extra['subtitleslangs'] = [x.strip() for x in settings.subtitle_langs.split(',') if x.strip()]
        extra['subtitlesformat'] = 'srt/best'
        if settings.embed_subs:
            processors.append({'key': 'FFmpegEmbedSubtitle'})
    return processors, extra


def base_options(
    settings: Settings,
    *,
    selector: str = 'bestvideo*+bestaudio/best',
    mode: str = 'video',
    output_dir: str | Path | None = None,
    playlist: bool = False,
    playlist_limit: int = 0,
    logger: YdlLogger | None = None,
    probe: bool = False,
    flat: bool = False,
) -> dict[str, Any]:
    ffmpeg = find_ffmpeg(settings.ffmpeg_path)
    processors, extra = _postprocessors(settings, mode, ffmpeg)
    outdir = Path(output_dir or settings.download_path).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    options: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'no_color': True,
        'logger': logger or YdlLogger(),
        'noplaylist': not playlist,
        'playlistend': playlist_limit if (playlist and playlist_limit > 0) else None,
        'outtmpl': str(outdir / settings.filename_template),
        'format': selector,
        'merge_output_format': 'mp4',
        'windowsfilenames': True,
        'trim_file_name': 180,
        'overwrites': not settings.skip_existing,
        'continuedl': True,
        'retries': 8,
        'fragment_retries': 8,
        'extractor_retries': 3,
        'file_access_retries': 3,
        'socket_timeout': 30,
        'concurrent_fragment_downloads': 4,
        'buffersize': 1024 * 1024,
        'progress_delta': 0.2,
        'cachedir': str(DATA_DIR / 'cache'),
        'simulate': bool(probe),
        **extra,
    }
    if processors:
        options['postprocessors'] = processors
    if options.get('playlistend') is None:
        options.pop('playlistend', None)

    ffmpeg_tools = _ffmpeg_options(settings)
    if ffmpeg_tools:
        options.update(ffmpeg_tools)
    if settings.proxy:
        options['proxy'] = settings.proxy
    if settings.rate_limit_bytes:
        options['ratelimit'] = settings.rate_limit_bytes
    if settings.use_archive:
        options['download_archive'] = str(ARCHIVE_FILE)
    options.update(_cookie_options(settings))
    if flat:
        options['extract_flat'] = 'in_playlist'
        options['playlistend'] = 200
    return options


def _format_info(fmt: dict[str, Any]) -> FormatInfo | None:
    format_id = fmt.get('format_id')
    if format_id is None:
        return None
    protocol = str(fmt.get('protocol') or '')
    if protocol in {'mhtml', 'data'}:
        return None
    vcodec = str(fmt.get('vcodec') or '')
    acodec = str(fmt.get('acodec') or '')
    if vcodec == 'none' and acodec == 'none':
        return None
    is_video = bool(vcodec and vcodec != 'none')
    is_audio = bool(acodec and acodec != 'none') and not is_video
    filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
    try:
        filesize = int(filesize or 0)
    except (TypeError, ValueError):
        filesize = 0
    return FormatInfo(
        format_id=str(format_id),
        ext=str(fmt.get('ext') or ''),
        width=int(fmt.get('width') or 0),
        height=int(fmt.get('height') or 0),
        fps=float(fmt.get('fps') or 0),
        vcodec=vcodec,
        acodec=acodec,
        tbr=float(fmt.get('tbr') or 0),
        abr=float(fmt.get('abr') or 0),
        filesize=filesize,
        protocol=protocol,
        note=str(fmt.get('format_note') or fmt.get('format') or ''),
        lang=str(fmt.get('language') or ''),
        is_audio=is_audio,
        is_video=is_video,
    )


def _sort_formats(formats: list[FormatInfo]) -> list[FormatInfo]:
    def key(fmt: FormatInfo):
        return (
            0 if fmt.is_video else 1,
            -(fmt.height or 0),
            -(fmt.fps or 0),
            -(fmt.tbr or 0),
            fmt.format_id,
        )
    return sorted(formats, key=key)


def _parse_formats(info: dict[str, Any]) -> list[FormatInfo]:
    raw_formats = info.get('formats') or []
    result: list[FormatInfo] = []
    seen: set[str] = set()
    for fmt in raw_formats:
        if not isinstance(fmt, dict):
            continue
        parsed = _format_info(fmt)
        if not parsed:
            continue
        key = f'{parsed.format_id}|{parsed.height}|{parsed.ext}'
        if key in seen:
            continue
        seen.add(key)
        result.append(parsed)
    if not result and info.get('url'):
        fallback = _format_info({
            'format_id': info.get('format_id') or 'source',
            'url': info.get('url'),
            'ext': info.get('ext'),
            'width': info.get('width'),
            'height': info.get('height'),
            'fps': info.get('fps'),
            'vcodec': info.get('vcodec'),
            'acodec': info.get('acodec'),
            'tbr': info.get('tbr'),
            'filesize': info.get('filesize') or info.get('filesize_approx'),
            'protocol': info.get('protocol'),
            'format_note': info.get('format_note'),
        })
        if fallback:
            result.append(fallback)
    return _sort_formats(result)


def _entry_info(entry: dict[str, Any], index: int) -> EntryInfo:
    url = entry.get('webpage_url') or entry.get('url') or ''
    return EntryInfo(
        index=index,
        id=str(entry.get('id') or ''),
        title=str(entry.get('title') or f'第 {index} 个视频'),
        url=str(url),
        duration=float(entry.get('duration') or 0),
        uploader=str(entry.get('uploader') or entry.get('channel') or ''),
        thumbnail=str(entry.get('thumbnail') or ''),
    )


def media_from_info(info: dict[str, Any], fallback_url: str) -> MediaInfo:
    is_playlist = info.get('_type') == 'playlist' or (
        isinstance(info.get('entries'), (list, tuple)) and not info.get('formats')
    )
    entries_raw = info.get('entries') or []
    entries: list[EntryInfo] = []
    if is_playlist:
        for index, entry in enumerate(entries_raw, 1):
            if not isinstance(entry, dict):
                continue
            entries.append(_entry_info(entry, index))
            if len(entries) >= 300:
                break
    playlist_count = info.get('playlist_count') or info.get('n_entries') or len(entries)
    try:
        playlist_count = int(playlist_count or 0)
    except (TypeError, ValueError):
        playlist_count = len(entries)

    thumbnail = str(info.get('thumbnail') or '')
    if not thumbnail and entries:
        thumbnail = entries[0].thumbnail

    subtitles = info.get('subtitles') or {}
    if not isinstance(subtitles, dict):
        subtitles = {}
    automatic = info.get('automatic_captions') or {}
    subtitle_names = sorted(set(subtitles) | (set(automatic) if isinstance(automatic, dict) else set()))

    return MediaInfo(
        url=fallback_url,
        kind='playlist' if is_playlist else 'video',
        id=str(info.get('id') or ''),
        title=str(info.get('title') or '未命名视频'),
        description=str(info.get('description') or ''),
        uploader=str(info.get('uploader') or info.get('creator') or info.get('channel') or ''),
        uploader_id=str(info.get('uploader_id') or info.get('channel_id') or ''),
        thumbnail=thumbnail,
        duration=float(info.get('duration') or 0),
        extractor=str(info.get('extractor') or info.get('extractor_key') or ''),
        webpage_url=str(info.get('webpage_url') or fallback_url),
        view_count=int(info.get('view_count') or 0),
        like_count=int(info.get('like_count') or 0),
        comment_count=int(info.get('comment_count') or 0),
        upload_date=str(info.get('upload_date') or ''),
        formats=_parse_formats(info),
        entries=entries,
        subtitles={name: True for name in subtitle_names},
        is_live=bool(info.get('is_live')),
        playlist_count=playlist_count,
    )


def probe(url: str, settings: Settings, logger_sink: LogCallback | None = None) -> MediaInfo:
    if not YTDLP_AVAILABLE:
        raise RuntimeError('yt-dlp 未安装，请先运行：pip install -U yt-dlp')
    logger = YdlLogger(logger_sink)
    options = base_options(settings, probe=True, playlist=True, flat=True, logger=logger)
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        detail = clean_text(exc)
        raise RuntimeError(friendly_error(detail)) from exc
    if not info:
        raise RuntimeError('没有解析到任何内容，请检查链接是否有效。')
    return media_from_info(info, url)


def _resolve_filepath(
    info: dict[str, Any],
    last_filename: str,
    outdir: Path,
    mode: str,
) -> str:
    if info.get('_type') == 'playlist':
        return str(outdir)

    candidates: list[str] = []
    filepath = info.get('filepath')
    if filepath:
        candidates.append(str(filepath))
    for item in info.get('requested_downloads') or []:
        if isinstance(item, dict):
            path = item.get('filepath') or item.get('_filename')
            if path:
                candidates.append(str(path))
    if last_filename:
        candidates.append(last_filename)
        base = Path(last_filename)
        if mode == 'audio':
            candidates.extend([str(base.with_suffix('.mp3')), str(base.with_suffix('.m4a'))])
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path))
    # 后处理可能改变扩展名，按主文件名在下载目录里找最近的文件。
    stems = {Path(p).stem for p in candidates if p}
    stems = {stem.split('.')[0] for stem in stems if stem}
    if stems:
        for candidate in sorted(outdir.glob('*'), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if not candidate.is_file():
                continue
            if any(candidate.stem == stem or candidate.stem.startswith(stem + '.') for stem in stems):
                return str(candidate)
    # “跳过已存在文件”时 yt-dlp 可能不返回 filepath，用视频 ID 再找一次。
    video_id = str(info.get('id') or '')
    if video_id:
        try:
            matches = [
                path for path in outdir.glob(f'*{video_id}*')
                if path.is_file() and path.suffix.lower() not in {'.part', '.ytdl', '.jpg', '.webp', '.png'}
            ]
            if matches:
                return str(max(matches, key=lambda p: p.stat().st_mtime))
        except OSError:
            pass
    if candidates:
        return candidates[0]
    return ''


def _is_range_error(exc: Any) -> bool:
    text = str(exc).lower()
    return 'http error 416' in text or 'range not satisfiable' in text


def _clean_stale_parts(outdir: Path, current_filename: str, info_id: str) -> list[str]:
    """清理失效的 .part 分片。

    某些 CDN 在分片过期或换源后不再接受原来的 Range 位置，会返回 416；
    此时保留 .part 只会让每次重试都失败。
    """
    targets: set[Path] = set()
    if current_filename:
        base = Path(current_filename)
        targets.add(base.with_name(base.name + '.part'))
        if base.suffix.lower() == '.part':
            targets.add(base)
    for part in Path(outdir).glob('*.part'):
        if info_id and info_id in part.name:
            targets.add(part)
    removed: list[str] = []
    for path in targets:
        try:
            if path.is_file():
                path.unlink()
                removed.append(str(path))
        except OSError:
            pass
    return removed


def run_download(
    task: DownloadTask,
    settings: Settings,
    emit: EventCallback,
    logger_sink: LogCallback | None = None,
) -> DownloadResult:
    if not YTDLP_AVAILABLE:
        return DownloadResult(False, error='yt-dlp 未安装，请先运行：pip install -U yt-dlp')

    selector = format_selector(task.mode, task.quality, task.custom_format)
    logger = YdlLogger(logger_sink)
    options = base_options(
        settings,
        selector=selector,
        mode=task.mode,
        playlist=task.playlist,
        playlist_limit=task.playlist_limit,
        logger=logger,
    )
    outdir = Path(settings.download_path).expanduser()
    last_filename = ''
    current_filename = ''
    current_info_id = ''

    def progress_hook(data: dict[str, Any]) -> None:
        nonlocal last_filename, current_filename, current_info_id
        if task.cancel_event.is_set():
            raise DownloadCancelled()

        info = data.get('info_dict') or {}
        if info:
            task.apply_info(info)
            current_info_id = str(info.get('id') or current_info_id)
            task.playlist_index = int(data.get('playlist_index') or task.playlist_index or 0)
            task.playlist_count = int(data.get('playlist_count') or task.playlist_count or 0)
            emit('meta', task)
        if data.get('filename'):
            current_filename = str(data.get('filename'))

        if data.get('status') == 'downloading':
            downloaded = int(data.get('downloaded_bytes') or 0)
            total = int(data.get('total_bytes') or data.get('total_bytes_estimate') or 0)
            task.downloaded_bytes = downloaded
            if total:
                task.total_bytes = total
            task.speed = float(data.get('speed') or 0)
            task.eta = data.get('eta')
            percent = (downloaded / total * 100) if total else 0.0
            if task.playlist_count > 1 and task.playlist_index:
                percent = ((task.playlist_index - 1) + percent / 100) / task.playlist_count * 100
            task.progress = max(0.0, min(99.5, percent))
            task.status = 'downloading'
            emit('progress', task)
        elif data.get('status') == 'finished':
            last_filename = str(data.get('filename') or last_filename)
            task.status = 'processing'
            task.progress = max(task.progress, 99.0)
            emit('progress', task)
        elif data.get('status') == 'error':
            raise DownloadError(str(data.get('error') or '下载出错'))

    def postprocessor_hook(data: dict[str, Any]) -> None:
        nonlocal last_filename
        if task.cancel_event.is_set():
            raise DownloadCancelled()
        status = data.get('status')
        if status == 'started':
            task.status = 'processing'
            emit('progress', task)
        elif status == 'finished':
            task.status = 'processing'
            if data.get('filepath'):
                last_filename = str(data.get('filepath') or last_filename)
            emit('progress', task)

    options['progress_hooks'] = [progress_hook]
    options['postprocessor_hooks'] = [postprocessor_hook]

    task.mark('parsing')
    task.started_at = time.strftime('%Y-%m-%d %H:%M:%S')
    emit('status', task)

    info = None
    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(task.url, download=True)
            break
        except DownloadCancelled:
            task.mark('paused' if task.pause_requested else 'cancelled')
            emit('status', task)
            return DownloadResult(False, cancelled=not task.pause_requested,
                                  paused=task.pause_requested)
        except Exception as exc:
            if attempt == 0 and _is_range_error(exc):
                removed = _clean_stale_parts(outdir, current_filename, current_info_id)
                logger.warning(
                    '检测到断点分片失效（HTTP 416），已清理失效分片并从头重试。'
                    + (f'（{len(removed)} 个文件）' if removed else '')
                )
                options['continuedl'] = False
                task.downloaded_bytes = 0
                task.total_bytes = 0
                task.progress = 0
                task.error = ''
                task.speed = 0
                task.status = 'downloading'
                emit('status', task)
                current_filename = ''
                last_filename = ''
                continue
            message = friendly_error(exc)
            task.mark('error', message)
            emit('status', task)
            task.speed = 0
            return DownloadResult(False, error=message)
    task.speed = 0

    if not info:
        task.mark('error', '没有获取到下载内容。')
        emit('status', task)
        return DownloadResult(False, error=task.error)

    filepath = _resolve_filepath(info, last_filename, outdir, task.mode)
    task.filepath = filepath
    task.filename = Path(filepath).name if filepath else ''
    if filepath and Path(filepath).is_file():
        try:
            task.total_bytes = Path(filepath).stat().st_size
        except OSError:
            pass
    task.mark('completed')
    emit('status', task)
    return DownloadResult(True, filepath=filepath)


def update_ytdlp_command() -> list[str]:
    import sys
    return [sys.executable, '-m', 'pip', 'install', '-U', 'yt-dlp', '--disable-pip-version-check']
