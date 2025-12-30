"""功率谱估计与拼接工具。"""
from __future__ import annotations

from typing import Dict, Tuple

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
    """计算单段功率谱密度（dB）。

    约定：
    - 使用与采样配置一致的 `fft_size`，不足补零、超出截断；
    - 频轴通过 `fftshift` 对齐，使 0 Hz 附近位于中间，更便于与语义频谱对齐；
    - 返回值中的功率已转换为 dB 标度，适合在后续拼接与误差评估中直接使用。
    """

    freq_axis = make_frequency_axis(cfg)
    samples = _prepare_samples(iq.samples, cfg.fft_size)
    tap = get_window(window, cfg.fft_size, fftbins=True)
    windowed = samples * tap
    fft = np.fft.fftshift(np.fft.fft(windowed, n=cfg.fft_size))
    power = np.abs(fft) ** 2 / cfg.fft_size
    power_db = 10.0 * np.log10(power + POWER_EPS)
    return freq_axis, power_db


def compute_segmented_power_spectrum(
    iq: IQData,
    cfg: SamplingConfig,
    target_df_hz: float,
    window: str = "hann",
    time_agg_mode: str = "mean",
) -> Tuple[np.ndarray, np.ndarray]:
    """基于目标频率分辨率的分段功率谱估计（dB）。

    设计原则：
    - 根据采样率 sample_rate_hz 和目标分辨率 target_df_hz 计算 FFT 点数：
      N = round(sample_rate_hz / target_df_hz)；
    - 将整段 IQ 数据按 N 点分段，不足一段时补零，多出的样本整体参与统计；
    - 对每一段执行一次带窗 FFT，得到功率谱，再在时间维度上按 mean/max 聚合；
    - 返回的频率轴与单次 N 点 FFT 一致，分辨率接近 target_df_hz。
    """

    if target_df_hz <= 0:
        raise ValueError("target_df_hz 必须为正")
    if time_agg_mode not in {"mean", "max"}:
        raise ValueError(f"不支持的时间聚合模式: {time_agg_mode}")

    fs = float(cfg.sample_rate_hz)
    # 根据目标分辨率计算 FFT 点数，至少保证 2 点
    fft_size = int(round(fs / target_df_hz))
    if fft_size < 2:
        raise ValueError(
            f"根据目标分辨率计算得到的 FFT 点数过小: {fft_size}，"
            f"请调整 target_df_hz 或采样率（Fs={fs} Hz）"
        )

    samples = np.asarray(iq.samples, dtype=np.complex128)
    num_samples = samples.size
    if num_samples == 0:
        raise ValueError("IQ 样本为空，无法计算功率谱")

    # 频率轴基于单段 FFT 配置生成
    cfg_seg = SamplingConfig(
        sample_rate_hz=cfg.sample_rate_hz,
        center_freq_hz=cfg.center_freq_hz,
        fft_size=fft_size,
    )
    freq_axis = make_frequency_axis(cfg_seg)

    tap = get_window(window, fft_size, fftbins=True)

    # 分段循环：最后一段不足时补零
    num_chunks = (num_samples + fft_size - 1) // fft_size
    agg_power_linear = None
    agg_power_db = None

    for idx in range(num_chunks):
        start = idx * fft_size
        end = min(start + fft_size, num_samples)
        chunk = samples[start:end]
        if chunk.size < fft_size:
            padded = np.zeros(fft_size, dtype=chunk.dtype)
            padded[: chunk.size] = chunk
            chunk = padded

        windowed = chunk * tap
        fft = np.fft.fftshift(np.fft.fft(windowed, n=fft_size))
        power = np.abs(fft) ** 2 / fft_size

        if time_agg_mode == "mean":
            if agg_power_linear is None:
                agg_power_linear = power
            else:
                agg_power_linear += power
        else:  # "max"
            power_db = 10.0 * np.log10(power + POWER_EPS)
            if agg_power_db is None:
                agg_power_db = power_db
            else:
                agg_power_db = np.maximum(agg_power_db, power_db)

    if time_agg_mode == "mean":
        assert agg_power_linear is not None
        agg_power_linear /= float(num_chunks)
        power_db = 10.0 * np.log10(agg_power_linear + POWER_EPS)
    else:
        assert agg_power_db is not None
        power_db = agg_power_db

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
