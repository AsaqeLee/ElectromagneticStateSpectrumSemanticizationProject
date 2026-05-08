"""演示频谱分辨率对窄带信号的影响。

生成一个带宽 25 kHz 的窄带信号，并分别用 1 MHz 与 1 kHz 频率分辨率绘制功率谱，
比较两者的可见效果：
- 1 MHz 分辨率只能看到“某个 1 MHz bin 内有能量”，无法看出真实带宽；
- 1 kHz 分辨率可以清楚地看到 25 kHz 信号的宽度。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover
    from ...core.schemas import IQData, SamplingConfig
    from ...signal.spectrum import compute_power_spectrum
    from ...viz.plots import plot_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from electromagnetic_state.core.schemas import IQData, SamplingConfig
    from electromagnetic_state.signal.spectrum import compute_power_spectrum
    from electromagnetic_state.viz.plots import plot_spectrum


def generate_tone(fs_hz: float, duration_ms: float, freq_hz: float, snr_db: float) -> np.ndarray:
    """生成带噪窄带信号（复数 IQ）。"""

    num_samples = int(fs_hz * duration_ms / 1000.0)
    t = np.arange(num_samples) / fs_hz
    tone = np.exp(1j * 2 * np.pi * freq_hz * t)
    noise_power = 10 ** (-snr_db / 20.0) / np.sqrt(2.0)
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)) * noise_power
    return tone + noise


def compute_psd(samples: np.ndarray, cfg: SamplingConfig) -> tuple[np.ndarray, np.ndarray]:
    """调用工程内置功率谱函数。"""

    iq = IQData(samples=samples[: cfg.fft_size], sample_rate_hz=cfg.sample_rate_hz, center_freq_hz=cfg.center_freq_hz)
    return compute_power_spectrum(iq, cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description="频谱分辨率演示")
    parser.add_argument("--sample-rate", type=float, default=10e6, help="采样率 Hz")
    parser.add_argument("--duration-ms", type=float, default=10.0, help="信号时长 ms")
    parser.add_argument("--tone-khz", type=float, default=25.0, help="窄带信号频率 kHz")
    parser.add_argument("--snr-db", type=float, default=40.0, help="信噪比 dB（越大越明显）")
    parser.add_argument("--coarse-res-mhz", type=float, default=1.0, help="粗分辨率 MHz（示例 1 MHz）")
    parser.add_argument("--fine-res-khz", type=float, default=1.0, help="细分辨率 kHz（示例 1 kHz）")
    parser.add_argument("--png", type=Path, default=Path("data/resolution_demo.png"), help="输出对比图")
    args = parser.parse_args()

    samples = generate_tone(args.sample_rate, args.duration_ms, args.tone_khz * 1e3, args.snr_db)

    coarse_fft = int(args.sample_rate / (args.coarse_res_mhz * 1e6))
    fine_fft = int(args.sample_rate / (args.fine_res_khz * 1e3))
    coarse_fft = max(coarse_fft, 8)
    fine_fft = max(fine_fft, 1024)

    cfg_coarse = SamplingConfig(sample_rate_hz=args.sample_rate, center_freq_hz=0.0, fft_size=coarse_fft)
    cfg_fine = SamplingConfig(sample_rate_hz=args.sample_rate, center_freq_hz=0.0, fft_size=fine_fft)
    freq_coarse, power_coarse = compute_psd(samples, cfg_coarse)
    freq_fine, power_fine = compute_psd(samples, cfg_fine)

    args.png.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    plot_spectrum(freq_coarse, power_coarse, title=f"1) 分辨率 ~ {args.coarse_res_mhz:.1f} MHz", ax=axes[0])
    plot_spectrum(freq_fine, power_fine, title=f"2) 分辨率 ~ {args.fine_res_khz:.1f} kHz", ax=axes[1])
    axes[1].set_xlabel("频率 (MHz)")
    fig.suptitle(f"窄带信号 {args.tone_khz:.1f} kHz，SNR≈{args.snr_db:.0f} dB")
    fig.tight_layout()
    plt.savefig(args.png, dpi=120)
    plt.close(fig)

    print(f"coarse FFT size: {coarse_fft}, resolution ~ {cfg_coarse.resolution_hz/1e6:.3f} MHz")
    print(f"fine FFT size:   {fine_fft}, resolution ~ {cfg_fine.resolution_hz/1e3:.3f} kHz")
    print(f"figure saved to {args.png}")


if __name__ == "__main__":
    main()
