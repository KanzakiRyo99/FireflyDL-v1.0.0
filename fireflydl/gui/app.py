"""Tkinter 主应用与页面导航。"""

from __future__ import annotations

import queue
import re
import sys
import threading
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import messagebox
from typing import Callable

from PIL import Image, ImageTk

from .. import APP_NAME, APP_NAME_CN, APP_TAGLINE, __version__
from ..config import Settings
from ..history import HistoryStore
from ..manager import DownloadManager
from ..models import DownloadTask, MediaInfo
from ..paths import resource_path
from ..service import available, version as ytdlp_version
from ..utils import (
    clean_text, find_ffmpeg, ffmpeg_version, normalize_urls, open_path,
)
from .theme import COLORS, apply_theme, font
from .widgets import NavButton, RoundedButton, RoundedFrame, TextButton


def _enable_dpi_awareness() -> None:
    """必须在创建第一个 Tk 窗口之前调用。

    否则 Windows 会把整个窗口当作 96 DPI 的位图再放大，界面和字体都会发虚。
    """
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        # Per-Monitor V2（Windows 10 1703+）；返回 0 表示系统不支持，需要继续降级。
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(-4):
            return
    except Exception:
        pass
    try:
        import ctypes
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_enable_dpi_awareness()


PAGE_META = {
    'download': ('下载中心', '粘贴链接，自动识别站点与可用画质'),
    'parse': ('页面解析', '查看视频信息、清晰度、字幕与合集条目'),
    'history': ('历史记录', '回看并打开已经下载的内容'),
    'settings': ('设置', '下载目录、网络、后处理与工具选项'),
    'logs': ('运行日志', 'yt-dlp 与应用运行时的详细输出'),
    'about': ('关于', '版本信息、能力范围与使用说明'),
}

NAV_ITEMS = [
    ('download', '下载中心', '↓'),
    ('parse', '页面解析', '⌕'),
    ('history', '历史记录', '◷'),
    ('settings', '设置', '⚙'),
    ('logs', '运行日志', '▤'),
    ('about', '关于', 'ⓘ'),
]


def _load_photo(path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
    try:
        image = Image.open(path).convert('RGBA')
        image = image.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


class Toast:
    def __init__(self, root: tk.Misc):
        self.root = root
        self.frame: tk.Frame | None = None
        self._after_id: str | None = None

    def show(self, message: str, kind: str = 'info', title: str = '') -> None:
        self.hide()
        color = {
            'success': COLORS['green'],
            'error': COLORS['red'],
            'warning': COLORS['accent'],
            'info': COLORS['teal'],
        }.get(kind, COLORS['teal'])
        frame = RoundedFrame(
            self.root, bg=COLORS['card'], border=COLORS['border'],
            radius=14, inset=8, surface=COLORS['bg'],
        )
        content = tk.Frame(frame.body, bg=COLORS['card'])
        content.pack(fill='both', expand=True, padx=5, pady=3)
        bar = tk.Frame(content, bg=color, width=4)
        bar.pack(side='left', fill='y')
        body = tk.Frame(content, bg=COLORS['card'])
        body.pack(side='left', fill='both', expand=True, padx=12, pady=5)
        if title:
            tk.Label(body, text=title, bg=COLORS['card'], fg=COLORS['text'],
                     font=font(10, 'bold'), anchor='w').pack(anchor='w')
        tk.Label(body, text=clean_text(message, 320), bg=COLORS['card'],
                 fg=COLORS['text_soft'] if title else COLORS['text'],
                 font=font(9), justify='left', wraplength=380,
                 anchor='w').pack(anchor='w', pady=(2 if title else 0, 0))
        close = tk.Label(body, text='✕', bg=COLORS['card'], fg=COLORS['faint'],
                         font=font(9), cursor='hand2')
        close.place(relx=1.0, x=-2, y=0, anchor='ne')
        close.bind('<Button-1>', lambda _e: self.hide())
        frame.place(relx=1.0, rely=1.0, x=-24, y=-26, anchor='se')
        frame.lift()
        self.frame = frame
        self._after_id = self.root.after(4600, self.hide)

    def hide(self) -> None:
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self.frame is not None:
            try:
                self.frame.destroy()
            except tk.TclError:
                pass
            self.frame = None


class FireflyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self._dpi_scale = max(1.0, self.winfo_fpixels('1i') / 96.0)
        self.withdraw()
        self.title(f'{APP_NAME_CN} · {APP_NAME}')
        self.configure(bg=COLORS['bg'])
        self.minsize(int(1100 * self._dpi_scale), int(720 * self._dpi_scale))
        self.geometry(self._initial_geometry())
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self.settings = Settings.load()
        self.history = HistoryStore()
        self.events: queue.Queue[tuple] = queue.Queue()
        self._probe_callbacks: dict[str, tuple[Callable, Callable]] = {}
        self._last_clipboard = ''
        self._toast = Toast(self)
        self._closing = False
        self._engine_text = ''
        self._ffmpeg_text = ''

        self.style = apply_theme(self)
        self._set_icon()

        self.manager = DownloadManager(lambda: self.settings, self._worker_emit, self.history)

        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, NavButton] = {}
        self._build_shell()
        self._build_pages()
        self._refresh_engine_status()
        self._update_queue_status()
        self.navigate('download')

        if self.settings.window_geometry:
            if self._geometry_valid(self.settings.window_geometry):
                try:
                    self.geometry(self.settings.window_geometry)
                except tk.TclError:
                    pass
        self.after(80, self._poll_events)
        self.after(1100, self._clipboard_tick)
        self.deiconify()
        self.lift()
        self.after(60, self._apply_dark_titlebar)
        self.after(200, lambda: self.focus_force())

    def _initial_geometry(self) -> str:
        width = int(1200 * self._dpi_scale)
        height = int(760 * self._dpi_scale)
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            width = min(width, max(1060, screen_w - 120))
            height = min(height, max(700, screen_h - 130))
        except Exception:
            pass
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2 - 20)
        return f'{width}x{height}+{x}+{y}'

    def _geometry_valid(self, geometry: str) -> bool:
        """迁移旧配置或换显示器时，避免窗口尺寸/位置落在屏幕外。"""
        match = re.match(r'^(\d+)x(\d+)([+-]\d+)([+-]\d+)$', geometry or '')
        if not match:
            return False
        width, height, x, y = (int(value) for value in match.groups())
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        if width < int(1100 * self._dpi_scale) or height < int(720 * self._dpi_scale):
            return False
        if width > screen_w - 60 or height > screen_h - 80:
            return False
        if x < -10 or y < -10 or x + width > screen_w or y + height > screen_h:
            return False
        return True

    def _apply_dark_titlebar(self) -> None:
        """让 Windows 原生标题栏跟随深色主题。"""
        if not sys.platform.startswith('win'):
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            enabled = ctypes.c_int(1)
            # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+)；19 是旧版本。
            for attribute in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled),
                )
                if result == 0:
                    break
            self.update_idletasks()
        except Exception:
            pass

    def _set_icon(self) -> None:
        icon = resource_path('assets', 'firefly.ico')
        try:
            if icon.is_file():
                self.iconbitmap(str(icon))
        except tk.TclError:
            pass
        self._logo_photo = _load_photo(resource_path('assets', 'firefly.png'), (44, 44))
        if self._logo_photo:
            try:
                self.iconphoto(True, self._logo_photo)
            except tk.TclError:
                pass

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg=COLORS['sidebar'], width=234)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=COLORS['sidebar'], height=104)
        brand.pack(fill='x', padx=20, pady=(20, 8))
        brand.pack_propagate(False)
        if self._logo_photo:
            tk.Label(brand, image=self._logo_photo, bg=COLORS['sidebar']).pack(side='left')
        else:
            tk.Label(brand, text='✦', bg=COLORS['sidebar'], fg=COLORS['accent'],
                     font=font(26)).pack(side='left', padx=(4, 8))
        brand_text = tk.Frame(brand, bg=COLORS['sidebar'])
        brand_text.pack(side='left', padx=(11, 0), pady=(4, 0))
        tk.Label(brand_text, text=APP_NAME_CN, bg=COLORS['sidebar'], fg=COLORS['text'],
                 font=font(14, 'bold'), anchor='w').pack(anchor='w')
        tk.Label(brand_text, text='FIREFLYDL', bg=COLORS['sidebar'], fg=COLORS['faint'],
                 font=(font()[0], 8, 'bold'), anchor='w').pack(anchor='w', pady=(2, 0))

        nav = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        nav.pack(fill='x', padx=14, pady=(8, 0))
        for key, label, icon in NAV_ITEMS:
            button = NavButton(nav, key, label, icon, self.navigate)
            button.pack(fill='x', pady=2)
            self.nav_buttons[key] = button

        spacer = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        spacer.pack(fill='both', expand=True)

        status_card = RoundedFrame(
            self.sidebar, bg=COLORS['card'], border=COLORS['border'],
            radius=14, inset=8, surface=COLORS['sidebar'],
        )
        status_card.pack(fill='x', padx=14, pady=(8, 12))
        inner = tk.Frame(status_card.body, bg=COLORS['card'])
        inner.pack(fill='x', padx=13, pady=12)
        tk.Label(inner, text='引擎状态', bg=COLORS['card'], fg=COLORS['muted'],
                 font=font(8, 'bold'), anchor='w').pack(anchor='w')
        self.side_engine = tk.Label(inner, text='● yt-dlp 检测中', bg=COLORS['card'],
                                    fg=COLORS['muted'], font=font(8), anchor='w')
        self.side_engine.pack(anchor='w', pady=(4, 0))
        self.side_ffmpeg = tk.Label(inner, text='● ffmpeg 检测中', bg=COLORS['card'],
                                    fg=COLORS['muted'], font=font(8), anchor='w')
        self.side_ffmpeg.pack(anchor='w', pady=(2, 0))
        self.side_queue = tk.Label(inner, text='队列空闲', bg=COLORS['card'],
                                   fg=COLORS['faint'], font=font(8), anchor='w')
        self.side_queue.pack(anchor='w', pady=(7, 0))

        footer = tk.Frame(self.sidebar, bg=COLORS['sidebar'])
        footer.pack(fill='x', padx=20, pady=(0, 16))
        tk.Label(footer, text=f'v{__version__}  ·  1700+ 站点', bg=COLORS['sidebar'],
                 fg=COLORS['faint'], font=font(8), anchor='w').pack(anchor='w')
        tk.Label(footer, text=APP_TAGLINE, bg=COLORS['sidebar'],
                 fg=COLORS['faint'], font=font(8), anchor='w').pack(anchor='w', pady=(2, 0))

        self.main = tk.Frame(self, bg=COLORS['bg'])
        self.main.pack(side='left', fill='both', expand=True)

        self.header = tk.Frame(self.main, bg=COLORS['bg'], height=74)
        self.header.pack(fill='x', padx=26, pady=(16, 0))
        self.header.pack_propagate(False)
        header_left = tk.Frame(self.header, bg=COLORS['bg'])
        header_left.pack(side='left', fill='both', expand=True)
        self.page_title = tk.Label(header_left, text='下载中心', bg=COLORS['bg'],
                                   fg=COLORS['text'], font=font(19, 'bold'), anchor='w')
        self.page_title.pack(anchor='w')
        self.page_subtitle = tk.Label(header_left, text=PAGE_META['download'][1],
                                      bg=COLORS['bg'], fg=COLORS['muted'],
                                      font=font(9), anchor='w')
        self.page_subtitle.pack(anchor='w', pady=(3, 0))

        header_right = tk.Frame(self.header, bg=COLORS['bg'])
        header_right.pack(side='right')
        engine_box = RoundedFrame(
            header_right, bg=COLORS['card'], border=COLORS['border'],
            radius=12, inset=7, surface=COLORS['bg'],
        )
        engine_box.pack(side='left', padx=(0, 8), pady=10)
        self.engine_label = tk.Label(engine_box.body, text='● yt-dlp', bg=COLORS['card'],
                                     fg=COLORS['green'], font=font(8), padx=5, pady=2)
        self.engine_label.pack()
        ffmpeg_box = RoundedFrame(
            header_right, bg=COLORS['card'], border=COLORS['border'],
            radius=12, inset=7, surface=COLORS['bg'],
        )
        ffmpeg_box.pack(side='left', padx=(0, 10), pady=10)
        self.ffmpeg_label = tk.Label(ffmpeg_box.body, text='● ffmpeg', bg=COLORS['card'],
                                     fg=COLORS['muted'], font=font(8), padx=5, pady=2)
        self.ffmpeg_label.pack()
        RoundedButton(
            header_right, '打开下载目录', self.open_downloads,
            width=116, height=34, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=9, bold=False,
        ).pack(side='left', pady=10)

        tk.Frame(self.main, bg=COLORS['border_soft'], height=1).pack(fill='x', padx=26, pady=(10, 0))
        self.page_host = tk.Frame(self.main, bg=COLORS['bg'])
        self.page_host.pack(fill='both', expand=True, padx=26, pady=(12, 4))
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

        bottom = tk.Frame(self.main, bg=COLORS['bg'], height=26)
        bottom.pack(fill='x', padx=26, pady=(0, 20))
        self.bottom_status = tk.Label(bottom, text='● 就绪', bg=COLORS['bg'],
                                      fg=COLORS['faint'], font=font(8), anchor='w')
        self.bottom_status.pack(side='left')
        TextButton(bottom, '查看日志', lambda: self.navigate('logs'),
                   bg=COLORS['bg'], fg=COLORS['faint'], hover_fg=COLORS['accent'],
                   font_size=8).pack(side='right', padx=(0, 4))

    def _build_pages(self) -> None:
        from .download_page import DownloadPage
        from .parse_page import ParsePage
        from .history_page import HistoryPage
        from .settings_page import SettingsPage
        from .logs_page import LogsPage
        from .about_page import AboutPage

        self.download_page = DownloadPage(self.page_host, self)
        self.parse_page = ParsePage(self.page_host, self)
        self.history_page = HistoryPage(self.page_host, self)
        self.settings_page = SettingsPage(self.page_host, self)
        self.logs_page = LogsPage(self.page_host, self)
        self.about_page = AboutPage(self.page_host, self)
        for key, page in (
            ('download', self.download_page),
            ('parse', self.parse_page),
            ('history', self.history_page),
            ('settings', self.settings_page),
            ('logs', self.logs_page),
            ('about', self.about_page),
        ):
            page.grid(row=0, column=0, sticky='nsew')
            self.pages[key] = page

    # ---------- 导航与状态 ----------
    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if not page:
            return
        for page_key, button in self.nav_buttons.items():
            button.set_active(page_key == key)
        page.tkraise()
        title, subtitle = PAGE_META.get(key, ('', ''))
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)
        if hasattr(page, 'on_show'):
            page.on_show()

    def notify(self, message: str, kind: str = 'info', title: str = '') -> None:
        self._toast.show(message, kind, title)

    def post(self, event: tuple) -> None:
        self.events.put(event)

    def _worker_emit(self, kind: str, task: DownloadTask | None, message: str) -> None:
        self.events.put(('task', kind, task, message))

    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            for _ in range(120):
                event = self.events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        except Exception as exc:
            self.log_line(f'[界面] 事件处理异常：{exc}', 'error')
        self.after(80, self._poll_events)

    def _handle_event(self, event: tuple) -> None:
        if not event:
            return
        if event[0] == 'task':
            _, kind, task, message = event
            if task is not None:
                self.download_page.on_task_event(kind, task)
                self._update_queue_status()
                if kind == 'completed':
                    self.notify(f'已保存：{task.filename or task.display_title}', 'success', '下载完成')
                    self.history_page.reload()
                    if self.settings.open_folder_when_done and task.filepath:
                        open_path(task.filepath, select_file=True)
                elif kind == 'failed':
                    self.notify(task.error or message, 'error', '下载失败')
                elif kind == 'paused':
                    self.notify('任务已暂停，可随时继续。', 'warning')
            if kind == 'log' and message:
                self.log_line(message)
        elif event[0] == 'probe':
            _, token, media, image_bytes, error = event
            callback = self._probe_callbacks.pop(token, None)
            if not callback:
                return
            on_ok, on_err = callback
            if media is not None:
                self._run_callback(on_ok, media, image_bytes)
            else:
                self._run_callback(on_err, error or '解析失败')
        elif event[0] == 'log':
            self.log_line(event[1])

    @staticmethod
    def _run_callback(callback: Callable, *args) -> None:
        try:
            callback(*args)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print('callback error:', exc)

    def log_line(self, message: str, level: str = 'info') -> None:
        try:
            self.logs_page.append(message, level)
        except Exception:
            pass

    def _update_queue_status(self) -> None:
        tasks = self.manager.tasks()
        active = sum(1 for t in tasks if t.is_active)
        queued = sum(1 for t in tasks if t.status == 'queued')
        completed = sum(1 for t in tasks if t.status == 'completed')
        if active:
            text = f'队列 {len(tasks)}  ·  进行中 {active}  ·  等待 {queued}'
            color = COLORS['accent']
        elif queued:
            text = f'队列 {len(tasks)}  ·  等待 {queued}'
            color = COLORS['accent']
        elif completed:
            text = f'队列 {len(tasks)}  ·  已完成 {completed}'
            color = COLORS['green']
        else:
            text = '队列空闲'
            color = COLORS['faint']
        try:
            self.side_queue.configure(text=text, fg=color)
            self.bottom_status.configure(
                text=f'● {text}' if tasks else '● 就绪',
                fg=color if tasks else COLORS['faint'],
            )
        except tk.TclError:
            pass

    def _refresh_engine_status(self) -> None:
        if available():
            text = f'yt-dlp {ytdlp_version()}'
            self.engine_label.configure(text=f'● {text}', fg=COLORS['green'])
            self.side_engine.configure(text=f'● {text}', fg=COLORS['green'])
        else:
            self.engine_label.configure(text='● yt-dlp 未安装', fg=COLORS['red'])
            self.side_engine.configure(text='● yt-dlp 未安装', fg=COLORS['red'])
        ffmpeg = find_ffmpeg(self.settings.ffmpeg_path)
        if ffmpeg:
            version_text = ffmpeg_version(ffmpeg).split('-')[0]
            text = f'ffmpeg {version_text}'
            self.ffmpeg_label.configure(text=f'● {text}', fg=COLORS['teal'])
            self.side_ffmpeg.configure(text=f'● {text}', fg=COLORS['teal'])
        else:
            self.ffmpeg_label.configure(text='● ffmpeg 缺失', fg=COLORS['red'])
            self.side_ffmpeg.configure(text='● ffmpeg 缺失', fg=COLORS['red'])

    def settings_saved(self) -> None:
        self.manager.set_concurrency(self.settings.concurrency)
        self._refresh_engine_status()
        self.download_page.sync_settings()
        self._update_queue_status()
        self.parse_page.sync_settings()
        self.notify('设置已保存。', 'success')

    # ---------- 公共动作 ----------
    def add_urls(self, text: str, *, mode: str | None = None, quality: str | None = None,
                 custom_format: str = '', playlist: bool | None = None,
                 navigate: bool = True) -> list[DownloadTask]:
        if not normalize_urls(text):
            self.notify('没有找到有效链接，请粘贴完整的 http/https 地址。', 'warning')
            return []
        tasks = self.manager.add_urls(
            text,
            mode=mode or self.settings.default_mode,
            quality=quality or self.settings.default_quality,
            custom_format=custom_format,
            playlist=self.settings.playlist if playlist is None else playlist,
            playlist_limit=self.settings.playlist_limit,
        )
        if tasks:
            if navigate:
                self.navigate('download')
            self.notify(f'已加入 {len(tasks)} 个下载任务。', 'success', '任务已添加')
            self._update_queue_status()
        return tasks

    def probe_async(self, url: str, on_ok: Callable, on_error: Callable) -> None:
        token = f'probe-{id(on_ok)}-{len(self._probe_callbacks)}'
        self._probe_callbacks[token] = (on_ok, on_error)

        def worker() -> None:
            try:
                media = self.probe_now(url)
                image_bytes = self.fetch_image_bytes(media.best_thumbnail) if media.best_thumbnail else b''
                self.events.put(('probe', token, media, image_bytes, None))
            except Exception as exc:
                self.events.put(('probe', token, None, None, str(exc)))

        threading.Thread(target=worker, name='fireflydl-probe', daemon=True).start()

    def probe_now(self, url: str) -> MediaInfo:
        from .. import service
        return service.probe(
            url, self.settings,
            lambda message: self.events.put(('log', message)),
        )

    @staticmethod
    def fetch_image_bytes(url: str, limit: int = 8 * 1024 * 1024) -> bytes:
        if url.startswith('//'):
            url = 'https:' + url
        request = urllib.request.Request(url, headers={
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'),
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        })
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    return b''
                return data
        except Exception:
            return b''

    def open_downloads(self) -> None:
        path = self.settings.download_path
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.notify('无法创建下载目录，请到设置中更换路径。', 'error')
            return
        if not open_path(path):
            self.notify(f'无法打开目录：{path}', 'warning')

    def show_error(self, message: str, title: str = '操作失败') -> None:
        self.notify(message, 'error', title)

    # ---------- 剪贴板 ----------
    def _clipboard_tick(self) -> None:
        if self._closing:
            return
        if self.settings.clipboard_watch:
            try:
                text = self.clipboard_get()
            except tk.TclError:
                text = ''
            urls = normalize_urls(text or '')
            if urls:
                url = urls[0]
                if url != self._last_clipboard:
                    self._last_clipboard = url
                    self.download_page.fill_input(url)
                    self.notify('检测到剪贴板链接，已填入下载框。', 'info', '剪贴板监听')
        self.after(1100, self._clipboard_tick)

    # ---------- 关闭 ----------
    def _on_close(self) -> None:
        active = sum(1 for task in self.manager.tasks() if task.is_active)
        if active:
            if not messagebox.askyesno(
                '退出确认',
                f'还有 {active} 个任务正在下载。\n退出会中断下载（已下载的分片会保留），确定退出吗？',
                parent=self,
            ):
                return
        self._closing = True
        try:
            self.settings.window_geometry = self.geometry()
            self.settings.save()
        except Exception:
            pass
        self.manager.shutdown()
        self.destroy()

    def run(self) -> None:
        self.mainloop()
