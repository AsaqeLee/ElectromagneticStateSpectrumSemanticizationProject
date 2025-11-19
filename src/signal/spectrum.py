"""功率谱估计与拼接工具。"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np
from scipy.signal import get_window

from ..core.schemas import IQData, SamplingConfig
from .segmentation import make_frequency_axis

POWER_EPS = 1e-12


def _prepare_samples(samples: np.ndarray, fft_size: int) -> np.ndarray:
    """调整样本长度，不足时补零，超出时截断。"""

    if samples.size == fft_size:
        return samples
    if samples.size < fft_size:
        padded = np.zeros(fft_size, dtype=samples.dtype)
        padded[: samples.size] = samples
        return padded
    return samples[:fft_size]


def compute_power_spectrum(iq: IQData, cfg: SamplingConfig, window: str = "hann") -> Tuple[np.ndarray, np.ndarray]:
    """计算功率谱密度（dB）。"""

    freq_axis = make_frequency_axis(cfg)
    samples = _prepare_samples(iq.samples, cfg.fft_size)
    tap = get_window(window, cfg.fft_size, fftbins=True)
    windowed = samples * tap
    fft = np.fft.fftshift(np.fft.fft(windowed, n=cfg.fft_size))
    power = np.abs(fft) ** 2 / cfg.fft_size
    power_db = 10.0 * np.log10(power + POWER_EPS)
    return freq_axis, power_db


def aggregate_by_masks(power_db: np.ndarray, masks: Dict[str, np.ndarray], mode: str = "max") -> Dict[str, np.ndarray]:
    """按照掩码聚合功率谱，支持 max/mean。"""

    aggregated: Dict[str, np.ndarray] = {}
    for name, mask in masks.items():
        if mode == "mean":
            aggregated[name] = np.array([np.mean(power_db[mask])])
        else:
            aggregated[name] = np.array([np.max(power_db[mask])])
    return aggregated


def stitch_spectrum(freq_axis: np.ndarray, segments: Dict[str, np.ndarray], masks: Dict[str, np.ndarray], fill_value: float = -180.0) -> np.ndarray:
    """根据掩码将分段谱线合并为完整 30–2500 MHz 频谱。"""

    stitched = np.full(freq_axis.shape, fill_value=fill_value, dtype=float)
    for name, values in segments.items():
        mask = masks[name]
        segment = values
        if segment.size == 1:
            stitched[mask] = segment[0]
        else:
            stitched[mask] = segment
    return stitched
