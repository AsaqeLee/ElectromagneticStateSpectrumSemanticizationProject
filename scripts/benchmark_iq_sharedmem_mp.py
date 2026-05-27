#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""IQ 全量频谱计算基准：多进程 + 共享内存。

目的：
- 测试在当前真实 `data_segment/*.bin` 上，CPU 多进程 + 共享内存是否值得继续推进；
- 将“读取文件”和“频谱计算”拆开，重点衡量 FFT/聚合阶段的墙钟时间；
- 为后续是否切换到 CUDA 路径提供证据。

说明：
- 本脚本先把所有 `.bin` 读入主进程内存，再复制到 shared_memory；
- 子进程只做 `compute_segmented_power_spectrum(...)`，避免把结论混入磁盘 I/O；
- Windows 下必须使用 `if __name__ == '__main__'`，否则 `spawn` 会把自己玩死。
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from multiprocessing import get_context, shared_memory
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"

import sys

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from electromagnetic_state.io.reader import BinDataType, load_iq_file, parse_bin_filename  # type: ignore
from electromagnetic_state.core.schemas import SamplingConfig  # type: ignore
from electromagnetic_state.signal.spectrum import compute_segmented_power_spectrum  # type: ignore


@dataclass(frozen=True)
class SharedArrayDesc:
    shm_name: str
    shape: Tuple[int, ...]
    dtype_str: str
    file_name: str
    sample_rate_hz: float
    center_freq_hz: float


def _load_iq_arrays(input_dir: Path) -> List[Tuple[np.ndarray, str, float, float]]:
    files = sorted(input_dir.glob("*.bin"))
    if not files:
        raise FileNotFoundError(f"目录 {input_dir} 中没有 .bin 文件")

    out: List[Tuple[np.ndarray, str, float, float]] = []
    for path in files:
        meta_guess = parse_bin_filename(path.name, strict=False)
        sr_override = 204.8e6 if "bandwidth_mhz" not in meta_guess else None
        iq = load_iq_file(path, bin_dtype=BinDataType.INT16, sample_rate_hz=sr_override)
        arr = np.asarray(iq.samples, dtype=np.complex64)
        out.append((arr, path.name, float(iq.sample_rate_hz), float(iq.center_freq_hz)))
    return out


def _create_shared_arrays(
    arrays: Sequence[Tuple[np.ndarray, str, float, float]]
) -> Tuple[List[shared_memory.SharedMemory], List[SharedArrayDesc]]:
    shms: List[shared_memory.SharedMemory] = []
    descs: List[SharedArrayDesc] = []
    for arr, file_name, sample_rate_hz, center_freq_hz in arrays:
        shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
        buf = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
        buf[:] = arr
        shms.append(shm)
        descs.append(
            SharedArrayDesc(
                shm_name=shm.name,
                shape=tuple(arr.shape),
                dtype_str=str(arr.dtype),
                file_name=file_name,
                sample_rate_hz=sample_rate_hz,
                center_freq_hz=center_freq_hz,
            )
        )
    return shms, descs


def _worker(desc: SharedArrayDesc, segment_fft_size: int, time_agg_mode: str) -> Tuple[str, int, float]:
    shm = shared_memory.SharedMemory(name=desc.shm_name)
    try:
        arr = np.ndarray(desc.shape, dtype=np.dtype(desc.dtype_str), buffer=shm.buf)

        class IQ:
            pass

        iq = IQ()
        iq.samples = arr
        iq.sample_rate_hz = float(desc.sample_rate_hz)
        iq.center_freq_hz = float(desc.center_freq_hz)
        cfg = SamplingConfig(
            sample_rate_hz=float(desc.sample_rate_hz),
            center_freq_hz=float(desc.center_freq_hz),
            fft_size=8192,
        )
        freq_mhz, power_db = compute_segmented_power_spectrum(
            iq,
            cfg,
            target_df_hz=float(desc.sample_rate_hz) / float(segment_fft_size),
            window="hann",
            time_agg_mode=str(time_agg_mode),
        )
        return desc.file_name, int(freq_mhz.size), float(power_db.mean())
    finally:
        shm.close()


def _bench_serial(
    descs: Sequence[SharedArrayDesc],
    *,
    segment_fft_size: int,
    time_agg_mode: str,
    repeat: int,
) -> List[float]:
    costs: List[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        _ = [_worker(desc, segment_fft_size, time_agg_mode) for desc in descs]
        costs.append((time.perf_counter() - t0) * 1000.0)
    return costs


def _bench_pool(
    descs: Sequence[SharedArrayDesc],
    *,
    segment_fft_size: int,
    time_agg_mode: str,
    workers: int,
    repeat: int,
) -> List[float]:
    ctx = get_context("spawn")
    costs: List[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        with ctx.Pool(processes=int(workers)) as pool:
            _ = pool.starmap(
                _worker,
                [(desc, int(segment_fft_size), str(time_agg_mode)) for desc in descs],
            )
        costs.append((time.perf_counter() - t0) * 1000.0)
    return costs


def _fmt(values: Sequence[float]) -> str:
    return "[" + ", ".join(f"{v:.3f}" for v in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description="基准：IQ 共享内存 + 多进程频谱计算")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data_segment", help="IQ 目录")
    parser.add_argument("--segment-fft-size", type=int, default=512, help="分段 FFT 点数")
    parser.add_argument("--time-agg-mode", type=str, default="mean", choices=["mean", "max"], help="时间聚合方式")
    parser.add_argument("--repeat", type=int, default=2, help="每组重复次数")
    parser.add_argument("--workers", type=int, nargs="*", default=[2, 4, 6, 8, 12], help="测试的进程数列表")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    arrays = _load_iq_arrays(args.input_dir)
    shms, descs = _create_shared_arrays(arrays)

    try:
        print("================================================================================")
        print("IQ 共享内存 + 多进程基准")
        print("================================================================================")
        print(f"input_dir={args.input_dir}")
        print(f"file_count={len(descs)}")
        print(f"segment_fft_size={int(args.segment_fft_size)}")
        print(f"time_agg_mode={args.time_agg_mode}")
        print(f"repeat={int(args.repeat)}")

        serial_costs = _bench_serial(
            descs,
            segment_fft_size=int(args.segment_fft_size),
            time_agg_mode=str(args.time_agg_mode),
            repeat=int(args.repeat),
        )
        print()
        print(f"serial_sharedmem={_fmt(serial_costs)}, mean={sum(serial_costs)/len(serial_costs):.3f} ms")

        for worker_count in args.workers:
            costs = _bench_pool(
                descs,
                segment_fft_size=int(args.segment_fft_size),
                time_agg_mode=str(args.time_agg_mode),
                workers=int(worker_count),
                repeat=int(args.repeat),
            )
            print(f"mp_sharedmem[{int(worker_count)}]={_fmt(costs)}, mean={sum(costs)/len(costs):.3f} ms")
    finally:
        for shm in shms:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
