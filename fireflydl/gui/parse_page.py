"""页面解析页面。"""

from __future__ import annotations

import io
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from PIL import Image, ImageOps, ImageTk

from ..models import FormatInfo, MediaInfo
from ..utils import clean_text, human_count, human_duration, truncate_middle
from .theme import COLORS, font
from .widgets import Card, RoundedButton, RoundedFrame, TextButton

if TYPE_CHECKING:
    from .app import FireflyApp


class ParsePage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self.media: MediaInfo | None = None
        self._cover_photo: ImageTk.PhotoImage | None = None
        self._parsing = False
        self._format_map: dict[str, FormatInfo] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build_input()
        self._build_info()
        self._build_formats()
        self._build_actions()

    def _build_input(self) -> None:
        card = Card(self, padding=12)
        card.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        row = tk.Frame(card.body, bg=COLORS['card'])
        row.pack(fill='x')
        icon = tk.Label(row, text='⌕', bg=COLORS['card'], fg=COLORS['accent'],
                        font=font(16, 'bold'))
        icon.pack(side='left', padx=(2, 8))
        url_box = RoundedFrame(
            row, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=12, inset=6, surface=COLORS['card'],
        )
        url_box.pack(side='left', fill='x', expand=True)
        self.url_var = tk.StringVar(value=self.app.settings.last_parse_url)
        self.url_entry = ttk.Entry(url_box.body, textvariable=self.url_var,
                                   font=font(10), style='Seamless.TEntry')
        self.url_entry.pack(fill='x', ipady=1)
        self.url_entry.bind('<Return>', lambda _e: self.parse())
        TextButton(row, '粘贴', self._paste, bg=COLORS['card'], fg=COLORS['muted'],
                   font_size=9).pack(side='left', padx=(10, 8))
        self.parse_button = RoundedButton(
            row, '解析页面', self.parse, width=116, height=38,
            bg=COLORS['accent'], fg='#18130A', hover_bg=COLORS['accent_hover'],
            surface=COLORS['card'],
        )
        self.parse_button.pack(side='left', padx=(4, 0))
        self.status_label = tk.Label(card.body, text='粘贴链接后按 Enter，或点击「解析页面」。',
                                     bg=COLORS['card'], fg=COLORS['faint'],
                                     font=font(8), anchor='w')
        self.status_label.pack(anchor='w', pady=(7, 0))

    def _build_info(self) -> None:
        self.info_card = Card(self, padding=12)
        self.info_card.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        body = self.info_card.body
        body.grid_columnconfigure(1, weight=1)

        cover_frame = tk.Frame(body, bg=COLORS['card_alt'],
                               highlightbackground=COLORS['border'], highlightthickness=1)
        cover_frame.grid(row=0, column=0, rowspan=3, sticky='nw', padx=(0, 18))
        self.cover_label = tk.Label(cover_frame, text='暂无封面', bg=COLORS['card_alt'],
                                    fg=COLORS['faint'], font=font(9),
                                    width=38, height=11)
        self.cover_label.pack()

        top = tk.Frame(body, bg=COLORS['card'])
        top.grid(row=0, column=1, sticky='ew')
        self.site_chip = tk.Label(top, text='等待解析', bg=COLORS['card_alt'],
                                  fg=COLORS['muted'], font=font(8, 'bold'),
                                  padx=8, pady=3)
        self.site_chip.pack(side='left')
        self.kind_label = tk.Label(top, text='', bg=COLORS['card'], fg=COLORS['faint'],
                                   font=font(8))
        self.kind_label.pack(side='left', padx=(8, 0))

        self.title_label = tk.Label(
            body, text='粘贴一个视频链接，开始解析', bg=COLORS['card'],
            fg=COLORS['text'], font=font(14, 'bold'), anchor='w', justify='left',
            wraplength=680,
        )
        self.title_label.grid(row=1, column=1, sticky='ew', pady=(8, 3))

        self.uploader_label = tk.Label(
            body, text='支持 B站、抖音、快手、YouTube 等站点', bg=COLORS['card'],
            fg=COLORS['muted'], font=font(9), anchor='w',
        )
        self.uploader_label.grid(row=2, column=1, sticky='ew')

        self.meta_label = tk.Label(body, text='', bg=COLORS['card'], fg=COLORS['faint'],
                                   font=font(8), anchor='w')
        self.meta_label.grid(row=3, column=1, sticky='ew', pady=(4, 0))

        self.desc_text = tk.Text(
            body, height=2, bg=COLORS['card'], fg=COLORS['muted'], relief='flat',
            bd=0, font=font(8), wrap='word', padx=0, pady=0, cursor='arrow',
            highlightthickness=0,
        )
        self.desc_text.grid(row=4, column=1, sticky='ew', pady=(6, 0))
        self.desc_text.configure(state='disabled')

    def _build_formats(self) -> None:
        card = Card(self, padding=0)
        card.grid(row=2, column=0, sticky='nsew', pady=(0, 10))
        card.body.grid_rowconfigure(1, weight=1)
        card.body.grid_columnconfigure(0, weight=1)
        header = tk.Frame(card.body, bg=COLORS['card'])
        header.grid(row=0, column=0, sticky='ew', padx=16, pady=(13, 8))
        self.formats_title = tk.Label(header, text='可用格式', bg=COLORS['card'],
                                      fg=COLORS['text'], font=font(11, 'bold'))
        self.formats_title.pack(side='left')
        self.formats_hint = tk.Label(header, text='  双击某一行，直接下载该格式',
                                     bg=COLORS['card'], fg=COLORS['faint'], font=font(8))
        self.formats_hint.pack(side='left')
        self.formats_count = tk.Label(header, text='', bg=COLORS['card'],
                                      fg=COLORS['faint'], font=font(8))
        self.formats_count.pack(side='right')

        tree_frame = tk.Frame(card.body, bg=COLORS['card'])
        tree_frame.grid(row=1, column=0, sticky='nsew', padx=(12, 6), pady=(0, 12))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, show='headings', selectmode='browse',
                                 height=5)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<Double-1>', self._on_tree_double)
        self._set_format_columns()

        self.tree_empty = tk.Label(
            card.body, text='解析结果会显示在这里\n可以选择清晰度、编码与音频格式',
            bg=COLORS['card'], fg=COLORS['faint'], font=font(9), justify='center',
        )
        self.tree_empty.place(relx=0.5, rely=0.58, anchor='center')

    def _build_actions(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=3, column=0, sticky='ew')
        self.download_best = RoundedButton(
            bar, '下载最佳画质', lambda: self._download('video', 'best'),
            width=150, height=38, bg=COLORS['accent'], fg='#18130A',
            hover_bg=COLORS['accent_hover'], surface=COLORS['bg'],
        )
        self.download_best.pack(side='left')
        self.download_audio = RoundedButton(
            bar, '仅下载音频', lambda: self._download('audio', 'best'),
            width=126, height=38, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=9, bold=False,
        )
        self.download_audio.pack(side='left', padx=(10, 0))
        self.download_selected = RoundedButton(
            bar, '下载所选格式', self._download_selected,
            width=140, height=38, bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=9, bold=False,
        )
        self.download_selected.pack(side='left', padx=(10, 0))
        self.add_plain = TextButton(
            bar, '仅加入队列', lambda: self._download('video', 'best', queue_only=True),
            bg=COLORS['bg'], fg=COLORS['faint'], font_size=8,
        )
        self.add_plain.pack(side='left', padx=(14, 0))
        self._set_actions_enabled(False)

    # ---------- 数据与状态 ----------
    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (self.download_best, self.download_audio, self.download_selected):
            button.set_enabled(enabled)

    def _set_format_columns(self) -> None:
        columns = (
            ('id', '格式 ID', 130, 'w'),
            ('kind', '类型', 58, 'center'),
            ('res', '分辨率', 84, 'center'),
            ('codec', '编码', 128, 'w'),
            ('size', '大小', 86, 'e'),
            ('proto', '协议', 76, 'center'),
            ('note', '说明', 190, 'w'),
        )
        self.tree.configure(columns=[c[0] for c in columns])
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title, anchor='w' if anchor == 'w' else 'center')
            self.tree.column(key, width=width, minwidth=50, anchor=anchor, stretch=(key == 'note'))

    def _set_entry_columns(self) -> None:
        columns = (
            ('index', '#', 48, 'center'),
            ('title', '合集条目', 520, 'w'),
            ('duration', '时长', 90, 'center'),
            ('uploader', '作者', 160, 'w'),
        )
        self.tree.configure(columns=[c[0] for c in columns])
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title, anchor='w' if anchor == 'w' else 'center')
            self.tree.column(key, width=width, minwidth=45, anchor=anchor, stretch=(key == 'title'))

    def _paste(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = ''
        if text:
            self.url_var.set(text.strip())
            self.url_entry.focus_set()

    def _parse_url(self) -> str:
        text = self.url_var.get().strip()
        from ..utils import normalize_urls
        urls = normalize_urls(text)
        return urls[0] if urls else text

    def parse(self) -> None:
        if self._parsing:
            return
        url = self._parse_url()
        if not url:
            self.app.notify('请先粘贴视频链接。', 'warning')
            return
        self._parsing = True
        self.parse_button.set_enabled(False)
        self.parse_button.set_text('解析中…')
        self.status_label.configure(text='正在获取页面信息，请稍候…', fg=COLORS['accent'])
        self._set_actions_enabled(False)
        self.app.settings.last_parse_url = url

        def on_ok(media: MediaInfo, image_bytes: bytes) -> None:
            self._parsing = False
            self.parse_button.set_enabled(True)
            self.parse_button.set_text('解析页面')
            self._render(media, image_bytes)

        def on_err(message: str) -> None:
            self._parsing = False
            self.parse_button.set_enabled(True)
            self.parse_button.set_text('解析页面')
            self.status_label.configure(text=message, fg=COLORS['red'])
            self.app.notify(message, 'error', '解析失败')

        self.app.probe_async(url, on_ok, on_err)

    def _render(self, media: MediaInfo, image_bytes: bytes) -> None:
        self.media = media
        site_label, site_color = media.site
        self.site_chip.configure(text=site_label, bg=site_color,
                                 fg='#FFFFFF' if site_label != 'X' else '#111111')
        kind = '合集 / 播放列表' if media.kind == 'playlist' else '单视频'
        if media.is_live:
            kind += ' · 直播'
        self.kind_label.configure(text=kind)
        self.title_label.configure(text=media.title or '未命名视频')
        uploader = media.uploader or '未知作者'
        self.uploader_label.configure(text=f'UP 主 / 作者：{uploader}')
        meta_parts = []
        if media.duration:
            meta_parts.append(f'时长 {human_duration(media.duration)}')
        if media.upload_date:
            date = media.upload_date
            if len(date) == 8:
                date = f'{date[:4]}-{date[4:6]}-{date[6:]}'
            meta_parts.append(date)
        if media.view_count:
            meta_parts.append(f'播放 {human_count(media.view_count)}')
        if media.like_count:
            meta_parts.append(f'点赞 {human_count(media.like_count)}')
        if media.playlist_count:
            meta_parts.append(f'合集 {media.playlist_count} 项')
        if media.extractor:
            meta_parts.append(media.extractor)
        self.meta_label.configure(text='  ·  '.join(meta_parts) if meta_parts else '')

        description = clean_text(media.description, 220) or '暂无简介'
        self.desc_text.configure(state='normal')
        self.desc_text.delete('1.0', 'end')
        self.desc_text.insert('1.0', description)
        self.desc_text.configure(state='disabled')

        self._set_cover(image_bytes, site_color)
        self.tree.delete(*self.tree.get_children())
        self._format_map.clear()
        if media.kind == 'playlist':
            self._set_entry_columns()
            self.formats_title.configure(text='合集条目')
            self.formats_hint.configure(text='  双击条目可单独解析；下载按钮会保存整个合集')
            self.formats_count.configure(text=f'共 {media.playlist_count or len(media.entries)} 项')
            for entry in media.entries:
                self.tree.insert('', 'end', iid=f'entry-{entry.index}', values=(
                    entry.index, entry.title,
                    human_duration(entry.duration),
                    entry.uploader or '—',
                ))
            self.download_best.set_text('下载整个合集')
            self.download_audio.set_text('合集转音频')
            self.download_selected.set_enabled(False)
            self.add_plain.configure(text='仅加入队列')
        else:
            self._set_format_columns()
            self.formats_title.configure(text='可用格式')
            self.formats_hint.configure(text='  双击某一行，直接下载该格式')
            self.formats_count.configure(text=f'{len(media.formats)} 个格式')
            for index, fmt in enumerate(media.formats):
                iid = f'fmt-{index}'
                self._format_map[iid] = fmt
                self.tree.insert('', 'end', iid=iid, values=(
                    fmt.format_id, fmt.kind_text, fmt.resolution,
                    fmt.codec_short, fmt.size_text,
                    _protocol_text(fmt.protocol), truncate_middle(fmt.note, 34),
                ))
            self.download_best.set_text('下载最佳画质')
            self.download_audio.set_text('仅下载音频')
            self.download_selected.set_enabled(bool(media.formats))
        self.tree_empty.place_forget()
        self._set_actions_enabled(bool(media.formats) or bool(media.entries))
        if media.kind == 'playlist':
            self.download_best.set_enabled(bool(media.entries))
            self.download_audio.set_enabled(bool(media.entries))
        else:
            self.download_best.set_enabled(bool(media.formats))
            self.download_audio.set_enabled(True)
        self.status_label.configure(
            text=f'解析成功 · {site_label} · {self.formats_count.cget("text")}',
            fg=COLORS['green'],
        )

    def _set_cover(self, image_bytes: bytes, fallback_color: str) -> None:
        if not image_bytes:
            self.cover_label.configure(image='', text='暂无封面', bg=COLORS['card_alt'],
                                       fg=COLORS['faint'], width=38, height=11)
            self._cover_photo = None
            return
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            image = ImageOps.fit(image, (300, 169), method=Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._cover_photo = photo
            self.cover_label.configure(image=photo, text='', width=300, height=169)
        except Exception:
            self.cover_label.configure(image='', text='封面加载失败', bg=fallback_color,
                                       fg='#FFFFFF', width=38, height=11)
            self._cover_photo = None

    def _on_tree_double(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        iid = selection[0]
        if iid.startswith('entry-'):
            entry = next((e for e in (self.media.entries if self.media else [])
                          if f'entry-{e.index}' == iid), None)
            if entry and entry.url:
                self.url_var.set(entry.url)
                self.parse()
            return
        self._download_selected()

    def _download_selected(self) -> None:
        if not self.media or self.media.kind == 'playlist':
            self.app.notify('请先选择一个可用格式。', 'warning')
            return
        selection = self.tree.selection()
        if not selection:
            self.app.notify('请先在格式列表中选择一行。', 'warning')
            return
        fmt = self._format_map.get(selection[0])
        if not fmt:
            return
        mode = 'audio' if fmt.is_audio else 'video'
        self._download(mode, 'best', custom_format=fmt.format_id)

    def _download(self, mode: str, quality: str, custom_format: str = '',
                  queue_only: bool = False) -> None:
        if not self.media:
            self.app.notify('请先解析一个页面。', 'warning')
            return
        media = self.media
        url = media.webpage_url or media.url or self._parse_url()
        playlist = media.kind == 'playlist'
        self.app.add_urls(
            url, mode=mode, quality=quality, custom_format=custom_format,
            playlist=playlist, navigate=not queue_only,
        )

    def sync_settings(self) -> None:
        if not self.url_var.get().strip():
            self.url_var.set(self.app.settings.last_parse_url)

    def on_show(self) -> None:
        pass


def _protocol_text(protocol: str) -> str:
    mapping = {
        'https': 'HTTPS',
        'http': 'HTTP',
        'm3u8_native': 'HLS',
        'm3u8': 'HLS',
        'http_dash_segments': 'DASH',
        'dash': 'DASH',
        'websocket': 'WS',
    }
    return mapping.get(protocol, protocol.upper() if protocol else '—')
