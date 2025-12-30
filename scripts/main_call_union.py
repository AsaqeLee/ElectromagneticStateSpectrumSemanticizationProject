#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""主程序示例：在代码里调用 scripts.run_union

目的：
- 给出一个“主函数 main()”示例，演示如何在主程序中调用 `scripts/run_union.py`；
- 将 `run_union.main()` 的返回值透传给调用方（约定：成功返回 11）。

用法（在仓库根目录执行）：

    python scripts/main_call_union.py

注意：
- 若你把它当子进程跑，退出码会是 11（非 0）。某些调度系统会把非 0 视为失败；
  这取决于你对“11”的真实语义约定。
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_console_utf8() -> None:
    """Windows 控制台 UTF-8 兜底，避免中文输出触发编码异常。"""
    if sys.platform != "win32":  # pragma: no cover
        return

    import io

    try:
        if hasattr(sys.stdout, "buffer") and not sys.stdout.closed:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer") and not sys.stderr.closed:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    """主入口：调用 run_union.main() 并透传返回码。"""
    _ensure_console_utf8()

    # 确保从任意工作目录执行时，都能 import 到项目代码
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    try:
        import scripts.run_union as run_union
    except Exception as exc:
        print(f"[ERROR] 导入 scripts.run_union 失败：{exc}")
        return 1

    print("=" * 80)
    print("主程序示例：开始调用 scripts.run_union.main()")
    print("=" * 80)

    try:
        ret = int(run_union.main())
    except Exception as exc:
        print(f"[ERROR] run_union 执行失败：{exc}")
        return 1

    if ret == 11:
        print(f"[OK] run_union 执行成功，返回码={ret}")
    else:
        print(f"[WARN] run_union 返回非预期返回码={ret}（预期 11）")

    return ret


if __name__ == "__main__":
    sys.exit(main())

