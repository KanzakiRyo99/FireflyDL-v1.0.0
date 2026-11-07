"""界面主题与字体。"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


COLORS = {
    'bg': '#0B0E14',
    'sidebar': '#0E1118',
    'header': '#0B0E14',
    'card': '#161B25',
    'card_alt': '#1C2230',
    'card_hover': '#232B3B',
    'border': '#2A3243',
    'border_soft': '#1D2431',
    'text': '#F3F5FA',
    'text_soft': '#D5DCE9',
    'muted': '#98A2B5',
    'faint': '#6C7689',
    'accent': '#FFB45C',
    'accent_hover': '#FFC77D',
    'accent_dark': '#DA9435',
    'accent_soft': '#2D2417',
    'teal': '#5AD7CB',
    'green': '#60D99A',
    'red': '#FF7A7A',
    'red_soft': '#321A1D',
    'blue': '#78B2FF',
    'purple': '#BE9DF8',
    'yellow': '#F7D774',
}

FONT_FAMILY = 'Noto Sans SC'
FONT_BOLD_FAMILY = 'Noto Sans SC Medium'
MONO_FAMILY = 'Cascadia Mono'


def _safe_family(family: str) -> str:
    # Tk 字体元组会按 Tcl 列表解析，含空格的字体名必须加花括号。
    if ' ' in family and not family.startswith('{'):
        return '{' + family + '}'
    return family


def font(size: int = 10, weight: str = 'normal', family: str | None = None) -> tuple:
    # 小字号在 125/150% 缩放下容易发糊，统一抬高一档，同时保持层级关系。
    size = int(size)
    if size <= 8:
        size = 9
    elif size == 9:
        size = 10
    if family:
        family_name = family
        weight_name = weight
    elif weight == 'bold':
        # Noto 的 Medium 比合成粗体柔和，适合标题和按钮。
        family_name = FONT_BOLD_FAMILY
        weight_name = 'normal'
    else:
        family_name = FONT_FAMILY
        weight_name = weight
    return (_safe_family(family_name), size, weight_name)


def mono(size: int = 9) -> tuple:
    return (_safe_family(MONO_FAMILY), size, 'normal')


def _detect_families(root: tk.Misc) -> None:
    """优先 Noto Sans SC；未安装时退回系统字体，避免换机器后显示宋体。"""
    global FONT_FAMILY, FONT_BOLD_FAMILY, MONO_FAMILY
    try:
        families = set(tkfont.families(root))
    except tk.TclError:
        families = set()
    if 'Noto Sans SC' in families:
        FONT_FAMILY = 'Noto Sans SC'
        FONT_BOLD_FAMILY = ('Noto Sans SC Medium'
                            if 'Noto Sans SC Medium' in families else 'Noto Sans SC')
    elif 'Microsoft YaHei UI' in families:
        FONT_FAMILY = 'Microsoft YaHei UI'
        FONT_BOLD_FAMILY = 'Microsoft YaHei UI'
    elif 'Segoe UI' in families:
        FONT_FAMILY = 'Segoe UI'
        FONT_BOLD_FAMILY = 'Segoe UI'
    for candidate in ('Cascadia Mono', 'Consolas', 'Courier New'):
        if candidate in families:
            MONO_FAMILY = candidate
            break


def apply_theme(root: tk.Misc) -> ttk.Style:
    _detect_families(root)
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    root.option_add('*TCombobox*Listbox.background', COLORS['card_alt'])
    root.option_add('*TCombobox*Listbox.foreground', COLORS['text'])
    root.option_add('*TCombobox*Listbox.selectBackground', COLORS['accent'])
    root.option_add('*TCombobox*Listbox.selectForeground', '#151515')
    root.option_add('*TCombobox*Listbox.font', font(10))

    style.configure('.', background=COLORS['bg'], foreground=COLORS['text'],
                    font=font(10), borderwidth=0)
    style.configure('TFrame', background=COLORS['bg'])
    style.configure('Sidebar.TFrame', background=COLORS['sidebar'])
    style.configure('Card.TFrame', background=COLORS['card'])
    style.configure('CardAlt.TFrame', background=COLORS['card_alt'])
    style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'])
    style.configure('Card.TLabel', background=COLORS['card'], foreground=COLORS['text'])
    style.configure('Muted.TLabel', background=COLORS['bg'], foreground=COLORS['muted'])
    style.configure('CardMuted.TLabel', background=COLORS['card'], foreground=COLORS['muted'])
    style.configure('Title.TLabel', background=COLORS['bg'], foreground=COLORS['text'],
                    font=font(18, 'bold'))
    style.configure('H2.TLabel', background=COLORS['bg'], foreground=COLORS['text'],
                    font=font(12, 'bold'))
    style.configure('CardH2.TLabel', background=COLORS['card'], foreground=COLORS['text'],
                    font=font(12, 'bold'))
    style.configure('Accent.TLabel', background=COLORS['bg'], foreground=COLORS['accent'])
    style.configure('Teal.TLabel', background=COLORS['bg'], foreground=COLORS['teal'])

    # 输入框
    style.configure(
        'TEntry',
        fieldbackground=COLORS['card_alt'],
        foreground=COLORS['text'],
        insertcolor=COLORS['accent'],
        bordercolor=COLORS['border'],
        lightcolor=COLORS['border'],
        darkcolor=COLORS['border'],
        padding=(10, 8),
        relief='flat',
    )
    style.map('TEntry',
              bordercolor=[('focus', COLORS['accent'])],
              lightcolor=[('focus', COLORS['accent'])],
              darkcolor=[('focus', COLORS['accent'])],
              fieldbackground=[('disabled', COLORS['card'])])

    style.configure(
        'Seamless.TEntry',
        fieldbackground=COLORS['card_alt'],
        foreground=COLORS['text'],
        insertcolor=COLORS['accent'],
        bordercolor=COLORS['card_alt'],
        lightcolor=COLORS['card_alt'],
        darkcolor=COLORS['card_alt'],
        padding=(4, 4),
        relief='flat',
    )
    style.map('Seamless.TEntry',
              fieldbackground=[('readonly', COLORS['card_alt'])],
              bordercolor=[('focus', COLORS['card_alt'])],
              lightcolor=[('focus', COLORS['card_alt'])],
              darkcolor=[('focus', COLORS['card_alt'])])

    style.configure(
        'TCombobox',
        fieldbackground=COLORS['card_alt'],
        background=COLORS['card_alt'],
        foreground=COLORS['text'],
        arrowcolor=COLORS['muted'],
        bordercolor=COLORS['border'],
        lightcolor=COLORS['border'],
        darkcolor=COLORS['border'],
        padding=(9, 7),
        relief='flat',
    )
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', COLORS['card_alt']), ('disabled', COLORS['card'])],
        background=[('readonly', COLORS['card_alt']), ('active', COLORS['card_hover']),
                    ('disabled', COLORS['card'])],
        foreground=[('readonly', COLORS['text']), ('disabled', COLORS['faint'])],
        selectbackground=[('readonly', COLORS['card_alt'])],
        selectforeground=[('readonly', COLORS['text'])],
        bordercolor=[('focus', COLORS['accent'])],
        arrowcolor=[('active', COLORS['accent'])],
    )

    style.configure(
        'TSpinbox',
        fieldbackground=COLORS['card_alt'],
        background=COLORS['card_alt'],
        foreground=COLORS['text'],
        arrowcolor=COLORS['muted'],
        bordercolor=COLORS['border'],
        lightcolor=COLORS['border'],
        darkcolor=COLORS['border'],
        padding=(8, 6),
    )

    style.configure('TCheckbutton', background=COLORS['card'], foreground=COLORS['text_soft'],
                    font=font(9), focuscolor=COLORS['card'], indicatorcolor=COLORS['card_alt'],
                    bordercolor=COLORS['border'])
    style.map('TCheckbutton',
              background=[('active', COLORS['card'])],
              foreground=[('active', COLORS['text'])],
              indicatorcolor=[('selected', COLORS['accent']), ('active', COLORS['card_hover'])])
    style.configure('Page.TCheckbutton', background=COLORS['bg'], foreground=COLORS['text_soft'])
    style.map('Page.TCheckbutton', background=[('active', COLORS['bg'])])

    style.configure('TRadiobutton', background=COLORS['card'], foreground=COLORS['text_soft'],
                    font=font(9), focuscolor=COLORS['card'])
    style.map('TRadiobutton', background=[('active', COLORS['card'])],
              foreground=[('active', COLORS['text'])])

    # 表格
    style.configure(
        'Treeview',
        background=COLORS['card'],
        fieldbackground=COLORS['card'],
        foreground=COLORS['text_soft'],
        bordercolor=COLORS['border'],
        lightcolor=COLORS['card'],
        darkcolor=COLORS['card'],
        rowheight=38,
        font=font(10),
        relief='flat',
    )
    style.map('Treeview',
              background=[('selected', COLORS['accent_soft'])],
              foreground=[('selected', COLORS['accent'])])
    style.configure(
        'Treeview.Heading',
        background=COLORS['card_alt'],
        foreground=COLORS['muted'],
        bordercolor=COLORS['border'],
        lightcolor=COLORS['card_alt'],
        darkcolor=COLORS['card_alt'],
        relief='flat',
        font=font(9, 'bold'),
        padding=(10, 9),
    )
    style.map('Treeview.Heading', background=[('active', COLORS['card_hover'])],
              foreground=[('active', COLORS['text'])])
    style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])

    # 滚动条
    style.configure(
        'Vertical.TScrollbar',
        background=COLORS['border'],
        troughcolor=COLORS['bg'],
        bordercolor=COLORS['bg'],
        arrowcolor=COLORS['muted'],
        lightcolor=COLORS['border'],
        darkcolor=COLORS['border'],
        gripcount=0,
        arrowsize=12,
        width=9,
    )
    style.map('Vertical.TScrollbar', background=[('active', COLORS['faint'])])
    style.configure('Horizontal.TScrollbar', background=COLORS['border'],
                    troughcolor=COLORS['bg'], bordercolor=COLORS['bg'],
                    arrowcolor=COLORS['muted'], lightcolor=COLORS['border'],
                    darkcolor=COLORS['border'], width=9)

    # 进度条（备用，主要使用自绘进度条）
    style.configure('Accent.Horizontal.TProgressbar',
                    troughcolor=COLORS['card_alt'],
                    background=COLORS['accent'],
                    bordercolor=COLORS['card_alt'],
                    lightcolor=COLORS['accent'],
                    darkcolor=COLORS['accent'],
                    thickness=6)

    style.configure('TNotebook', background=COLORS['bg'], borderwidth=0)
    style.configure('TNotebook.Tab', background=COLORS['card'], foreground=COLORS['muted'],
                    padding=(18, 8), borderwidth=0)
    style.map('TNotebook.Tab', background=[('selected', COLORS['card_alt'])],
              foreground=[('selected', COLORS['accent'])])

    try:
        default = tkfont.nametofont('TkDefaultFont')
        default.configure(family=FONT_FAMILY, size=10)
        text_font = tkfont.nametofont('TkTextFont')
        text_font.configure(family=FONT_FAMILY, size=10)
        fixed = tkfont.nametofont('TkFixedFont')
        fixed.configure(family=MONO_FAMILY, size=9)
    except tk.TclError:
        pass
    return style
