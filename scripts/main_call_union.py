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
import time
from pathlib import Path


def _ensure_console_utf8() -> None:
    """Windows 控制台 UTF-8 兜底，避免中文输出触发编码异常。"""
    if sys.platform != "win32":  # pragma: no cover
        return

    def _try_reconfigure(stream) -> None:
        if stream is None:
            return
        if getattr(stream, "closed", False):
            return
        if not hasattr(stream, "reconfigure"):
            return
        try:
            stream.reconfigure(
                encoding="utf-8",
                errors="replace",
                line_buffering=True,
                write_through=True,
            )
        except Exception:
            return

    _try_reconfigure(sys.stdout)
    _try_reconfigure(sys.stderr)


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

    runs = 5
    for idx in range(1, runs + 1):
        print("-" * 80)
        print(f"第 {idx}/{runs} 次调用 run_union.main()")
        print("-" * 80)
        try:
            ret = int(run_union.main())
            
        except Exception as exc:
            print(f"[ERROR] 第 {idx} 次 run_union 执行失败：{exc}")
            return 1

        if ret != 11:
            print(f"[ERROR] 第 {idx} 次 run_union 返回非预期返回码={ret}（预期 11）")
            return 1

        print(f"[OK] 第 {idx} 次 run_union 执行成功，返回码={ret}")

        if idx != runs:
            time.sleep(1)

    print("=" * 80)
    print(f"[OK] 连续调用完成：共 {runs} 次，均返回 11")
    print("=" * 80)
    return 11


if __name__ == "__main__":
    sys.exit(main())
