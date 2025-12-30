"""干扰信号（Jammer）生成模块。

本模块参考 `jam.m` 中的六类干扰定义，提供 Python 版本的 IQ 信号生成函数：

- noise_fm: 噪声调频干扰；
- single_tone: 单音干扰；
- multi_tone: 多音干扰；
- comb: 梳状谱干扰；
- partial_band_noise: 部分带宽噪声干扰；
- sweep: 扫频干扰。

所有函数返回值为 (IQ, bandwidth_hz)，其中 IQ 为 complex128 一维数组。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple, Optional

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass
class JammerConfig:
    """干扰信号配置。"""

    length: int = 32768
    sample_rate_hz: float = 125e6
    jnr_db: float = 15.0


def _ensure_rng(rng: Optional[np.random.Generator]) -> np.random.Generator:
    """确保返回一个 np.random.Generator 实例。

    支持的输入：
    - None: 使用全局默认生成器（不可预测）；
    - Generator 实例: 直接返回；
    - 整型种子: 使用该种子构造新的 Generator。

    其他类型一律视为错误，防止悄悄把错误对象当成随机数源。
    """
    if rng is None:
        return np.random.default_rng()
    if isinstance(rng, np.random.Generator):
        return rng
    if isinstance(rng, (int, np.integer)):
        return np.random.default_rng(int(rng))
    raise TypeError(f"rng 必须是 np.random.Generator 或整数种子，当前类型: {type(rng)!r}")


def _add_awgn_measured(iq: np.ndarray, snr_db: float, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """模拟 Matlab `awgn(x, snr, 'measured')` 行为：按输入信号测得功率添加 AWGN。

    - snr_db 在这里等价于 JNR（干扰相对噪声功率比）；
    - 若信号功率为 0，则直接返回原始信号。
    """

    rng = _ensure_rng(rng)
    power = float(np.mean(np.abs(iq) ** 2))
    if power <= 0.0 or not np.isfinite(power):
        return iq.astype(np.complex128, copy=True)
    snr_linear = 10.0 ** (snr_db / 10.0)
    noise_power = power / snr_linear
    sigma = np.sqrt(noise_power / 2.0)
    noise = sigma * (rng.standard_normal(iq.shape) + 1j * rng.standard_normal(iq.shape))
    return iq.astype(np.complex128, copy=False) + noise


def _lowpass_real(
    x: np.ndarray,
    cutoff_hz: float,
    fs_hz: float,
    order: int = 6,
) -> np.ndarray:
    """简单 IIR 低通滤波，近似 Matlab `lowpass`（仅用于噪声整形，不追求完全一致）。"""

    if cutoff_hz <= 0.0:
        return np.zeros_like(x)
    nyquist = fs_hz / 2.0
    wn = cutoff_hz / nyquist
    if wn >= 1.0:
        return x
    sos = butter(order, wn, btype="lowpass", output="sos")
    return sosfiltfilt(sos, x)


def noise_fm_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """Noise FM 干扰。

    对应 jam.m 中的 `noise_fm`：
    - 在 [50 kHz, 1000 kHz] 范围内随机带宽；
    - 通过低通滤波的宽带噪声作为调制信号；
    - 使用积分噪声做频率调制，最终加测得 JNR 的 AWGN。
    """

    rng = _ensure_rng(rng)
    length = cfg.length
    fs = cfg.sample_rate_hz

    bandwidth = rng.integers(50_000, 1_000_000 + 1)
    delta_f = int(rng.integers(25_000, bandwidth // 2 + 1))
    f_m = bandwidth / 2.0 - float(delta_f)

    t = np.arange(length, dtype=float) / fs
    noise = rng.standard_normal(length).astype(float)
    noise = _lowpass_real(noise, f_m, fs)

    # 对应 Matlab: m = cumsum([0 noise(1:len-1)]) / fs
    m = np.cumsum(np.concatenate([[0.0], noise[:-1]])) / fs
    max_noise = float(np.max(np.abs(noise))) or 1.0
    k_f = 2.0 * np.pi * delta_f / max_noise
    phase = 2.0 * np.pi * fc_hz * t + k_f * m
    iq = np.exp(1j * phase)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=rng)
    return iq_noisy, float(bandwidth)


def single_tone_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """单音干扰，对应 jam.m `single_tone`。"""

    length = cfg.length
    fs = cfg.sample_rate_hz
    t = np.arange(length, dtype=float) / fs
    iq = np.exp(1j * 2.0 * np.pi * fc_hz * t)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=_ensure_rng(rng))
    bandwidth = 24_000.0
    return iq_noisy, bandwidth


def multi_tone_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """多音干扰，对应 jam.m `multi_tone`。"""

    rng = _ensure_rng(rng)
    length = cfg.length
    fs = cfg.sample_rate_hz

    tone_num = int(rng.integers(3, 20 + 1))
    freq_sep = int(rng.integers(100_000, 1_000_000 + 1))
    bandwidth = 24_000.0 + (tone_num - 1) * freq_sep
    fl = fc_hz - 0.5 * bandwidth + 24_000.0
    f_arr = fl + np.arange(tone_num, dtype=float) * freq_sep

    t = np.arange(length, dtype=float) / fs
    iq = np.zeros(length, dtype=np.complex128)
    for f in f_arr:
        iq += np.exp(1j * 2.0 * np.pi * f * t)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=rng)
    return iq_noisy, float(bandwidth)


def comb_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """梳状谱干扰，对应 jam.m `comb`。"""

    rng = _ensure_rng(rng)
    length = cfg.length
    fs = cfg.sample_rate_hz

    comb_num = int(rng.integers(3, 20 + 1))
    comb_width = int(rng.integers(100_000, 500_000 + 1))
    freq_sep = 2 * comb_width
    bandwidth = (comb_num - 1) * freq_sep + comb_width
    fl = fc_hz - 0.5 * bandwidth + 0.5 * comb_width
    f_arr = fl + np.arange(comb_num, dtype=float) * freq_sep

    t = np.arange(length, dtype=float) / fs
    iq = np.zeros(length, dtype=np.complex128)
    for fj in f_arr:
        noise = rng.standard_normal(length).astype(float)
        noise = _lowpass_real(noise, comb_width / 2.0, fs)
        iq += noise * np.exp(1j * 2.0 * np.pi * fj * t)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=rng)
    return iq_noisy, float(bandwidth)


def partial_band_noise_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """部分带宽噪声干扰，对应 jam.m `partial_band_noise`。"""

    rng = _ensure_rng(rng)
    length = cfg.length
    fs = cfg.sample_rate_hz

    bandwidth = int(rng.integers(100_000, 20_000_000 + 1))
    t = np.arange(length, dtype=float) / fs
    noise = rng.standard_normal(length).astype(float)
    noise = _lowpass_real(noise, bandwidth / 2.0, fs)
    iq = noise * np.exp(1j * 2.0 * np.pi * fc_hz * t)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=rng)
    return iq_noisy, float(bandwidth)


def sweep_jammer(
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """扫频干扰，对应 jam.m `sweep`。"""

    rng = _ensure_rng(rng)
    length = cfg.length
    fs = cfg.sample_rate_hz

    bandwidth = int(rng.integers(1_000_000, 20_000_000 + 1))
    fl = float(np.floor(fc_hz - 0.5 * bandwidth))
    t = np.arange(length, dtype=float) / fs
    ts = length / fs
    df = bandwidth / ts
    beta = np.pi * df
    omega = 2.0 * np.pi * fl
    phase = beta * t**2 + omega * t
    iq = np.exp(1j * phase)
    iq_noisy = _add_awgn_measured(iq, cfg.jnr_db, rng=rng)
    return iq_noisy, float(bandwidth)


JAMMER_REGISTRY: Dict[str, Callable[[float, JammerConfig, Optional[np.random.Generator]], Tuple[np.ndarray, float]]] = {
    "noise_fm": noise_fm_jammer,
    "single_tone": single_tone_jammer,
    "multi_tone": multi_tone_jammer,
    "comb": comb_jammer,
    "partial_band_noise": partial_band_noise_jammer,
    "sweep": sweep_jammer,
}


def generate_jammer(
    jam_type: str,
    fc_hz: float,
    cfg: JammerConfig,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """统一入口：根据 jam_type 生成干扰信号。

    参数：
    - jam_type: 'noise_fm' / 'single_tone' / 'multi_tone' / 'comb' /
      'partial_band_noise' / 'sweep';
    - fc_hz: 干扰中心频率（Hz）；
    - cfg: JammerConfig。
    """

    try:
        fn = JAMMER_REGISTRY[jam_type]
    except KeyError as exc:
        raise ValueError(f"未知干扰类型: {jam_type}") from exc
    return fn(fc_hz, cfg, rng)
