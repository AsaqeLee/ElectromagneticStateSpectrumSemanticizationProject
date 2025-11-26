"""频谱拼接工具：支持多个200MHz分段拼接为完整30-2500MHz频谱。

本模块提供灵活的频谱拼接功能：
- 支持从 IQ 数据或已计算的功率谱进行拼接；
- 支持多种拼接策略（最大值、平均值、加权平均）；
- 自动处理频率重叠区域；
- 提供程序化和文件化两种接口。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from ..core.schemas import IQData, SamplingConfig
from .spectrum import compute_power_spectrum


class StitchMode(str, Enum):
    """拼接模式。"""

    MAX = "max"  # 取最大值（适用于干扰检测）
    MEAN = "mean"  # 取平均值（降低噪声）
    WEIGHTED_MEAN = "weighted_mean"  # 加权平均（中心权重高）
    FIRST = "first"  # 优先使用第一个（按频率排序）
    LAST = "last"  # 优先使用最后一个（按频率排序）


@dataclass
class SpectrumSegment:
    """频谱分段数据。"""

    freq_mhz: np.ndarray  # 频率轴 MHz
    power_db: np.ndarray  # 功率谱 dB
    center_freq_mhz: float  # 中心频率 MHz
    bandwidth_mhz: float  # 带宽 MHz
    metadata: dict = None  # 附加元数据

    def __post_init__(self) -> None:
        if self.freq_mhz.shape != self.power_db.shape:
            raise ValueError(f"频率轴与功率谱形状不匹配: {self.freq_mhz.shape} vs {self.power_db.shape}")
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StitchedSpectrum:
    """拼接后的频谱结果。"""

    freq_mhz: np.ndarray  # 频率轴 MHz
    power_db: np.ndarray  # 功率谱 dB
    coverage_map: np.ndarray  # 覆盖次数（每个频点被多少个分段覆盖）
    segment_count: int  # 分段数量
    freq_min_mhz: float  # 最小频率
    freq_max_mhz: float  # 最大频率
    mode: StitchMode  # 拼接模式
    metadata: dict = None  # 附加元数据

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


def _compute_weight(freq_mhz: np.ndarray, center_freq_mhz: float, bandwidth_mhz: float) -> np.ndarray:
    """计算加权平均的权重（中心频率权重高）。

    使用高斯型权重函数，中心位置权重为1，边缘逐渐降低。
    """
    # 归一化距离（0表示中心，1表示边缘）
    distance = np.abs(freq_mhz - center_freq_mhz) / (bandwidth_mhz / 2.0)
    # 高斯权重
    weight = np.exp(-2.0 * distance**2)
    return weight


def _build_global_axis(segments: List[SpectrumSegment]) -> Tuple[np.ndarray, float]:
    """构建全局频率轴。

    返回：
    - global_axis: 全局频率轴 MHz
    - step: 频率步长 MHz
    """
    if not segments:
        raise ValueError("至少需要一个频谱分段")

    # 检查所有分段的频率步长是否一致
    steps = []
    for seg in segments:
        if seg.freq_mhz.size < 2:
            raise ValueError(f"分段频率点数不足: {seg.freq_mhz.size}")
        step = float(seg.freq_mhz[1] - seg.freq_mhz[0])
        steps.append(step)

    base_step = steps[0]
    for i, step in enumerate(steps):
        if not np.isclose(step, base_step, rtol=1e-3, atol=1e-6):
            raise ValueError(f"分段 {i} 频率步长 {step:.6f} MHz 与首段 {base_step:.6f} MHz 不一致")

    # 确定全局频率范围
    f_min = min(seg.freq_mhz.min() for seg in segments)
    f_max = max(seg.freq_mhz.max() for seg in segments)

    # 生成全局频率轴
    global_axis = np.arange(f_min, f_max + base_step / 2.0, base_step)

    return global_axis, base_step


def stitch_segments(
    segments: List[SpectrumSegment],
    mode: StitchMode = StitchMode.MAX,
    fill_value: float = -180.0,
) -> StitchedSpectrum:
    """拼接多个频谱分段。

    参数：
    - segments: 频谱分段列表
    - mode: 拼接模式
    - fill_value: 未覆盖区域的填充值 dB

    返回：
    - StitchedSpectrum: 拼接后的频谱
    """
    if not segments:
        raise ValueError("至少需要一个频谱分段")

    # 构建全局频率轴
    global_axis, step = _build_global_axis(segments)
    global_min = float(global_axis.min())
    global_max = float(global_axis.max())

    # 预检查：确保每个分段与全局频率轴存在合理重叠，避免静默丢弃
    for i, seg in enumerate(segments):
        if seg.freq_mhz.size == 0:
            raise ValueError(f"分段 {i} 频率点数为 0，无法参与拼接")

        seg_min = float(seg.freq_mhz.min())
        seg_max = float(seg.freq_mhz.max())

        # 完全超出全局范围：直接报错而不是静默丢弃
        if seg_max < global_min - step or seg_min > global_max + step:
            raise ValueError(
                f"分段 {i} 的频率范围 [{seg_min:.6f}, {seg_max:.6f}] MHz "
                f"完全落在全局范围 [{global_min:.6f}, {global_max:.6f}] MHz 之外"
            )

        # 计算重叠比例，过小则给出警告（但仍然允许拼接）
        overlap_min = max(seg_min, global_min)
        overlap_max = min(seg_max, global_max)
        if overlap_max > overlap_min:
            overlap_ratio = (overlap_max - overlap_min) / (seg_max - seg_min)
            if overlap_ratio < 0.5:
                import warnings

                warnings.warn(
                    f"分段 {i} 与全局频率轴的重叠比例仅 "
                    f"{overlap_ratio * 100:.1f}%，大部分数据可能被丢弃",
                    RuntimeWarning,
                )

    # 初始化拼接结果
    if mode == StitchMode.MAX:
        global_power = np.full_like(global_axis, fill_value, dtype=float)
    elif mode == StitchMode.MEAN or mode == StitchMode.WEIGHTED_MEAN:
        # 对于平均模式，需要累加功率（线性域）和权重
        global_power_linear = np.zeros_like(global_axis, dtype=float)
        global_weight = np.zeros_like(global_axis, dtype=float)
    elif mode == StitchMode.FIRST or mode == StitchMode.LAST:
        global_power = np.full_like(global_axis, fill_value, dtype=float)
        global_filled = np.zeros_like(global_axis, dtype=bool)
    else:
        raise ValueError(f"不支持的拼接模式: {mode}")

    # 覆盖次数统计
    coverage_map = np.zeros_like(global_axis, dtype=int)

    # 对于 FIRST/LAST 模式，需要按频率排序
    if mode == StitchMode.FIRST or mode == StitchMode.LAST:
        segments = sorted(segments, key=lambda s: s.center_freq_mhz)
        if mode == StitchMode.LAST:
            segments = segments[::-1]

    # 逐个拼接分段
    for seg in segments:
        # 计算分段在全局轴上的索引
        # 注意：np.searchsorted 返回的是“右侧插入点”，直接使用会系统性偏向右侧，
        # 导致频率误差接近一个步长，从而被下面的校验逻辑全部过滤掉。
        # 这里改为“在左右邻居中选择距离最近的索引”，保证浮点误差不至于导致整段被丢弃。
        upper = np.searchsorted(global_axis, seg.freq_mhz)
        upper = np.clip(upper, 0, global_axis.size - 1)
        lower = np.clip(upper - 1, 0, global_axis.size - 1)

        err_lower = np.abs(global_axis[lower] - seg.freq_mhz)
        err_upper = np.abs(global_axis[upper] - seg.freq_mhz)

        # 选择误差更小的那个索引作为最终映射位置
        choose_upper = err_upper <= err_lower
        idx = np.where(choose_upper, upper, lower)

        # 验证频率对齐误差，如果超过步长的一半则跳过该点
        freq_error = np.abs(global_axis[idx] - seg.freq_mhz)
        valid = freq_error < (step / 2.0)

        idx_valid = idx[valid]
        power_valid = seg.power_db[valid]

        if mode == StitchMode.MAX:
            # 取最大值
            global_power[idx_valid] = np.maximum(global_power[idx_valid], power_valid)
            coverage_map[idx_valid] += 1

        elif mode == StitchMode.MEAN:
            # 简单平均（线性域）
            power_linear = 10.0 ** (power_valid / 10.0)
            global_power_linear[idx_valid] += power_linear
            global_weight[idx_valid] += 1.0
            coverage_map[idx_valid] += 1

        elif mode == StitchMode.WEIGHTED_MEAN:
            # 加权平均（线性域）
            freq_valid = seg.freq_mhz[valid]
            weight = _compute_weight(freq_valid, seg.center_freq_mhz, seg.bandwidth_mhz)
            power_linear = 10.0 ** (power_valid / 10.0)
            global_power_linear[idx_valid] += power_linear * weight
            global_weight[idx_valid] += weight
            coverage_map[idx_valid] += 1

        elif mode == StitchMode.FIRST or mode == StitchMode.LAST:
            # 优先使用第一个/最后一个
            mask = ~global_filled[idx_valid]
            global_power[idx_valid[mask]] = power_valid[mask]
            global_filled[idx_valid[mask]] = True
            coverage_map[idx_valid] += 1

    # 后处理
    if mode == StitchMode.MEAN or mode == StitchMode.WEIGHTED_MEAN:
        # 计算平均值（转回 dB）
        mask = global_weight > 0
        global_power = np.full_like(global_axis, fill_value, dtype=float)
        global_power[mask] = 10.0 * np.log10(global_power_linear[mask] / global_weight[mask])

    return StitchedSpectrum(
        freq_mhz=global_axis,
        power_db=global_power,
        coverage_map=coverage_map,
        segment_count=len(segments),
        freq_min_mhz=float(global_axis.min()),
        freq_max_mhz=float(global_axis.max()),
        mode=mode,
    )


def stitch_from_iq_data(
    iq_data_list: List[IQData],
    configs: List[SamplingConfig],
    mode: StitchMode = StitchMode.MAX,
    fill_value: float = -180.0,
    window: str = "hann",
) -> StitchedSpectrum:
    """从 IQ 数据列表拼接频谱。

    参数：
    - iq_data_list: IQ 数据列表
    - configs: 采样配置列表（与 iq_data_list 一一对应）
    - mode: 拼接模式
    - fill_value: 未覆盖区域的填充值 dB
    - window: 窗函数类型

    返回：
    - StitchedSpectrum: 拼接后的频谱
    """
    if len(iq_data_list) != len(configs):
        raise ValueError(f"IQ数据数量 ({len(iq_data_list)}) 与配置数量 ({len(configs)}) 不匹配")

    segments = []
    for iq, cfg in zip(iq_data_list, configs):
        freq_mhz, power_db = compute_power_spectrum(iq, cfg, window=window)
        bandwidth_mhz = cfg.sample_rate_hz / 1e6
        segment = SpectrumSegment(
            freq_mhz=freq_mhz,
            power_db=power_db,
            center_freq_mhz=cfg.center_freq_hz / 1e6,
            bandwidth_mhz=bandwidth_mhz,
        )
        segments.append(segment)

    return stitch_segments(segments, mode=mode, fill_value=fill_value)


def load_segment_from_npz(path: Path) -> SpectrumSegment:
    """从 npz 文件加载频谱分段。

    期望格式：
    - freq_mhz: 频率轴 MHz
    - power_db: 功率谱 dB
    - center_freq_mhz: 中心频率 MHz（可选）
    - bandwidth_mhz: 带宽 MHz（可选）
    """
    with np.load(path) as data:
        freq_mhz = data["freq_mhz"]
        power_db = data["power_db"]
        center_freq_mhz = float(data.get("center_freq_mhz", np.mean(freq_mhz)))
        bandwidth_mhz = float(data.get("bandwidth_mhz", freq_mhz.max() - freq_mhz.min()))

        # 加载其他元数据
        metadata = {k: data[k].item() if data[k].size == 1 else data[k] for k in data.files if k not in ["freq_mhz", "power_db", "center_freq_mhz", "bandwidth_mhz"]}

    return SpectrumSegment(
        freq_mhz=freq_mhz,
        power_db=power_db,
        center_freq_mhz=center_freq_mhz,
        bandwidth_mhz=bandwidth_mhz,
        metadata=metadata,
    )


def stitch_from_npz_files(
    file_paths: List[Path],
    mode: StitchMode = StitchMode.MAX,
    fill_value: float = -180.0,
) -> StitchedSpectrum:
    """从多个 npz 文件拼接频谱。

    参数：
    - file_paths: npz 文件路径列表
    - mode: 拼接模式
    - fill_value: 未覆盖区域的填充值 dB

    返回：
    - StitchedSpectrum: 拼接后的频谱
    """
    segments = [load_segment_from_npz(path) for path in file_paths]
    return stitch_segments(segments, mode=mode, fill_value=fill_value)
