#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务二：30–2500 MHz 频谱拼接（无绘图）耗时基准。

目标：回答“拼接 30–2500 MHz 频谱需要多长时间？”并给出可复现实验口径。

重要说明（口径）：
- 本脚本默认测量“同一 Python 进程内”的算法耗时，计时范围覆盖：
  1) 读取/解析/解码 `.bin`（load_bin_segments）
  2) 分段 FFT（NFFT 固定）+ 时间聚合（compute_segmented_power_spectrum）
  3) 拼接（stitch_segments）
- 不包含：绘图、保存 PNG、Python 冷启动/模块 import。
  如果你用 `python scripts/benchmark_task2_stitch_speed.py` 每跑一次就起一个新进程，
  那么“端到端墙钟时间”会被 Python/SciPy 的 import 主导，这不是算法本身的问题。

用法示例：

  # 使用 data_segment 目录（13 个 200MHz 窗口），NFFT=512
  python scripts/benchmark_task2_stitch_speed.py

  # 指定输入目录、重复次数
  python scripts/benchmark_task2_stitch_speed.py --input-dir data_segment --repeat 20 --warmup 2
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from electromagnetic_state.core.schemas import SamplingConfig  # type: ignore
from electromagnetic_state.io.reader import BinDataType, load_bin_segments  # type: ignore
from electromagnetic_state.signal.spectrum import compute_segmented_power_spectrum  # type: ignore
from electromagnetic_state.signal.stitcher import SpectrumSegment, StitchMode, stitch_segments  # type: ignore


@dataclass(frozen=True)
class Timings:
    load_s: float
    fft_s: float
    stitch_s: float
    total_s: float


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


def _format_ms(seconds: float) -> str:
    return f"{seconds * 1000.0:.3f}"


def _run_once(
    *,
    input_dir: Path,
    pattern: str,
    bin_dtype: BinDataType,
    default_sample_rate_hz: float,
    segment_fft_size: int,
    time_agg_mode: str,
    stitch_mode: StitchMode,
    fill_value_db: float,
    window: str,
) -> tuple[Timings, int, int]:
    t0 = time.perf_counter()
    iq_list = load_bin_segments(
        input_dir,
        pattern,
        bin_dtype,
        default_sample_rate_hz=default_sample_rate_hz,
    )
    t1 = time.perf_counter()

    segments: List[SpectrumSegment] = []
    for iq in iq_list:
        cfg = SamplingConfig(
            sample_rate_hz=float(iq.sample_rate_hz),
            center_freq_hz=float(iq.center_freq_hz),
            fft_size=int(segment_fft_size),
        )
        target_df_hz = float(iq.sample_rate_hz) / float(segment_fft_size)
        freq_mhz, power_db = compute_segmented_power_spectrum(
            iq=iq,
            cfg=cfg,
            target_df_hz=target_df_hz,
            window=window,
            time_agg_mode=time_agg_mode,
        )

        segments.append(
            SpectrumSegment(
                freq_mhz=freq_mhz,
                power_db=power_db,
                center_freq_mhz=float(iq.center_freq_hz) / 1e6,
                bandwidth_mhz=float(iq.sample_rate_hz) / 1e6,
            )
        )

    t2 = time.perf_counter()
    stitched = stitch_segments(segments, mode=stitch_mode, fill_value=float(fill_value_db))
    t3 = time.perf_counter()

    timings = Timings(load_s=t1 - t0, fft_s=t2 - t1, stitch_s=t3 - t2, total_s=t3 - t0)
    return timings, len(segments), int(stitched.freq_mhz.size)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="任务二拼接耗时基准（不绘图）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data_segment"), help="包含 .bin 的目录")
    parser.add_argument("--pattern", type=str, default="*.bin", help="文件匹配模式")
    parser.add_argument("--dtype", type=str, default="int16", choices=["int16"], help=".bin 数据类型")
    parser.add_argument("--sample-rate", type=float, default=204.8e6, help="默认采样率 Hz（用于 130MHz.bin 命名）")
    parser.add_argument("--segment-fft-size", type=int, default=512, help="分段 FFT 点数（NFFT）")
    parser.add_argument("--time-agg-mode", type=str, default="mean", choices=["mean", "max"], help="分段时间聚合方式")
    parser.add_argument("--mode", type=str, default="max", choices=["max", "mean", "weighted_mean", "first", "last"], help="拼接模式")
    parser.add_argument("--fill-value-db", type=float, default=-180.0, help="未覆盖区域填充值（dB）")
    parser.add_argument("--window", type=str, default="hann", help="窗函数名")
    parser.add_argument("--warmup", type=int, default=1, help="预热次数（不计入统计）")
    parser.add_argument("--repeat", type=int, default=10, help="计时重复次数")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Windows 控制台在某些环境下默认编码可能不是 UTF-8，直接打印中文会触发 UnicodeEncodeError。
    # 这里尽量把 stdout/stderr 切到 UTF-8，保证脚本“能跑完并给出数字”。
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    input_dir = (ROOT / args.input_dir).resolve() if not args.input_dir.is_absolute() else args.input_dir
    if not input_dir.exists():
        raise SystemExit(f"输入目录不存在: {input_dir}")

    if int(args.segment_fft_size) <= 1:
        raise SystemExit("--segment-fft-size 必须 > 1（本脚本专注分段 FFT 口径）")

    bin_dtype = BinDataType(str(args.dtype))
    stitch_mode = StitchMode(str(args.mode))

    for _ in range(int(args.warmup)):
        _run_once(
            input_dir=input_dir,
            pattern=str(args.pattern),
            bin_dtype=bin_dtype,
            default_sample_rate_hz=float(args.sample_rate),
            segment_fft_size=int(args.segment_fft_size),
            time_agg_mode=str(args.time_agg_mode),
            stitch_mode=stitch_mode,
            fill_value_db=float(args.fill_value_db),
            window=str(args.window),
        )

    load_times: List[float] = []
    fft_times: List[float] = []
    stitch_times: List[float] = []
    total_times: List[float] = []
    seg_count = 0
    stitched_points = 0

    for _ in range(int(args.repeat)):
        timings, seg_count, stitched_points = _run_once(
            input_dir=input_dir,
            pattern=str(args.pattern),
            bin_dtype=bin_dtype,
            default_sample_rate_hz=float(args.sample_rate),
            segment_fft_size=int(args.segment_fft_size),
            time_agg_mode=str(args.time_agg_mode),
            stitch_mode=stitch_mode,
            fill_value_db=float(args.fill_value_db),
            window=str(args.window),
        )
        load_times.append(timings.load_s)
        fft_times.append(timings.fft_s)
        stitch_times.append(timings.stitch_s)
        total_times.append(timings.total_s)

    def summarize(values: List[float]) -> tuple[float, float, float]:
        values_sorted = sorted(values)
        return (
            statistics.median(values_sorted),
            _percentile(values_sorted, 0.95),
            statistics.mean(values_sorted),
        )

    load_med, load_p95, load_mean = summarize(load_times)
    fft_med, fft_p95, fft_mean = summarize(fft_times)
    st_med, st_p95, st_mean = summarize(stitch_times)
    tot_med, tot_p95, tot_mean = summarize(total_times)

    df_mhz = float(args.sample_rate) / float(args.segment_fft_size) / 1e6

    print("=" * 80)
    print("任务二：30–2500 MHz 频谱拼接耗时基准（无绘图，同进程口径）")
    print("=" * 80)
    print(f"input_dir={input_dir}")
    print(f"files={seg_count}")
    print(f"Fs={float(args.sample_rate)/1e6:.3f} MHz, NFFT={int(args.segment_fft_size)}, Δf={df_mhz:.3f} MHz")
    print(f"time_agg={args.time_agg_mode}, stitch_mode={args.mode}, window={args.window}, fill={float(args.fill_value_db):.1f} dB")
    print(f"repeat={int(args.repeat)}, warmup={int(args.warmup)}")
    print(f"stitched_points={stitched_points}")
    print()
    print(f"{'stage':>10}  {'median(ms)':>10}  {'p95(ms)':>10}  {'mean(ms)':>10}")
    print(f"{'load':>10}  {_format_ms(load_med):>10}  {_format_ms(load_p95):>10}  {_format_ms(load_mean):>10}")
    print(f"{'fft':>10}  {_format_ms(fft_med):>10}  {_format_ms(fft_p95):>10}  {_format_ms(fft_mean):>10}")
    print(f"{'stitch':>10}  {_format_ms(st_med):>10}  {_format_ms(st_p95):>10}  {_format_ms(st_mean):>10}")
    print(f"{'total':>10}  {_format_ms(tot_med):>10}  {_format_ms(tot_p95):>10}  {_format_ms(tot_mean):>10}")


if __name__ == "__main__":
    main()
