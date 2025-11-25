#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""甲方交付演示 - 生成简洁版和高级版双版本图像。

输出目录: data/delivery/
- simple/  简洁版
- premium/ 高级版
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Windows编码修复
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.signal.spectrum_composer import SpectrumComposerConfig, JammerSpec, compose_spectrum
from src.signal.stitcher import stitch_segments, SpectrumSegment, StitchMode
from src.semantics.decode import decode_semantic
from src.core.schemas import SemanticParams
from src.visualization.spectrum_plot import (
    plot_spectrum_simple,
    plot_spectrum_premium,
    plot_comparison_premium,
    plot_multi_segment_premium,
)


def main():
    # 输出目录
    output_dir = Path("data/delivery")
    simple_dir = output_dir / "simple"
    premium_dir = output_dir / "premium"
    simple_dir.mkdir(parents=True, exist_ok=True)
    premium_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("电磁态频谱语义化工程 - 甲方交付版本")
    print("=" * 60)

    # ==================== 任务一：干扰频谱合成 ====================
    print("\n[任务一] 干扰频谱合成...")

    cfg = SpectrumComposerConfig(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        resolution_mhz=1.0,
        # noise_floor_db 使用默认值 -80.0（基于真实采集数据分析）
    )

    # 添加多种干扰（JNR相对底噪，调整为符合真实动态范围）
    jammers = [
        JammerSpec("single_tone", 450.0, 25.0),  # 信号峰值约 -55dB
        JammerSpec("sweep", 850.0, 23.0),
        JammerSpec("noise_fm", 1200.0, 20.0),
        JammerSpec("comb", 1800.0, 18.0),
        JammerSpec("partial_band_noise", 2100.0, 15.0),
    ]
    for j in jammers:
        cfg.jammers.append(j)

    rng = np.random.default_rng(42)
    freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

    # 干扰区域标记
    jammer_regions = [
        (400, 500),
        (800, 900),
        (1150, 1250),
        (1750, 1850),
        (2050, 2150),
    ]

    # 标注
    annotations = [
        {"freq": 450, "power": power_db[420], "text": "Single Tone"},
        {"freq": 850, "power": power_db[820], "text": "Sweep"},
        {"freq": 1200, "power": power_db[1170], "text": "Noise FM"},
        {"freq": 1800, "power": power_db[1770], "text": "Comb"},
        {"freq": 2100, "power": power_db[2070], "text": "Partial Band"},
    ]

    # 简洁版
    plot_spectrum_simple(
        freq_mhz, power_db,
        title="Task 1: Composed Jammer Spectrum",
        save_path=simple_dir / "task1_composed.png",
    )

    # 高级版
    plot_spectrum_premium(
        freq_mhz, power_db,
        title="Electromagnetic Spectrum with Multiple Jammers",
        subtitle="5 jammer types across 30-2500 MHz band",
        save_path=premium_dir / "task1_composed.png",
        jammer_regions=jammer_regions,
        annotations=annotations,
    )

    print(f"  频率范围: {freq_mhz.min():.0f} - {freq_mhz.max():.0f} MHz")
    print(f"  功率范围: {power_db.min():.1f} - {power_db.max():.1f} dB")
    print(f"  已保存: task1_composed.png")

    # ==================== 任务二：频谱拼接 ====================
    print("\n[任务二] 频谱拼接...")

    # 模拟多个200MHz分段（使用1MHz分辨率与全局一致）
    segments = []
    centers = [130, 330, 530, 730, 930, 1130, 1330, 1530, 1730, 1930, 2130, 2330]

    rng_seg = np.random.default_rng(123)
    for center in centers:
        # 201点覆盖200MHz = 1MHz分辨率
        seg_freq = np.linspace(center - 100, center + 100, 201)
        # 底噪：基准值 + 随机波动（基于真实数据：-80dB ± 10dB）
        seg_power = -80.0 + rng_seg.standard_normal(201) * 5.0

        # 在某些频段添加干扰特征
        if 400 < center < 600:
            seg_power[80:120] += 20  # 模拟干扰峰值（JNR约20dB）

        segments.append(SpectrumSegment(
            freq_mhz=seg_freq,
            power_db=seg_power,
            center_freq_mhz=float(center),
            bandwidth_mhz=200.0,
        ))

    stitched = stitch_segments(segments, mode=StitchMode.MAX)

    # 简洁版
    plot_spectrum_simple(
        stitched.freq_mhz, stitched.power_db,
        title="Task 2: Stitched Spectrum",
        save_path=simple_dir / "task2_stitched.png",
    )

    # 高级版
    plot_multi_segment_premium(
        stitched.freq_mhz, stitched.power_db,
        stitched.coverage_map, len(segments),
        title="Multi-Segment Spectrum Stitching Result",
        save_path=premium_dir / "task2_stitched.png",
    )

    print(f"  分段数量: {len(segments)}")
    print(f"  频率范围: {stitched.freq_min_mhz:.0f} - {stitched.freq_max_mhz:.0f} MHz")
    print(f"  覆盖率: {(stitched.coverage_map > 0).sum() / len(stitched.coverage_map) * 100:.1f}%")
    print(f"  已保存: task2_stitched.png")

    # ==================== 任务三：语义恢复 ====================
    print("\n[任务三] 语义恢复...")

    # 创建理想频谱（基于真实数据特征）
    ideal_power = np.full(2471, -80.0)
    ideal_power[470:1471] = -60.0  # 干扰区域（JNR = 20dB）

    # 语义参数
    params = SemanticParams(
        yonghu=1,
        youwu=1,
        menxian=-80.0,  # 真实底噪水平
        pos_edge=[470],
        neg_edge=[1470],
        start=470,
        end=1470,
        fenbianlv=2471,
        sinr=np.array([20.0]),  # 信噪比20dB，符合真实动态范围
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
    )

    # 恢复
    recovered = decode_semantic(params)
    freq_semantic = np.linspace(30.0, 2500.0, 2471)

    # 简洁版
    plot_spectrum_simple(
        freq_semantic, recovered,
        title="Task 3: Recovered Spectrum",
        save_path=simple_dir / "task3_recovered.png",
    )

    # 高级版 - 对比图
    plot_comparison_premium(
        freq_semantic, ideal_power, recovered,
        title="Semantic Spectrum Recovery",
        save_path=premium_dir / "task3_comparison.png",
    )

    # 计算误差
    mask = np.ones(2471, dtype=bool)
    mask[470] = False
    mask[1470] = False
    mae = np.mean(np.abs(recovered[mask] - ideal_power[mask]))
    max_err = np.max(np.abs(recovered[mask] - ideal_power[mask]))

    print(f"  MAE: {mae:.2f} dB")
    print(f"  Max Error: {max_err:.2f} dB")
    print(f"  已保存: task3_recovered.png, task3_comparison.png")

    # 保存数据
    np.savez(
        output_dir / "task1_composed.npz",
        freq_mhz=freq_mhz, power_db=power_db,
    )
    np.savez(
        output_dir / "task2_stitched.npz",
        freq_mhz=stitched.freq_mhz,
        power_db=stitched.power_db,
        coverage_map=stitched.coverage_map,
    )
    np.savez(
        output_dir / "task3_recovered.npz",
        freq_mhz=freq_semantic,
        power_db=recovered,
        ideal_power=ideal_power,
    )

    print("\n" + "=" * 60)
    print("交付文件已生成:")
    print(f"  简洁版: {simple_dir}")
    print(f"  高级版: {premium_dir}")
    print(f"  数据:   {output_dir}/*.npz")
    print("=" * 60)


if __name__ == "__main__":
    main()
