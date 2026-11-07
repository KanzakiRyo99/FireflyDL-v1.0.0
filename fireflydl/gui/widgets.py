"""自绘控件与通用界面组件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .theme import COLORS, font


def surface_color(widget, fallback: str = COLORS['bg']) -> str:
    try:
        return str(widget.cget('bg'))
    except Exception:
        return fallback


def rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
                 radius: int = 8, **kwargs) -> int:
    radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1,
        x2, y1 + radius, x2, y2 - radius, x2, y2,
        x2 - radius, y2, x1 + radius, y2, x1, y2,
        x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedFrame(tk.Frame):
    """带圆角背景的容器，内容放进 ``body``。

    Tk 原生 Frame 不能圆角；这里用 Canvas 画底板，把内容 Frame 内缩到圆角
    以内，既保留布局能力，也避免方形内容盖住圆角。
    """

    def __init__(self, parent, *, bg: str = COLORS['card_alt'],
                 border: str = COLORS['border'], radius: int = 12,
                 inset: int = 6, surface: str | None = None, **kwargs):
        parent_bg = surface or surface_color(parent)
        super().__init__(parent, bg=parent_bg, bd=0, **kwargs)
        self._bg = bg
        self._border = border
        self._radius = radius
        self._surface = parent_bg
        self._canvas = tk.Canvas(self, bg=parent_bg, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=bg, bd=0)
        self.body.pack(fill='both', expand=True, padx=inset, pady=inset)
        self.bind('<Configure>', lambda _e: self._redraw())

    def _redraw(self) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self._canvas.delete('all')
        rounded_rect(self._canvas, 1, 1, width - 1, height - 1, self._radius,
                     fill=self._bg, outline=self._border, width=1)

    def set_colors(self, bg: str | None = None, border: str | None = None) -> None:
        if bg:
            self._bg = bg
            self.body.configure(bg=bg)
        if border:
            self._border = border
        self._redraw()


class RoundedButton(tk.Canvas):
    """Canvas 绘制的圆角按钮，支持 hover 与禁用状态。"""

    def __init__(
        self,
        parent,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        width: int = 132,
        height: int = 38,
        bg: str = COLORS['accent'],
        fg: str = '#16130E',
        hover_bg: str | None = None,
        border: str = '',
        radius: int = 12,
        surface: str = COLORS['bg'],
        font_size: int = 10,
        bold: bool = True,
        padx: int = 14,
    ):
        super().__init__(parent, width=width, height=height, bg=surface,
                         highlightthickness=0, bd=0, cursor='hand2')
        self._text = text
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg or bg
        self._border = border
        self._radius = radius
        self._font = font(font_size, 'bold' if bold else 'normal')
        self._enabled = True
        self._hover = False
        self._width = width
        self._height = height
        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self._draw()

    def _draw(self) -> None:
        self.delete('all')
        fill = self._bg
        fg = self._fg
        border = self._border
        if not self._enabled:
            fill = COLORS['card_alt']
            fg = COLORS['faint']
            border = COLORS['border']
        elif self._hover:
            fill = self._hover_bg
        if border:
            rounded_rect(self, 1, 1, self._width - 1, self._height - 1,
                         self._radius, fill=fill, outline=border, width=1)
        else:
            rounded_rect(self, 0, 0, self._width, self._height,
                         self._radius, fill=fill, outline='')
        self.create_text(
            self._width // 2, self._height // 2 + 1,
            text=self._text, fill=fg, font=self._font,
        )

    def _on_click(self, _event=None) -> None:
        if self._enabled and self._command:
            self._command()

    def _on_enter(self, _event=None) -> None:
        if self._enabled:
            self._hover = True
            self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.configure(cursor='hand2' if enabled else 'arrow')
        self._draw()

    def set_text(self, text: str, fg: str | None = None, bg: str | None = None) -> None:
        self._text = text
        if fg:
            self._fg = fg
        if bg:
            self._bg = bg
            self._hover_bg = bg
        self._draw()


class TextButton(tk.Label):
    """无边框的文字按钮，用于任务行内的小操作。"""

    def __init__(self, parent, text: str, command: Callable[[], None],
                 *, bg: str = COLORS['card'], fg: str = COLORS['muted'],
                 hover_fg: str = COLORS['accent'], font_size: int = 9,
                 padx: int = 4):
        super().__init__(parent, text=text, bg=bg, fg=fg, cursor='hand2',
                         font=font(font_size), padx=padx, pady=2)
        self._fg = fg
        self._hover_fg = hover_fg
        self._command = command
        self.bind('<Enter>', lambda _e: self.configure(fg=self._hover_fg))
        self.bind('<Leave>', lambda _e: self.configure(fg=self._fg))
        self.bind('<Button-1>', lambda _e: self._command())

    def set_text(self, text: str, fg: str | None = None) -> None:
        self.configure(text=text)
        if fg:
            self._fg = fg
            self.configure(fg=fg)


class Card(tk.Frame):
    def __init__(self, parent, *, padding: int = 18, bg: str = COLORS['card'],
                 border: str = COLORS['border'], radius: int = 16,
                 surface: str | None = None, **kwargs):
        parent_bg = surface or surface_color(parent)
        super().__init__(parent, bg=parent_bg, bd=0, **kwargs)
        self._bg = bg
        self._border = border
        self._radius = radius
        self._canvas = tk.Canvas(self, bg=parent_bg, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=bg, bd=0)
        # 多出的 8px 是圆角安全区，避免内容方角盖住圆角。
        self.body.pack(fill='both', expand=True, padx=padding + 8, pady=padding + 8)
        self.bind('<Configure>', lambda _e: self._redraw())

    def _redraw(self) -> None:
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self._canvas.delete('all')
        rounded_rect(self._canvas, 1, 1, width - 1, height - 1, self._radius,
                     fill=self._bg, outline=self._border, width=1)


class NavButton(tk.Canvas):
    def __init__(self, parent, key: str, label: str, icon: str,
                 command: Callable[[str], None]):
        super().__init__(parent, bg=COLORS['sidebar'], height=46,
                         highlightthickness=0, bd=0, cursor='hand2')
        self.key = key
        self._label = label
        self._icon = icon
        self._command = command
        self._active = False
        self._hover = False
        self.bind('<Configure>', lambda _e: self._paint())
        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_click(self, _event=None) -> None:
        self._command(self.key)

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._paint()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._paint()

    def _paint(self) -> None:
        self.delete('all')
        width = max(2, self.winfo_width())
        height = 44
        if self._active:
            bg = COLORS['card']
            fg = COLORS['text']
            icon_fg = COLORS['accent']
            border = COLORS['border']
        elif self._hover:
            bg = COLORS['card_alt']
            fg = COLORS['text_soft']
            icon_fg = COLORS['accent']
            border = ''
        else:
            bg = COLORS['sidebar']
            fg = COLORS['muted']
            icon_fg = COLORS['faint']
            border = ''
        if bg != COLORS['sidebar']:
            rounded_rect(self, 0, 0, width, height, 12, fill=bg,
                         outline=border, width=1 if border else 0)
        if self._active:
            rounded_rect(self, 13, 13, 16, 31, 3, fill=COLORS['accent'], outline='')
        self.create_text(31, height // 2, text=self._icon, fill=icon_fg,
                         font=(font()[0], 14))
        self.create_text(48, height // 2, text=self._label, fill=fg,
                         font=font(10), anchor='w')

    def set_active(self, active: bool) -> None:
        self._active = active
        self._paint()


class ProgressBar(tk.Canvas):
    def __init__(self, parent, *, height: int = 6, bg: str = COLORS['card'],
                 track: str = '#293142', color: str = COLORS['accent']):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self._height = height
        self._track = track
        self._color = color
        self._value = 0.0
        self._last_width = 1
        self.bind('<Configure>', lambda _e: self._draw())

    def set(self, value: float, color: str | None = None) -> None:
        self._value = max(0.0, min(100.0, float(value or 0)))
        if color:
            self._color = color
        self._draw()

    def set_color(self, color: str) -> None:
        self._color = color
        self._draw()

    def _draw(self) -> None:
        self.delete('all')
        width = max(1, self.winfo_width())
        height = self._height
        self._last_width = width
        rounded_rect(self, 0, 0, width, height, height // 2, fill=self._track, outline='')
        fill_width = int(width * self._value / 100)
        if fill_width >= 2:
            rounded_rect(self, 0, 0, max(fill_width, height), height,
                         height // 2, fill=self._color, outline='')


class ScrollFrame(tk.Frame):
    """竖向滚动容器，通过 ``.interior`` 放入内容。"""

    def __init__(self, parent, *, bg: str = COLORS['bg']):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')
        self.interior = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.interior, anchor='nw')
        self.interior.bind('<Configure>', self._on_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind('<Enter>', self._bind_wheel)
        self.canvas.bind('<Leave>', self._unbind_wheel)

    def _on_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None) -> None:
        self.canvas.bind_all('<MouseWheel>', self._on_wheel)
        self.canvas.bind_all('<Button-4>', self._on_wheel)
        self.canvas.bind_all('<Button-5>', self._on_wheel)

    def _unbind_wheel(self, _event=None) -> None:
        self.canvas.unbind_all('<MouseWheel>')
        self.canvas.unbind_all('<Button-4>')
        self.canvas.unbind_all('<Button-5>')

    def _on_wheel(self, event) -> None:
        if getattr(event, 'num', None) == 4:
            delta = -1
        elif getattr(event, 'num', None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, 'units')

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0)


class SiteBadge(tk.Canvas):
    def __init__(self, parent, text: str, color: str, *, size: int = 40,
                 bg: str = COLORS['card']):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._text = (text or '视')[:1]
        self._color = color
        self._size = size
        self._bg = bg
        self._draw()

    def set(self, text: str, color: str) -> None:
        self._text = (text or '视')[:1]
        self._color = color
        self._draw()

    def _draw(self) -> None:
        self.delete('all')
        rounded_rect(self, 0, 0, self._size, self._size, 12,
                     fill=self._color, outline='')
        self.create_text(self._size // 2, self._size // 2 + 1,
                         text=self._text, fill='#FFFFFF',
                         font=(font()[0], 15, 'bold'))


class CheckItem(tk.Frame):
    """自绘深色复选框，避免 ttk 在 Windows 主题下出现白底。"""

    def __init__(self, parent, text: str, variable: tk.BooleanVar,
                 *, bg: str = COLORS['card'], fg: str = COLORS['text_soft'],
                 font_size: int = 9, command: Callable[[], None] | None = None):
        super().__init__(parent, bg=bg, cursor='hand2')
        self.variable = variable
        self._bg = bg
        self._fg = fg
        self._hover = False
        self._command = command
        self.canvas = tk.Canvas(self, width=17, height=17, bg=bg,
                                highlightthickness=0, bd=0, cursor='hand2')
        self.canvas.pack(side='left', pady=1)
        self.label = tk.Label(self, text=text, bg=bg, fg=fg,
                              font=font(font_size), cursor='hand2', anchor='w')
        self.label.pack(side='left', padx=(7, 0))
        for widget in (self, self.canvas, self.label):
            widget.bind('<Button-1>', self._toggle)
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
        self._trace = variable.trace_add('write', lambda *_: self._draw())
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self.label.configure(fg=COLORS['text'])
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self.label.configure(fg=self._fg)
        self._draw()

    def _toggle(self, _event=None) -> None:
        self.variable.set(not bool(self.variable.get()))
        if self._command:
            self._command()

    def _draw(self) -> None:
        self.canvas.delete('all')
        selected = bool(self.variable.get())
        fill = COLORS['accent'] if selected else (
            COLORS['card_hover'] if self._hover else COLORS['card_alt'])
        outline = COLORS['accent'] if selected else COLORS['border']
        rounded_rect(self.canvas, 1, 1, 16, 16, 4, fill=fill, outline=outline, width=1)
        if selected:
            self.canvas.create_line(5, 9, 8, 12, 13, 6, fill='#17130B',
                                    width=2, capstyle='round', joinstyle='round')

    def set_enabled(self, enabled: bool) -> None:
        self.configure(cursor='hand2' if enabled else 'arrow')
        self.label.configure(cursor='hand2' if enabled else 'arrow')
        if not enabled:
            self.label.configure(fg=COLORS['faint'])


class SectionHeader(tk.Frame):
    def __init__(self, parent, title: str, subtitle: str = '',
                 *, bg: str = COLORS['bg']):
        super().__init__(parent, bg=bg)
        left = tk.Frame(self, bg=bg)
        left.pack(side='left', fill='x', expand=True)
        tk.Label(left, text=title, bg=bg, fg=COLORS['text'],
                 font=font(12, 'bold'), anchor='w').pack(anchor='w')
        if subtitle:
            tk.Label(left, text=subtitle, bg=bg, fg=COLORS['muted'],
                     font=font(9), anchor='w').pack(anchor='w', pady=(2, 0))


def divider(parent, *, bg: str = COLORS['border'], pad_y: int = 8) -> tk.Frame:
    frame = tk.Frame(parent, bg=bg, height=1)
    frame.pack(fill='x', pady=pad_y)
    return frame
