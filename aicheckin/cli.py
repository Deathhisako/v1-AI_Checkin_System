"""CLI 入口(供 pip 安装后的 `aicheckin` 命令使用)。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    # 复用仓库根 main.py 的逻辑
    import main as _main
    return _main.main()


if __name__ == "__main__":
    raise SystemExit(main())
