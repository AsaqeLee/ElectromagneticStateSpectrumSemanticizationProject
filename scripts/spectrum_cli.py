#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""电磁态频谱语义化工程 - 交互式CLI工具

提供三个核心功能的交互式操作界面：
1. 干扰频谱合成
2. 频谱分段拼接
3. 语义参数编解码
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

# Fix Windows console encoding
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
        # 在某些环境下 stdout 可能没有 buffer 属性，忽略即可
        pass

# 添加项目根目录到 sys.path，确保可以导入 src 包
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.signal.spectrum_composer import (
    SpectrumComposerConfig,
    JammerSpec,
    compose_spectrum,
)
from src.signal.stitcher import (
    SpectrumSegment,
    stitch_segments,
    StitchMode,
    load_segment_from_npz,
)
from src.pipeline.stitch.stitch_real_data import stitch_from_bin_directory
from src.io.reader import BinDataType, load_iq_file
from src.signal.spectrum import compute_power_spectrum, compute_segmented_power_spectrum
from src.semantics.decode_v2 import (
    decode_semantic_v2 as decode_semantic,
    load_semantic_v2_file as load_semantic_file,
)
from src.core.schemas import (
    SamplingConfig,
    DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
    DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
    DEFAULT_SEMANTIC_NUM_BINS,
    DEFAULT_SEMANTIC_NOISE_FLOOR_DB,
)

# 任务二+任务三 并集输出（脚本复用）
import scripts.run_union as run_union


# 干扰类型选项表：内部使用英文标识，对用户展示中文描述
JAMMER_TYPE_CHOICES = [
    ("noise_fm", "调频噪声干扰"),
    ("single_tone", "单音干扰"),
    ("multi_tone", "多音干扰"),
    ("comb", "梳状干扰"),
    ("partial_band_noise", "部分频带噪声干扰"),
    ("sweep", "扫频干扰"),
]


def save_spectrum_png(freq_mhz: np.ndarray, power_db: np.ndarray, output_path: Path, title: str = "") -> None:
    """将频谱画成曲线并保存为 PNG 文件"""
    if plt is None:
        print("  ⚠️ 未安装 matplotlib，无法保存频谱图 (PNG)")
        return

    try:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(freq_mhz, power_db, linewidth=0.8)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        if title:
            ax.set_title(title)
        ax.grid(True, linestyle="--", alpha=0.5)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        print(f"  ✓ 频谱图已保存: {output_path}")
    except Exception as e:
        print(f"  ⚠️ 保存频谱图失败: {e}")


def _collect_bin_files(bin_dir: Path, pattern: str) -> list[Path]:
    """收集目录下匹配到的 .bin 文件。

    规则：
    - 优先使用 pattern；
    - 若 pattern 未匹配到但目录下只有一个 *.bin，则直接返回该文件（避免通配符误伤）；
    - 若 pattern 未匹配到且目录下存在多个 *.bin，则提示用户修正 pattern。
    """

    matched = sorted(bin_dir.glob(pattern))
    if matched:
        return matched

    fallback = sorted(bin_dir.glob("*.bin"))
    if len(fallback) == 1:
        return fallback
    if len(fallback) > 1:
        raise FileNotFoundError(
            f"通配符 {pattern} 未匹配到文件，但目录下存在 {len(fallback)} 个 .bin；请调整文件匹配模式后重试。"
        )
    raise FileNotFoundError(f"目录 {bin_dir} 中未找到任何 .bin 文件。")





def clear_screen():
    """清屏"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """打印欢迎横幅"""
    print("\n" + "=" * 80)
    print("║" + " " * 78 + "║")
    print("║" + "电磁态频谱语义化工程 - 交互式CLI".center(76) + "║")
    print("║" + " " * 78 + "║")
    print("=" * 80)


def print_menu():
    """打印主菜单"""
    print("\n【主菜单】")
    print("  1. 任务一：合成干扰功率谱 (30-2500 MHz)")
    print("  2. 任务二：拼接频谱分段（单文件 FFT 支持）")
    print("  3. 任务三：语义参数恢复频谱")
    print("  4. 查看使用指南")
    print("  11. 任务二+任务三：输出并集频谱 (run_union)")
    print("  5. 退出")
    print("-" * 80)


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """获取用户输入，支持默认值"""
    if default:
        user_input = input(f"{prompt} [默认: {default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def get_float(prompt: str, default: Optional[float] = None) -> float:
    """获取浮点数输入"""
    while True:
        try:
            val = get_input(prompt, str(default) if default else None)
            return float(val)
        except ValueError:
            print("  ⚠️ 输入无效，请输入数字")


def get_int(prompt: str, default: Optional[int] = None) -> int:
    """获取整数输入"""
    while True:
        try:
            val = get_input(prompt, str(default) if default else None)
            return int(val)
        except ValueError:
            print("  ⚠️ 输入无效，请输入整数")


def task1_interactive():
    """任务一：交互式合成干扰功率谱"""
    print("\n" + "=" * 80)
    print("【任务一】合成干扰功率谱")
    print("=" * 80)

    # 配置参数
    print("\n➤ 频谱配置")
    freq_min = get_float("  频段下限 (MHz)", 30.0)
    freq_max = get_float("  频段上限 (MHz)", 2500.0)
    resolution = get_float("  频率分辨率 (MHz)", 1.0)
    noise_floor = get_float("  底噪功率 (dB)", -120.0)

    # 高级配置：采样率 / IQ 长度 / 随机种子（用于复现）
    print("\n➤ 高级配置（可直接回车使用默认值）")
    sample_rate_hz = get_float("  IQ 采样率 (Hz)", 125e6)
    iq_length = get_int("  IQ 信号长度", 32768)
    seed_str = get_input("  随机种子（可留空，整数，便于复现）", None).strip()
    seed = int(seed_str) if seed_str else None

    cfg = SpectrumComposerConfig(
        freq_min_mhz=freq_min,
        freq_max_mhz=freq_max,
        resolution_mhz=resolution,
        noise_floor_db=noise_floor,
        sample_rate_hz=sample_rate_hz,
        iq_length=iq_length,
    )

    # 添加干扰（使用数字菜单选择类型，避免手敲长英文单词）
    print("\n➤ 添加干扰信号")
    print("  可用类型（输入对应编号即可）：")
    for idx, (jam_type, desc) in enumerate(JAMMER_TYPE_CHOICES, start=1):
        print(f"    {idx}. {desc} ({jam_type})")

    while True:
        print(f"\n  当前已添加 {len(cfg.jammers)} 个干扰")
        choice = get_input("  继续添加干扰? (y/n)", "n")
        if choice.lower() != "y":
            break

        type_index = get_int("    选择干扰类型编号", 2)
        if not (1 <= type_index <= len(JAMMER_TYPE_CHOICES)):
            print("    ⚠️ 无效编号，请重新输入")
            continue

        jam_type = JAMMER_TYPE_CHOICES[type_index - 1][0]
        center_freq = get_float("    中心频率 (MHz)", 500.0)
        jnr_db = get_float("    JNR (dB)", 15.0)

        cfg.jammers.append(
            JammerSpec(jam_type=jam_type, center_freq_mhz=center_freq, jnr_db=jnr_db)
        )
        print(f"    ✓ 已添加: {jam_type} @ {center_freq} MHz, JNR={jnr_db} dB")

    if not cfg.jammers:
        print("\n  ⚠️ 未添加任何干扰，取消操作")
        return

    # 生成频谱
    print("\n➤ 生成功率谱...")
    try:
        # 使用可选随机种子，便于在 pipeline/批处理场景下复现
        rng = np.random.default_rng(seed)
        freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
        print(f"  ✓ 生成成功: {freq_mhz.size} 个频点")

        # 保存
        save_choice = get_input("\n  保存结果? (y/n)", "y")
        if save_choice.lower() == 'y':
            output_dir = Path(get_input("    输出目录", "data/cli_results"))
            output_dir.mkdir(parents=True, exist_ok=True)

            npz_path = output_dir / "composed_spectrum.npz"
            np.savez(npz_path, freq_mhz=freq_mhz, power_db=power_db)
            print(f"  ✓ 已保存: {npz_path}")

            # 保存配置
            config_path = output_dir / "jammer_config.json"
            # 记录完整合成配置，便于后续通过 batch CLI/pipeline 复现
            config_data = {
                "freq_min_mhz": freq_min,
                "freq_max_mhz": freq_max,
                "resolution_mhz": resolution,
                "noise_floor_db": noise_floor,
                "sample_rate_hz": sample_rate_hz,
                "iq_length": iq_length,
                "seed": seed,
                "jammers": [
                    {
                        "type": j.jam_type,  # 与 src.pipeline.compose_spectrum.load_jammer_config_file 对齐
                        "center_freq_mhz": j.center_freq_mhz,
                        "jnr_db": j.jnr_db,
                        **(
                            {"bandwidth_mhz": j.bandwidth_mhz}
                            if getattr(j, "bandwidth_mhz", None) is not None
                            else {}
                        ),
                    }
                    for j in cfg.jammers
                ],
            }
            config_path.write_text(
                json.dumps(config_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"  ✓ 配置已保存: {config_path}")

            # 保存频谱图
            png_path = output_dir / "composed_spectrum.png"
            title = f"Composed Spectrum ({len(cfg.jammers)} jammers)"
            if seed is not None:
                title += f", seed={seed}"
            save_spectrum_png(freq_mhz, power_db, png_path, title=title)

        print(f"\n  频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
        print(f"  功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")

    except Exception as e:
        print(f"\n  ✗ 错误: {e}")
        import traceback
        traceback.print_exc()


def task2_interactive():
    """任务二：交互式拼接频谱"""
    print("\n" + "=" * 80)
    print("【任务二】拼接频谱分段")
    print("=" * 80)

    # 选择数据源类型
    print("\n➤ 数据源选择")
    print("  1. 从 NPZ 文件逐个加载频谱分段（已计算好的功率谱）")
    print("  2. 从 BIN 文件目录批量加载 IQ 数据（自动计算频谱并拼接）")
    
    source_choice = get_input("  选择数据源 (1/2)", "1")
    
    # ========== 方式 1: 从 NPZ 文件加载（原有逻辑） ==========
    if source_choice == "1":
        print("\n➤ 加载频谱分段 (.npz 文件)")
        print("  npz 文件应包含: freq_mhz, power_db, center_freq_mhz, bandwidth_mhz")

        segments = []
        while True:
            print(f"\n  当前已加载 {len(segments)} 个分段")
            choice = get_input("  加载分段? (y/n)", "n")
            if choice.lower() != 'y':
                break

            npz_path = Path(get_input("    npz 文件路径"))
            if not npz_path.exists():
                print(f"    ⚠️ 文件不存在: {npz_path}")
                continue

            try:
                seg = load_segment_from_npz(npz_path)
                segments.append(seg)
                print(f"    ✓ 已加载: {seg.center_freq_mhz:.1f} MHz, {seg.bandwidth_mhz:.1f} MHz 带宽")
            except Exception as e:
                print(f"    ✗ 加载失败: {e}")

        if len(segments) < 2:
            print("\n  ⚠️ 至少需要2个分段才能拼接")
            return

        # 选择拼接模式
        print("\n➤ 拼接模式")
        print("  1. MAX - 取最大值（适合干扰检测）")
        print("  2. MEAN - 简单平均（降低噪声）")
        print("  3. WEIGHTED_MEAN - 加权平均（中心权重高）")

        mode_choice = get_input("  选择模式 (1/2/3)", "1")
        mode_map = {"1": StitchMode.MAX, "2": StitchMode.MEAN, "3": StitchMode.WEIGHTED_MEAN}
        mode = mode_map.get(mode_choice, StitchMode.MAX)

        fill_value = get_float("  未覆盖区域填充值 (dB)", -180.0)

        # 拼接
        print("\n➤ 执行拼接...")
        try:
            result = stitch_segments(segments, mode=mode, fill_value=fill_value)
            print(f"  ✓ 拼接成功")
            print(f"    频段: {result.freq_min_mhz:.2f} - {result.freq_max_mhz:.2f} MHz")
            print(f"    频点数: {result.freq_mhz.size}")
            print(f"    最大覆盖: {result.coverage_map.max()} 段")

            # 保存结果
            _save_stitched_result(result, mode)

        except Exception as e:
            print(f"\n  ✗ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    # ========== 方式 2: 从 BIN 文件目录加载（新增功能） ==========
    elif source_choice == "2":
        print("\n➤ BIN 文件配置")
        print("  文件命名规范（兼容多种）：")
        print("   - 完整: {type}_{freq}MHz_{bw}MHz_{timestamp}.bin")
        print("     例: single_130MHz_204.8MHz_11h14m22s.bin")
        print("   - 简化: {freq}MHz.bin")
        print("     例: 130MHz.bin（此时采样率使用下面的“默认采样率”）")
        
        # 获取目录路径
        bin_dir = Path(get_input("  BIN 文件目录路径", "data/raw_segments"))
        if not bin_dir.exists():
            print(f"  ⚠️ 目录不存在: {bin_dir}")
            return
        
        # 文件匹配模式
        pattern = get_input("  文件匹配模式", "*.bin")

        try:
            matched_files = _collect_bin_files(bin_dir, pattern)
        except FileNotFoundError as e:
            print(f"\n  ✗ 错误: {e}")
            return

        print(f"\n  ✓ 匹配到 {len(matched_files)} 个 .bin 文件")
        
        # 数据类型选择
        print("\n➤ BIN 数据类型")
        print("  1. int16    - 交织 I/Q int16（最常见，默认）")
        print("  2. int8     - 交织 I/Q int8")
        print("  3. float32  - 交织 I/Q float32")
        print("  4. complex64  - 连续复数 float32")
        print("  5. complex128 - 连续复数 float64")
        
        dtype_choice = get_input("  选择数据类型 (1-5)", "1")
        dtype_map = {
            "1": BinDataType.INT16,
            "2": BinDataType.INT8,
            "3": BinDataType.FLOAT32,
            "4": BinDataType.COMPLEX64,
            "5": BinDataType.COMPLEX128,
        }
        bin_dtype = dtype_map.get(dtype_choice, BinDataType.INT16)

        # 当文件名不包含带宽/采样率时（例如 130MHz.bin），用该值补全 sample_rate_hz。
        # 若文件名本身包含带宽（例如 single_130MHz_204.8MHz_xxx.bin），该值不会覆盖文件名推断结果。
        default_sample_rate_hz = get_float("  默认采样率 (Hz，仅用于 130MHz.bin 简化命名)", 204.8e6)
        
        # 频谱计算模式
        print("\n➤ 频谱计算模式（影响速度与分辨率）")
        print("  1. 分段 FFT（Welch 风格，使用全部 IQ，推荐用于大样本 .bin）")
        print("  2. 单次 FFT（截断/补零到 fft_size，适合快速验证）")
        calc_mode_choice = get_input("  选择模式 (1/2)", "1")

        print("\n➤ 频谱计算参数（可直接回车使用默认值）")
        window = get_input("  窗函数 (hann/hamming/blackman)", "hann")

        # 默认采用：NFFT=512（Fs=204.8MHz 时约 400kHz 分辨率）
        segment_fft_size: Optional[int] = None
        time_agg_mode = "mean"
        fft_size: Optional[int] = None

        if calc_mode_choice == "1":
            segment_fft_size = get_int("  分段 FFT 点数 (NFFT)", 512)
            time_agg_mode = get_input("  分段时间聚合 (mean/max)", "mean")
        else:
            fft_size = get_int("  FFT 点数", 8192)

        # 单文件：直接 FFT 绘图（用户需求：目录下只有 1 个 .bin 时不需要匹配文件名，直接加载绘制）
        if len(matched_files) == 1:
            bin_path = matched_files[0]
            print("\n➤ 检测到仅 1 个 .bin 文件，将进入单文件 FFT 模式（不进行拼接）")
            print(f"  文件: {bin_path.name}")

            # 用户需求默认：Fs=204.8MHz，Fc=0（基带）
            sample_rate_hz = get_float("  采样率 (Hz)", 204.8e6)
            center_freq_hz = get_float("  中心频率 (Hz)", 0.0)

            print("\n➤ 计算功率谱...")
            try:
                iq = load_iq_file(
                    bin_path,
                    sample_rate_hz=sample_rate_hz,
                    center_freq_hz=center_freq_hz,
                    bin_dtype=bin_dtype,
                )

                if segment_fft_size is not None:
                    cfg = SamplingConfig(
                        sample_rate_hz=iq.sample_rate_hz,
                        center_freq_hz=iq.center_freq_hz,
                        fft_size=segment_fft_size,
                    )
                    target_df_hz = float(iq.sample_rate_hz) / float(segment_fft_size)
                    freq_mhz, power_db = compute_segmented_power_spectrum(
                        iq,
                        cfg,
                        target_df_hz=target_df_hz,
                        window=window,
                        time_agg_mode=time_agg_mode,
                    )
                    num_chunks = (iq.samples.size + int(segment_fft_size) - 1) // int(segment_fft_size)
                else:
                    assert fft_size is not None
                    cfg = SamplingConfig(
                        sample_rate_hz=iq.sample_rate_hz,
                        center_freq_hz=iq.center_freq_hz,
                        fft_size=fft_size,
                    )
                    freq_mhz, power_db = compute_power_spectrum(iq, cfg, window=window)
                    num_chunks = 1
            except Exception as e:
                print(f"\n  ✗ 错误: {e}")
                import traceback
                traceback.print_exc()
                return

            print(f"  ✓ 计算成功")
            print(f"    频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
            print(f"    功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")
            if segment_fft_size is not None:
                df_khz = float(iq.sample_rate_hz) / float(segment_fft_size) / 1e3
                print(f"    分段 FFT: NFFT={segment_fft_size}, 分段数={num_chunks}, Δf≈{df_khz:.3f} kHz")
                print(f"    窗函数: {window}, 时间聚合: {time_agg_mode}")
            else:
                assert fft_size is not None
                df_khz = float(iq.sample_rate_hz) / float(fft_size) / 1e3
                print(f"    单次 FFT: NFFT={fft_size}, Δf≈{df_khz:.3f} kHz, 窗函数: {window}")

            save_choice = get_input("\n  保存结果? (y/n)", "y")
            if save_choice.lower() == "y":
                output_dir = Path(get_input("    输出目录", "data/cli_results"))
                output_dir.mkdir(parents=True, exist_ok=True)

                stem = bin_path.stem
                mode_tag = f"segfft{segment_fft_size}" if segment_fft_size is not None else f"fft{fft_size}"
                npz_path = output_dir / f"{stem}_{mode_tag}.npz"
                meta = {
                    "sample_rate_hz": float(sample_rate_hz),
                    "center_freq_hz": float(center_freq_hz),
                    "fft_mode": "segmented" if segment_fft_size is not None else "single",
                    # 约定：fft_size 表示最终输出谱线的点数（对分段 FFT 来说就是 NFFT）
                    "fft_size": int(segment_fft_size if segment_fft_size is not None else fft_size),
                    "num_chunks": int(num_chunks),
                    "window": str(window),
                    "source_file": str(bin_path),
                    "bin_dtype": str(bin_dtype.value),
                }
                if segment_fft_size is not None:
                    meta["segment_fft_size"] = int(segment_fft_size)
                    meta["time_agg_mode"] = str(time_agg_mode)
                np.savez(npz_path, freq_mhz=freq_mhz, power_db=power_db, **meta)
                print(f"  ✓ 已保存: {npz_path}")

                png_path = output_dir / f"{stem}_{mode_tag}.png"
                save_spectrum_png(
                    freq_mhz,
                    power_db,
                    png_path,
                    title=f"{mode_tag}: {bin_path.name} (Fs={sample_rate_hz/1e6:.1f} MHz, Fc={center_freq_hz/1e6:.3f} MHz)",
                )
            return
        
        # 拼接模式
        print("\n➤ 拼接模式")
        print("  1. MAX - 取最大值（适合干扰检测）")
        print("  2. MEAN - 简单平均（降低噪声）")
        print("  3. WEIGHTED_MEAN - 加权平均（中心权重高）")
        
        mode_choice = get_input("  选择模式 (1/2/3)", "1")
        mode_map = {"1": StitchMode.MAX, "2": StitchMode.MEAN, "3": StitchMode.WEIGHTED_MEAN}
        mode = mode_map.get(mode_choice, StitchMode.MAX)
        
        fill_value = get_float("  未覆盖区域填充值 (dB)", -180.0)
        
        # 执行拼接
        print("\n➤ 加载 BIN 文件并执行拼接...")
        try:
            # 若选用分段 FFT：固定 NFFT（默认 512），对每个分段使用其自身 Fs 计算 target_df=Fs/NFFT
            seg_fft_size_for_stitch = segment_fft_size if calc_mode_choice == "1" else None
            fft_size_for_stitch = int(fft_size if fft_size is not None else (segment_fft_size or 8192))
            result, segments = stitch_from_bin_directory(
                directory=bin_dir,
                pattern=pattern,
                bin_dtype=bin_dtype,
                mode=mode,
                fft_size=fft_size_for_stitch,
                window=window,
                fill_value=fill_value,
                time_agg_mode=time_agg_mode,
                segment_fft_size=seg_fft_size_for_stitch,
                default_sample_rate_hz=float(default_sample_rate_hz),
            )
            
            print(f"\n  ✓ 拼接成功")
            print(f"    频段: {result.freq_min_mhz:.2f} - {result.freq_max_mhz:.2f} MHz")
            print(f"    频点数: {result.freq_mhz.size}")
            print(f"    最大覆盖: {result.coverage_map.max()} 段")
            print(f"    已拼接分段数: {len(segments)}")
            
            # 保存结果
            _save_stitched_result(result, mode)
            
        except FileNotFoundError as e:
            print(f"\n  ✗ 错误: {e}")
            print("  提示: 请检查目录路径和文件匹配模式")
        except Exception as e:
            print(f"\n  ✗ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    else:
        print("\n  ⚠️ 无效的选择，请输入 1 或 2")


def _save_stitched_result(result, mode):
    """保存拼接结果的辅助函数"""
    save_choice = get_input("\n  保存结果? (y/n)", "y")
    if save_choice.lower() == 'y':
        output_dir = Path(get_input("    输出目录", "data/cli_results"))
        output_dir.mkdir(parents=True, exist_ok=True)

        npz_path = output_dir / "stitched_spectrum.npz"
        np.savez(
            npz_path,
            freq_mhz=result.freq_mhz,
            power_db=result.power_db,
            coverage_map=result.coverage_map,
        )
        print(f"  ✓ 已保存: {npz_path}")

        # 保存拼接频谱图
        png_path = output_dir / "stitched_spectrum.png"
        save_spectrum_png(result.freq_mhz, result.power_db, png_path, title=f"Stitched Spectrum ({mode.name})")


def task3_interactive():
    """任务三：交互式语义恢复"""
    print("\n" + "=" * 80)
    print("【任务三】语义参数恢复频谱")
    print("=" * 80)

    # 直接获取 JSON 文件路径
    json_path = Path(get_input("\n  语义 JSON 文件路径"))
    if not json_path.exists():
        print(f"  ⚠️ 文件不存在: {json_path}")
        return

    # 加载语义文件
    print("\n➤ 加载语义参数...")
    try:
        raw = json_path.read_text(encoding="utf-8")
        params = load_semantic_file(json_path)
        print("  ✓ 语义参数加载成功")
    except Exception as e:
        print(f"  ✗ 加载失败: {e}")
        print("  提示: 请确保使用正确格式的语义文件 (包含 jammer_regions 和 num_bins 字段)")
        return

    # 按"全局默认语义轴"覆写四个核心字段
    params.freq_min_mhz = DEFAULT_SEMANTIC_FREQ_MIN_MHZ
    params.freq_max_mhz = DEFAULT_SEMANTIC_FREQ_MAX_MHZ
    params.num_bins = DEFAULT_SEMANTIC_NUM_BINS
    params.noise_floor_db = DEFAULT_SEMANTIC_NOISE_FLOOR_DB

    # 解码恢复频谱
    print("\n➤ 恢复频谱...")
    try:
        power_db = decode_semantic(params)
    except Exception as e:
        print(f"  ✗ 解码失败: {e}")
        import traceback
        traceback.print_exc()
        return

    freq_mhz = np.linspace(
        DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
        DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
        DEFAULT_SEMANTIC_NUM_BINS,
    )

    print(f"  ✓ 恢复成功")
    print(f"    频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
    print(f"    功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")
    print(f"    分辨率: {(freq_mhz[1] - freq_mhz[0]):.2f} MHz")

    # 保存结果
    save_choice = get_input("\n  保存结果? (y/n)", "y")
    if save_choice.lower() == "y":
        output_dir = Path(get_input("    输出目录", "data/cli_results"))
        output_dir.mkdir(parents=True, exist_ok=True)

        npz_path = output_dir / "recovered_spectrum.npz"
        np.savez(npz_path, freq_mhz=freq_mhz, power_db=power_db)
        print(f"  ✓ 频谱已保存: {npz_path}")

        # 保留原始语义 JSON
        semantic_copy = output_dir / "semantic_params.json"
        semantic_copy.write_text(raw, encoding="utf-8")
        print(f"  ✓ 语义参数已保存: {semantic_copy}")

        png_path = output_dir / "recovered_spectrum.png"
        save_spectrum_png(freq_mhz, power_db, png_path, title="Recovered Spectrum")


def task23_union_interactive() -> None:
    """任务二+任务三：并集输出（复用 scripts/run_union.py）。"""
    print("\n" + "=" * 80)
    print("【任务二+任务三】输出并集频谱（run_union）")
    print("=" * 80)
    print("说明：默认读取 data_segment/ 与 data_semantic/semantic.json，输出到 output/。")

    try:
        ret = run_union.main()
    except Exception as exc:
        print(f"  ✗ 执行失败：{exc}")
        return

    if ret == 11:
        print("  ✓ 并集流程执行完成（返回码=11）")
    else:
        print(f"  ⚠️ 并集流程返回非预期返回码：{ret}")


def show_guide():
    """显示使用指南"""
    print("\n" + "=" * 80)
    print("【使用指南】")
    print("=" * 80)
    print("""
任务一：合成干扰功率谱
  - 目的：在 30-2500 MHz 频段内组合多种干扰信号生成功率谱
  - 支持六类干扰：noise_fm, single_tone, multi_tone, comb, partial_band_noise, sweep
  - 输出：频谱 npz 文件和干扰配置 JSON

任务二：拼接频谱分段（或单文件 FFT）
  - 方式1：从 npz 文件逐个加载频谱分段并拼接
  - 方式2：从 bin 目录批量加载：匹配到 1 个 .bin 时直接计算 FFT 并保存；匹配到多个 .bin 时自动计算并拼接
  - 单文件 .bin 默认采用“分段 FFT”：NFFT=512（Fs=204.8MHz 时约 400kHz 分辨率），时间聚合默认 mean
  - 拼接支持三种模式：MAX, MEAN, WEIGHTED_MEAN
  - 输出：npz + PNG（若安装 matplotlib）

任务三：语义参数恢复频谱
  - 目的：从语义化参数重建功率谱
  - 输入：语义参数 JSON 文件
  - 语义格式包含：freq_min_mhz, freq_max_mhz, num_bins, noise_floor_db, jammer_regions
  - 自动使用全局默认语义轴参数覆写（30-2500 MHz, 2471 bins）
  - 输出：恢复的频谱（recovered_spectrum.npz）和语义参数文件

关键修复说明：
  ✓ 任务一修复：在基带生成干扰后频域平移，避免违反Nyquist定理
  ✓ 任务二修复：使用 searchsorted 避免浮点精度问题
  ✓ 任务三修复：边缘增强限制在 5dB 以内，避免过度修正

数据格式：
  - npz 文件: freq_mhz (频率轴), power_db (功率谱)
  - JSON 文件: 语义参数字典
""")
    input("\n按回车返回主菜单...")


def main():
    """主循环"""
    while True:
        clear_screen()
        print_banner()
        print_menu()

        choice = get_input("请选择", "5")

        if choice == "1":
            task1_interactive()
            input("\n按回车返回主菜单...")
        elif choice == "2":
            task2_interactive()
            input("\n按回车返回主菜单...")
        elif choice == "3":
            task3_interactive()
            input("\n按回车返回主菜单...")
        elif choice == "4":
            show_guide()
        elif choice == "11":
            task23_union_interactive()
            input("\n按回车返回主菜单...")
        elif choice == "5":
            print("\n再见！")
            break
        else:
            print("\n⚠️ 无效选择")
            input("按回车继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，退出程序")
        sys.exit(0)
    except Exception as e:
        print(f"\n致命错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
