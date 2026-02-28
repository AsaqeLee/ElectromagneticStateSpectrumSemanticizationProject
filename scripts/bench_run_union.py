#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_union 性能基准（不绘图）。

目的：
- 对比 256/512 点分段 FFT 的耗时；
- 验证“拼接 30–2500 MHz + 语义并集 + 保存 union_spectrum.npz”的端到端耗时；
- 给工程侧一个可复现的基准入口（热启动/同进程）。

注意：
- 该脚本测的是“同一 Python 进程内”的热路径耗时（更接近实际系统集成场景）。
- 若你用 `python scripts/run_union.py` 每次新起进程，启动/导入耗时会远大于 FFT 本身；
  这种冷启动耗时不在本脚本默认测量范围内（可用 --include-cold 打开粗测）。
"""
from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # 允许 `import scripts.run_union`（scripts 为隐式 namespace package）
    sys.path.insert(0, str(ROOT))


def _percentile_sorted(values_sorted: list[float], p: float) -> float:
    """简易分位数（p in [0,1]），values_sorted 必须已排序。"""
    if not values_sorted:
        return float("nan")
    if p <= 0:
        return float(values_sorted[0])
    if p >= 1:
        return float(values_sorted[-1])
    idx = int(round((len(values_sorted) - 1) * p))
    idx = max(0, min(idx, len(values_sorted) - 1))
    return float(values_sorted[idx])


def _format_ms(ms: float) -> str:
    if ms != ms:  # NaN
        return "nan"
    return f"{ms:.3f} ms"


def _bench_hot(nfft_list: Iterable[int], repeat: int, warmup: int) -> None:
    from scripts import run_union  # 延迟导入：让基准更清晰

    print("================================================================================")
    print("run_union 热路径基准（同进程，quiet=True，enable_plot=False）")
    print("================================================================================")
    print(f"repeat={repeat}, warmup={warmup}")

    for nfft in nfft_list:
        if nfft <= 0:
            raise SystemExit(f"nfft 必须为正：{nfft}")

        # warmup：让 OS 文件缓存、FFT 内部状态进入稳定态
        for _ in range(warmup):
            run_union.main(quiet=True, enable_plot=False, segment_fft_size=int(nfft))

        costs_ms: list[float] = []
        for _ in range(repeat):
            t0 = time.perf_counter()
            run_union.main(quiet=True, enable_plot=False, segment_fft_size=int(nfft))
            costs_ms.append((time.perf_counter() - t0) * 1000.0)

        costs_sorted = sorted(costs_ms)
        mean_ms = statistics.fmean(costs_ms)
        p50_ms = _percentile_sorted(costs_sorted, 0.50)
        p95_ms = _percentile_sorted(costs_sorted, 0.95)
        p99_ms = _percentile_sorted(costs_sorted, 0.99)

        print()
        print(f"[NFFT={nfft}]")
        print(f"  mean: {_format_ms(mean_ms)}")
        print(f"  p50 : {_format_ms(p50_ms)}")
        print(f"  p95 : {_format_ms(p95_ms)}")
        print(f"  p99 : {_format_ms(p99_ms)}")
        print(f"  min : {_format_ms(min(costs_ms))}")
        print(f"  max : {_format_ms(max(costs_ms))}")


def _bench_cold(nfft: int) -> None:
    """冷启动粗测：每次新起进程执行一次 main()。"""
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from scripts import run_union; "
            f"sys.exit(run_union.main(quiet=True, enable_plot=False, segment_fft_size={int(nfft)}))"
        ),
    ]

    print()
    print("================================================================================")
    print("run_union 冷启动粗测（每次新进程，含导入/启动开销）")
    print("================================================================================")
    print(f"cmd: {' '.join(cmd)}")

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    cost_ms = (time.perf_counter() - t0) * 1000.0
    print(f"exit_code={proc.returncode}, wall={_format_ms(cost_ms)}")
    if proc.returncode != 11:
        print("stderr:")
        print(proc.stderr.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="run_union 性能基准（不绘图）")
    parser.add_argument(
        "--nfft",
        type=int,
        nargs="*",
        default=[256, 512],
        help="分段 FFT 点数列表（默认：256 512）",
    )
    parser.add_argument("--repeat", type=int, default=10, help="重复次数（默认 10）")
    parser.add_argument("--warmup", type=int, default=1, help="预热次数（默认 1）")
    parser.add_argument(
        "--include-cold",
        action="store_true",
        help="额外做一次冷启动粗测（每次新进程，耗时会很大）",
    )
    args = parser.parse_args()

    # 基础检查：确保在仓库根目录运行（否则 scripts import 可能找不到数据目录）
    if not (ROOT / "data_segment").exists():
        print("警告：未找到 data_segment 目录，基准可能退化为“仅语义底噪”。")

    _bench_hot(args.nfft, repeat=int(args.repeat), warmup=int(args.warmup))

    if args.include_cold:
        _bench_cold(int(args.nfft[-1] if args.nfft else 512))

    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
