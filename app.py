#!/usr/bin/env python3
"""FireflyDL 启动入口。

默认启动图形界面；传入 ``--cli`` 或任意命令行参数时转交 CLI。

    python app.py                 # GUI
    python app.py --cli URL ...   # CLI
    python app.py --version
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    args = sys.argv[1:]
    if '--cli' in args:
        args = [arg for arg in args if arg != '--cli']
        from fireflydl.cli import main as cli_main
        return cli_main(args)
    if args and args[0] in {'-h', '--help', '--version', '--update', '--list-sites'}:
        from fireflydl.cli import main as cli_main
        return cli_main(args)
    try:
        from fireflydl.gui.app import FireflyApp
    except Exception as exc:
        try:
            import tkinter.messagebox as messagebox
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                'FireflyDL 启动失败',
                f'无法加载图形界面：\n{exc}\n\n'
                '请先运行：pip install -U yt-dlp pillow mutagen\n'
                '也可以使用命令行：python app.py --cli URL',
            )
            root.destroy()
        except Exception:
            print(f'FireflyDL 启动失败：{exc}', file=sys.stderr)
        return 1
    FireflyApp().run()
    return 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
