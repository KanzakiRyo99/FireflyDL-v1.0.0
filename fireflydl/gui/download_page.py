"""下载中心页面。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ..config import MODE_CHOICES, QUALITY_CHOICES
from ..models import DownloadTask
from ..utils import human_bytes, truncate_middle
from .theme import COLORS, font
from .widgets import (
    Card, CheckItem, ProgressBar, RoundedButton, RoundedFrame, ScrollFrame,
    SiteBadge, TextButton,
)

if TYPE_CHECKING:
    from .app import FireflyApp


class TaskRow(RoundedFrame):
    def __init__(self, parent, app: 'FireflyApp', task: DownloadTask):
        super().__init__(parent, bg=COLORS['card'], border=COLORS['border'],
                         radius=14, inset=8, surface=COLORS['card'])
        self.app = app
        self.task = task
        self._status = ''
        self._site = ''
        content = self.body
        content.grid_columnconfigure(1, weight=1)
        content.grid_columnconfigure(2, minsize=92)
        content.grid_columnconfigure(3, minsize=116)

        self.badge = SiteBadge(content, task.site, task.site_color, size=42,
                               bg=COLORS['card'])
        self.badge.grid(row=0, column=0, rowspan=2, padx=(6, 12),
                        pady=(7, 0), sticky='n')

        self.title_label = tk.Label(
            content, text='', bg=COLORS['card'], fg=COLORS['text'],
            font=font(10, 'bold'), anchor='w', justify='left',
        )
        self.title_label.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=(7, 0))

        self.percent_label = tk.Label(
            content, text='', bg=COLORS['card'], fg=COLORS['accent'],
            font=font(11, 'bold'), anchor='e',
        )
        self.percent_label.grid(row=0, column=2, sticky='e', padx=(0, 8), pady=(7, 0))

        self.meta_label = tk.Label(
            content, text='', bg=COLORS['card'], fg=COLORS['muted'], font=font(8),
            anchor='w',
        )
        self.meta_label.grid(row=1, column=1, sticky='ew', padx=(0, 8), pady=(2, 6))

        self.state_label = tk.Label(
            content, text='', bg=COLORS['card'], fg=COLORS['muted'], font=font(8),
            anchor='e',
        )
        self.state_label.grid(row=1, column=2, sticky='e', padx=(0, 8), pady=(2, 6))

        self.actions = tk.Frame(content, bg=COLORS['card'])
        self.actions.grid(row=0, column=3, rowspan=2, sticky='e',
                          padx=(0, 8), pady=(7, 0))
        self.action_buttons: list[TextButton] = []

        self.progress = ProgressBar(content, height=6, bg=COLORS['card'])
        self.progress.grid(row=2, column=1, columnspan=3, sticky='ew',
                           padx=(0, 10), pady=(0, 9))

        for widget in (self, content, self.title_label, self.meta_label,
                       self.percent_label, self.state_label, self.badge):
            widget.bind('<Double-Button-1>', self._open)
        self.update_view(force=True)

    def _clear_actions(self) -> None:
        for button in self.action_buttons:
            button.destroy()
        self.action_buttons.clear()

    def _add_action(self, text: str, command, fg: str = COLORS['muted'],
                    hover: str = COLORS['accent']) -> None:
        button = TextButton(self.actions, text, command, bg=COLORS['card'],
                            fg=fg, hover_fg=hover, font_size=8)
        button.pack(side='left', padx=2)
        self.action_buttons.append(button)

    def _build_actions(self) -> None:
        self._clear_actions()
        task = self.task
        if task.is_active:
            self._add_action('暂停', lambda: self.app.manager.pause(task.id))
            self._add_action('取消', lambda: self.app.manager.cancel(task.id),
                             hover=COLORS['red'])
        elif task.status == 'queued':
            self._add_action('暂停', lambda: self.app.manager.pause(task.id))
            self._add_action('取消', lambda: self.app.manager.cancel(task.id),
                             hover=COLORS['red'])
        elif task.status == 'paused':
            self._add_action('继续', lambda: self.app.manager.resume(task.id),
                             fg=COLORS['accent'])
            self._add_action('移除', lambda: self.app.manager.remove(task.id),
                             hover=COLORS['red'])
        elif task.status == 'completed':
            self._add_action('打开', self._open, fg=COLORS['teal'])
            self._add_action('移除', lambda: self.app.manager.remove(task.id),
                             hover=COLORS['red'])
        elif task.status in {'error', 'cancelled'}:
            self._add_action('重试', lambda: self.app.manager.retry(task.id),
                             fg=COLORS['accent'])
            self._add_action('移除', lambda: self.app.manager.remove(task.id),
                             hover=COLORS['red'])

    def _open(self, _event=None) -> None:
        task = self.task
        if task.filepath:
            from ..utils import open_path
            if not open_path(task.filepath, select_file=True):
                self.app.notify('文件可能已被移动或删除。', 'warning')
        elif task.status == 'completed':
            self.app.open_downloads()

    def update_view(self, force: bool = False) -> None:
        task = self.task
        title = truncate_middle(task.display_title, 64)
        if self.title_label.cget('text') != title:
            self.title_label.configure(text=title)
        if self._site != task.site:
            self.badge.set(task.site, task.site_color)
            self._site = task.site
        meta = task.meta_text
        if task.filename:
            meta = f'{meta}  ·  {task.filename}'
        meta = truncate_middle(meta, 88)
        if self.meta_label.cget('text') != meta:
            self.meta_label.configure(text=meta)

        self.percent_label.configure(text=task.progress_text)
        state = task.speed_text
        if task.status == 'completed':
            state = f'已保存 · {human_bytes(task.total_bytes)}'
        elif task.status == 'error':
            state = truncate_middle(task.error or '下载失败', 46)
        elif task.status == 'paused':
            state = f'已暂停 · {human_bytes(task.downloaded_bytes)}'
        elif task.status == 'cancelled':
            state = '已取消'
        state = truncate_middle(state, 52)
        if self.state_label.cget('text') != state:
            self.state_label.configure(text=state)

        color = COLORS['accent']
        if task.status == 'completed':
            color = COLORS['green']
        elif task.status in {'error', 'cancelled'}:
            color = COLORS['red']
        elif task.status == 'paused':
            color = COLORS['yellow']
        elif task.status == 'processing':
            color = COLORS['teal']
        elif task.status == 'parsing':
            color = COLORS['blue']
        self.percent_label.configure(fg=color)
        state_color = COLORS['muted']
        if task.status == 'error':
            state_color = COLORS['red']
        elif task.status == 'completed':
            state_color = COLORS['green']
        elif task.status == 'paused':
            state_color = COLORS['yellow']
        self.state_label.configure(fg=state_color)
        self.progress.set(task.progress, color)

        if force or task.status != self._status:
            self._status = task.status
            self._build_actions()


class DownloadPage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self.rows: dict[str, TaskRow] = {}
        self._placeholder_active = False
        self._building = True
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_input()
        self._build_toolbar()
        self._build_list()
        self._building = False

    # ---------- 输入区 ----------
    def _build_input(self) -> None:
        card = Card(self, padding=16)
        card.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        top = tk.Frame(card.body, bg=COLORS['card'])
        top.pack(fill='x')
        tk.Label(top, text='粘贴视频链接', bg=COLORS['card'], fg=COLORS['text'],
                 font=font(11, 'bold')).pack(side='left')
        tk.Label(top, text='  支持分享文案 / 多条链接 / BV 号', bg=COLORS['card'],
                 fg=COLORS['faint'], font=font(8)).pack(side='left', pady=(2, 0))
        TextButton(top, '清空', self.clear_input, bg=COLORS['card'],
                   fg=COLORS['faint'], hover_fg=COLORS['text'], font_size=8).pack(side='right')
        TextButton(top, '粘贴', self.paste_clipboard, bg=COLORS['card'],
                   fg=COLORS['muted'], hover_fg=COLORS['accent'], font_size=8).pack(
            side='right', padx=(0, 6))

        text_wrap = RoundedFrame(
            card.body, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=14, inset=6, surface=COLORS['card'],
        )
        text_wrap.pack(fill='x', pady=(9, 11))
        self.url_text = tk.Text(
            text_wrap.body, height=3, bg=COLORS['card_alt'], fg=COLORS['faint'],
            insertbackground=COLORS['accent'], relief='flat', bd=0,
            font=font(10), wrap='word', padx=10, pady=7, spacing1=1, spacing3=2,
        )
        self.url_text.pack(fill='x')
        self.url_text.bind('<FocusIn>', self._on_focus_in)
        self.url_text.bind('<FocusOut>', self._on_focus_out)
        self.url_text.bind('<Control-Return>', lambda _e: self.add_to_queue())
        self._show_placeholder()

        controls = tk.Frame(card.body, bg=COLORS['card'])
        controls.pack(fill='x')
        tk.Label(controls, text='模式', bg=COLORS['card'], fg=COLORS['muted'],
                 font=font(8)).pack(side='left')
        self.mode_var = tk.StringVar()
        mode_box = RoundedFrame(
            controls, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=10, inset=5, surface=COLORS['card'],
        )
        mode_box.pack(side='left', padx=(6, 14))
        self.mode_combo = ttk.Combobox(
            mode_box.body, textvariable=self.mode_var, state='readonly',
            values=list(MODE_CHOICES.values()), width=13, font=font(9),
        )
        self.mode_combo.pack(fill='x')
        self.mode_combo.bind('<<ComboboxSelected>>', lambda _e: self._mode_changed())

        tk.Label(controls, text='清晰度', bg=COLORS['card'], fg=COLORS['muted'],
                 font=font(8)).pack(side='left')
        self.quality_var = tk.StringVar()
        quality_box = RoundedFrame(
            controls, bg=COLORS['card_alt'], border=COLORS['border'],
            radius=10, inset=5, surface=COLORS['card'],
        )
        quality_box.pack(side='left', padx=(6, 14))
        self.quality_combo = ttk.Combobox(
            quality_box.body, textvariable=self.quality_var, state='readonly',
            values=list(QUALITY_CHOICES.values()), width=12, font=font(9),
        )
        self.quality_combo.pack(fill='x')

        self.playlist_var = tk.BooleanVar(value=self.app.settings.playlist)
        self.playlist_check = CheckItem(
            controls, '下载整个合集', self.playlist_var,
            bg=COLORS['card'], font_size=8,
        )
        self.playlist_check.pack(side='left', padx=(0, 12))

        self.add_button = RoundedButton(
            controls, '添加到队列  →', self.add_to_queue,
            width=150, height=38, bg=COLORS['accent'], fg='#18130A',
            hover_bg=COLORS['accent_hover'], surface=COLORS['card'],
        )
        self.add_button.pack(side='right')

        self.sync_settings()
        self._mode_changed(silent=True)

    def _show_placeholder(self) -> None:
        self._placeholder_active = True
        self.url_text.delete('1.0', 'end')
        self.url_text.insert('1.0',
                             '粘贴视频链接或分享文案，支持 B站 / 抖音 / 快手 / YouTube / TikTok…\n'
                             '多条链接请用换行分隔；也可以直接输入 BV 号。')
        self.url_text.configure(fg=COLORS['faint'])

    def _on_focus_in(self, _event=None) -> None:
        if self._placeholder_active:
            self.url_text.delete('1.0', 'end')
            self.url_text.configure(fg=COLORS['text'])
            self._placeholder_active = False

    def _on_focus_out(self, _event=None) -> None:
        if not self._placeholder_active and not self.url_text.get('1.0', 'end').strip():
            self._show_placeholder()

    def _mode_changed(self, silent: bool = False) -> None:
        mode = self._selected_mode()
        state = 'disabled' if mode == 'audio' else 'readonly'
        try:
            self.quality_combo.configure(state=state)
        except tk.TclError:
            pass

    def _selected_mode(self) -> str:
        label = self.mode_var.get()
        for key, value in MODE_CHOICES.items():
            if value == label:
                return key
        return self.app.settings.default_mode

    def _selected_quality(self) -> str:
        label = self.quality_var.get()
        for key, value in QUALITY_CHOICES.items():
            if value == label:
                return key
        return self.app.settings.default_quality

    def sync_settings(self) -> None:
        settings = self.app.settings
        try:
            self.mode_var.set(MODE_CHOICES.get(settings.default_mode, MODE_CHOICES['video']))
            self.quality_var.set(QUALITY_CHOICES.get(settings.default_quality, QUALITY_CHOICES['best']))
            self.playlist_var.set(settings.playlist)
        except Exception:
            pass
        self._mode_changed(silent=True)

    def fill_input(self, url: str) -> None:
        if self._placeholder_active:
            self.url_text.delete('1.0', 'end')
            self.url_text.configure(fg=COLORS['text'])
            self._placeholder_active = False
        current = self.url_text.get('1.0', 'end').strip()
        if current and url not in current:
            self.url_text.insert('end', '\n' + url)
        else:
            self.url_text.delete('1.0', 'end')
            self.url_text.insert('1.0', url)
        self.url_text.focus_set()

    def clear_input(self) -> None:
        self.url_text.delete('1.0', 'end')
        if self.focus_get() is self.url_text:
            # 光标还在输入框里时不要塞入占位文字，否则用户一输入就会追加到占位内容后面。
            self.url_text.configure(fg=COLORS['text'])
            self._placeholder_active = False
        else:
            self._placeholder_active = False
            self._show_placeholder()

    def paste_clipboard(self) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = ''
        if text:
            self.fill_input(text.strip())
        else:
            self.app.notify('剪贴板里没有文本。', 'warning')

    def add_to_queue(self) -> None:
        if self._placeholder_active:
            self.app.notify('请先粘贴视频链接。', 'warning')
            return
        text = self.url_text.get('1.0', 'end').strip()
        if not text:
            self.app.notify('请先粘贴视频链接。', 'warning')
            return
        tasks = self.app.add_urls(
            text,
            mode=self._selected_mode(),
            quality=self._selected_quality(),
            playlist=self.playlist_var.get(),
        )
        if tasks:
            self.clear_input()
            self.url_text.focus_set()

    # ---------- 工具栏与队列 ----------
    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=1, column=0, sticky='ew', pady=(0, 8))
        left = tk.Frame(bar, bg=COLORS['bg'])
        left.pack(side='left')
        tk.Label(left, text='下载队列', bg=COLORS['bg'], fg=COLORS['text'],
                 font=font(11, 'bold')).pack(side='left')
        self.count_label = tk.Label(left, text='0', bg=COLORS['card_alt'],
                                    fg=COLORS['muted'], font=font(8),
                                    padx=7, pady=2)
        self.count_label.pack(side='left', padx=(8, 0))
        self.queue_hint = tk.Label(left, text='', bg=COLORS['bg'], fg=COLORS['faint'],
                                   font=font(8))
        self.queue_hint.pack(side='left', padx=(10, 0))

        right = tk.Frame(bar, bg=COLORS['bg'])
        right.pack(side='right')
        TextButton(right, '全部开始', self._resume_all, bg=COLORS['bg'],
                   fg=COLORS['muted'], hover_fg=COLORS['accent'], font_size=8).pack(
            side='left', padx=(0, 12))
        TextButton(right, '全部暂停', self._pause_all, bg=COLORS['bg'],
                   fg=COLORS['muted'], hover_fg=COLORS['accent'], font_size=8).pack(
            side='left', padx=(0, 12))
        TextButton(right, '清空已完成', self._clear_finished, bg=COLORS['bg'],
                   fg=COLORS['faint'], hover_fg=COLORS['red'], font_size=8).pack(side='left')

    def _build_list(self) -> None:
        self.list_card = tk.Frame(self, bg=COLORS['card'],
                                  highlightbackground=COLORS['border'], highlightthickness=1)
        self.list_card.grid(row=2, column=0, sticky='nsew')
        self.list_card.grid_rowconfigure(0, weight=1)
        self.list_card.grid_columnconfigure(0, weight=1)
        self.list_scroll = ScrollFrame(self.list_card, bg=COLORS['card'])
        self.list_scroll.grid(row=0, column=0, sticky='nsew', padx=(10, 4), pady=10)
        self.list_scroll.scrollbar.configure(style='Vertical.TScrollbar')
        self.list_scroll.interior.configure(bg=COLORS['card'])
        self.list_scroll.canvas.configure(bg=COLORS['card'])

        self.empty = tk.Frame(self.list_scroll.interior, bg=COLORS['card'])
        self.empty.pack(fill='both', expand=True, pady=68)
        tk.Label(self.empty, text='✦', bg=COLORS['card'], fg=COLORS['accent'],
                 font=font(30)).pack()
        tk.Label(self.empty, text='队列里还没有任务', bg=COLORS['card'], fg=COLORS['text_soft'],
                 font=font(11, 'bold')).pack(pady=(8, 2))
        tk.Label(self.empty, text='粘贴链接并点击「添加到队列」，或使用页面解析选择清晰度。',
                 bg=COLORS['card'], fg=COLORS['faint'], font=font(9)).pack()

    def _update_counts(self) -> None:
        tasks = self.app.manager.tasks()
        active = sum(1 for task in tasks if task.is_active)
        done = sum(1 for task in tasks if task.status == 'completed')
        failed = sum(1 for task in tasks if task.status in {'error', 'cancelled'})
        try:
            self.count_label.configure(text=str(len(tasks)))
            parts = []
            if active:
                parts.append(f'{active} 个进行中')
            if done:
                parts.append(f'{done} 个已完成')
            if failed:
                parts.append(f'{failed} 个失败/取消')
            self.queue_hint.configure(text='  ·  '.join(parts) if parts else '等待添加任务',
                                      fg=COLORS['red'] if failed else COLORS['faint'])
        except tk.TclError:
            pass
        if tasks:
            self.empty.pack_forget()
        else:
            self.empty.pack(fill='both', expand=True, pady=68)

    def on_task_event(self, kind: str, task: DownloadTask) -> None:
        if kind == 'removed':
            row = self.rows.pop(task.id, None)
            if row is not None:
                row.destroy()
            self._update_counts()
            return
        row = self.rows.get(task.id)
        if row is None:
            row = TaskRow(self.list_scroll.interior, self.app, task)
            row.pack(fill='x', pady=(0, 9))
            self.rows[task.id] = row
            self.empty.pack_forget()
        else:
            row.update_view(force=(kind == 'completed'))
        self._update_counts()

    def _pause_all(self) -> None:
        count = self.app.manager.pause_all()
        if count:
            self.app.notify(f'已暂停 {count} 个任务。', 'info')
        else:
            self.app.notify('当前没有可以暂停的任务。', 'warning')

    def _resume_all(self) -> None:
        count = self.app.manager.resume_all()
        if count:
            self.app.notify(f'已继续 {count} 个任务。', 'success')
        else:
            self.app.notify('没有等待继续的任务。', 'warning')

    def _clear_finished(self) -> None:
        count = self.app.manager.clear_finished()
        if count:
            self.app.notify(f'已移除 {count} 个已结束任务。', 'info')
        else:
            self.app.notify('没有已结束的任务。', 'warning')

    def on_show(self) -> None:
        self._update_counts()
