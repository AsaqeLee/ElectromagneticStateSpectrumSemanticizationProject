#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""完整的三任务演示脚本：干扰合成、频谱拼接、语义恢复

本脚本演示电磁态频谱语义化工程的三个核心功能：
1. 任务一：在 30-2500 MHz 频段内任意组合生成干扰功率谱
2. 任务二：拼接 200MHz 频谱分段为完整宽带频谱（需要实际采集数据）
3. 任务三：从语义参数恢复功率谱

运行方式：
    python demo_all_tasks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
from src.signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
from src.semantics.decode import decode_semantic
from src.core.schemas import SemanticParams


def task1_compose_spectrum():
    """任务一：生成干扰功率谱"""
    print("\n" + "=" * 80)
    print("任务一：在 30-2500 MHz 频段内组合生成干扰功率谱")
    print("=" * 80)

    # 创建配置
    cfg = SpectrumComposerConfig(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        resolution_mhz=1.0,
        noise_floor_db=-120.0,
        sample_rate_hz=125e6,
        iq_length=32768,
    )

    # 添加多个干扰信号
    jammers = [
        ("single_tone", 500.0, 20.0),
        ("multi_tone", 1200.0, 18.0),
        ("sweep", 1800.0, 22.0),
        ("partial_band_noise", 800.0, 16.0),
    ]

    for jam_type, center_freq_mhz, jnr_db in jammers:
        add_jammer(cfg, jam_type, center_freq_mhz, jnr_db)
        print(f"  添加干扰: {jam_type:20s} @ {center_freq_mhz:7.1f} MHz, JNR={jnr_db:5.1f} dB")

    # 生成功率谱
    rng = np.random.default_rng(42)
    freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

    # 保存结果
    output_dir = Path("data/demo_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    npz_path = output_dir / "task1_composed_spectrum.npz"
    np.savez(npz_path, freq_mhz=freq_mhz, power_db=power_db)
    print(f"\n  功率谱已保存: {npz_path}")

    # 绘图
    png_path = output_dir / "task1_composed_spectrum.png"
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(freq_mhz, power_db, linewidth=0.8, color='blue', alpha=0.7)
    ax.set_xlabel("Frequency (MHz)", fontsize=12)
    ax.set_ylabel("Power (dB)", fontsize=12)
    ax.set_title("Task 1: Composed Jammer Spectrum (30-2500 MHz)", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlim(30, 2500)
    fig.tight_layout()
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  功率谱图已保存: {png_path}")

    print(f"\n  频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
    print(f"  频点数量: {freq_mhz.size}")
    print(f"  功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")

    return freq_mhz, power_db


def task2_stitch_spectrum():
    """任务二：频谱拼接演示（使用模拟数据）"""
    print("\n" + "=" * 80)
    print("任务二：拼接 200MHz 频谱分段为完整 30-2500 MHz 频谱")
    print("=" * 80)

    print("  注意: 此任务需要实际采集的 .bin 文件")
    print("  当前演示使用模拟分段数据")

    # 模拟 3 个 200MHz 分段
    segments = []
    centers = [130, 500, 1200]  # MHz

    for center_mhz in centers:
        # 模拟频谱分段
        bandwidth_mhz = 200.0
        f_min = center_mhz - bandwidth_mhz / 2
        f_max = center_mhz + bandwidth_mhz / 2
        freq = np.linspace(f_min, f_max, 1024)

        # 模拟功率谱（底噪 + 随机峰值）
        power = np.random.normal(-120, 5, freq.size)
        # 在中心频率附近添加干扰
        mask = (freq > center_mhz - 20) & (freq < center_mhz + 20)
        power[mask] += 30

        seg = SpectrumSegment(
            freq_mhz=freq,
            power_db=power,
            center_freq_mhz=center_mhz,
            bandwidth_mhz=bandwidth_mhz,
        )
        segments.append(seg)
        print(f"  模拟分段: center={center_mhz:7.1f} MHz, bandwidth={bandwidth_mhz:6.1f} MHz")

    # 拼接
    stitched = stitch_segments(segments, mode=StitchMode.MAX, fill_value=-180.0)

    # 保存结果
    output_dir = Path("data/demo_results")
    npz_path = output_dir / "task2_stitched_spectrum.npz"
    np.savez(
        npz_path,
        freq_mhz=stitched.freq_mhz,
        power_db=stitched.power_db,
        coverage_map=stitched.coverage_map,
    )
    print(f"\n  拼接频谱已保存: {npz_path}")

    # 绘图
    png_path = output_dir / "task2_stitched_spectrum.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    # 功率谱
    ax1.plot(stitched.freq_mhz, stitched.power_db, linewidth=0.8, color='green', alpha=0.7)
    ax1.set_ylabel("Power (dB)", fontsize=12)
    ax1.set_title("Task 2: Stitched Spectrum (Simulated)", fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')

    # 覆盖图
    ax2.plot(stitched.freq_mhz, stitched.coverage_map, linewidth=0.8, color='red', alpha=0.7)
    ax2.set_xlabel("Frequency (MHz)", fontsize=12)
    ax2.set_ylabel("Coverage Count", fontsize=12)
    ax2.set_title("Segment Coverage Map", fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')

    fig.tight_layout()
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  拼接频谱图已保存: {png_path}")

    print(f"\n  拼接频段: {stitched.freq_min_mhz:.2f} - {stitched.freq_max_mhz:.2f} MHz")
    print(f"  分段数量: {stitched.segment_count}")
    print(f"  最大覆盖: {stitched.coverage_map.max()} 段")

    return stitched.freq_mhz, stitched.power_db


def task3_semantic_recovery():
    """任务三：语义参数恢复频谱（独立演示）"""
    print("\n" + "=" * 80)
    print("任务三：从语义参数恢复功率谱")
    print("=" * 80)

    # 创建语义参数（模拟实际场景：描述500-1500MHz频段内的干扰）
    # 这是一个独立的语义编码示例，不依赖任务一
    params = SemanticParams(
        yonghu=1,
        youwu=1,
        menxian=-120.0,  # 底噪功率
        pos_edge=[470, 970],  # 正边缘索引：500MHz和1000MHz处
        neg_edge=[720, 1470],  # 负边缘索引：750MHz和1500MHz处
        start=470,  # (500-30) / 1.0 ≈ 470
        end=1470,   # (1500-30) / 1.0 ≈ 1470
        fenbianlv=2471,  # (2500-30)/1.0 + 1
        sinr=np.array([15.0]),  # 干扰相对底噪 15dB
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
    )

    print(f"  语义参数:")
    print(f"    底噪 (menxian): {params.menxian:.2f} dB")
    print(f"    干扰范围索引: [{params.start}, {params.end}]")
    print(f"    频率范围: {params.freq_min_mhz:.0f} - {params.freq_max_mhz:.0f} MHz")
    print(f"    分辨率: {params.resolution_mhz:.2f} MHz")
    print(f"    SINR: {params.sinr[0]:.1f} dB")

    # 恢复频谱
    recovered_power = decode_semantic(params)

    # 构建频率轴（与语义参数对应）
    freq_mhz = np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.fenbianlv)

    # 创建理想参考频谱（用于评估恢复质量）
    # 在实际应用中，这应该是编码前的原始频谱
    ideal_power = np.full_like(recovered_power, params.menxian)
    ideal_power[params.start:params.end+1] = params.menxian + params.sinr[0]

    # 计算恢复误差
    diff = recovered_power - ideal_power
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    max_err = float(np.max(np.abs(diff)))

    # 保存结果
    output_dir = Path("data/demo_results")
    npz_path = output_dir / "task3_recovered_spectrum.npz"
    np.savez(npz_path, freq_mhz=freq_mhz, power_db=recovered_power, ideal_power_db=ideal_power)
    print(f"\n  恢复频谱已保存: {npz_path}")

    # 保存评估报告
    report = {
        "yonghu": params.yonghu,
        "youwu": params.youwu,
        "mae_db": mae,
        "rmse_db": rmse,
        "max_err_db": max_err,
        "samples": freq_mhz.size,
        "semantic_freq_min_mhz": params.freq_min_mhz,
        "semantic_freq_max_mhz": params.freq_max_mhz,
        "semantic_resolution_mhz": params.resolution_mhz,
        "edge_boost_applied": True,
    }

    report_path = output_dir / "task3_eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  评估报告已保存: {report_path}")

    # 绘图对比
    png_path = output_dir / "task3_semantic_recovery.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 理想频谱 vs 恢复频谱
    ax1.plot(freq_mhz, ideal_power, linewidth=1.5, color='blue', alpha=0.7, label='Ideal (Pre-encoding)')
    ax1.plot(freq_mhz, recovered_power, linewidth=1.0, color='red', alpha=0.7, linestyle='--', label='Recovered (Post-decoding)')
    ax1.set_ylabel("Power (dB)", fontsize=12)
    ax1.set_title("Task 3: Semantic Spectrum Recovery", fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_xlim(30, 2500)

    # 误差
    ax2.plot(freq_mhz, diff, linewidth=0.8, color='purple', alpha=0.7)
    ax2.axhline(0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel("Frequency (MHz)", fontsize=12)
    ax2.set_ylabel("Error (dB)", fontsize=12)
    ax2.set_title(f"Recovery Error (MAE={mae:.2f} dB, RMSE={rmse:.2f} dB)", fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_xlim(30, 2500)

    fig.tight_layout()
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  对比图已保存: {png_path}")

    print(f"\n  误差统计:")
    print(f"    MAE:  {mae:.2f} dB")
    print(f"    RMSE: {rmse:.2f} dB")
    print(f"    MAX:  {max_err:.2f} dB")

    return recovered_power, report


def main():
    """主函数：运行所有三个任务"""
    print("\n" + "#" * 80)
    print("#" + " " * 78 + "#")
    print("#" + "  电磁态频谱语义化工程 - 完整演示".center(78) + "#")
    print("#" + " " * 78 + "#")
    print("#" * 80)

    try:
        # 任务一：生成干扰功率谱
        freq_mhz, power_db = task1_compose_spectrum()

        # 任务二：频谱拼接
        task2_stitch_spectrum()

        # 任务三：语义恢复（独立演示）
        task3_semantic_recovery()

    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 80)
    print("所有任务完成！结果已保存至 data/demo_results/ 目录")
    print("=" * 80)
    print("\n查看结果:")
    print("  - 任务一功率谱: data/demo_results/task1_composed_spectrum.png")
    print("  - 任务二拼接谱: data/demo_results/task2_stitched_spectrum.png")
    print("  - 任务三语义恢复: data/demo_results/task3_semantic_recovery.png")
    print("")


if __name__ == "__main__":
    main()
