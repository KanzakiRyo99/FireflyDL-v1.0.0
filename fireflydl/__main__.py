"""支持 ``python -m fireflydl`` 运行。"""

from .cli import main

if __name__ == '__main__':
    raise SystemExit(main())
