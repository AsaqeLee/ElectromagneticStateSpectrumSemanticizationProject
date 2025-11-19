"""分析 comb_130MHz_204.8MHz_11h01m58s.bin 信号的功率谱特性。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ..core.schemas import IQData, SamplingConfig
    from ..signal.spectrum import compute_power_spectrum
    from ..viz.plots import plot_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from core.schemas import IQData, SamplingConfig
    from signal.spectrum import compute_power_spectrum
    from viz.plots import plot_spectrum


def load_int16_iq(path: Path) -> np.ndarray:
    """按 int16 I/Q 交织格式读取 .bin 文件。"""

    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2 != 0:
        raw = raw[:-1]
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    return i + 1j * q


def find_comb_peaks(freq_mhz: np.ndarray, power_db: np.ndarray, max_peaks: int = 12, min_spacing_mhz: float = 1.0) -> np.ndarray:
    """从功率谱中提取若干梳状峰值位置。"""

    idx_sorted = np.argsort(power_db)[::-1]
    selected: list[int] = []
    for idx in idx_sorted:
        f = freq_mhz[idx]
        if not selected or all(abs(f - freq_mhz[j]) > min_spacing_mhz for j in selected):
            selected.append(idx)
        if len(selected) >= max_peaks:
            break
    selected = sorted(selected, key=lambda i: freq_mhz[i])
    return np.array(selected, dtype=int)


def main() -> None:
    parser = argparse.ArgumentParser(description="分析 comb_130MHz_204.8MHz_11h01m58s.bin 频谱特性")
    parser.add_argument("--file", type=Path, default=Path("comb_130MHz_204.8MHz_11h01m58s.bin"), help="int16 I/Q 交织格式的 bin 文件")
    parser.add_argument("--sample-rate", type=float, default=204.8e6, help="采样率 Hz")
    parser.add_argument("--center-freq", type=float, default=130e6, help="中心频率 Hz")
    parser.add_argument("--fft-size", type=int, default=262144, help="FFT 点数")
    parser.add_argument("--png", type=Path, default=Path("data/comb_130MHz_psd.png"), help="功率谱密度图输出路径")
    args = parser.parse_args()

    samples = load_int16_iq(args.file)
    if samples.size < args.fft_size:
        print(f"警告: 样本数 {samples.size} 小于 FFT 点数 {args.fft_size}，将自动补零", file=sys.stderr)

    cfg = SamplingConfig(sample_rate_hz=args.sample_rate, center_freq_hz=args.center_freq, fft_size=args.fft_size)
    iq = IQData(samples=samples, sample_rate_hz=cfg.sample_rate_hz, center_freq_hz=cfg.center_freq_hz)
    freq_mhz, power_db = compute_power_spectrum(iq, cfg)

    # 保存频谱图
    args.png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 4))
    plot_spectrum(freq_mhz, power_db, title="comb_130MHz_204.8MHz PSD")
    plt.tight_layout()
    plt.savefig(args.png, dpi=120)
    plt.close()
    print(f"PSD saved to {args.png}")

    # 提取若干峰值并打印简单特性
    peak_idx = find_comb_peaks(freq_mhz, power_db)
    peak_freqs = freq_mhz[peak_idx]
    peak_powers = power_db[peak_idx]
    if peak_freqs.size >= 2:
        spacings = np.diff(peak_freqs)
        avg_spacing = float(np.mean(spacings))
    else:
        spacings = np.array([])
        avg_spacing = float("nan")

    noise_floor = float(np.percentile(power_db, 5))
    main_peak = float(np.max(power_db))

    print("=== comb spectrum characteristics (approx) ===")
    print(f"samples: {samples.size}, fft_size: {cfg.fft_size}")
    print(f"freq range: {freq_mhz.min():.2f} MHz ~ {freq_mhz.max():.2f} MHz")
    print(f"main peak: {main_peak:.1f} dB, noise floor: {noise_floor:.1f} dB, dyn range: {main_peak - noise_floor:.1f} dB")
    print("top peaks (MHz, dB):")
    for f, p in zip(peak_freqs, peak_powers):
        print(f"  {f:8.3f} MHz, {p:6.1f} dB")
    if spacings.size > 0:
        print(f"avg spacing between peaks: {avg_spacing:.3f} MHz")


if __name__ == "__main__":
    main()
