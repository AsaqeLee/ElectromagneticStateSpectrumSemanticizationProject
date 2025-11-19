"""任务1：生成仿真 IQ 数据并支持功率谱密度绘制。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ..core.config import ProjectConfig, default_config
    from ..core.schemas import IQData, SamplingConfig
    from ..signal.spectrum import compute_power_spectrum
    from ..viz.plots import plot_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from core.config import ProjectConfig, default_config
    from core.schemas import IQData, SamplingConfig
    from signal.spectrum import compute_power_spectrum
    from viz.plots import plot_spectrum


def _generate_carriers(num_samples: int, sample_rate: float, freqs_mhz: Sequence[float]) -> np.ndarray:
    t = np.arange(num_samples) / sample_rate
    signal = np.zeros(num_samples, dtype=np.complex128)
    for idx, freq_mhz in enumerate(freqs_mhz):
        amp = 0.5 + 0.5 * np.random.rand()
        phase = np.random.rand() * 2 * np.pi
        tone = amp * np.exp(1j * (2 * np.pi * freq_mhz * 1e6 * t + phase))
        signal += tone
    return signal


def simulate(cfg: ProjectConfig, duration_ms: float, carriers: Sequence[float], noise_db: float) -> np.ndarray:
    num_samples = int(cfg.sampling.sample_rate_hz * duration_ms / 1000.0)
    base_noise = (10 ** (noise_db / 20.0)) / np.sqrt(2)
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * base_noise
    tones = _generate_carriers(num_samples, cfg.sampling.sample_rate_hz, carriers)
    return tones + noise


def main() -> None:
    parser = argparse.ArgumentParser(description="任务1：生成仿真 IQ 数据并可绘制功率谱密度")
    parser.add_argument("--output", type=Path, default=Path("data/demo_iq.npz"), help="输出 npz 文件路径")
    parser.add_argument("--duration-ms", type=float, default=10.0, help="信号时长（毫秒）")
    parser.add_argument("--carriers", type=float, nargs="+", default=(50.0, 150.0, 800.0, 1800.0), help="载波中心频率 MHz")
    parser.add_argument("--noise-db", type=float, default=-60.0, help="底噪电平 dB")
    parser.add_argument("--plot-psd", action="store_true", help="生成并保存仿真 IQ 的功率谱密度图")
    parser.add_argument(
        "--psd-output",
        type=Path,
        default=Path("data/demo_iq_psd.png"),
        help="功率谱密度图输出路径（PNG）",
    )
    args = parser.parse_args()

    cfg = default_config()
    cfg.ensure_output_root()
    iq = simulate(cfg, args.duration_ms, args.carriers, args.noise_db)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output,
        iq=iq.astype(np.complex128),
        sample_rate_hz=cfg.sampling.sample_rate_hz,
        center_freq_hz=cfg.sampling.center_freq_hz,
    )
    print(f"写入 {args.output}, 样本数 {iq.size}")

    if args.plot_psd:
        # 使用与 cfg.sampling 一致的 FFT 配置计算功率谱密度
        sampling_cfg = SamplingConfig(
            sample_rate_hz=cfg.sampling.sample_rate_hz,
            center_freq_hz=cfg.sampling.center_freq_hz,
            fft_size=cfg.sampling.fft_size,
        )
        iq_struct = IQData(samples=iq, sample_rate_hz=sampling_cfg.sample_rate_hz, center_freq_hz=sampling_cfg.center_freq_hz)
        freq_mhz, power_db = compute_power_spectrum(iq_struct, sampling_cfg)
        args.psd_output.parent.mkdir(parents=True, exist_ok=True)
        plt.figure(figsize=(8, 4))
        plot_spectrum(freq_mhz, power_db, title="场景一仿真 IQ 功率谱密度")
        plt.tight_layout()
        plt.savefig(args.psd_output, dpi=120)
        plt.close()
        print(f"功率谱密度图已保存到 {args.psd_output}")


if __name__ == "__main__":
    main()
