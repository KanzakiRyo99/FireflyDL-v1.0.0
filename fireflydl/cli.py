"""命令行模式。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import APP_NAME_CN, __version__
from .config import COOKIE_BROWSERS, MODE_CHOICES, QUALITY_CHOICES, Settings
from .history import HistoryStore
from .manager import DownloadManager
from .models import DownloadTask, MediaInfo
from .service import available, probe, update_ytdlp_command, version as ytdlp_version
from .utils import (
    friendly_error, human_bytes, human_count, human_duration, normalize_urls,
    strip_ansi, truncate_middle,
)


def _enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if sys.platform.startswith('win'):
        try:
            os.system('')
        except Exception:
            pass


def banner() -> str:
    return (
        '\n'
        '  ✦  流萤  FireflyDL  v' + __version__ + '\n'
        '     多站点视频下载 · 页面解析 · 命令行与 GUI\n'
        '     ' + '─' * 46 + '\n'
        '     支持 B站 / 抖音 / 快手 / YouTube / TikTok 等 1700+ 站点\n'
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='fireflydl',
        description='流萤 FireflyDL：多站点视频下载与页面解析（B站/抖音/快手/YouTube 等）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            '示例：\n'
            '  python cli.py "https://www.bilibili.com/video/BV1xx411c7mD" -q 1080\n'
            '  python cli.py URL1 URL2 --audio -o D:\\Videos\n'
            '  python cli.py URL --info\n'
            '  python cli.py URL --formats --json\n'
            '  python cli.py URL --cookies-from-browser edge\n'
            '  python cli.py --gui\n'
        ),
    )
    parser.add_argument('urls', nargs='*', help='视频链接、分享文案或 BV 号；可一次传多个。')
    parser.add_argument('--gui', action='store_true', help='启动图形界面。')
    parser.add_argument('--interactive', '-i', action='store_true', help='进入交互式下载模式。')
    parser.add_argument('--info', action='store_true', help='只解析并显示视频信息与格式，不下载。')
    parser.add_argument('--formats', action='store_true', help='显示全部可用格式（等同 --info）。')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出解析结果（不下载）。')
    parser.add_argument('-a', '--audio', action='store_true', help='仅下载音频（MP3）。')
    parser.add_argument('-q', '--quality', choices=list(QUALITY_CHOICES),
                        help='画质：best/2160/1440/1080/720/480/360，默认读取设置。')
    parser.add_argument('-f', '--format', dest='format_id', default='',
                        help='自定义 yt-dlp format selector，例如 137+140。')
    parser.add_argument('-o', '--output', help='下载目录。')
    parser.add_argument('--filename', help='文件命名模板，必须包含 %%(ext)s。')
    parser.add_argument('--playlist', action=argparse.BooleanOptionalAction, default=None,
                        help='是否下载整个合集/播放列表（默认读取设置）。')
    parser.add_argument('--playlist-limit', type=int, default=None, help='合集最多下载 N 个。')
    parser.add_argument('--cookies-from-browser', choices=[k for k in COOKIE_BROWSERS if k],
                        help='从浏览器读取 Cookie，例如 chrome / edge / firefox。')
    parser.add_argument('--cookies', help='Netscape 格式 cookies.txt 路径。')
    parser.add_argument('--proxy', help='代理，例如 http://127.0.0.1:7890。')
    parser.add_argument('--concurrency', type=int, default=1, help='同时下载数量（默认 1）。')
    parser.add_argument('--subs', action=argparse.BooleanOptionalAction, default=None,
                        help='是否下载字幕。')
    parser.add_argument('--thumbnail', action=argparse.BooleanOptionalAction, default=None,
                        help='是否嵌入封面。')
    parser.add_argument('--metadata', action=argparse.BooleanOptionalAction, default=None,
                        help='是否写入元数据。')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示 yt-dlp 日志。')
    parser.add_argument('--quiet', action='store_true', help='不显示实时进度。')
    parser.add_argument('--list-sites', action='store_true', help='列出部分支持站点。')
    parser.add_argument('--update', action='store_true', help='更新 yt-dlp 内核。')
    parser.add_argument('--version', action='store_true', help='显示版本。')
    return parser


def _print_info(media: MediaInfo) -> None:
    print()
    print('═' * 76)
    print(f'标题    {media.title}')
    print(f'站点    {media.site[0]}  ·  {media.extractor or "—"}')
    print(f'作者    {media.uploader or "—"}')
    print(f'时长    {human_duration(media.duration)}')
    if media.upload_date:
        print(f'日期    {media.upload_date}')
    if media.view_count or media.like_count:
        print(f'数据    播放 {human_count(media.view_count)}  ·  点赞 {human_count(media.like_count)}')
    print(f'链接    {media.webpage_url or media.url}')
    if media.description:
        print(f'简介    {truncate_middle(media.description, 100)}')
    if media.kind == 'playlist':
        print(f'类型    合集 / 播放列表，共 {media.playlist_count or len(media.entries)} 项')
        print('─' * 76)
        print(f'{"#":>4}  {"时长":<8}  {"标题":<50}  作者')
        for entry in media.entries:
            print(f'{entry.index:>4}  {human_duration(entry.duration):<8}  '
                  f'{truncate_middle(entry.title, 50):<50}  {entry.uploader or "—"}')
        print('═' * 76)
        return
    print(f'类型    {"直播" if media.is_live else "视频"}  ·  共 {len(media.formats)} 个格式')
    print('─' * 76)
    print(f'{"格式ID":<22} {"类型":<5} {"分辨率":<10} {"编码":<20} {"大小":>10}  {"协议":<8} 说明')
    for fmt in media.formats:
        print(
            f'{truncate_middle(fmt.format_id, 22):<22} {fmt.kind_text:<5} '
            f'{fmt.resolution:<10} {truncate_middle(fmt.codec_short, 20):<20} '
            f'{fmt.size_text:>10}  {fmt.protocol[:8]:<8} {truncate_middle(fmt.note, 28)}'
        )
    print('═' * 76)


def _json_info(media: MediaInfo) -> dict[str, Any]:
    data = asdict(media)
    data['site'] = media.site[0]
    return data


def _terminal_emit_factory(quiet: bool, verbose: bool):
    lock = __import__('threading').Lock()
    last_line = {'value': ''}

    def emit(kind: str, task: DownloadTask | None, message: str) -> None:
        if task is None:
            return
        with lock:
            if kind == 'log':
                if verbose:
                    sys.stdout.write('\r' + ' ' * 110 + '\r')
                    print(strip_ansi(message), flush=True)
                return
            if kind == 'added':
                print(f'  + 已加入：{task.site} · {task.url}', flush=True)
                return
            if kind == 'completed':
                if last_line['value']:
                    sys.stdout.write('\r' + ' ' * min(110, len(last_line['value'])) + '\r')
                    last_line['value'] = ''
                print(f'  ✓ 完成：{task.display_title}', flush=True)
                if task.filepath:
                    print(f'    {task.filepath}', flush=True)
                return
            if kind == 'failed':
                if last_line['value']:
                    sys.stdout.write('\r' + ' ' * min(110, len(last_line['value'])) + '\r')
                    last_line['value'] = ''
                print(f'  ✗ 失败：{task.display_title}\n    {task.error}', flush=True)
                return
            if kind in {'paused', 'cancelled'}:
                print(f'  · {task.status_label}：{task.display_title}', flush=True)
                return
            if kind == 'progress' and not quiet and task.status == 'downloading':
                if not sys.stdout.isatty():
                    return
                title = truncate_middle(task.display_title, 30)
                line = (f'  ↓ {task.progress:5.1f}%  {task.speed_text}  '
                        f'{human_bytes(task.downloaded_bytes)}  {title}')
                padding = ' ' * max(0, len(last_line['value']) - len(line))
                sys.stdout.write('\r' + line + padding)
                sys.stdout.flush()
                last_line['value'] = line
                return
            if kind == 'status' and task.status == 'processing' and not quiet:
                if sys.stdout.isatty():
                    sys.stdout.write('\r' + ' ' * min(110, len(last_line['value'])) + '\r')
                    print(f'  ⚙ 处理中：{truncate_middle(task.display_title, 46)}', flush=True)
                return

    return emit


def _apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    if args.output:
        settings.download_dir = os.path.abspath(os.path.expanduser(args.output))
    if args.filename:
        if '%(ext)s' not in args.filename:
            raise SystemExit('错误：--filename 必须包含 %(ext)s')
        settings.filename_template = args.filename
    if args.quality:
        settings.default_quality = args.quality
    if args.audio:
        settings.default_mode = 'audio'
    if args.cookies_from_browser:
        settings.cookies_from_browser = args.cookies_from_browser
        settings.cookies_file = ''
    if args.cookies:
        path = Path(args.cookies).expanduser()
        if not path.is_file():
            raise SystemExit(f'错误：Cookie 文件不存在：{path}')
        settings.cookies_file = str(path)
        settings.cookies_from_browser = ''
    if args.proxy:
        settings.proxy = args.proxy
    if args.playlist is not None:
        settings.playlist = args.playlist
    if args.playlist_limit is not None:
        settings.playlist_limit = max(0, args.playlist_limit)
    if args.subs is not None:
        settings.write_subs = args.subs
    if args.thumbnail is not None:
        settings.embed_thumbnail = args.thumbnail
    if args.metadata is not None:
        settings.embed_metadata = args.metadata
    settings.concurrency = max(1, min(6, args.concurrency or 1))
    return settings.normalized()


def _download_urls(urls: list[str], settings: Settings, args: argparse.Namespace) -> int:
    history = HistoryStore()
    emit = _terminal_emit_factory(args.quiet, args.verbose)
    manager = DownloadManager(lambda: settings, emit, history)
    tasks = manager.add_urls(
        '\n'.join(urls),
        mode=settings.default_mode,
        quality=settings.default_quality,
        custom_format=args.format_id,
        playlist=settings.playlist,
        playlist_limit=settings.playlist_limit,
    )
    if not tasks:
        print('错误：没有识别到有效链接。', file=sys.stderr)
        return 1
    try:
        while True:
            all_tasks = manager.tasks()
            if all(task.is_finished for task in all_tasks):
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('\n正在取消任务…', file=sys.stderr)
        manager.shutdown()
        return 130
    manager.shutdown()
    failed = [task for task in manager.tasks() if task.status == 'error']
    if failed:
        print(f'\n完成：{len(tasks) - len(failed)} 成功，{len(failed)} 失败。')
        return 1
    print(f'\n全部完成：{len(tasks)} 个任务。')
    return 0


def _interactive(settings: Settings, args: argparse.Namespace) -> int:
    print(banner())
    print('  交互模式：直接粘贴链接回车下载；输入 :q 退出。')
    print('  命令：:audio  :video  :quality 1080  :dir PATH  :info URL')
    print()
    while True:
        try:
            text = input('firefly> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        lower = text.lower()
        if lower in {':q', ':quit', 'exit', 'quit'}:
            return 0
        if lower in {':h', ':help', 'help'}:
            print('  :audio / :video       切换下载模式')
            print('  :quality 1080         设置画质（best/2160/1440/1080/720/480/360）')
            print('  :dir PATH             设置下载目录')
            print('  :info URL             只解析')
            print('  :q                    退出')
            continue
        if lower == ':audio':
            settings.default_mode = 'audio'
            print('  已切换为仅音频（MP3）。')
            continue
        if lower == ':video':
            settings.default_mode = 'video'
            print('  已切换为视频 + 音频。')
            continue
        if lower.startswith(':quality '):
            value = text.split(None, 1)[1].strip()
            if value in QUALITY_CHOICES:
                settings.default_quality = value
                print(f'  画质已设置为 {QUALITY_CHOICES[value]}。')
            else:
                print('  可选：' + ', '.join(QUALITY_CHOICES))
            continue
        if lower.startswith(':dir '):
            path = Path(text.split(None, 1)[1].strip().strip('"')).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            settings.download_dir = str(path)
            print(f'  下载目录：{path}')
            continue
        if lower.startswith(':info '):
            url = normalize_urls(text.split(None, 1)[1])
            if url:
                try:
                    _print_info(probe(url[0], settings, print))
                except Exception as exc:
                    print(f'  解析失败：{friendly_error(exc)}')
            continue
        urls = normalize_urls(text)
        if not urls:
            print('  没有识别到有效链接。')
            continue
        try:
            _download_urls(urls, settings, args)
        except Exception as exc:
            print(f'  下载失败：{friendly_error(exc)}')


def main(argv: list[str] | None = None) -> int:
    _enable_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        try:
            from .gui.app import FireflyApp
            FireflyApp().run()
            return 0
        except Exception as exc:
            print(f'无法启动图形界面：{exc}', file=sys.stderr)
            return 1
    if args.version:
        print(f'{APP_NAME_CN} FireflyDL v{__version__}')
        print(f'yt-dlp {ytdlp_version() if available() else "未安装"}')
        print(f'Python {sys.version.split()[0]}')
        return 0
    if args.list_sites:
        print(banner())
        print('  B站 / 抖音 / 快手 / YouTube / TikTok / 微博 / 小红书 / X /\n'
              '  Instagram / Facebook / Vimeo / Twitch / AcFun / 爱奇艺 /\n'
              '  腾讯视频 / 优酷 / 芒果TV / 豆瓣 / 知乎 等 1700+ 站点')
        return 0
    if args.update:
        print('正在更新 yt-dlp…')
        result = subprocess.run(update_ytdlp_command())
        return result.returncode

    if not available():
        print('错误：yt-dlp 未安装。请运行：pip install -U yt-dlp mutagen', file=sys.stderr)
        return 1

    settings = _apply_overrides(Settings.load(), args)
    urls = normalize_urls('\n'.join(args.urls))

    if not urls:
        if args.interactive or sys.stdin.isatty():
            return _interactive(settings, args)
        print(banner())
        print('  没有提供链接。运行 python cli.py --help 查看参数。')
        return 2

    if args.json or args.info or args.formats:
        results: list[dict[str, Any]] = []
        failed = 0
        for url in urls:
            try:
                media = probe(url, settings, lambda msg: print(msg) if args.verbose else None)
            except Exception as exc:
                failed += 1
                print(f'解析失败：{url}\n  {friendly_error(exc)}', file=sys.stderr)
                continue
            if args.json:
                results.append(_json_info(media))
            else:
                _print_info(media)
        if args.json:
            print(json.dumps(results if len(results) != 1 else results[0],
                             ensure_ascii=False, indent=2))
        return 1 if failed else 0

    print(banner())
    print(f'  下载目录：{settings.download_path}')
    print(f'  画质：{QUALITY_CHOICES.get(settings.default_quality, settings.default_quality)}  ·  '
          f'模式：{MODE_CHOICES.get(settings.default_mode, settings.default_mode)}')
    if settings.cookies_from_browser:
        print(f'  Cookie：浏览器 {settings.cookies_from_browser}')
    elif settings.cookies_file:
        print(f'  Cookie：{settings.cookies_file}')
    if settings.proxy:
        print(f'  代理：{settings.proxy}')
    print()
    return _download_urls(urls, settings, args)


if __name__ == '__main__':
    raise SystemExit(main())
