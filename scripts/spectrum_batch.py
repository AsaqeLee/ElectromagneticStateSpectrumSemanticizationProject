#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电磁态频谱语义化工程 - 批处理CLI

支持命令行参数的非交互式操作，用于自动化流程。

用法示例:
  # 任务一：合成干扰频谱
  python spectrum_batch.py compose --jammer single_tone:500:20 --jammer sweep:1200:18 -o output.npz

  # 任务二：拼接真实数据
  python spectrum_batch.py stitch --input-dir data_segment --mode max -o stitched.npz

  # 任务三：语义恢复
  python spectrum_batch.py decode --input semantic_case01.json -o recovered_v2.npz
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Note: 编码处理已在各模块中完成

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signal.spectrum_composer import SpectrumComposerConfig, JammerSpec, compose_spectrum
from src.signal.stitcher import StitchMode
from src.pipeline.stitch.stitch_real_data import stitch_from_bin_directory
from src.io.reader import BinDataType
from src.semantics.decode_v2 import decode_file_v2


def _import_plt():
    """按需导入 matplotlib。

    目的：当用户不需要绘图时，避免导入 matplotlib 带来的冷启动开销与无 GUI 环境报错。
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:  # pragma: no cover - 依赖环境差异大
        raise RuntimeError("需要绘图功能，但 matplotlib 不可用/不可导入") from e
    return plt


def cmd_compose(args):
    """任务一：合成干扰频谱"""
    cfg = SpectrumComposerConfig(
        freq_min_mhz=args.freq_min,
        freq_max_mhz=args.freq_max,
        resolution_mhz=args.resolution,
        noise_floor_db=args.noise_floor,
    )

    # 解析干扰配置
    for jammer_str in args.jammer:
        parts = jammer_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"干扰格式错误: {jammer_str}，应为 type:freq:jnr")
        jam_type, freq, jnr = parts[0], float(parts[1]), float(parts[2])
        cfg.jammers.append(JammerSpec(jam_type, freq, jnr))
        print(f"添加干扰: {jam_type} @ {freq} MHz, JNR={jnr} dB")

    # 生成频谱
    rng = np.random.default_rng(args.seed)
    freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

    # 保存
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output, freq_mhz=freq_mhz, power_db=power_db)
    print(f"频谱已保存: {args.output}")

    # 可视化
    if args.show or args.plot:
        plt = _import_plt()
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(freq_mhz, power_db, linewidth=0.8)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        ax.set_title(f"Composed Spectrum: {len(cfg.jammers)} Jammers")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(args.freq_min, args.freq_max)
        fig.tight_layout()

        if args.plot:
            plt.savefig(args.plot, dpi=150, bbox_inches='tight')
            print(f"图像已保存: {args.plot}")

        if args.show:
            plt.show()
        else:
            plt.close(fig)

    print(f"频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
    print(f"功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")


def cmd_stitch(args):
    """任务二：拼接真实数据"""
    bin_dtype = BinDataType(args.dtype)
    mode = StitchMode(args.mode)

    segment_fft_size = int(args.segment_fft_size)
    if segment_fft_size > 0:
        stitched, segments = stitch_from_bin_directory(
            args.input_dir,
            args.pattern,
            bin_dtype,
            mode,
            args.fft_size,
            segment_fft_size=segment_fft_size,
            time_agg_mode=str(args.time_agg_mode),
            default_sample_rate_hz=float(args.sample_rate),
        )
    else:
        stitched, segments = stitch_from_bin_directory(
            args.input_dir,
            args.pattern,
            bin_dtype,
            mode,
            args.fft_size,
            default_sample_rate_hz=float(args.sample_rate),
        )

    # 保存
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output,
        freq_mhz=stitched.freq_mhz,
        power_db=stitched.power_db,
        coverage_map=stitched.coverage_map,
    )
    print(f"拼接频谱已保存: {args.output}")

    # 可视化
    if args.show or args.plot:
        plt = _import_plt()
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(stitched.freq_mhz, stitched.power_db, linewidth=0.5)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        ax.set_title(f"Stitched Spectrum: {len(segments)} segments")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        if args.plot:
            plt.savefig(args.plot, dpi=150, bbox_inches='tight')
            print(f"图像已保存: {args.plot}")

        if args.show:
            plt.show()
        else:
            plt.close(fig)

    print(f"频率范围: {stitched.freq_min_mhz:.2f} - {stitched.freq_max_mhz:.2f} MHz")
    print(f"功率范围: {stitched.power_db.min():.2f} - {stitched.power_db.max():.2f} dB")


def cmd_decode(args):
    """"任务三：基于 v2 语义参数恢复频谱。"""

    params, power_db = decode_file_v2(args.input)
    freq_mhz = np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.num_bins)

    # 保存
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output, freq_mhz=freq_mhz, power_db=power_db)
    print(f"v2 恢复频谱已保存: {args.output}")

    # 可视化
    if args.show or args.plot:
        plt = _import_plt()
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(freq_mhz, power_db, linewidth=0.8)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        ax.set_title("Recovered Spectrum from v2 Semantic Encoding")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        if args.plot:
            plt.savefig(args.plot, dpi=150, bbox_inches='tight')
            print(f"图像已保存: {args.plot}")

        if args.show:
            plt.show()
        else:
            plt.close(fig)

    print(f"频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
    print(f"功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")


def main():
    parser = argparse.ArgumentParser(
        description="电磁态频谱语义化工程 - 批处理CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 任务一：合成
    p_compose = subparsers.add_parser("compose", help="合成干扰频谱")
    p_compose.add_argument("--jammer", action="append", required=True,
                          help="干扰配置 type:freq:jnr，可多次使用")
    p_compose.add_argument("-o", "--output", type=Path, default=Path("composed.npz"))
    p_compose.add_argument("--freq-min", type=float, default=30.0)
    p_compose.add_argument("--freq-max", type=float, default=2500.0)
    p_compose.add_argument("--resolution", type=float, default=1.0)
    p_compose.add_argument("--noise-floor", type=float, default=-120.0)
    p_compose.add_argument("--seed", type=int, default=None)
    p_compose.add_argument("--show", action="store_true", help="显示图形")
    p_compose.add_argument("--plot", type=Path, help="保存图像路径")
    p_compose.set_defaults(func=cmd_compose)

    # 任务二：拼接
    p_stitch = subparsers.add_parser("stitch", help="拼接真实数据")
    p_stitch.add_argument("--input-dir", type=Path, required=True)
    p_stitch.add_argument("-o", "--output", type=Path, default=Path("stitched.npz"))
    p_stitch.add_argument("--pattern", default="*.bin")
    p_stitch.add_argument("--dtype", default="int16",
                         choices=["int16", "int8", "float32", "complex64"])
    p_stitch.add_argument("--mode", default="max",
                         choices=["max", "mean", "weighted_mean"])
    p_stitch.add_argument("--fft-size", type=int, default=8192)
    p_stitch.add_argument(
        "--segment-fft-size",
        type=int,
        default=512,
        help="分段 FFT 点数（NFFT）。>0 启用分段 FFT；=0 禁用分段 FFT 并退回单次 FFT（使用 --fft-size）",
    )
    p_stitch.add_argument(
        "--time-agg-mode",
        type=str,
        default="mean",
        choices=["mean", "max"],
        help="分段 FFT 的时间聚合方式（仅在启用 --segment-fft-size 时生效）",
    )
    p_stitch.add_argument(
        "--sample-rate",
        type=float,
        default=204.8e6,
        help="默认采样率 Hz（当文件名不包含带宽/采样率信息时使用，例如 130MHz.bin）",
    )
    p_stitch.add_argument("--show", action="store_true")
    p_stitch.add_argument("--plot", type=Path)
    p_stitch.set_defaults(func=cmd_stitch)

    # 任务三：解码（仅 v2）
    p_decode = subparsers.add_parser("decode", help="语义恢复 (v2/jammer_regions)")
    p_decode.add_argument("--input", type=Path, required=True, help="v2 语义参数 JSON/TXT")
    p_decode.add_argument("-o", "--output", type=Path, default=Path("recovered_v2.npz"))
    p_decode.add_argument("--show", action="store_true")
    p_decode.add_argument("--plot", type=Path)
    p_decode.set_defaults(func=cmd_decode)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        args.func(args)
        return 0
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Fix Windows 控制台编码，避免在非 UTF-8 终端下打印中文报错
    if sys.platform == "win32":
        import io

        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding="utf-8",
                errors="replace",
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding="utf-8",
                errors="replace",
            )
        except (AttributeError, ValueError):
            # 某些环境下 sys.stdout 可能不暴露 buffer，忽略即可
            pass

    sys.exit(main())
