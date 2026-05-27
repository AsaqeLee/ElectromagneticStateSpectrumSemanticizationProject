#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实时输入测试驱动。

用途：
- 为 `scripts/run_union_realtime.py` 准备一套独立的测试输入；
- 周期性更新语义 TXT 文件，并切换 IQ `.bin` 输入；
- 可选地顺手拉起实时脚本作为子进程，方便一键联调。

设计约束：
- 不污染默认 `data_segment/` 与 `data_semantic/`；
- 默认在 `output/realtime_input_test/` 下建立沙箱；
- 语义同时写入：
  1) `semantic.txt`，便于人工查看；
  2) `semantic_YYYY-MM-DD_HH-MM-SS.txt`，用于 freshness 规则；
- IQ 目录名只在脚本启动时生成一次时间戳，这意味着：
  - 启动后前 3 秒内，IQ 目录会被视为“新鲜”；
  - 3 秒后若不重启实时脚本，IQ freshness 会自然过期；
  - 这正好可以测试“新鲜时并集 / 过期后回退语义”的切换逻辑。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_IQ_DIR = ROOT / "data_segment"
DEFAULT_SANDBOX_ROOT = ROOT / "output" / "realtime_input_test"


def _ensure_console_utf8() -> None:
    if sys.platform != "win32":
        return

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or getattr(stream, "closed", False):
            continue
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


def _now_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _list_iq_samples(source_iq_dir: Path) -> List[Path]:
    samples = sorted(source_iq_dir.glob("*.bin"))
    if not samples:
        raise FileNotFoundError(f"未找到 IQ 样本：{source_iq_dir}")
    return samples


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _safe_link_or_copy(src: Path, dst: Path) -> None:
    """优先硬链接，失败再复制。

    这样同盘测试时几乎零成本；若文件系统/权限不支持，再退回 copy2。
    """
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _render_semantic_text(update_index: int) -> str:
    """生成一个简单但持续变化的语义 TXT。"""
    base_start = 80 + (update_index * 35) % 300
    second_start = 500 + (update_index * 60) % 500
    first_jnr = 3 + (update_index % 5) * 2
    second_jnr = 8 + (update_index % 4) * 3
    lines = [
        "# 自动生成的实时语义测试输入",
        "num_bins=2471",
        "[jammer_regions]",
        f"{base_start},{base_start + 20},{first_jnr}",
        f"{second_start},{second_start + 45},{second_jnr}",
        "",
    ]
    return "\n".join(lines)


def _write_semantic_files(semantic_dir: Path, update_index: int) -> Path:
    semantic_dir.mkdir(parents=True, exist_ok=True)
    semantic_text = _render_semantic_text(update_index)
    semantic_txt_path = semantic_dir / "semantic.txt"
    semantic_txt_path.write_text(semantic_text, encoding="utf-8")

    stamped_path = semantic_dir / f"semantic_{_now_tag()}.txt"
    stamped_path.write_text(semantic_text, encoding="utf-8")
    return stamped_path


def _publish_iq_sample(iq_dir: Path, sample_path: Path) -> Path:
    """向测试 IQ 目录发布一个样本。

    注意：
    - 不能在实时进程读取期间强删旧 `.bin`，Windows 下会直接撞文件锁；
    - 因此这里采用“存在则 touch，不存在则新增”的策略；
    - 这样目录签名仍会变化，足以触发 run_union_realtime.py 重算。
    """
    iq_dir.mkdir(parents=True, exist_ok=True)
    target = iq_dir / sample_path.name
    if target.exists():
        os.utime(target, None)
    else:
        _safe_link_or_copy(sample_path, target)
    return target


def _start_realtime_worker(
    *,
    iq_dir: Path,
    semantic_dir: Path,
    output_npz: Path,
    poll_interval: float,
    semantic_fresh_seconds: float,
    debug: bool,
) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-u",
        str(ROOT / "scripts" / "run_union_realtime.py"),
        "--iq-dir",
        str(iq_dir),
        "--semantic-dir",
        str(semantic_dir),
        "--output",
        str(output_npz),
        "--poll-interval",
        str(poll_interval),
        "--semantic-fresh-seconds",
        str(semantic_fresh_seconds),
    ]
    if debug:
        cmd.append("--debug")

    creationflags = 0 if debug else getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        creationflags=creationflags,
    )


def _print_run_hint(iq_dir: Path, semantic_dir: Path, output_npz: Path) -> None:
    cmd = (
        "python -u scripts\\run_union_realtime.py "
        f"--iq-dir \"{iq_dir}\" "
        f"--semantic-dir \"{semantic_dir}\" "
        f"--output \"{output_npz}\" "
        "--debug"
    )
    print("请在另一个终端运行以下命令：")
    print(cmd)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 run_union_realtime.py 生成实时测试输入")
    parser.add_argument(
        "--source-iq-dir",
        type=Path,
        default=DEFAULT_SOURCE_IQ_DIR,
        help="原始 IQ 样本目录（默认 data_segment）",
    )
    parser.add_argument(
        "--sandbox-root",
        type=Path,
        default=DEFAULT_SANDBOX_ROOT,
        help="测试沙箱根目录（默认 output/realtime_input_test）",
    )
    parser.add_argument(
        "--updates",
        type=int,
        default=6,
        help="更新轮数（默认 6）",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="两次更新之间的秒数（默认 2.0）",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=4,
        help="循环使用的 IQ 样本数（默认 4）",
    )
    parser.add_argument(
        "--launch-worker",
        action="store_true",
        help="同时启动 run_union_realtime.py 子进程",
    )
    parser.add_argument(
        "--keep-worker",
        action="store_true",
        help="与 --launch-worker 配合使用；脚本结束后不自动停止子进程",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.2,
        help="子进程 run_union_realtime.py 的轮询间隔（默认 0.2）",
    )
    parser.add_argument(
        "--semantic-fresh-seconds",
        type=float,
        default=3.0,
        help="子进程 run_union_realtime.py 的 freshness 窗口（默认 3.0）",
    )
    parser.add_argument(
        "--debug-worker",
        action="store_true",
        help="若启动子进程，则为它加上 --debug",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=6.0,
        help="更新结束后，给子进程留出的收敛时间（默认 6 秒）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要执行的动作，不真正写文件/起进程",
    )
    return parser.parse_args()


def main() -> int:
    _ensure_console_utf8()
    args = _parse_args()

    source_iq_dir = args.source_iq_dir.resolve()
    sandbox_root = args.sandbox_root.resolve()
    semantic_dir = sandbox_root / "data_semantic"
    iq_dir = sandbox_root / f"data_segment_{_now_tag()}"
    output_npz = sandbox_root / "output" / "union_spectrum.npz"

    samples = _list_iq_samples(source_iq_dir)
    sample_count = max(1, min(int(args.sample_count), len(samples)))
    selected_samples = samples[:sample_count]

    print("=" * 80)
    print("实时输入测试驱动启动")
    print(f"源 IQ 目录: {source_iq_dir}")
    print(f"沙箱目录: {sandbox_root}")
    print(f"测试 IQ 目录: {iq_dir}")
    print(f"测试语义目录: {semantic_dir}")
    print(f"输出 npz: {output_npz}")
    print(f"更新轮数: {int(args.updates)}")
    print(f"更新间隔: {float(args.interval):.1f} 秒")
    print(f"使用 IQ 样本数: {sample_count}")
    print("=" * 80)

    if args.dry_run:
        _print_run_hint(iq_dir, semantic_dir, output_npz)
        for update_index in range(int(args.updates)):
            sample_path = selected_samples[update_index % sample_count]
            print(
                f"[DRY-RUN] 第 {update_index + 1} 轮: "
                f"IQ={sample_path.name}, "
                f"SEM=semantic_{_now_tag()}.txt"
            )
        return 0

    sandbox_root.mkdir(parents=True, exist_ok=True)
    _reset_dir(semantic_dir)
    _reset_dir(iq_dir)
    output_npz.parent.mkdir(parents=True, exist_ok=True)

    worker_proc: Optional[subprocess.Popen] = None
    if args.launch_worker:
        worker_proc = _start_realtime_worker(
            iq_dir=iq_dir,
            semantic_dir=semantic_dir,
            output_npz=output_npz,
            poll_interval=float(args.poll_interval),
            semantic_fresh_seconds=float(args.semantic_fresh_seconds),
            debug=bool(args.debug_worker),
        )
        print(f"[INFO] 已启动实时脚本子进程，PID={worker_proc.pid}")
    else:
        _print_run_hint(iq_dir, semantic_dir, output_npz)

    try:
        for update_index in range(int(args.updates)):
            sample_path = selected_samples[update_index % sample_count]
            linked_path = _publish_iq_sample(iq_dir, sample_path)
            semantic_path = _write_semantic_files(semantic_dir, update_index)
            print(
                f"[UPDATE {update_index + 1}/{int(args.updates)}] "
                f"IQ={linked_path.name}, "
                f"SEM={semantic_path.name}"
            )
            if update_index < int(args.updates) - 1:
                time.sleep(float(args.interval))
    except KeyboardInterrupt:
        print("\n用户中断，测试驱动退出")
    finally:
        if worker_proc is not None and not args.keep_worker:
            settle_seconds = max(float(args.settle_seconds), 0.0)
            if settle_seconds > 0.0 and worker_proc.poll() is None:
                print(f"[INFO] 等待实时脚本收敛 {settle_seconds:.1f} 秒")
                time.sleep(settle_seconds)
            if worker_proc.poll() is None:
                worker_proc.terminate()
                try:
                    worker_proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    worker_proc.kill()
            print("[INFO] 已停止实时脚本子进程")

    print("测试驱动结束")
    print(f"请检查输出文件是否更新：{output_npz}")
    print("注意：IQ freshness 绑在目录名时间戳上；若需重新获得 3 秒“新鲜 IQ”窗口，请重新运行本脚本。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
