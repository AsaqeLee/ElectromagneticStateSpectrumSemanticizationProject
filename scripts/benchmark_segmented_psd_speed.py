#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分段功率谱（Welch 风格）速度基准脚本。

本脚本用于回答一个很具体的问题：
在固定总 IQ 点数下，选择不同 FFT 点数（例如 256 点 vs 512 点）
会带来怎样的“每个文件/每次计算”耗时差异。

注意：
- 这里测的是“生成最终可绘制的一条功率谱曲线”的计算耗时：
  加窗 + FFTShift + |X|^2 + 聚合(mean/max) + dB 转换；
- 默认使用随机复数 IQ，避免 I/O 干扰；也可通过 --bin-path 使用真实 .bin 数据；
- 绘图通常比 FFT 更慢。本脚本不包含绘图耗时。

用法示例：

  # 131072 点，Fs=204.8MHz，对比 256/512 FFT
  python scripts/benchmark_segmented_psd_speed.py

  # 使用真实 .bin（int16 交织 I/Q）
  python scripts/benchmark_segmented_psd_speed.py --bin-path data\\IQ_data\\slot_11\\xxx_130MHz_204.8MHz_11h01m58s.bin
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.schemas import IQData, SamplingConfig  # type: ignore
from src.io.reader import BinDataType, load_iq_file  # type: ignore
from src.signal.spectrum import compute_segmented_power_spectrum  # type: ignore


def _generate_iq_data(total_samples: int, seed: int = 42) -> np.ndarray:
    if total_samples <= 0:
        raise ValueError("total_samples 必须为正整数")
    rng = np.random.default_rng(seed)
    real = rng.standard_normal(total_samples)
    imag = rng.standard_normal(total_samples)
    return real.astype(np.float64) + 1j * imag.astype(np.float64)


def _as_absolute_path(p: Path) -> Path:
    p_str = str(p)
    if p_str.startswith("@"):
        p_str = p_str[1:]
        p = Path(p_str)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def _format_ms(seconds: float) -> str:
    return f"{seconds * 1000.0:.3f} ms"


@dataclass(frozen=True)
class BenchResult:
    nfft: int
    num_chunks: int
    df_hz: float
    median_s: float
    p95_s: float
    mean_s: float


def _percentile(sorted_values: List[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("percentile 输入为空")
    if not (0.0 <= q <= 1.0):
        raise ValueError("q 必须在 [0, 1]")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(np.floor(pos))
    hi = int(np.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _benchmark_one(
    *,
    samples: np.ndarray,
    fs_hz: float,
    center_freq_hz: float,
    nfft: int,
    window: str,
    time_agg_mode: str,
    warmup: int,
    repeat: int,
) -> BenchResult:
    if nfft <= 1:
        raise ValueError("nfft 必须大于 1")
    if warmup < 0:
        raise ValueError("warmup 不能为负")
    if repeat <= 0:
        raise ValueError("repeat 必须为正整数")
    if time_agg_mode not in {"mean", "max"}:
        raise ValueError("time_agg_mode 仅支持 mean/max")

    iq = IQData(samples=samples, sample_rate_hz=fs_hz, center_freq_hz=center_freq_hz)
    cfg = SamplingConfig(sample_rate_hz=fs_hz, center_freq_hz=center_freq_hz, fft_size=nfft)
    target_df_hz = fs_hz / float(nfft)

    num_chunks = (samples.size + nfft - 1) // nfft

    for _ in range(warmup):
        _ = compute_segmented_power_spectrum(
            iq=iq,
            cfg=cfg,
            target_df_hz=target_df_hz,
            window=window,
            time_agg_mode=time_agg_mode,
        )

    times: List[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        freq_axis, power_db = compute_segmented_power_spectrum(
            iq=iq,
            cfg=cfg,
            target_df_hz=target_df_hz,
            window=window,
            time_agg_mode=time_agg_mode,
        )
        t1 = time.perf_counter()

        if freq_axis.size != nfft or power_db.size != nfft:
            raise RuntimeError("输出长度异常，基准测试不可信")

        times.append(t1 - t0)

    times_sorted = sorted(times)
    return BenchResult(
        nfft=nfft,
        num_chunks=num_chunks,
        df_hz=target_df_hz,
        median_s=statistics.median(times_sorted),
        p95_s=_percentile(times_sorted, 0.95),
        mean_s=statistics.mean(times_sorted),
    )


def _print_results(results: Iterable[BenchResult]) -> None:
    rows = list(results)
    rows.sort(key=lambda r: r.nfft)

    print("=" * 80)
    print("分段功率谱计算耗时对比（不含绘图/I/O）")
    print("=" * 80)
    print(f"{'NFFT':>6}  {'chunks':>6}  {'Δf(kHz)':>10}  {'median':>12}  {'p95':>12}  {'mean':>12}")
    for r in rows:
        print(
            f"{r.nfft:6d}  {r.num_chunks:6d}  {r.df_hz/1e3:10.3f}  "
            f"{_format_ms(r.median_s):>12}  {_format_ms(r.p95_s):>12}  {_format_ms(r.mean_s):>12}"
        )

    if len(rows) >= 2:
        fastest = min(rows, key=lambda r: r.median_s)
        slowest = max(rows, key=lambda r: r.median_s)
        ratio = slowest.median_s / fastest.median_s if fastest.median_s > 0 else float("inf")
        print()
        print(f"最快: NFFT={fastest.nfft} (median={_format_ms(fastest.median_s)})")
        print(f"最慢: NFFT={slowest.nfft} (median={_format_ms(slowest.median_s)})")
        print(f"耗时比(最慢/最快): {ratio:.3f}x")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="基准测试：分段功率谱计算耗时（Welch 风格）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--total-samples", type=int, default=131_072, help="总采样点数（复数点数）")
    parser.add_argument("--fs-mhz", type=float, default=204.8, help="采样率（MHz），仅在随机数据模式使用")
    parser.add_argument("--center-mhz", type=float, default=0.0, help="中心频率（MHz），仅用于频轴")
    parser.add_argument("--nfft", type=int, nargs="+", default=[256, 512], help="要对比的 FFT 点数列表")
    parser.add_argument("--repeat", type=int, default=20, help="每个 NFFT 的计时重复次数")
    parser.add_argument("--warmup", type=int, default=3, help="预热次数（不计入统计）")
    parser.add_argument("--window", type=str, default="hann", help="窗函数名称（scipy.signal.get_window）")
    parser.add_argument("--time-agg-mode", type=str, default="mean", choices=["mean", "max"], help="时间聚合方式")
    parser.add_argument("--bin-path", type=Path, default=None, help="指定 .bin 文件路径，使用真实 IQ 数据")
    parser.add_argument("--bin-dtype", type=str, default="int16", choices=["int16"], help=".bin 数据类型（当前仅实现 int16 交织）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子（随机数据模式）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.bin_path is not None:
        bin_path = _as_absolute_path(args.bin_path)
        if not bin_path.exists():
            raise SystemExit(f".bin 文件不存在: {bin_path}")
        bin_dtype = BinDataType.INT16
        iq = load_iq_file(bin_path, bin_dtype=bin_dtype)
        samples = np.asarray(iq.samples, dtype=np.complex128)
        fs_hz = float(iq.sample_rate_hz)
        center_hz = float(iq.center_freq_hz)
        print(f"[输入] 使用真实 .bin: {bin_path}")
        print(f"[输入] samples={samples.size}, Fs={fs_hz/1e6:.3f} MHz, center={center_hz/1e6:.3f} MHz")
    else:
        fs_hz = float(args.fs_mhz) * 1e6
        center_hz = float(args.center_mhz) * 1e6
        samples = _generate_iq_data(args.total_samples, seed=int(args.seed))
        samples = np.asarray(samples, dtype=np.complex128)
        print(f"[输入] 使用随机 IQ: samples={samples.size}, Fs={fs_hz/1e6:.3f} MHz, center={center_hz/1e6:.3f} MHz")

    results: List[BenchResult] = []
    for nfft in args.nfft:
        r = _benchmark_one(
            samples=samples,
            fs_hz=fs_hz,
            center_freq_hz=center_hz,
            nfft=int(nfft),
            window=str(args.window),
            time_agg_mode=str(args.time_agg_mode),
            warmup=int(args.warmup),
            repeat=int(args.repeat),
        )
        results.append(r)

    _print_results(results)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io

        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    main()

