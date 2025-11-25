"""将 comb_130MHz 与 comb_330MHz 两段 IQ 信号的频谱叠加显示在同一张图上。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ...core.schemas import IQData, SamplingConfig
    from ...signal.spectrum import compute_power_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from core.schemas import IQData, SamplingConfig
    from signal.spectrum import compute_power_spectrum


def load_int16_iq(path: Path) -> np.ndarray:
    """按 int16 I/Q 交织格式读取 .bin 文件。"""

    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2 != 0:
        raw = raw[:-1]
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    return i + 1j * q


def main() -> None:
    parser = argparse.ArgumentParser(description="overlay PSD of comb_130MHz and comb_330MHz")
    parser.add_argument("--file-a", type=Path, default=Path("comb_130MHz_204.8MHz_11h01m58s.bin"), help="int16 I/Q file A")
    parser.add_argument("--file-b", type=Path, default=Path("comb_330MHz_204.8MHz_11h08m36s.bin"), help="int16 I/Q file B")
    parser.add_argument("--sample-rate", type=float, default=204.8e6, help="sample rate Hz for both files")
    parser.add_argument("--center-a", type=float, default=130e6, help="center frequency Hz for file A")
    parser.add_argument("--center-b", type=float, default=330e6, help="center frequency Hz for file B")
    parser.add_argument("--fft-size", type=int, default=262144, help="FFT size")
    parser.add_argument("--png", type=Path, default=Path("data/comb_130_330_psd.png"), help="output PNG path")
    args = parser.parse_args()

    # 文件 A：130 MHz comb
    samples_a = load_int16_iq(args.file_a)
    cfg_a = SamplingConfig(sample_rate_hz=args.sample_rate, center_freq_hz=args.center_a, fft_size=args.fft_size)
    iq_a = IQData(samples=samples_a, sample_rate_hz=cfg_a.sample_rate_hz, center_freq_hz=cfg_a.center_freq_hz)
    freq_a, power_a = compute_power_spectrum(iq_a, cfg_a)

    # 文件 B：330 MHz comb
    samples_b = load_int16_iq(args.file_b)
    cfg_b = SamplingConfig(sample_rate_hz=args.sample_rate, center_freq_hz=args.center_b, fft_size=args.fft_size)
    iq_b = IQData(samples=samples_b, sample_rate_hz=cfg_b.sample_rate_hz, center_freq_hz=cfg_b.center_freq_hz)
    freq_b, power_b = compute_power_spectrum(iq_b, cfg_b)

    # 绘图：同一坐标轴下叠加两个频谱
    args.png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(freq_a, power_a, label="comb @ 130 MHz", linewidth=0.7)
    ax.plot(freq_b, power_b, label="comb @ 330 MHz", linewidth=0.7)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title("PSD overlay: 130 MHz & 330 MHz comb")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    plt.savefig(args.png, dpi=120)
    plt.close(fig)

    # 打印简要信息（仅 ASCII，避免编码问题）
    print(f"Overlay PSD saved to {args.png}")
    print(f"file A freq range: {freq_a.min():.2f} MHz ~ {freq_a.max():.2f} MHz")
    print(f"file B freq range: {freq_b.min():.2f} MHz ~ {freq_b.max():.2f} MHz")


if __name__ == "__main__":
    main()

