#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""启动 run_union_realtime.py 的临时入口。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REALTIME_SCRIPT = ROOT / "scripts" / "run_union_realtime.py"


def build_realtime_command() -> list[str]:
    """构造实时脚本启动命令。"""
    return [
        sys.executable,
        "-u",
        str(REALTIME_SCRIPT),
        "--debug",
        "--plot",
    ]


def start_run_union_realtime_in_new_terminal() -> subprocess.Popen:
    """在新终端中启动电磁频谱态势实时模块。"""
    if not REALTIME_SCRIPT.exists():
        raise FileNotFoundError(f"未找到实时脚本：{REALTIME_SCRIPT}")

    command = build_realtime_command()

    if sys.platform == "win32":
        command_line = subprocess.list2cmdline(command)
        process = subprocess.Popen(
            ["cmd", "/k", command_line],
            cwd=str(ROOT),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
    else:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
        )

    print(f"电磁频谱态势实时模块已启动，PID={process.pid}")
    print(f"启动命令: {subprocess.list2cmdline(command)}")
    return process


def main() -> int:
    start_run_union_realtime_in_new_terminal()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
