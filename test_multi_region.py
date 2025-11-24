#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试多区域频谱语义恢复。

场景：30-2500 MHz频段内有5个不连续的干扰区域：
- 80-120 MHz
- 500-520 MHz
- 600-720 MHz
- 1500-1800 MHz
- 2200-2300 MHz
"""
import sys
import os
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Windows编码修复
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.schemas import SemanticParams
from src.semantics.decode_multi import decode_semantic_multi_region
from src.visualization.spectrum_plot import plot_spectrum_premium


def main():
    print("=" * 60)
    print("多区域频谱语义恢复测试")
    print("=" * 60)

    # 场景：5个不连续干扰区域
    # 频率范围 30-2500 MHz，分辨率 1 MHz → 2471 个点
    freq_axis = np.linspace(30.0, 2500.0, 2471)

    # 计算每个区域的 bin 索引
    # 公式: bin_index = (freq_mhz - freq_min) / resolution
    def freq_to_bin(freq_mhz):
        return int((freq_mhz - 30.0) / 1.0)

    regions_mhz = [
        (80, 120),
        (500, 520),
        (600, 720),
        (1500, 1800),
        (2200, 2300),
    ]

    regions_bins = [(freq_to_bin(start), freq_to_bin(end)) for start, end in regions_mhz]

    print(f"\n干扰区域（频率 → bin索引）:")
    for (f_start, f_end), (b_start, b_end) in zip(regions_mhz, regions_bins):
        print(f"  {f_start:4d}-{f_end:4d} MHz → bin [{b_start:4d}, {b_end:4d}]")

    # 每个区域的 JNR
    jnr_values = [25.0, 20.0, 22.0, 18.0, 15.0]

    # 构造语义参数
    params = SemanticParams(
        yonghu=1,
        youwu=1,
        menxian=-80.0,  # 底噪
        pos_edge=[b[0] for b in regions_bins],  # 5个区域起点
        neg_edge=[b[1] for b in regions_bins],  # 5个区域终点
        start=0,  # 多区域模式下不使用
        end=0,
        fenbianlv=2471,
        sinr=np.array(jnr_values),
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
    )

    print(f"\n语义参数:")
    print(f"  底噪: {params.menxian} dB")
    print(f"  区域数: {len(params.pos_edge)}")
    print(f"  JNR: {jnr_values}")

    # 恢复频谱
    power_db = decode_semantic_multi_region(params)

    # 统计
    noise_mask = power_db == params.menxian
    jammer_mask = ~noise_mask

    print(f"\n恢复结果:")
    print(f"  总点数: {len(power_db)}")
    print(f"  底噪点数: {noise_mask.sum()} ({noise_mask.sum()/len(power_db)*100:.1f}%)")
    print(f"  干扰点数: {jammer_mask.sum()} ({jammer_mask.sum()/len(power_db)*100:.1f}%)")
    print(f"  功率范围: {power_db.min():.1f} - {power_db.max():.1f} dB")

    # 验证每个区域
    print(f"\n各区域功率验证:")
    for i, ((b_start, b_end), jnr) in enumerate(zip(regions_bins, jnr_values)):
        region_power = power_db[b_start:b_end+1]
        expected_power = params.menxian + jnr

        is_correct = np.allclose(region_power, expected_power)
        actual_avg = region_power.mean()

        status = "✓" if is_correct else "✗"
        print(f"  {status} 区域 {i+1}: 期望={expected_power:.1f} dB, 实际={actual_avg:.1f} dB")

    # 验证空白区域是否为底噪
    print(f"\n空白区域验证:")
    # 检查第一个空白区域：bin 0-49（30-79 MHz）
    blank1 = power_db[0:freq_to_bin(79)+1]
    print(f"  30-79 MHz: {np.allclose(blank1, params.menxian)} (应为底噪)")

    # 检查区域间空白：120-499 MHz
    blank2 = power_db[freq_to_bin(121):freq_to_bin(499)+1]
    print(f"  121-499 MHz: {np.allclose(blank2, params.menxian)} (应为底噪)")

    # 可视化
    print(f"\n生成可视化...")

    # 标注区域
    jammer_regions_viz = [(f[0], f[1]) for f in regions_mhz]
    annotations = [
        {"freq": (start+end)/2, "power": params.menxian + jnr + 3,
         "text": f"Region {i+1}\n{jnr:.0f} dB JNR"}
        for i, ((start, end), jnr) in enumerate(zip(regions_mhz, jnr_values))
    ]

    plot_spectrum_premium(
        freq_axis, power_db,
        title="Multi-Region Spectrum Semantic Recovery",
        subtitle="5 non-contiguous jammer regions in 30-2500 MHz band",
        save_path="data/delivery/premium/multi_region_test.png",
        jammer_regions=jammer_regions_viz,
        annotations=annotations,
    )

    print(f"  已保存: data/delivery/premium/multi_region_test.png")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
