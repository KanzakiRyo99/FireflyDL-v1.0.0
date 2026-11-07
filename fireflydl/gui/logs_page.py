"""运行日志页面。"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import TYPE_CHECKING

from ..paths import LOG_FILE
from ..utils import open_path
from .theme import COLORS, font, mono
from .widgets import CheckItem, RoundedButton, RoundedFrame, TextButton

if TYPE_CHECKING:
    from .app import FireflyApp


class LogsPage(tk.Frame):
    def __init__(self, parent, app: 'FireflyApp'):
        super().__init__(parent, bg=COLORS['bg'])
        self.app = app
        self._line_count = 0
        self._file_handle = None
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_console()
        self._open_log_file()
        self.append('流萤下载器已启动，等待任务。', 'info')

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=COLORS['bg'])
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        tk.Label(bar, text='运行日志', bg=COLORS['bg'], fg=COLORS['text'],
                 font=font(12, 'bold')).pack(side='left')
        self.count_label = tk.Label(bar, text='1 行', bg=COLORS['card_alt'],
                                    fg=COLORS['muted'], font=font(8), padx=8, pady=2)
        self.count_label.pack(side='left', padx=(8, 0))
        self.auto_scroll = tk.BooleanVar(value=True)
        CheckItem(bar, '自动滚动', self.auto_scroll, bg=COLORS['bg'],
                  font_size=8).pack(side='right', padx=(0, 12))
        TextButton(bar, '清空', self.clear, bg=COLORS['bg'], fg=COLORS['faint'],
                   font_size=8).pack(side='right', padx=(0, 14))
        TextButton(bar, '复制全部', self.copy_all, bg=COLORS['bg'],
                   fg=COLORS['faint'], font_size=8).pack(side='right', padx=(0, 14))
        TextButton(bar, '打开日志文件', self.open_log_file, bg=COLORS['bg'],
                   fg=COLORS['faint'], font_size=8).pack(side='right', padx=(0, 14))

    def _build_console(self) -> None:
        frame = RoundedFrame(
            self, bg='#090B0F', border=COLORS['border'],
            radius=14, inset=6, surface=COLORS['bg'],
        )
        frame.grid(row=1, column=0, sticky='nsew', pady=(0, 10))
        frame.body.grid_rowconfigure(0, weight=1)
        frame.body.grid_columnconfigure(0, weight=1)
        self.text = tk.Text(
            frame.body, bg='#090B0F', fg=COLORS['text_soft'], relief='flat', bd=0,
            insertbackground=COLORS['accent'], font=mono(9), wrap='word',
            padx=14, pady=12, spacing1=1, spacing3=2, state='disabled',
        )
        self.text.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(frame.body, orient='vertical', command=self.text.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        self.text.configure(yscrollcommand=scroll.set)
        self.text.tag_configure('info', foreground=COLORS['text_soft'])
        self.text.tag_configure('debug', foreground=COLORS['muted'])
        self.text.tag_configure('warning', foreground=COLORS['accent'])
        self.text.tag_configure('error', foreground=COLORS['red'])
        self.text.tag_configure('success', foreground=COLORS['green'])
        self.text.tag_configure('muted', foreground=COLORS['faint'])

        bottom = tk.Frame(self, bg=COLORS['bg'])
        bottom.grid(row=2, column=0, sticky='ew')
        tk.Label(bottom, text=f'日志文件：{LOG_FILE}', bg=COLORS['bg'],
                 fg=COLORS['faint'], font=font(8)).pack(side='left')
        RoundedButton(
            bottom, '清空日志', self.clear, width=100, height=32,
            bg=COLORS['card_alt'], fg=COLORS['text_soft'],
            hover_bg=COLORS['card_hover'], border=COLORS['border'],
            surface=COLORS['bg'], font_size=8, bold=False,
        ).pack(side='right', padx=(0, 4))

    def _open_log_file(self) -> None:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._file_handle = open(LOG_FILE, 'a', encoding='utf-8')
        except OSError:
            self._file_handle = None

    def append(self, message: str, level: str = 'info') -> None:
        message = (message or '').rstrip()
        if not message:
            return
        tag = level
        lower = message.lower()
        if '[错误]' in message or 'error' in lower or '[error]' in lower:
            tag = 'error'
        elif '[警告]' in message or 'warning' in lower or '[warning]' in lower:
            tag = 'warning'
        elif '[调试]' in message or '[debug]' in message:
            tag = 'debug'
        elif level == 'success':
            tag = 'success'
        stamp = datetime.now().strftime('%H:%M:%S')
        line = f'{stamp}  {message}\n'
        try:
            self.text.configure(state='normal')
            self.text.insert('end', line, tag)
            self._line_count += 1
            if self._line_count > 4000:
                self.text.delete('1.0', '1200.0')
                self._line_count -= 1200
            if self.auto_scroll.get():
                self.text.see('end')
            self.text.configure(state='disabled')
            self.count_label.configure(text=f'{self._line_count} 行')
        except tk.TclError:
            return
        if self._file_handle:
            try:
                self._file_handle.write(line)
                self._file_handle.flush()
            except OSError:
                pass

    def clear(self) -> None:
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')
        self._line_count = 0
        self.count_label.configure(text='0 行')
        try:
            if self._file_handle:
                self._file_handle.seek(0)
                self._file_handle.truncate(0)
        except OSError:
            pass

    def copy_all(self) -> None:
        text = self.text.get('1.0', 'end').strip()
        if not text:
            self.app.notify('日志为空。', 'info')
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.app.notify('日志已复制到剪贴板。', 'success')

    def open_log_file(self) -> None:
        if LOG_FILE.exists():
            open_path(LOG_FILE, select_file=True)
        else:
            self.app.notify('日志文件还没有生成。', 'info')

    def on_show(self) -> None:
        if self.auto_scroll.get():
            self.text.see('end')

    def destroy(self) -> None:
        try:
            if self._file_handle:
                self._file_handle.close()
        except Exception:
            pass
        super().destroy()
