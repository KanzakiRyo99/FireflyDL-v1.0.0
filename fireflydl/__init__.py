"""FireflyDL · 流萤下载器。

一个以 yt-dlp 为内核、带桌面 GUI 与命令行双模式的多站点视频下载与页面解析工具。
"""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = '1.0.0'
APP_NAME = 'FireflyDL'
APP_NAME_CN = '流萤下载器'
APP_TAGLINE = '把喜欢的光影，留在本地'


def _project_root() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def ensure_plugin_path() -> Path:
    """把项目根目录加入 sys.path，让 yt-dlp 能发现 ``yt_dlp_plugins``。

    必须在创建 YoutubeDL 实例之前调用；本包在 import 时已自动执行一次。
    """
    root = _project_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


ensure_plugin_path()
