#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""IQ 全量频谱计算基准：PyTorch CUDA。

目的：
- 在 `xd_torch` 环境中验证 GPU 是否足以将“全量 IQ 频谱计算”压到 <1s；
- 保持算法口径尽量接近当前 `compute_segmented_power_spectrum(..., NFFT=512, mean)`；
- 分离两种时间：
  1) host->device 传输 + CUDA 计算
  2) 纯 CUDA 热计算（数据已驻留显存）
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch


def _load_complex64_bins(input_dir: Path) -> Tuple[np.ndarray, float]:
    files = sorted(input_dir.glob("*.bin"))
    if not files:
        raise FileNotFoundError(f"目录 {input_dir} 中没有 .bin 文件")

    arrays: List[np.ndarray] = []
    sample_rate_hz = 204.8e6
    for path in files:
        raw = np.fromfile(path, dtype=np.int16)
        if raw.size % 2 != 0:
            raw = raw[:-1]
        iq = raw.astype(np.float32).view(np.complex64)
        arrays.append(np.asarray(iq, dtype=np.complex64))

    lengths = {arr.shape[0] for arr in arrays}
    if len(lengths) != 1:
        raise ValueError(f"当前 CUDA 基准要求所有 bin 长度一致，实际长度集合: {sorted(lengths)}")

    stacked = np.stack(arrays, axis=0)  # [file_count, num_samples]
    return stacked, sample_rate_hz


def _cuda_segmented_mean_power(
    samples_gpu: torch.Tensor,
    *,
    nfft: int,
) -> torch.Tensor:
    """批量计算 [B, N] 复数 IQ 的分段平均功率谱。"""
    batch_size, num_samples = samples_gpu.shape
    num_chunks = (num_samples + int(nfft) - 1) // int(nfft)
    padded_len = num_chunks * int(nfft)
    if padded_len != num_samples:
        pad = torch.zeros((batch_size, padded_len - num_samples), dtype=samples_gpu.dtype, device=samples_gpu.device)
        samples_gpu = torch.cat([samples_gpu, pad], dim=1)

    chunks = samples_gpu.reshape(batch_size, num_chunks, int(nfft))
    window = torch.hann_window(int(nfft), periodic=True, device=samples_gpu.device, dtype=torch.float32)
    windowed = chunks * window
    fft = torch.fft.fft(windowed, n=int(nfft), dim=-1)
    power_linear = (fft.real * fft.real + fft.imag * fft.imag) / float(nfft)
    agg = power_linear.mean(dim=1)
    half = int(nfft) // 2
    shifted = torch.cat([agg[:, half:], agg[:, :half]], dim=1)
    power_db = 10.0 * torch.log10(shifted + 1e-12)
    return power_db


def _bench_transfer_and_compute(samples_np: np.ndarray, *, nfft: int, device: str, repeat: int) -> List[float]:
    costs: List[float] = []
    for _ in range(repeat):
        torch.cuda.synchronize(device)
        t0 = time.perf_counter()
        samples_gpu = torch.from_numpy(samples_np).to(device=device, dtype=torch.complex64, non_blocking=False)
        _ = _cuda_segmented_mean_power(samples_gpu, nfft=int(nfft))
        torch.cuda.synchronize(device)
        costs.append((time.perf_counter() - t0) * 1000.0)
    return costs


def _bench_compute_only(samples_gpu: torch.Tensor, *, nfft: int, device: str, repeat: int) -> List[float]:
    costs: List[float] = []
    for _ in range(repeat):
        torch.cuda.synchronize(device)
        t0 = time.perf_counter()
        _ = _cuda_segmented_mean_power(samples_gpu, nfft=int(nfft))
        torch.cuda.synchronize(device)
        costs.append((time.perf_counter() - t0) * 1000.0)
    return costs


def _fmt(values: List[float]) -> str:
    return "[" + ", ".join(f"{v:.3f}" for v in values) + "]"


def main() -> int:
    parser = argparse.ArgumentParser(description="基准：PyTorch CUDA 批量 IQ 频谱计算")
    parser.add_argument("--input-dir", type=Path, default=Path("data_segment"), help="IQ 目录")
    parser.add_argument("--nfft", type=int, default=512, help="分段 FFT 点数")
    parser.add_argument("--device", type=str, default="cuda:0", help="CUDA 设备")
    parser.add_argument("--repeat", type=int, default=3, help="重复次数")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("当前环境 torch.cuda.is_available() 为 False")

    samples_np, sample_rate_hz = _load_complex64_bins(args.input_dir)

    if hasattr(__import__("sys").stdout, "reconfigure"):
        __import__("sys").stdout.reconfigure(encoding="utf-8", errors="replace")

    print("================================================================================")
    print("PyTorch CUDA IQ 全量频谱基准")
    print("================================================================================")
    print(f"input_dir={args.input_dir}")
    print(f"shape={samples_np.shape}")
    print(f"sample_rate_hz={sample_rate_hz}")
    print(f"nfft={int(args.nfft)}")
    print(f"device={args.device}")
    print(f"repeat={int(args.repeat)}")

    transfer_costs = _bench_transfer_and_compute(
        samples_np,
        nfft=int(args.nfft),
        device=str(args.device),
        repeat=int(args.repeat),
    )
    print()
    print(
        "cuda_transfer_plus_compute="
        f"{_fmt(transfer_costs)}, mean={sum(transfer_costs)/len(transfer_costs):.3f} ms"
    )

    samples_gpu = torch.from_numpy(samples_np).to(device=str(args.device), dtype=torch.complex64, non_blocking=False)
    compute_costs = _bench_compute_only(
        samples_gpu,
        nfft=int(args.nfft),
        device=str(args.device),
        repeat=int(args.repeat),
    )
    print(
        "cuda_compute_only="
        f"{_fmt(compute_costs)}, mean={sum(compute_costs)/len(compute_costs):.3f} ms"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
