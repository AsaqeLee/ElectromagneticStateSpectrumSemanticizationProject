"""自动边缘检测模块。

从功率谱中自动检测干扰边缘位置，用于语义编码。
"""
from __future__ import annotations

from typing import Tuple, List

import numpy as np
from scipy.ndimage import uniform_filter1d


def detect_edges(
    power_db: np.ndarray,
    threshold_db: float = 10.0,
    smoothing_window: int = 5,
    min_gap: int = 3,
) -> Tuple[List[int], List[int]]:
    """自动检测功率谱的正/负边缘。

    算法：
    1. 平滑功率谱以减少噪声
    2. 计算一阶差分
    3. 找到差分超过阈值的位置
    4. 正差分为正边缘（功率上升），负差分为负边缘（功率下降）
    5. 合并相邻的边缘点

    参数:
    - power_db: 功率谱 (dB)
    - threshold_db: 边缘检测阈值 (dB)
    - smoothing_window: 平滑窗口大小
    - min_gap: 最小边缘间距

    返回:
    - pos_edge: 正边缘索引列表
    - neg_edge: 负边缘索引列表
    """
    if power_db.size < 3:
        return [], []

    # 平滑
    if smoothing_window > 1:
        smoothed = uniform_filter1d(power_db, size=smoothing_window, mode='nearest')
    else:
        smoothed = power_db.copy()

    # 一阶差分
    diff = np.diff(smoothed)

    # 检测正边缘（上升沿）
    pos_mask = diff > threshold_db
    pos_indices = np.where(pos_mask)[0].tolist()

    # 检测负边缘（下降沿）
    neg_mask = diff < -threshold_db
    neg_indices = np.where(neg_mask)[0].tolist()

    # 合并相邻边缘
    pos_edge = _merge_close_indices(pos_indices, min_gap)
    neg_edge = _merge_close_indices(neg_indices, min_gap)

    return pos_edge, neg_edge


def _merge_close_indices(indices: List[int], min_gap: int) -> List[int]:
    """合并相邻的索引点。

    将间距小于min_gap的连续索引合并为一个（取中间位置）。
    """
    if not indices:
        return []

    merged = []
    group_start = indices[0]
    group_end = indices[0]

    for idx in indices[1:]:
        if idx - group_end <= min_gap:
            # 扩展当前组
            group_end = idx
        else:
            # 保存当前组的中心位置
            merged.append((group_start + group_end) // 2)
            group_start = idx
            group_end = idx

    # 保存最后一组
    merged.append((group_start + group_end) // 2)

    return merged


def detect_jammer_region(
    power_db: np.ndarray,
    noise_floor_db: float,
    snr_threshold_db: float = 6.0,
) -> Tuple[int, int]:
    """检测干扰区域的起止索引。

    算法：
    1. 找到功率超过 noise_floor + snr_threshold 的区域
    2. 返回连续区域的起止索引

    参数:
    - power_db: 功率谱 (dB)
    - noise_floor_db: 底噪功率 (dB)
    - snr_threshold_db: 干扰检测阈值相对底噪 (dB)

    返回:
    - start: 起始索引
    - end: 结束索引
    """
    threshold = noise_floor_db + snr_threshold_db
    above_threshold = power_db > threshold

    if not np.any(above_threshold):
        # 没有干扰
        return 0, 0

    # 找到第一个和最后一个超过阈值的点
    indices = np.where(above_threshold)[0]
    start = int(indices[0])
    end = int(indices[-1])

    return start, end


def estimate_sinr(
    power_db: np.ndarray,
    start: int,
    end: int,
    noise_floor_db: float,
) -> np.ndarray:
    """估计干扰区域的SINR。

    参数:
    - power_db: 功率谱 (dB)
    - start: 干扰起始索引
    - end: 干扰结束索引
    - noise_floor_db: 底噪功率 (dB)

    返回:
    - sinr: 干扰区域每个频点的SINR (dB)
    """
    if start > end or end >= power_db.size:
        return np.array([0.0])

    jammer_power = power_db[start:end+1]
    sinr = jammer_power - noise_floor_db

    return sinr


def auto_encode_semantic(
    power_db: np.ndarray,
    freq_min_mhz: float = 30.0,
    freq_max_mhz: float = 2500.0,
    noise_percentile: float = 10.0,
    snr_threshold_db: float = 6.0,
    edge_threshold_db: float = 10.0,
) -> dict:
    """自动从功率谱提取语义参数。

    这是一个简化版编码器，用于演示边缘检测功能。
    完整编码器应由专门的算法团队实现。

    参数:
    - power_db: 功率谱 (dB)
    - freq_min_mhz: 频率下限 (MHz)
    - freq_max_mhz: 频率上限 (MHz)
    - noise_percentile: 底噪估计百分位数
    - snr_threshold_db: 干扰检测阈值 (dB)
    - edge_threshold_db: 边缘检测阈值 (dB)

    返回:
    - 语义参数字典
    """
    # 估计底噪（使用低百分位数）
    noise_floor = float(np.percentile(power_db, noise_percentile))

    # 检测干扰区域
    start, end = detect_jammer_region(power_db, noise_floor, snr_threshold_db)

    # 检测边缘
    pos_edge, neg_edge = detect_edges(power_db, edge_threshold_db)

    # 估计SINR
    if start < end:
        sinr = estimate_sinr(power_db, start, end, noise_floor)
        has_jammer = 1
    else:
        sinr = np.array([0.0])
        has_jammer = 0

    return {
        "yonghu": 1,
        "youwu": has_jammer,
        "menxian": noise_floor,
        "pos_edge": pos_edge,
        "neg_edge": neg_edge,
        "start": start,
        "end": end,
        "fenbianlv": power_db.size,
        "sinr": sinr.tolist(),
        "freq_min_mhz": freq_min_mhz,
        "freq_max_mhz": freq_max_mhz,
    }
