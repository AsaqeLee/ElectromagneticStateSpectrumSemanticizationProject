"""频段划分与索引映射，服务于拼接与语义恢复评估。"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from ..core.config import DEFAULT_WINDOW_CENTERS_MHZ
from ..core.schemas import BandConfig, SamplingConfig

WINDOW_HALF_BANDWIDTH_MHZ = 100.0  # 200 MHz 全带宽


def make_frequency_axis(cfg: SamplingConfig) -> np.ndarray:
    """生成频轴（MHz），使用 fftshift 对齐直观频谱。"""

    freq_hz = np.fft.fftfreq(cfg.fft_size, d=1.0 / cfg.sample_rate_hz)
    freq_hz = np.fft.fftshift(freq_hz + cfg.center_freq_hz)
    return freq_hz / 1e6


def band_mask(freq_mhz: np.ndarray, band: BandConfig) -> np.ndarray:
    """给定频轴与 BandConfig，返回布尔掩码。"""

    return (freq_mhz >= band.start_freq_mhz) & (freq_mhz <= band.end_freq_mhz)


def window_masks(freq_mhz: np.ndarray, centers_mhz: Sequence[float] = DEFAULT_WINDOW_CENTERS_MHZ) -> Dict[float, np.ndarray]:
    """返回以中心频率为键的 200 MHz 窗口掩码。"""

    masks: Dict[float, np.ndarray] = {}
    for center in centers_mhz:
        start = center - WINDOW_HALF_BANDWIDTH_MHZ
        end = center + WINDOW_HALF_BANDWIDTH_MHZ
        masks[center] = (freq_mhz >= start) & (freq_mhz <= end)
    return masks


def segment_bands(
    cfg: SamplingConfig,
    coarse_bands: Sequence[BandConfig],
    window_centers_mhz: Sequence[float] = DEFAULT_WINDOW_CENTERS_MHZ,
) -> Dict[str, np.ndarray]:
    """综合 coarse 频段与 200 MHz 窗口的索引掩码集合。"""

    freq_mhz = make_frequency_axis(cfg)
    masks: Dict[str, np.ndarray] = {}
    for band in coarse_bands:
        masks[f"band::{band.name}"] = band_mask(freq_mhz, band)
    for center, mask in window_masks(freq_mhz, window_centers_mhz).items():
        masks[f"window::{center}MHz"] = mask
    return masks


def trimmed_axis(freq_mhz: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """提取掩码内的频轴，便于裁剪谱线。"""

    return freq_mhz[mask]
