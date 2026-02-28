"""任务二：使用真实.bin数据进行频谱拼接。

从data_segment目录读取真实采集的IQ数据，计算功率谱并拼接。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Union

import numpy as np

try:
    # 优先作为 src 包内部模块导入（正常通过 src.pipeline.stitch 使用时）
    from ..io.reader import load_bin_segments, BinDataType
    from ..signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from ..signal.spectrum import compute_power_spectrum, compute_segmented_power_spectrum
    from ..core.schemas import SamplingConfig
except ImportError:
    # 兼容直接运行本文件的场景：将仓库根目录加入 sys.path 后按 src 包导入
    root_dir = Path(__file__).resolve().parents[3]
    if str(root_dir) not in sys.path:
        sys.path.append(str(root_dir))
    from src.io.reader import load_bin_segments, BinDataType
    from src.signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from src.signal.spectrum import compute_power_spectrum, compute_segmented_power_spectrum
    from src.core.schemas import SamplingConfig


def stitch_from_bin_directory(
    directory: Union[str, Path],
    pattern: str = "*.bin",
    bin_dtype: BinDataType = BinDataType.INT16,
    mode: StitchMode = StitchMode.MAX,
    fft_size: int = 8192,
    window: str = "hann",
    fill_value: float = -180.0,
    target_df_hz: Optional[float] = None,
    time_agg_mode: str = "mean",
    segment_fft_size: Optional[int] = None,
    default_sample_rate_hz: Optional[float] = 204.8e6,
) -> tuple:
    """从目录中的.bin文件拼接频谱。

    参数:
    - directory: 包含.bin文件的目录
    - pattern: 文件匹配模式
    - bin_dtype: 数据类型
    - mode: 拼接模式
    - fft_size: FFT点数（当未指定 target_df_hz 时生效）
    - window: 窗函数
    - fill_value: 未覆盖区域填充值
    - target_df_hz: 目标频率分辨率（Hz），指定时将按分段 FFT 计算功率谱
    - time_agg_mode: 分段之间的时间聚合方式（mean/max）
    - segment_fft_size: 分段 FFT 点数（NFFT）。指定时将覆盖 target_df_hz，
      且对每个分段按其自身采样率计算 target_df_hz=Fs/NFFT，保证得到固定 NFFT。
    - default_sample_rate_hz: 当文件名无法推断采样率时使用的默认采样率（Hz）。
      典型场景：文件名仅为 `{center}MHz.bin`。

    返回:
    - stitched: 拼接后的频谱对象
    - segments: 分段列表（用于调试）
    """
    # 加载所有.bin文件
    iq_list = load_bin_segments(
        directory,
        pattern,
        bin_dtype,
        default_sample_rate_hz=default_sample_rate_hz,
    )
    print(f"已加载 {len(iq_list)} 个IQ分段")

    if not iq_list:
        raise ValueError("未找到有效的IQ数据")

    # 转换为频谱分段
    segments = []
    for iq in iq_list:
        # 创建采样配置（用于频轴与 FFT 尺度）
        cfg = SamplingConfig(
            sample_rate_hz=iq.sample_rate_hz,
            center_freq_hz=iq.center_freq_hz,
            fft_size=fft_size,
        )

        # 计算功率谱：
        # - 若指定了 segment_fft_size，则采用固定 NFFT 的分段 FFT（推荐用于大样本 .bin）；
        # - 否则若指定了 target_df_hz，则采用目标分辨率分段 FFT；
        # - 否则沿用原有单次 FFT 行为。
        if segment_fft_size is not None:
            if segment_fft_size < 2:
                raise ValueError(f"segment_fft_size 过小: {segment_fft_size}（至少 2）")
            seg_target_df_hz = float(iq.sample_rate_hz) / float(segment_fft_size)
            freq_mhz, power_db = compute_segmented_power_spectrum(
                iq,
                cfg,
                target_df_hz=seg_target_df_hz,
                window=window,
                time_agg_mode=time_agg_mode,
            )
        elif target_df_hz is not None:
            freq_mhz, power_db = compute_segmented_power_spectrum(
                iq,
                cfg,
                target_df_hz=target_df_hz,
                window=window,
                time_agg_mode=time_agg_mode,
            )
        else:
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
        "--segment-fft-size",
        type=int,
        default=512,
        help="分段 FFT 点数（NFFT）。>0 启用分段 FFT；=0 禁用并退回单次 FFT（使用 --fft-size）",
    )
    parser.add_argument(
        "--time-agg-mode",
        type=str,
        default="mean",
        choices=["mean", "max"],
        help="分段 FFT 的时间聚合方式（仅在启用 --segment-fft-size 时生效）",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=204.8e6,
        help="默认采样率 Hz（当文件名不包含带宽/采样率信息时使用，例如 130MHz.bin）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/real_stitch_results"),
        help="输出目录",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="不生成 PNG 图（仅保存 npz，适用于性能测试/无图形环境）",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="显示图形",
    )
    args = parser.parse_args()

    if args.show and args.no_plot:
        raise SystemExit("参数错误：--show 需要绘图，不能与 --no-plot 同时使用")

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
    if int(args.segment_fft_size) > 0:
        print(f"分段 FFT: NFFT={int(args.segment_fft_size)}, 时间聚合={args.time_agg_mode}")
    else:
        print(f"单次 FFT: NFFT={args.fft_size}")
    print()

    # 执行拼接
    segment_fft_size = int(args.segment_fft_size)
    stitched, segments = stitch_from_bin_directory(
        args.input_dir,
        args.pattern,
        bin_dtype,
        mode,
        args.fft_size,
        segment_fft_size=(segment_fft_size if segment_fft_size > 0 else None),
        time_agg_mode=str(args.time_agg_mode),
        default_sample_rate_hz=float(args.sample_rate),
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

    if not args.no_plot:
        # 绘图是可选路径：不要在模块 import 阶段引入 matplotlib（启动慢、还容易在无 GUI 环境炸）。
        import matplotlib.pyplot as plt

        png_path = args.output_dir / "stitched_real_spectrum.png"
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # 功率谱
        ax1.plot(stitched.freq_mhz, stitched.power_db, linewidth=0.5, color='blue', alpha=0.8)
        ax1.set_ylabel("Power (dB)", fontsize=12)
        ax1.set_title(
            f"Real Data Stitched Spectrum ({len(segments)} segments, mode={args.mode})",
            fontsize=14,
            fontweight='bold',
        )
        ax1.grid(True, alpha=0.3, linestyle='--')

        # 标记每个分段的范围
        colors = plt.cm.Set2(np.linspace(0, 1, len(segments)))
        for i, seg in enumerate(segments):
            f_min = seg.freq_mhz.min()
            f_max = seg.freq_mhz.max()
            ax1.axvspan(
                f_min,
                f_max,
                alpha=0.1,
                color=colors[i],
                label=f"{seg.metadata.get('jam_type', f'seg{i}')} @ {seg.center_freq_mhz:.0f}MHz",
            )

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
    # Fix Windows console encoding for CLI use
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
            # 某些环境下 sys.stdout 可能不暴露 buffer，忽略即可
            pass

    main()
