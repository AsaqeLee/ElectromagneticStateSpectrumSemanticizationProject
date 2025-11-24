"""宽带功率谱合成工具：在 30-2500 MHz 频段内组合多个干扰信号生成功率谱。

本模块提供在指定频段（默认 30-2500 MHz）内任意组合多种干扰信号的功能：
- 支持同时添加多个不同类型、不同位置的干扰；
- 直接生成功率谱（dB），无需存储大量 IQ 数据；
- 适用于快速仿真和频谱占用分析。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from .jammers import JAMMER_REGISTRY, JammerConfig, generate_jammer
from .spectrum import POWER_EPS


@dataclass
class JammerSpec:
    """单个干扰信号配置。"""

    jam_type: str  # 干扰类型：noise_fm, single_tone, multi_tone, comb, partial_band_noise, sweep
    center_freq_mhz: float  # 干扰中心频率 MHz
    jnr_db: float = 15.0  # 干扰相对噪声比 dB
    bandwidth_mhz: float | None = None  # 干扰带宽 MHz（可选，由干扰类型自动确定）


@dataclass
class SpectrumComposerConfig:
    """宽带功率谱合成配置。"""

    freq_min_mhz: float = 30.0  # 频段下限 MHz
    freq_max_mhz: float = 2500.0  # 频段上限 MHz
    resolution_mhz: float = 1.0  # 频率分辨率 MHz
    noise_floor_db: float = -80.0  # 底噪基准功率 dB（基于真实采集数据：-77dB，实际会加±5dB随机波动）
    sample_rate_hz: float = 125e6  # IQ采样率（用于生成干扰信号）
    iq_length: int = 32768  # IQ信号长度（用于功率谱估计）
    jammers: List[JammerSpec] = field(default_factory=list)

    @property
    def num_bins(self) -> int:
        """频谱bin数量。"""
        return int(np.ceil((self.freq_max_mhz - self.freq_min_mhz) / self.resolution_mhz)) + 1

    @property
    def freq_axis_mhz(self) -> np.ndarray:
        """频率轴 MHz。"""
        return np.linspace(self.freq_min_mhz, self.freq_max_mhz, self.num_bins)


def _generate_jammer_spectrum(
    spec: JammerSpec,
    sample_rate_hz: float,
    iq_length: int,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """生成单个干扰的频谱。

    工作原理：
    1. 在基带（fc=0）生成干扰IQ信号，确保信号在Nyquist范围内；
    2. 计算基带功率谱；
    3. 通过频率轴平移将功率谱移到目标中心频率。

    这样避免了在时域生成超过采样率一半的高频信号（违反Nyquist），
    而是利用功率谱的平移不变性直接在频域定位。

    返回：
    - freq_axis_mhz: 频率轴 MHz（已平移到目标中心频率）
    - power_db: 功率谱 dB
    - actual_bandwidth_hz: 实际带宽 Hz
    """
    cfg = JammerConfig(length=iq_length, sample_rate_hz=sample_rate_hz, jnr_db=spec.jnr_db)

    # 在基带生成干扰（fc=0），功率谱形状正确
    iq, bandwidth_hz = generate_jammer(spec.jam_type, 0.0, cfg, rng=rng)

    # 计算基带功率谱
    fft_result = np.fft.fftshift(np.fft.fft(iq, n=iq_length))
    power = np.abs(fft_result) ** 2 / iq_length
    power_db = 10.0 * np.log10(power + POWER_EPS)

    # 归一化：将功率谱归一化到 [0, 1] 范围，峰值对应 JNR
    # 这样干扰峰值 = 底噪 + JNR（在 compose_spectrum 中叠加时）
    power_db_normalized = power_db - power_db.max()  # 峰值归零
    # 将归一化后的功率转换回线性用于正确叠加
    # power_db 现在表示相对于峰值的形状

    # 生成基带频率轴（中心在0）
    freq_hz = np.fft.fftshift(np.fft.fftfreq(iq_length, d=1.0 / sample_rate_hz))

    # 平移到目标中心频率（在频域而非时域）
    target_center_hz = spec.center_freq_mhz * 1e6
    freq_mhz = (freq_hz + target_center_hz) / 1e6

    return freq_mhz, power_db_normalized, bandwidth_hz


def _interpolate_spectrum(
    freq_src_mhz: np.ndarray,
    power_src_db: np.ndarray,
    freq_dst_mhz: np.ndarray,
) -> np.ndarray:
    """将源频谱插值到目标频率轴。

    对于目标频率轴上不在源频率范围内的点，功率设为 -inf（后续用底噪填充）。
    """
    # 只在源频率范围内插值
    mask = (freq_dst_mhz >= freq_src_mhz.min()) & (freq_dst_mhz <= freq_src_mhz.max())
    power_dst_db = np.full_like(freq_dst_mhz, -np.inf)

    if np.any(mask):
        power_dst_db[mask] = np.interp(freq_dst_mhz[mask], freq_src_mhz, power_src_db)

    return power_dst_db


def compose_spectrum(
    cfg: SpectrumComposerConfig,
    rng: np.random.Generator | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """合成宽带功率谱。

    流程：
    1. 初始化为���噪；
    2. 逐个生成干扰信号的功率谱；
    3. 插值到统一频率轴；
    4. 按功率叠加（线性域相加后转dB）。

    返回：
    - freq_axis_mhz: 频率轴 MHz
    - power_db: 合成功率谱 dB
    """
    if rng is None:
        rng = np.random.default_rng()

    freq_axis = cfg.freq_axis_mhz

    # 初始化为随机波动的底噪（更真实）
    # 底噪 = 基准值 + 随机波动（基于真实数据分析：±10dB波动，使用5dB标准差）
    noise_variation_db = rng.standard_normal(len(freq_axis)) * 5.0  # 5dB标准差 ≈ ±10dB范围
    noise_db = cfg.noise_floor_db + noise_variation_db
    power_linear = 10.0 ** (noise_db / 10.0)

    for spec in cfg.jammers:
        if spec.jam_type not in JAMMER_REGISTRY:
            raise ValueError(f"未知干扰类型: {spec.jam_type}")

        # 生成干扰频谱（已归一化，峰值为0dB）
        freq_jam_mhz, power_jam_normalized_db, bw_hz = _generate_jammer_spectrum(
            spec, cfg.sample_rate_hz, cfg.iq_length, rng
        )

        # 插值到目标频率轴
        power_jam_interp_db = _interpolate_spectrum(freq_jam_mhz, power_jam_normalized_db, freq_axis)

        # 应用 JNR：峰值功率 = 底噪 + JNR
        # 归一化功率 + 底噪 + JNR = 实际功率
        power_jam_absolute_db = power_jam_interp_db + cfg.noise_floor_db + spec.jnr_db

        # 转换为线性域并叠加
        power_jam_linear = 10.0 ** (power_jam_absolute_db / 10.0)
        power_jam_linear[~np.isfinite(power_jam_linear)] = 0.0  # 处理 -inf
        power_linear += power_jam_linear

    # 转换回 dB
    power_db = 10.0 * np.log10(power_linear + POWER_EPS)

    return freq_axis, power_db


def add_jammer(
    cfg: SpectrumComposerConfig,
    jam_type: str,
    center_freq_mhz: float,
    jnr_db: float = 15.0,
) -> None:
    """向配置中添加一个干扰。"""
    cfg.jammers.append(JammerSpec(jam_type=jam_type, center_freq_mhz=center_freq_mhz, jnr_db=jnr_db))
