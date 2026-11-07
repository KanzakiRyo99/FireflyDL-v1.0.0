"""关于页面。"""

from __future__ import annotations

import platform
import sys
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageTk

from .. import APP_NAME, APP_NAME_CN, APP_TAGLINE, __version__
from ..paths import DATA_DIR, resource_path
from ..service import available, version as ytdlp_version
from ..utils import find_ffmpeg, ffmpeg_version, open_path, open_url
from .theme import COLORS, font
from .widgets import Card, RoundedButton, ScrollFrame, TextButton

if TYPE_CHECKING:
    from .app import FireflyApp


class AboutPage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self._logo_photo = None
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.scroll = ScrollFrame(self, bg=COLORS['bg'])
        self.scroll.grid(row=0, column=0, sticky='nsew')
        self.scroll.interior.configure(bg=COLORS['bg'])
        self._build_hero()
        self._build_features()
        self._build_sites()
        self._build_diagnostics()
        self._build_footer()

    def _build_hero(self) -> None:
        card = Card(self.scroll.interior, padding=24)
        card.pack(fill='x', pady=(0, 12))
        body = card.body
        image_path = resource_path('assets', 'firefly.png')
        try:
            logo = Image.open(image_path).convert('RGBA').resize((92, 92), Image.LANCZOS)
            self._logo_photo = ImageTk.PhotoImage(logo)
            tk.Label(body, image=self._logo_photo, bg=COLORS['card']).pack(side='left', padx=(0, 22))
        except Exception:
            tk.Label(body, text='✦', bg=COLORS['card'], fg=COLORS['accent'],
                     font=font(44)).pack(side='left', padx=(0, 22))
        info = tk.Frame(body, bg=COLORS['card'])
        info.pack(side='left', fill='both', expand=True)
        title_row = tk.Frame(info, bg=COLORS['card'])
        title_row.pack(anchor='w')
        tk.Label(title_row, text=APP_NAME_CN, bg=COLORS['card'], fg=COLORS['text'],
                 font=font(22, 'bold')).pack(side='left')
        tk.Label(title_row, text=f'  v{__version__}', bg=COLORS['card'],
                 fg=COLORS['accent'], font=font(10, 'bold')).pack(side='left', pady=(8, 0))
        tk.Label(info, text=APP_TAGLINE, bg=COLORS['card'], fg=COLORS['muted'],
                 font=font(10)).pack(anchor='w', pady=(3, 8))
        chips = tk.Frame(info, bg=COLORS['card'])
        chips.pack(anchor='w')
        for text, color in (
            ('Python', COLORS['blue']),
            ('yt-dlp 内核', COLORS['green']),
            ('Tkinter GUI', COLORS['purple']),
            ('命令行模式', COLORS['accent']),
            ('本地运行', COLORS['teal']),
        ):
            tk.Label(chips, text=text, bg=COLORS['card_alt'], fg=color,
                     font=font(8), padx=8, pady=3).pack(side='left', padx=(0, 6))

    def _build_features(self) -> None:
        wrap = tk.Frame(self.scroll.interior, bg=COLORS['bg'])
        wrap.pack(fill='x', pady=(0, 12))
        for index in range(3):
            wrap.grid_columnconfigure(index, weight=1, uniform='feature')
        features = [
            ('⌁', '多站点支持', 'B站、抖音、快手、YouTube、TikTok、微博、小红书、X、Instagram 等 1700+ 站点。'),
            ('⌕', '页面解析', '查看标题、作者、封面、字幕与全部可用格式，双击即可下载指定清晰度。'),
            ('⇣', '队列与批量', '多条链接同时排队，暂停/继续/重试，限速、代理、Cookie 与后处理一应俱全。'),
            ('⚙', '双模式', '双击图标使用图形界面；命令行支持 -f、--audio、--json 等自动化参数。'),
            ('✦', '本地优先', '设置、Cookie 与下载记录只留在本机，不上传账号信息，不经过第三方服务器。'),
            ('↻', '持续更新', '内核可一键更新，快手扩展随项目内置，遇到站点改版也能快速适配。'),
        ]
        for index, (icon, title, desc) in enumerate(features):
            card = Card(wrap, padding=15)
            card.grid(row=index // 3, column=index % 3, sticky='nsew',
                      padx=(0 if index % 3 == 0 else 6, 0 if index % 3 == 2 else 6),
                      pady=(0, 10))
            tk.Label(card.body, text=icon, bg=COLORS['card'], fg=COLORS['accent'],
                     font=font(18)).pack(anchor='w')
            tk.Label(card.body, text=title, bg=COLORS['card'], fg=COLORS['text'],
                     font=font(10, 'bold')).pack(anchor='w', pady=(5, 3))
            tk.Label(card.body, text=desc, bg=COLORS['card'], fg=COLORS['muted'],
                     font=font(8), wraplength=184, justify='left').pack(anchor='w')

    def _build_sites(self) -> None:
        card = Card(self.scroll.interior, padding=18)
        card.pack(fill='x', pady=(0, 12))
        tk.Label(card.body, text='支持的站点（部分）', bg=COLORS['card'],
                 fg=COLORS['text'], font=font(11, 'bold')).pack(anchor='w')
        tk.Label(card.body, text='内核覆盖 1700+ 站点；快手通过内置扩展解析，抖音等登录受限站点可在设置中导入 Cookie。',
                 bg=COLORS['card'], fg=COLORS['faint'], font=font(8),
                 justify='left').pack(anchor='w', pady=(3, 10))
        chips = tk.Frame(card.body, bg=COLORS['card'])
        chips.pack(fill='x')
        sites = ['B站', '抖音', '快手', 'YouTube', 'TikTok', '微博', '小红书', 'X',
                 'Instagram', 'Facebook', 'Vimeo', 'Twitch', 'AcFun', '爱奇艺',
                 '腾讯视频', '优酷', '芒果TV', '豆瓣', '知乎', '更多…']
        for index, site in enumerate(sites):
            tk.Label(chips, text=site, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
                     font=font(8), padx=9, pady=4).grid(
                row=index // 10, column=index % 10, padx=(0, 6), pady=(0, 6), sticky='w')

    def _build_diagnostics(self) -> None:
        card = Card(self.scroll.interior, padding=18)
        card.pack(fill='x', pady=(0, 12))
        header = tk.Frame(card.body, bg=COLORS['card'])
        header.pack(fill='x')
        tk.Label(header, text='运行环境', bg=COLORS['card'], fg=COLORS['text'],
                 font=font(11, 'bold')).pack(side='left')
        TextButton(header, '复制诊断信息', self.copy_diagnostics, bg=COLORS['card'],
                   fg=COLORS['faint'], font_size=8).pack(side='right')
        ffmpeg = find_ffmpeg(self.app.settings.ffmpeg_path)
        rows = [
            ('Python', f'{platform.python_version()}  ·  {platform.architecture()[0]}'),
            ('yt-dlp', ytdlp_version() if available() else '未安装'),
            ('ffmpeg', f'{ffmpeg_version(ffmpeg)}  ·  {ffmpeg or "未找到"}'),
            ('系统', f'{platform.system()} {platform.release()}'),
            ('数据目录', str(DATA_DIR)),
            ('快手扩展', '已内置（yt_dlp_plugins/extractor/kuaishou.py）'),
        ]
        for label, value in rows:
            row = tk.Frame(card.body, bg=COLORS['card'])
            row.pack(fill='x', pady=2)
            tk.Label(row, text=label, bg=COLORS['card'], fg=COLORS['muted'],
                     font=font(8), width=10, anchor='w').pack(side='left')
            tk.Label(row, text=value, bg=COLORS['card'], fg=COLORS['text_soft'],
                     font=font(8), anchor='w').pack(side='left', fill='x', expand=True)

    def _build_footer(self) -> None:
        card = Card(self.scroll.interior, padding=18)
        card.pack(fill='x', pady=(0, 8))
        tk.Label(card.body, text='使用提醒', bg=COLORS['card'], fg=COLORS['accent'],
                 font=font(10, 'bold')).pack(anchor='w')
        tk.Label(
            card.body,
            text=('请仅下载你拥有版权、已获授权或允许个人存档的内容。'
                  '本工具不绕过付费墙或 DRM，不提供内容分发；请遵守各站点用户协议与当地法律。'),
            bg=COLORS['card'], fg=COLORS['muted'], font=font(8),
            justify='left', wraplength=820,
        ).pack(anchor='w', pady=(4, 12))
        buttons = tk.Frame(card.body, bg=COLORS['card'])
        buttons.pack(anchor='w')
        RoundedButton(
            buttons, '打开项目目录', self.open_project_dir,
            width=128, height=34, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['card'], font_size=8, bold=False,
        ).pack(side='left')
        RoundedButton(
            buttons, 'yt-dlp 项目主页', lambda: open_url('https://github.com/yt-dlp/yt-dlp'),
            width=132, height=34, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['card'], font_size=8, bold=False,
        ).pack(side='left', padx=(8, 0))
        tk.Label(card.body, text='FireflyDL 与 yt-dlp 开发者无隶属关系，仅使用其开源内核。',
                 bg=COLORS['card'], fg=COLORS['faint'], font=font(8)).pack(
            anchor='w', pady=(10, 0))

    def copy_diagnostics(self) -> None:
        ffmpeg = find_ffmpeg(self.app.settings.ffmpeg_path)
        text = '\n'.join([
            f'{APP_NAME} v{__version__}',
            f'Python {platform.python_version()} / {platform.system()} {platform.release()}',
            f'yt-dlp {ytdlp_version() if available() else "未安装"}',
            f'ffmpeg {ffmpeg_version(ffmpeg)} ({ffmpeg or "未找到"})',
            f'数据目录 {DATA_DIR}',
        ])
        self.clipboard_clear()
        self.clipboard_append(text)
        self.app.notify('诊断信息已复制。', 'success')

    def open_project_dir(self) -> None:
        if getattr(sys, 'frozen', False):
            target = Path(sys.executable).resolve().parent
        else:
            target = Path(__file__).resolve().parents[2]
        open_path(target)

    def on_show(self) -> None:
        self.scroll.scroll_to_top()
