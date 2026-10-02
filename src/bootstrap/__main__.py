"""支持 python -m src.bootstrap。"""

from .commands import main

if __name__ == "__main__":
    raise SystemExit(main())
