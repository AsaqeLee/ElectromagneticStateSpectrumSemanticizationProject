#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最小示例：如何调用 scripts.run_union.main。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent

from scripts import run_union  # noqa: E402


def run_once() -> None:
    start_time = time.perf_counter()
    return_code = run_union.main(
        quiet=True,
        enable_plot=False,
        segment_fft_size=512,
        time_agg_mode="mean",
        noise_floor_dbm_1mhz=-105.0,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    output_path = ROOT / "output" / "union_spectrum.npz"
    data = np.load(output_path)
    freq_mhz = data["freq_mhz"]
    power_db = data["power_db"]
    jnr_db = data["jnr_db"] if "jnr_db" in data.files else None

    print("=== 单次调用 ===")
    print(f"返回码: {return_code}")
    print(f"耗时: {elapsed_ms:.3f} ms")
    print(f"输出文件: {output_path}")
    print(
        "频轴: "
        f"{float(freq_mhz[0]):.1f} ~ {float(freq_mhz[-1]):.1f} MHz, "
        f"点数 {freq_mhz.size}, 步进 {float(freq_mhz[1] - freq_mhz[0]):.1f} MHz"
    )
    print(
        "总功率范围: "
        f"{float(power_db.min()):.3f} ~ {float(power_db.max()):.3f} dBm@1MHz"
    )
    if jnr_db is not None:
        print(
            "JNR范围: "
            f"{float(jnr_db.min()):.3f} ~ {float(jnr_db.max()):.3f} dB"
        )


def run_hot_loop(loop_count: int = 5) -> None:
    print("\n=== 热调用示例 ===")
    print("说明: 第 1 次通常包含首次初始化，后续更接近真实热调用时延。")

    elapsed_list_ms: list[float] = []
    for index in range(loop_count):
        start_time = time.perf_counter()
        return_code = run_union.main(
            quiet=True,
            enable_plot=False,
            segment_fft_size=512,
            time_agg_mode="mean",
            noise_floor_dbm_1mhz=-105.0,
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        elapsed_list_ms.append(elapsed_ms)
        print(f"第 {index + 1} 次: ret={return_code}, {elapsed_ms:.3f} ms")

    if elapsed_list_ms:
        average_ms = sum(elapsed_list_ms) / len(elapsed_list_ms)
        print(f"平均耗时: {average_ms:.3f} ms")
        print(f"最小耗时: {min(elapsed_list_ms):.3f} ms")
        print(f"最大耗时: {max(elapsed_list_ms):.3f} ms")


def main() -> None:
    run_once()
    run_hot_loop(loop_count=5)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()