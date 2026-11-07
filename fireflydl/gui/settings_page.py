"""设置页面。"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any

from ..config import COOKIE_BROWSERS, MODE_CHOICES, QUALITY_CHOICES, Settings
from ..paths import DATA_DIR
from ..service import available, update_ytdlp_command, version as ytdlp_version
from ..utils import find_ffmpeg, open_path
from .theme import COLORS, font
from .widgets import Card, CheckItem, RoundedButton, RoundedFrame, ScrollFrame, TextButton

if TYPE_CHECKING:
    from .app import FireflyApp


class SettingsPage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self.vars: dict[str, tk.Variable] = {}
        self._update_queue: queue.Queue = queue.Queue()
        self._update_running = False
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scroll = ScrollFrame(self, bg=COLORS['bg'])
        self.scroll.grid(row=0, column=0, sticky='nsew')
        self.scroll.interior.configure(bg=COLORS['bg'])
        self._build_sections()
        self._build_savebar()
        self.load_values()

    # ---------- 变量与小工具 ----------
    def _var(self, key: str, value: Any, kind: str = 'str') -> tk.Variable:
        if kind == 'bool':
            var: tk.Variable = tk.BooleanVar(value=bool(value))
        elif kind == 'int':
            var = tk.IntVar(value=int(value or 0))
        elif kind == 'float':
            var = tk.DoubleVar(value=float(value or 0))
        else:
            var = tk.StringVar(value=str(value or ''))
        self.vars[key] = var
        return var

    def _section(self, title: str, subtitle: str = '') -> tk.Frame:
        card = Card(self.scroll.interior, padding=18)
        card.pack(fill='x', pady=(0, 12))
        heading = tk.Frame(card.body, bg=COLORS['card'])
        heading.pack(fill='x', pady=(0, 10))
        tk.Label(heading, text=title, bg=COLORS['card'], fg=COLORS['text'],
                 font=font(11, 'bold')).pack(anchor='w')
        if subtitle:
            tk.Label(heading, text=subtitle, bg=COLORS['card'], fg=COLORS['faint'],
                     font=font(8), anchor='w', justify='left').pack(anchor='w', pady=(3, 0))
        body = tk.Frame(card.body, bg=COLORS['card'])
        body.pack(fill='x')
        body.grid_columnconfigure(1, weight=1)
        return body

    def _row(self, body: tk.Frame, row: int, label: str, hint: str = '') -> None:
        tk.Label(body, text=label, bg=COLORS['card'], fg=COLORS['text_soft'],
                 font=font(9), anchor='w').grid(
            row=row, column=0, sticky='nw', padx=(0, 16), pady=(0, 4))
        if hint:
            tk.Label(body, text=hint, bg=COLORS['card'], fg=COLORS['faint'],
                     font=font(8), anchor='w', justify='left').grid(
                row=row + 1, column=1, sticky='w', pady=(0, 10))

    def _browse_row(self, body: tk.Frame, row: int, label: str, key: str,
                    kind: str, hint: str = '') -> None:
        self._row(body, row, label, hint)
        wrap = tk.Frame(body, bg=COLORS['card'])
        wrap.grid(row=row, column=1, sticky='ew', pady=(0, 6))
        wrap.grid_columnconfigure(0, weight=1)
        entry_box = RoundedFrame(
            wrap, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=10, inset=5, surface=COLORS['card'],
        )
        entry_box.grid(row=0, column=0, sticky='ew')
        entry = ttk.Entry(entry_box.body, textvariable=self.vars[key],
                          font=font(9), style='Seamless.TEntry')
        entry.pack(fill='x')
        RoundedButton(
            wrap, '浏览', lambda: self._browse(key, kind),
            width=64, height=32, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['card'], font_size=8, bold=False,
        ).grid(row=0, column=1, padx=(8, 0))

    def _combo_row(self, body: tk.Frame, row: int, label: str, key: str,
                   values: list[str], hint: str = '') -> None:
        self._row(body, row, label, hint)
        box = RoundedFrame(
            body, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=10, inset=5, surface=COLORS['card'],
        )
        box.grid(row=row, column=1, sticky='w', pady=(0, 6))
        combo = ttk.Combobox(box.body, textvariable=self.vars[key], values=values,
                             state='readonly', font=font(9), width=32)
        combo.pack(fill='x')

    def _rounded_entry(self, parent: tk.Frame, variable: tk.Variable,
                       *, width: int | None = None) -> RoundedFrame:
        box = RoundedFrame(
            parent, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=10, inset=5, surface=COLORS['card'],
        )
        entry = ttk.Entry(box.body, textvariable=variable, font=font(9),
                          style='Seamless.TEntry', width=width or 20)
        entry.pack(fill='x')
        return box

    def _spinbox(self, parent: tk.Frame, row: int | None, key: str,
                 from_: float, to: float, increment: float, *, width: int = 8,
                 side: str | None = None) -> tk.Spinbox:
        is_float = isinstance(increment, float)
        spin = tk.Spinbox(
            parent, from_=from_, to=to, increment=increment, width=width,
            textvariable=self.vars[key], bg=COLORS['card_alt'], fg=COLORS['text'],
            buttonbackground=COLORS['card_alt'], disabledbackground=COLORS['card'],
            relief='flat', bd=0, highlightthickness=1,
            highlightbackground=COLORS['border'], highlightcolor=COLORS['accent'],
            insertbackground=COLORS['accent'], font=font(9),
            format='%.1f' if is_float else '%.0f',
        )
        if side:
            spin.pack(side=side)
        else:
            spin.grid(row=row, column=1, sticky='w', pady=(0, 6))
        return spin

    # ---------- 页面构建 ----------
    def _build_sections(self) -> None:
        self._build_download_section()
        self._build_network_section()
        self._build_postprocess_section()
        self._build_tools_section()

    def _build_download_section(self) -> None:
        body = self._section('下载', '下载位置、并发数与默认清晰度')
        self._var('download_dir', self.app.settings.download_dir)
        self._browse_row(body, 0, '下载目录', 'download_dir', 'dir',
                         '文件将按下方命名模板保存在该目录。')
        self._var('concurrency', self.app.settings.concurrency, 'int')
        self._row(body, 2, '同时下载数', '建议 1–3；网络较慢时降低并发更稳定。')
        self._spinbox(body, 2, 'concurrency', 1, 6, 1, width=6)

        self._var('default_mode', MODE_CHOICES.get(self.app.settings.default_mode))
        self._combo_row(body, 4, '默认模式', 'default_mode', list(MODE_CHOICES.values()))
        self._var('default_quality', QUALITY_CHOICES.get(self.app.settings.default_quality))
        self._combo_row(body, 5, '默认清晰度', 'default_quality', list(QUALITY_CHOICES.values()))

        self._var('filename_template', self.app.settings.filename_template)
        self._row(body, 6, '文件命名模板',
                  '使用 yt-dlp 模板变量，例如 %(title).120B [%(id)s].%(ext)s；必须包含 %(ext)s。')
        self._rounded_entry(body, self.vars['filename_template']).grid(
            row=6, column=1, sticky='ew', pady=(0, 6))

        self._var('rate_limit_mb', self.app.settings.rate_limit_mb, 'float')
        self._row(body, 8, '单任务限速', '单位 MB/s，填 0 表示不限速。')
        rate_wrap = tk.Frame(body, bg=COLORS['card'])
        rate_wrap.grid(row=8, column=1, sticky='w', pady=(0, 6))
        self._spinbox(rate_wrap, None, 'rate_limit_mb', 0, 200, 0.5, width=8,
                      side='left')
        tk.Label(rate_wrap, text='MB/s', bg=COLORS['card'], fg=COLORS['faint'],
                 font=font(8)).pack(side='left', padx=(6, 0))

    def _build_network_section(self) -> None:
        body = self._section(
            '登录凭证与网络',
            '抖音、B站高清/字幕、YouTube 年龄限制等场景需要浏览器 Cookie。Cookie 只保存在本机。',
        )
        self._var('cookies_from_browser',
                  COOKIE_BROWSERS.get(self.app.settings.cookies_from_browser,
                                      COOKIE_BROWSERS['']))
        self._combo_row(body, 0, '浏览器 Cookie', 'cookies_from_browser',
                        list(COOKIE_BROWSERS.values()),
                        '选择已登录目标网站的浏览器；若同时填写 Cookie 文件，优先使用文件。')
        self._var('cookies_file', self.app.settings.cookies_file)
        self._browse_row(body, 2, 'Cookie 文件', 'cookies_file', 'file',
                         'Netscape 格式的 cookies.txt，可由浏览器扩展导出。')
        self._var('proxy', self.app.settings.proxy)
        self._row(body, 4, '代理地址',
                  '支持 http://、https://、socks5://，例如 http://127.0.0.1:7890；留空表示直连。')
        self._rounded_entry(body, self.vars['proxy']).grid(
            row=4, column=1, sticky='ew', pady=(0, 6))

    def _build_postprocess_section(self) -> None:
        body = self._section('下载与后处理', '字幕、封面、元数据与合集行为')
        self._var('playlist', self.app.settings.playlist, 'bool')
        self._var('skip_existing', self.app.settings.skip_existing, 'bool')
        self._var('open_folder_when_done', self.app.settings.open_folder_when_done, 'bool')
        self._var('clipboard_watch', self.app.settings.clipboard_watch, 'bool')
        checks = [
            ('playlist', '默认下载整个合集 / 播放列表'),
            ('skip_existing', '跳过已存在的同名文件'),
            ('open_folder_when_done', '下载完成后在资源管理器中定位文件'),
            ('clipboard_watch', '监听剪贴板，自动填入视频链接'),
        ]
        for index, (key, label) in enumerate(checks):
            CheckItem(body, label, self.vars[key], bg=COLORS['card']).grid(
                row=index, column=0, columnspan=2, sticky='w', pady=3)

        self._var('write_subs', self.app.settings.write_subs, 'bool')
        self._var('embed_subs', self.app.settings.embed_subs, 'bool')
        self._var('embed_thumbnail', self.app.settings.embed_thumbnail, 'bool')
        self._var('embed_metadata', self.app.settings.embed_metadata, 'bool')
        self._var('use_archive', self.app.settings.use_archive, 'bool')
        checks2 = [
            ('write_subs', '下载字幕（含自动字幕）'),
            ('embed_subs', '把字幕嵌入视频容器'),
            ('embed_thumbnail', '嵌入封面图'),
            ('embed_metadata', '写入标题、作者等元数据'),
            ('use_archive', '使用下载档案（永久跳过已下载 ID）'),
        ]
        for index, (key, label) in enumerate(checks2):
            CheckItem(body, label, self.vars[key], bg=COLORS['card']).grid(
                row=index, column=2, sticky='w', padx=(28, 0), pady=3)

        self._var('playlist_limit', self.app.settings.playlist_limit, 'int')
        self._row(body, 5, '合集数量上限', '填 0 表示不限制；仅对合集 / 播放列表生效。')
        self._spinbox(body, 5, 'playlist_limit', 0, 9999, 1, width=8)

        self._var('subtitle_langs', self.app.settings.subtitle_langs)
        self._row(body, 7, '字幕语言', '逗号分隔的优先级，例如 zh-Hans,zh-CN,zh,en。')
        self._rounded_entry(body, self.vars['subtitle_langs']).grid(
            row=7, column=1, sticky='ew', pady=(0, 6))

    def _build_tools_section(self) -> None:
        body = self._section('工具与维护', 'ffmpeg、yt-dlp 版本和本地数据')
        self._var('ffmpeg_path', self.app.settings.ffmpeg_path)
        self._browse_row(body, 0, 'ffmpeg 路径', 'ffmpeg_path', 'ffmpeg',
                         '填写 ffmpeg.exe 路径或所在目录；留空自动从 PATH 和常见位置查找。')
        ff = find_ffmpeg(self.app.settings.ffmpeg_path)
        tk.Label(body, text=f'当前：{ff or "未检测到"}', bg=COLORS['card'],
                 fg=COLORS['teal'] if ff else COLORS['red'],
                 font=font(8), anchor='w').grid(row=2, column=0, columnspan=2,
                                                sticky='w', pady=(0, 10))

        tools = tk.Frame(body, bg=COLORS['card'])
        tools.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(2, 4))
        self.version_label = tk.Label(
            tools, text=f'yt-dlp {ytdlp_version() if available() else "未安装"}',
            bg=COLORS['card'], fg=COLORS['muted'], font=font(9),
        )
        self.version_label.pack(side='left')
        self.update_button = RoundedButton(
            tools, '更新 yt-dlp', self.update_ytdlp, width=104, height=32,
            bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['card'], font_size=8, bold=False,
        )
        self.update_button.pack(side='left', padx=(12, 0))
        TextButton(tools, '打开数据目录', lambda: open_path(DATA_DIR),
                   bg=COLORS['card'], fg=COLORS['faint'], font_size=8).pack(
            side='left', padx=(14, 0))
        TextButton(tools, '清空缓存', self.clear_cache,
                   bg=COLORS['card'], fg=COLORS['faint'],
                   hover_fg=COLORS['red'], font_size=8).pack(side='left', padx=(12, 0))
        self.update_status = tk.Label(body, text='', bg=COLORS['card'],
                                      fg=COLORS['faint'], font=font(8), anchor='w')
        self.update_status.grid(row=4, column=0, columnspan=2, sticky='w', pady=(4, 0))

    def _build_savebar(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=1, column=0, sticky='ew', pady=(8, 12))
        tk.Label(bar, text='设置保存在本机  ·  不会上传任何账号信息',
                 bg=COLORS['bg'], fg=COLORS['faint'], font=font(8)).pack(side='left')
        RoundedButton(bar, '保存设置', self.save, width=124, height=38,
                      bg=COLORS['accent'], fg='#18130A',
                      hover_bg=COLORS['accent_hover'], surface=COLORS['bg']).pack(
            side='right', padx=(0, 4))
        TextButton(bar, '恢复默认', self.restore_defaults, bg=COLORS['bg'],
                   fg=COLORS['faint'], hover_fg=COLORS['accent'], font_size=8).pack(
            side='right', padx=(0, 14))

    # ---------- 载入 / 保存 ----------
    def load_values(self, settings: Settings | None = None) -> None:
        settings = settings or self.app.settings
        mapping = {
            'download_dir': settings.download_dir,
            'concurrency': settings.concurrency,
            'default_mode': MODE_CHOICES.get(settings.default_mode, MODE_CHOICES['video']),
            'default_quality': QUALITY_CHOICES.get(settings.default_quality,
                                                   QUALITY_CHOICES['best']),
            'filename_template': settings.filename_template,
            'rate_limit_mb': settings.rate_limit_mb,
            'cookies_from_browser': COOKIE_BROWSERS.get(settings.cookies_from_browser,
                                                       COOKIE_BROWSERS['']),
            'cookies_file': settings.cookies_file,
            'proxy': settings.proxy,
            'playlist': settings.playlist,
            'skip_existing': settings.skip_existing,
            'open_folder_when_done': settings.open_folder_when_done,
            'clipboard_watch': settings.clipboard_watch,
            'write_subs': settings.write_subs,
            'embed_subs': settings.embed_subs,
            'embed_thumbnail': settings.embed_thumbnail,
            'embed_metadata': settings.embed_metadata,
            'use_archive': settings.use_archive,
            'playlist_limit': settings.playlist_limit,
            'subtitle_langs': settings.subtitle_langs,
            'ffmpeg_path': settings.ffmpeg_path,
        }
        for key, value in mapping.items():
            if key in self.vars:
                try:
                    self.vars[key].set(value)
                except Exception:
                    pass
        try:
            self.version_label.configure(
                text=f'yt-dlp {ytdlp_version() if available() else "未安装"}')
        except Exception:
            pass

    def _browse(self, key: str, kind: str) -> None:
        current = str(self.vars[key].get() or '')
        if kind == 'dir':
            path = filedialog.askdirectory(parent=self, initialdir=current or str(Path.home()))
        elif kind == 'ffmpeg':
            path = filedialog.askopenfilename(
                parent=self, title='选择 ffmpeg',
                filetypes=[('ffmpeg 可执行文件', '*.exe'), ('所有文件', '*.*')],
            )
        else:
            path = filedialog.askopenfilename(
                parent=self, title='选择 Cookie 文件',
                filetypes=[('Cookie 文本', '*.txt'), ('所有文件', '*.*')],
            )
        if path:
            self.vars[key].set(path)

    def save(self) -> None:
        settings = self.app.settings
        try:
            download_dir = str(self.vars['download_dir'].get()).strip()
            if not download_dir:
                raise ValueError('请填写下载目录。')
            path = Path(download_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            settings.download_dir = str(path)
            settings.concurrency = int(self.vars['concurrency'].get())
            label = str(self.vars['default_mode'].get())
            settings.default_mode = next(
                (key for key, value in MODE_CHOICES.items() if value == label), 'video')
            quality_label = str(self.vars['default_quality'].get())
            settings.default_quality = next(
                (key for key, value in QUALITY_CHOICES.items() if value == quality_label), 'best')
            template = str(self.vars['filename_template'].get()).strip()
            if '%(ext)s' not in template:
                raise ValueError('文件命名模板必须包含 %(ext)s。')
            settings.filename_template = template
            settings.rate_limit_mb = float(self.vars['rate_limit_mb'].get() or 0)
            browser_label = str(self.vars['cookies_from_browser'].get())
            settings.cookies_from_browser = next(
                (key for key, value in COOKIE_BROWSERS.items() if value == browser_label), '')
            settings.cookies_file = str(self.vars['cookies_file'].get()).strip()
            if settings.cookies_file and not Path(settings.cookies_file).expanduser().is_file():
                raise ValueError('Cookie 文件不存在，请重新选择。')
            settings.proxy = str(self.vars['proxy'].get()).strip()
            settings.playlist = bool(self.vars['playlist'].get())
            settings.skip_existing = bool(self.vars['skip_existing'].get())
            settings.open_folder_when_done = bool(self.vars['open_folder_when_done'].get())
            settings.clipboard_watch = bool(self.vars['clipboard_watch'].get())
            settings.write_subs = bool(self.vars['write_subs'].get())
            settings.embed_subs = bool(self.vars['embed_subs'].get())
            settings.embed_thumbnail = bool(self.vars['embed_thumbnail'].get())
            settings.embed_metadata = bool(self.vars['embed_metadata'].get())
            settings.use_archive = bool(self.vars['use_archive'].get())
            settings.playlist_limit = int(self.vars['playlist_limit'].get())
            settings.subtitle_langs = str(self.vars['subtitle_langs'].get()).strip()
            settings.ffmpeg_path = str(self.vars['ffmpeg_path'].get()).strip()
            if settings.proxy and not settings.proxy.startswith(
                    ('http://', 'https://', 'socks4://', 'socks5://', 'socks5h://')):
                raise ValueError('代理地址应以 http://、https:// 或 socks5:// 开头。')
            settings.normalized().save()
        except Exception as exc:
            self.app.notify(str(exc), 'error', '保存失败')
            return
        self.load_values()
        self.app.settings_saved()
        self.app._refresh_engine_status()

    def restore_defaults(self) -> None:
        if not messagebox.askyesno('恢复默认', '确定把所有设置恢复为默认值吗？', parent=self):
            return
        default = Settings().normalized()
        self.load_values(default)
        self.app.notify('已填入默认值，点击「保存设置」后生效。', 'info')

    def clear_cache(self) -> None:
        import shutil
        cache = DATA_DIR / 'cache'
        if not cache.exists():
            self.app.notify('缓存目录已经是空的。', 'info')
            return
        try:
            shutil.rmtree(cache)
            cache.mkdir(parents=True, exist_ok=True)
            self.app.notify('缓存已清空。', 'success')
        except OSError as exc:
            self.app.notify(f'清空缓存失败：{exc}', 'error')

    # ---------- yt-dlp 更新 ----------
    def update_ytdlp(self) -> None:
        if self._update_running:
            return
        if getattr(sys, 'frozen', False):
            self.app.notify('打包版内置了 yt-dlp，无法用 pip 更新；请使用源码版更新后重新打包。', 'warning')
            return
        self._update_running = True
        self.update_button.set_enabled(False)
        self.update_button.set_text('更新中…')
        self.update_status.configure(text='正在运行 pip install -U yt-dlp，请稍候…',
                                     fg=COLORS['accent'])

        def worker() -> None:
            try:
                flags = 0x08000000 if sys.platform.startswith('win') else 0
                process = subprocess.run(
                    update_ytdlp_command(), stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                    errors='replace', timeout=300, creationflags=flags,
                )
                self._update_queue.put((process.returncode, process.stdout or ''))
            except Exception as exc:
                self._update_queue.put((-1, str(exc)))

        threading.Thread(target=worker, name='fireflydl-update', daemon=True).start()
        self.after(400, self._poll_update)

    def _poll_update(self) -> None:
        try:
            returncode, output = self._update_queue.get_nowait()
        except queue.Empty:
            if self._update_running:
                self.after(400, self._poll_update)
            return
        self._update_running = False
        self.update_button.set_enabled(True)
        self.update_button.set_text('更新 yt-dlp')
        tail = '\n'.join((output or '').strip().splitlines()[-3:])
        if returncode == 0:
            self.update_status.configure(
                text='更新完成。重启应用后生效。', fg=COLORS['green'])
            self.app.log_line('[更新] yt-dlp 更新成功：' + tail)
            messagebox.showinfo('更新完成', 'yt-dlp 已更新，请重启应用以加载新版本。', parent=self)
        else:
            self.update_status.configure(text=f'更新失败：{tail[-160:]}', fg=COLORS['red'])
            self.app.log_line('[更新] yt-dlp 更新失败：' + tail)
            self.app.notify('yt-dlp 更新失败，详情见运行日志。', 'error')

    def on_show(self) -> None:
        self.scroll.scroll_to_top()
