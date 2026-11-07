"""历史记录页面。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from ..utils import human_bytes, open_path, truncate_middle
from .theme import COLORS, font
from .widgets import Card, RoundedButton, TextButton

if TYPE_CHECKING:
    from .app import FireflyApp


class HistoryPage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self.records: dict[str, dict] = {}
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_table()
        self._build_actions()
        self.reload()

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        tk.Label(bar, text='已下载内容', bg=COLORS['bg'], fg=COLORS['text'],
                 font=font(12, 'bold')).pack(side='left')
        self.count_label = tk.Label(bar, text='0 条', bg=COLORS['card_alt'],
                                    fg=COLORS['muted'], font=font(8), padx=8, pady=2)
        self.count_label.pack(side='left', padx=(8, 0))
        TextButton(bar, '清空历史', self.clear_all, bg=COLORS['bg'],
                   fg=COLORS['faint'], hover_fg=COLORS['red'], font_size=8).pack(side='right')

    def _build_table(self) -> None:
        card = Card(self, padding=0)
        card.grid(row=1, column=0, sticky='nsew', pady=(0, 12))
        card.body.grid_rowconfigure(0, weight=1)
        card.body.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            card.body, show='headings', selectmode='browse',
            columns=('title', 'site', 'status', 'time', 'size'),
        )
        self.tree.grid(row=0, column=0, sticky='nsew', padx=(12, 4), pady=12)
        scroll = ttk.Scrollbar(card.body, orient='vertical', command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns', pady=12, padx=(0, 6))
        self.tree.configure(yscrollcommand=scroll.set)
        settings = (
            ('title', '标题', 430, 'w'),
            ('site', '站点', 84, 'center'),
            ('status', '状态', 82, 'center'),
            ('time', '完成时间', 180, 'center'),
            ('size', '大小', 86, 'e'),
        )
        for key, title, width, anchor in settings:
            self.tree.heading(key, text=title, anchor='w' if anchor == 'w' else 'center')
            self.tree.column(key, width=width, minwidth=60, anchor=anchor,
                             stretch=(key == 'title'))
        self.tree.tag_configure('ok', foreground=COLORS['text_soft'])
        self.tree.tag_configure('bad', foreground=COLORS['red'])
        self.tree.bind('<Double-1>', lambda _e: self.open_file())
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.empty = tk.Label(
            card.body, text='还没有下载记录\n完成一次下载后，会在这里留下足迹',
            bg=COLORS['card'], fg=COLORS['faint'], font=font(9), justify='center',
        )
        self.empty.place(relx=0.5, rely=0.5, anchor='center')

    def _build_actions(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=2, column=0, sticky='ew')
        self.open_button = RoundedButton(
            bar, '打开文件', self.open_file, width=112, height=36,
            bg=COLORS['accent'], fg='#18130A', hover_bg=COLORS['accent_hover'],
            surface=COLORS['bg'],
        )
        self.open_button.pack(side='left')
        RoundedButton(
            bar, '打开所在目录', self.open_folder, width=132, height=36,
            bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=9, bold=False,
        ).pack(side='left', padx=(10, 0))
        RoundedButton(
            bar, '重新下载', self.redownload, width=112, height=36,
            bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=9, bold=False,
        ).pack(side='left', padx=(10, 0))
        TextButton(bar, '删除记录', self.delete_selected, bg=COLORS['bg'],
                   fg=COLORS['faint'], hover_fg=COLORS['red'], font_size=9).pack(
            side='right', padx=(0, 4))
        self._set_buttons(False)

    def _set_buttons(self, enabled: bool) -> None:
        for button in (self.open_button,):
            button.set_enabled(enabled)

    def reload(self) -> None:
        self.records = {item.get('id', ''): item for item in self.app.history.all()}
        self.tree.delete(*self.tree.get_children())
        for record in self.app.history.all():
            record_id = record.get('id', '')
            if not record_id:
                continue
            status = record.get('status', '')
            status_text = '已完成' if status == 'completed' else '未完成'
            time_text = record.get('finished_at') or record.get('created_at') or '—'
            self.tree.insert('', 'end', iid=record_id, tags=('ok',) if status == 'completed' else ('bad',),
                             values=(
                                 truncate_middle(record.get('title') or record.get('url') or '—', 74),
                                 record.get('site') or '—',
                                 status_text,
                                 time_text,
                                 human_bytes(record.get('size')),
                             ))
        count = len(self.tree.get_children())
        self.count_label.configure(text=f'{count} 条')
        if count:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor='center')
        self._set_buttons(bool(self.tree.selection()))

    def _selected(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self.records.get(selection[0])

    def open_file(self) -> None:
        record = self._selected()
        if not record:
            self.app.notify('请先选择一条记录。', 'warning')
            return
        path = record.get('filepath')
        if path:
            from pathlib import Path
            if Path(path).exists():
                open_path(path, select_file=True)
                return
        self.open_folder()

    def open_folder(self) -> None:
        record = self._selected()
        if record and record.get('filepath'):
            from pathlib import Path
            path = Path(record['filepath'])
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                open_path(folder)
                return
        self.app.open_downloads()

    def redownload(self) -> None:
        record = self._selected()
        if not record:
            self.app.notify('请先选择一条记录。', 'warning')
            return
        url = record.get('url')
        if not url:
            self.app.notify('这条记录没有可用的链接。', 'warning')
            return
        self.app.add_urls(
            url,
            mode=record.get('mode') or 'video',
            quality=record.get('quality') or 'best',
            custom_format=record.get('custom_format') or '',
            playlist=bool(record.get('playlist')),
        )

    def delete_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            self.app.notify('请先选择一条记录。', 'warning')
            return
        for record_id in selection:
            self.app.history.remove(record_id)
        self.reload()

    def clear_all(self) -> None:
        if not self.tree.get_children():
            return
        if not messagebox.askyesno('清空历史', '确定要清空全部下载历史吗？\n（不会删除已下载的文件）',
                                   parent=self):
            return
        self.app.history.clear()
        self.reload()

    def on_show(self) -> None:
        self.reload()

    def _on_select(self, _event=None) -> None:
        self._set_buttons(bool(self.tree.selection()))
