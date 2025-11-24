#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""为任务二创建模拟的 .bin 采集文件

此脚本生成符合命名规范的模拟 IQ 数据文件，用于测试频谱拼接功能。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.signal.jammers import generate_jammer, JammerConfig


def create_simulated_bin_file(
    output_path: Path,
    center_freq_mhz: float,
    sample_rate_mhz: float,
    num_samples: int = 262144,
    jam_type: str = "multi_tone",
    jnr_db: float = 20.0,
):
    """创建一个模拟的 .bin 文件"""

    # 生成干扰信号
    cfg = JammerConfig(
        length=num_samples,
        sample_rate_hz=sample_rate_mhz * 1e6,
        jnr_db=jnr_db,
    )

    # 中心频率为 0（基带）
    iq, bandwidth_hz = generate_jammer(jam_type, fc_hz=0.0, cfg=cfg, rng=np.random.default_rng(42))

    # 转换为 int16 格式
    # 归一化到 [-1, 1]
    peak_val = np.max(np.abs(iq))
    if peak_val > 0:
        iq_scaled = iq * (0.8 / peak_val)  # 留 20% 余量
    else:
        iq_scaled = iq

    # 转换为 int16 I/Q 交织格式
    i_part = np.real(iq_scaled)
    q_part = np.imag(iq_scaled)

    i_int16 = np.clip(i_part * 32767, -32768, 32767).astype(np.int16)
    q_int16 = np.clip(q_part * 32767, -32768, 32767).astype(np.int16)

    # 交织 I/Q
    iq_interleaved = np.empty(num_samples * 2, dtype=np.int16)
    iq_interleaved[0::2] = i_int16
    iq_interleaved[1::2] = q_int16

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    iq_interleaved.tofile(output_path)

    return bandwidth_hz


def main():
    """创建多个模拟的频谱分段文件"""
    print("\n" + "=" * 80)
    print("为任务二创建模拟的 .bin 采集文件")
    print("=" * 80)

    output_dir = Path("data/test_segments")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 模拟 5 个频段的采集
    segments = [
        (130, "multi_tone"),
        (330, "sweep"),
        (530, "partial_band_noise"),
        (930, "comb"),
        (1530, "single_tone"),
    ]

    sample_rate_mhz = 204.8
    num_samples = 262144

    print(f"\n输出目录: {output_dir}")
    print(f"采样率: {sample_rate_mhz} MHz")
    print(f"样本数: {num_samples}\n")

    for center_mhz, jam_type in segments:
        filename = f"comb_{center_mhz}MHz_{sample_rate_mhz}MHz_simulated.bin"
        output_path = output_dir / filename

        bandwidth_hz = create_simulated_bin_file(
            output_path,
            center_freq_mhz=center_mhz,
            sample_rate_mhz=sample_rate_mhz,
            num_samples=num_samples,
            jam_type=jam_type,
            jnr_db=20.0,
        )

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  创建文件: {filename}")
        print(f"    中心频率: {center_mhz} MHz")
        print(f"    干扰类型: {jam_type}")
        print(f"    干扰带宽: {bandwidth_hz/1e6:.2f} MHz")
        print(f"    文件大小: {file_size_mb:.2f} MB\n")

    print("=" * 80)
    print(f"完成！共创建 {len(segments)} 个模拟采集文件")
    print("=" * 80)
    print(f"\n现在可以运行任务二测试:")
    print(f"  python -m src.pipeline.stitch_multi \\")
    print(f"    --input-dir {output_dir} \\")
    print(f"    --fft-size 262144 \\")
    print(f"    --output-npz data/task2_stitched.npz \\")
    print(f"    --output-png data/task2_stitched.png")
    print("")


if __name__ == "__main__":
    main()
