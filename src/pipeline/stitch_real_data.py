"""任务二：使用真实.bin数据进行频谱拼接。

从data_segment目录读取真实采集的IQ数据，计算功率谱并拼接。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    from ..io.reader import load_bin_segments, load_iq_file, BinDataType
    from ..signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from ..signal.spectrum import compute_power_spectrum
    from ..core.schemas import SamplingConfig
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from io.reader import load_bin_segments, load_iq_file, BinDataType
    from signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from signal.spectrum import compute_power_spectrum
    from core.schemas import SamplingConfig


def stitch_from_bin_directory(
    directory: str | Path,
    pattern: str = "*.bin",
    bin_dtype: BinDataType = BinDataType.INT16,
    mode: StitchMode = StitchMode.MAX,
    fft_size: int = 8192,
    window: str = "hann",
    fill_value: float = -180.0,
) -> tuple:
    """从目录中的.bin文件拼接频谱。

    参数:
    - directory: 包含.bin文件的目录
    - pattern: 文件匹配模式
    - bin_dtype: 数据类型
    - mode: 拼接模式
    - fft_size: FFT点数
    - window: 窗函数
    - fill_value: 未覆盖区域填充值

    返回:
    - stitched: 拼接后的频谱对象
    - segments: 分段列表（用于调试）
    """
    # 加载所有.bin文件
    iq_list = load_bin_segments(directory, pattern, bin_dtype)
    print(f"已加载 {len(iq_list)} 个IQ分段")

    if not iq_list:
        raise ValueError("未找到有效的IQ数据")

    # 转换为频谱分段
    segments = []
    for iq in iq_list:
        # 创建采样配置
        cfg = SamplingConfig(
            sample_rate_hz=iq.sample_rate_hz,
            center_freq_hz=iq.center_freq_hz,
            fft_size=fft_size,
        )

        # 计算功率谱
        freq_mhz, power_db = compute_power_spectrum(iq, cfg, window=window)

        # 创建分段
        seg = SpectrumSegment(
            freq_mhz=freq_mhz,
            power_db=power_db,
            center_freq_mhz=iq.center_freq_hz / 1e6,
            bandwidth_mhz=iq.sample_rate_hz / 1e6,
            metadata=iq.meta,
        )
        segments.append(seg)

        jam_type = iq.meta.get("jam_type", "unknown")
        print(f"  分段: {jam_type} @ {seg.center_freq_mhz:.1f} MHz, "
              f"带宽 {seg.bandwidth_mhz:.1f} MHz, "
              f"功率范围 [{power_db.min():.1f}, {power_db.max():.1f}] dB")

    # 拼接
    stitched = stitch_segments(segments, mode=mode, fill_value=fill_value)

    return stitched, segments


def main():
    parser = argparse.ArgumentParser(
        description="任务二：使用真实.bin数据进行频谱拼接",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data_segment"),
        help="包含.bin文件的目录",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.bin",
        help="文件匹配模式",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        choices=["int16", "int8", "float32", "complex64", "complex128"],
        default="int16",
        help="数据类型",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["max", "mean", "weighted_mean"],
        default="max",
        help="拼接模式",
    )
    parser.add_argument(
        "--fft-size",
        type=int,
        default=8192,
        help="FFT点数",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/real_stitch_results"),
        help="输出目录",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="显示图形",
    )
    args = parser.parse_args()

    # 检查输入目录
    if not args.input_dir.exists():
        raise SystemExit(f"输入目录不存在: {args.input_dir}")

    # 设置参数
    bin_dtype = BinDataType(args.dtype)
    mode = StitchMode(args.mode)

    print("=" * 80)
    print("任务二：使用真实数据进行频谱拼接")
    print("=" * 80)
    print(f"输入目录: {args.input_dir}")
    print(f"数据类型: {args.dtype}")
    print(f"拼接模式: {args.mode}")
    print(f"FFT点数: {args.fft_size}")
    print()

    # 执行拼接
    stitched, segments = stitch_from_bin_directory(
        args.input_dir,
        args.pattern,
        bin_dtype,
        mode,
        args.fft_size,
    )

    # 保存结果
    args.output_dir.mkdir(parents=True, exist_ok=True)

    npz_path = args.output_dir / "stitched_real_spectrum.npz"
    np.savez(
        npz_path,
        freq_mhz=stitched.freq_mhz,
        power_db=stitched.power_db,
        coverage_map=stitched.coverage_map,
    )
    print(f"\n拼接频谱已保存: {npz_path}")

    # 绘图
    png_path = args.output_dir / "stitched_real_spectrum.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # 功率谱
    ax1.plot(stitched.freq_mhz, stitched.power_db, linewidth=0.5, color='blue', alpha=0.8)
    ax1.set_ylabel("Power (dB)", fontsize=12)
    ax1.set_title(f"Real Data Stitched Spectrum ({len(segments)} segments, mode={args.mode})",
                  fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')

    # 标记每个分段的范围
    colors = plt.cm.Set2(np.linspace(0, 1, len(segments)))
    for i, seg in enumerate(segments):
        f_min = seg.freq_mhz.min()
        f_max = seg.freq_mhz.max()
        ax1.axvspan(f_min, f_max, alpha=0.1, color=colors[i],
                   label=f"{seg.metadata.get('jam_type', f'seg{i}')} @ {seg.center_freq_mhz:.0f}MHz")

    ax1.legend(loc='upper right', fontsize=8, ncol=2)

    # 覆盖图
    ax2.plot(stitched.freq_mhz, stitched.coverage_map, linewidth=0.8, color='red', alpha=0.7)
    ax2.set_xlabel("Frequency (MHz)", fontsize=12)
    ax2.set_ylabel("Coverage Count", fontsize=12)
    ax2.set_title("Segment Coverage Map", fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_ylim(0, max(stitched.coverage_map.max() + 1, 2))

    fig.tight_layout()
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    print(f"拼接频谱图已保存: {png_path}")

    if args.show:
        plt.show()
    else:
        plt.close(fig)

    # 打印统计
    print(f"\n拼接结果统计:")
    print(f"  频率范围: {stitched.freq_min_mhz:.2f} - {stitched.freq_max_mhz:.2f} MHz")
    print(f"  频点数: {stitched.freq_mhz.size}")
    print(f"  分段数: {stitched.segment_count}")
    print(f"  最大覆盖: {stitched.coverage_map.max()} 段")
    print(f"  功率范围: {stitched.power_db.min():.2f} - {stitched.power_db.max():.2f} dB")


if __name__ == "__main__":
    main()
