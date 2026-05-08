"""任务一演示：在 30–2500 MHz 频段上绘制六类干扰信号的功率谱。

说明：
- 干扰的时间域生成严格参考 `jam.m` 中的六类干扰定义（见 `src/signal/jammers.py`）；
- 为了直接在 30–2500 MHz 轴上展示，这里在计算功率谱时将频率轴线性拉伸到该范围，
  即时间域采样率与显示频率范围不再一一对应，仅用于可视化形状对比。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ...core.schemas import IQData, SamplingConfig
    from ...signal.jammers import JAMMER_REGISTRY, JammerConfig, generate_jammer
    from ...signal.spectrum import compute_power_spectrum
    from ...viz.plots import plot_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from electromagnetic_state.core.schemas import IQData, SamplingConfig
    from electromagnetic_state.signal.jammers import JAMMER_REGISTRY, JammerConfig, generate_jammer
    from electromagnetic_state.signal.spectrum import compute_power_spectrum
    from electromagnetic_state.viz.plots import plot_spectrum


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="任务一：六类干扰在 30–2500 MHz 频段上的功率谱示例")
    parser.add_argument("--output-dir", type=Path, default=Path("data/jammer_demo"), help="输出图像目录")
    parser.add_argument("--length", type=int, default=32768, help="每个干扰样本的采样点数")
    parser.add_argument("--sample-rate", type=float, default=125e6, help="干扰生成的采样率 Hz（仅用于时间域生成）")
    parser.add_argument("--jnr", type=float, default=15.0, help="JNR（dB），用于 awgn 添加噪声")
    parser.add_argument("--freq-min", type=float, default=30.0, help="显示频率下限 MHz，默认 30")
    parser.add_argument("--freq-max", type=float, default=2500.0, help="显示频率上限 MHz，默认 2500")
    parser.add_argument(
        "--fc-span",
        type=float,
        default=1e6,
        help="干扰中心频率偏移范围 Hz，在 [-fc_span, fc_span] 内随机取值，仅影响包络形状",
    )
    parser.add_argument("--seed", type=int, default=0, help="随机种子，便于复现（0 表示使用默认种子）")
    args = parser.parse_args()

    rng = np.random.default_rng(None if args.seed == 0 else args.seed)

    # 时间域干扰生成配置（严格跟随 jam.m）
    jammer_cfg = JammerConfig(length=args.length, sample_rate_hz=args.sample_rate, jnr_db=args.jnr)

    _ensure_dir(args.output_dir)

    jam_types = list(JAMMER_REGISTRY.keys())

    # 为避免频域重叠，将 30–2500 MHz 区间切成若干不重叠子带，每类干扰占一个子带。
    # 子带宽度取为采样率对应频宽（fs），保证频谱完整落在该子带内：
    #   每个子带覆盖 center_mhz ± fs/2（MHz），不同子带之间按 fs 间隔排布。
    slot_width_mhz = args.sample_rate / 1e6
    freq_span_mhz = args.freq_max - args.freq_min
    total_slot_span = slot_width_mhz * len(jam_types)
    if total_slot_span > freq_span_mhz:
        raise SystemExit(
            f"频段 [{args.freq_min},{args.freq_max}] MHz 无法容纳 {len(jam_types)} 个宽度为 {slot_width_mhz:.1f} MHz 的不重叠子带，"
            "请减小 sample-rate 或缩小干扰种类数量。"
        )

    # 收集每类干扰的频谱，便于后面在同一张图中叠加
    spectra = []

    for idx, jam_type in enumerate(jam_types):
        # 为当前干扰分配一个不重叠子带中心
        center_mhz = args.freq_min + slot_width_mhz * (0.5 + idx)
        sampling_cfg = SamplingConfig(
            sample_rate_hz=args.sample_rate,
            center_freq_hz=center_mhz * 1e6,
            fft_size=args.length,
        )

        # 在基带生成干扰（fc=0），频谱通过 center_mhz 平移到指定子带
        iq, _bw = generate_jammer(jam_type, 0.0, jammer_cfg, rng=rng)

        iq_struct = IQData(
            samples=iq.astype(np.complex128, copy=False),
            sample_rate_hz=sampling_cfg.sample_rate_hz,
            center_freq_hz=sampling_cfg.center_freq_hz,
        )
        freq_mhz, power_db = compute_power_spectrum(iq_struct, sampling_cfg)

        # 为了保持统一，只在 [freq_min, freq_max] 内展示
        mask = (freq_mhz >= args.freq_min) & (freq_mhz <= args.freq_max)
        freq_mhz = freq_mhz[mask]
        power_db = power_db[mask]

        fig, ax = plt.subplots(figsize=(10, 4))
        title = f"{jam_type} 干扰功率谱 (JNR={args.jnr:.1f} dB)"
        plot_spectrum(freq_mhz, power_db, title=title, ax=ax)
        fig.tight_layout()

        out_path = args.output_dir / f"{jam_type}_spectrum.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"saved spectrum: {out_path}")

        spectra.append((jam_type, freq_mhz, power_db))

    # 在一张图中叠加六类干扰的功率谱，便于整体对比；同时对齐底噪水平，避免不同类型噪声地板不一致。
    if spectra:
        # 估计每条曲线的底噪（采用较低分位数），再平移到统一基线
        floors = []
        for _jam_type, _freq_mhz, power_db in spectra:
            floors.append(float(np.percentile(power_db, 10)))
        global_floor = min(floors) if floors else 0.0

        fig, ax = plt.subplots(figsize=(12, 5))
        for (jam_type, freq_mhz, power_db), noise_floor in zip(spectra, floors):
            shift = noise_floor - global_floor
            aligned_power = power_db - shift
            ax.plot(freq_mhz, power_db, linewidth=0.8, label=jam_type)
        ax.set_xlabel("频率 (MHz)")
        ax.set_ylabel("功率 (dB)")
        ax.set_title(f"六类干扰功率谱对比 (JNR={args.jnr:.1f} dB)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        combined_path = args.output_dir / "all_jammers_spectrum.png"
        fig.savefig(combined_path, dpi=150)
        plt.close(fig)
        print(f"saved combined spectrum: {combined_path}")


if __name__ == "__main__":
    main()
