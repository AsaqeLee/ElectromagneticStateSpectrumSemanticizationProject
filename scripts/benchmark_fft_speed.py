#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FFT 速度基准测试脚本。

目的：
- 比较在同样总采样点数下：
  1）整体一次 FFT；
  2）按固定长度分段做多次 FFT；
  哪种方式更快。

说明：
- 默认使用随机复数 IQ 数据（numpy 生成），不依赖实际 .bin 文件；
- 只关心时间开销，不关心 FFT 结果，因此分段 FFT 的结果会简单累加避免被优化掉；
- 可通过命令行参数调整总采样点数、分段大小和重复次数。

用法示例：

    # 使用默认参数对比
    python scripts/benchmark_fft_speed.py

    # 指定总长度 16M 点、分段 262144 点、重复 5 次
    python scripts/benchmark_fft_speed.py --total-samples 16777216 --chunk-size 262144 --repeat 5
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Tuple, Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from electromagnetic_state.io.reader import load_iq_file, BinDataType  # type: ignore


def _generate_iq_data(total_samples: int, seed: Optional[int] = 42) -> np.ndarray:
    """生成随机复数 IQ 数据。

    参数：
    - total_samples: 总采样点数（复数点数）
    - seed: 随机种子，方便复现
    """
    if total_samples <= 0:
        raise ValueError("total_samples 必须为正整数")

    rng = np.random.default_rng(seed)
    real = rng.standard_normal(total_samples)
    imag = rng.standard_normal(total_samples)
    return real.astype(np.float64) + 1j * imag.astype(np.float64)


def _benchmark_full_fft(samples: np.ndarray, repeat: int = 3) -> float:
    """对整段数据执行多次 FFT，返回平均耗时（秒）。"""

    if repeat <= 0:
        raise ValueError("repeat 必须为正整数")

    # 预热一次，避免首次调用开销干扰
    _ = np.fft.fft(samples)

    t0 = time.perf_counter()
    acc = 0.0 + 0.0j  # 累加结果，避免被完全优化掉
    for _ in range(repeat):
        fft_res = np.fft.fft(samples)
        acc += fft_res[0]
    t1 = time.perf_counter()

    # 打印累加值，避免静态检查误报“未使用变量”
    print(f"[整体 FFT] 结果累加实部: {acc.real:.3e}")
    return (t1 - t0) / repeat


def _benchmark_chunk_fft(
    samples: np.ndarray,
    chunk_size: int,
    repeat: int = 3,
) -> float:
    """将数据按 chunk_size 分段做 FFT，返回平均耗时（秒）。"""

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    if repeat <= 0:
        raise ValueError("repeat 必须为正整数")

    total_samples = samples.size
    if total_samples == 0:
        raise ValueError("输入 samples 为空")

    # 计算分段数（最后一段可能不足 chunk_size，直接零填充）
    num_chunks = (total_samples + chunk_size - 1) // chunk_size

    # 预热：做一遍分段 FFT
    for i in range(num_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, total_samples)
        chunk = samples[start:end]
        if chunk.size < chunk_size:
            padded = np.zeros(chunk_size, dtype=samples.dtype)
            padded[: chunk.size] = chunk
            chunk = padded
        _ = np.fft.fft(chunk)

    t0 = time.perf_counter()
    acc = 0.0 + 0.0j
    for _ in range(repeat):
        for i in range(num_chunks):
            start = i * chunk_size
            end = min(start + chunk_size, total_samples)
            chunk = samples[start:end]
            if chunk.size < chunk_size:
                padded = np.zeros(chunk_size, dtype=samples.dtype)
                padded[: chunk.size] = chunk
                chunk = padded
            fft_res = np.fft.fft(chunk)
            acc += fft_res[0]
    t1 = time.perf_counter()

    print(f"[分段 FFT] 结果累加实部: {acc.real:.3e}")
    return (t1 - t0) / repeat


def run_benchmark_with_samples(
    samples: np.ndarray,
    chunk_size: int,
    repeat: int,
    sample_rate_hz: Optional[float] = None,
    target_df_hz: Optional[float] = None,
) -> Tuple[float, float]:
    """执行一次基准测试，返回整体 FFT 和分段 FFT 的平均耗时。"""

    total_samples = samples.size

    print("=" * 80)
    print("FFT 速度基准测试")
    print("=" * 80)
    print(f"总采样点数: {total_samples}")
    print(f"分段大小  : {chunk_size}")
    print(f"重复次数  : {repeat}")
    if sample_rate_hz is not None:
        df_full = sample_rate_hz / total_samples
        df_chunk = sample_rate_hz / chunk_size
        print(f"采样率      : {sample_rate_hz / 1e6:.3f} MHz")
        print(f"整体 FFT 分辨率: {df_full / 1e3:.3f} kHz")
        print(f"分段 FFT 分辨率: {df_chunk / 1e3:.3f} kHz")
        if target_df_hz is not None:
            print(f"目标分辨率  : {target_df_hz / 1e3:.3f} kHz")
    print()

    t_full = _benchmark_full_fft(samples, repeat=repeat)
    print(f"\n整体 FFT 平均耗时: {t_full * 1000:.3f} ms")

    t_chunk = _benchmark_chunk_fft(samples, chunk_size=chunk_size, repeat=repeat)
    print(f"分段 FFT 平均耗时: {t_chunk * 1000:.3f} ms")

    speedup = t_chunk / t_full if t_full > 0 else float("inf")
    print("\n结果对比：")
    print(f"  分段 / 整体 耗时比: {speedup:.3f}x")
    if speedup > 1.0:
        print("  结论：在当前参数下，整体 FFT 更快。")
    else:
        print("  结论：在当前参数下，分段 FFT 更快或相近。")

    return t_full, t_chunk


def run_benchmark(
    total_samples: int,
    chunk_size: int,
    repeat: int,
) -> Tuple[float, float]:
    """使用随机数据执行一次基准测试。"""

    samples = _generate_iq_data(total_samples)
    return run_benchmark_with_samples(samples, chunk_size, repeat)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="比较整体 FFT 与分段 FFT 的运行时间",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--total-samples",
        type=int,
        default=1_048_576,
        help="总采样点数（复数点数）",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=262_144,
        help="分段 FFT 的每段大小",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="每种方式重复次数，用于取平均耗时",
    )
    parser.add_argument(
        "--bin-path",
        type=Path,
        default=None,
        help="指定 .bin 文件路径，使用真实 IQ 数据；为空则使用随机数据",
    )
    parser.add_argument(
        "--target-df-khz",
        type=float,
        default=100.0,
        help="分段 FFT 目标频率分辨率（kHz），仅在使用 .bin 数据时生效",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.bin_path is not None:
        # 允许路径前面带一个 '@'（例如 @data_segment\\xxx.bin）
        bin_path_str = str(args.bin_path)
        if bin_path_str.startswith("@"):
            bin_path_str = bin_path_str[1:]
        bin_path = Path(bin_path_str)
        if not bin_path.is_absolute():
            bin_path = ROOT / bin_path
        if not bin_path.exists():
            raise SystemExit(f".bin 文件不存在: {bin_path}")

        iq = load_iq_file(bin_path, bin_dtype=BinDataType.INT16)
        samples = iq.samples
        sample_rate_hz = iq.sample_rate_hz

        target_df_hz = args.target_df_khz * 1e3
        if target_df_hz <= 0:
            raise SystemExit("target-df-khz 必须为正值")

        fft_size = int(round(sample_rate_hz / target_df_hz))
        if fft_size <= 0:
            raise SystemExit("根据目标分辨率计算得到的 FFT 点数无效")

        chunk_size = fft_size

        run_benchmark_with_samples(
            samples=samples,
            chunk_size=chunk_size,
            repeat=args.repeat,
            sample_rate_hz=sample_rate_hz,
            target_df_hz=target_df_hz,
        )
    else:
        run_benchmark(
            total_samples=args.total_samples,
            chunk_size=args.chunk_size,
            repeat=args.repeat,
        )


if __name__ == "__main__":
    if sys.platform == "win32":
        import io

        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
        except (AttributeError, ValueError):
            pass

    main()
