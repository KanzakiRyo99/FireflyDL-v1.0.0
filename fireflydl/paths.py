"""应用路径与资源定位。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_FOLDER = 'FireflyDL'


def app_data_dir() -> Path:
    base = os.environ.get('APPDATA') or os.environ.get('XDG_CONFIG_HOME')
    if base:
        path = Path(base) / APP_FOLDER
    else:
        path = Path.home() / f'.{APP_FOLDER.lower()}'
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = app_data_dir()
CONFIG_FILE = DATA_DIR / 'settings.json'
HISTORY_FILE = DATA_DIR / 'history.json'
ARCHIVE_FILE = DATA_DIR / 'downloaded.txt'
LOG_FILE = DATA_DIR / 'fireflydl.log'


def resource_root() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def default_download_dir() -> Path:
    videos = Path.home() / 'Videos'
    if videos.is_dir():
        return videos / APP_FOLDER
    return Path.home() / 'Downloads' / APP_FOLDER
