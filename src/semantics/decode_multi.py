"""支持多区域的语义解码器。

当前 decode.py 的实现只支持单个连续区域 [start, end]。
本模块提供多区域支持，利用 pos_edge/neg_edge 定义多个不连续区域，
并提供自动模式 `decode_semantic_auto`。
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np

from ..core.schemas import SemanticParams


def decode_semantic_multi_region(params: SemanticParams) -> np.ndarray:
    """从语义参数恢复频谱（支持多个不连续干扰区域）。

    使用 pos_edge/neg_edge 成对定义多个区域：
    - pos_edge[i] 和 neg_edge[i] 定义第 i 个干扰区域
    - 每个区域使用 sinr[i] 作为 JNR（如果 sinr 是标量则所有区域用同一个值）
    - 区域索引语义为闭区间 [start, end]，即同时包含起止两个端点

    示例：
        params = SemanticParams(
            menxian=-80.0,
            pos_edge=[80, 500, 600, 1500, 2200],
            neg_edge=[120, 520, 720, 1800, 2300],
            fenbianlv=2471,
            sinr=np.array([25.0, 20.0, 22.0, 18.0, 15.0]),
            # start/end 在此模式下不使用
            start=0,
            end=0,
            ...
        )
        spectrum = decode_semantic_multi_region(params)
    """
    # 基本校验
    if len(params.pos_edge) != len(params.neg_edge):
        raise ValueError(
            f"pos_edge 和 neg_edge 数量必须相等，"
            f"当前 pos_edge={len(params.pos_edge)}, neg_edge={len(params.neg_edge)}"
        )

    num_regions = len(params.pos_edge)

    # sinr 校验
    if params.sinr.size != 1 and params.sinr.size != num_regions:
        raise ValueError(
            f"sinr 长度必须是 1（所有区域共用）或 {num_regions}（每区域一个），"
            f"当前为 {params.sinr.size}"
        )

    # 初始化为底噪
    power_db = np.full(params.fenbianlv, params.menxian, dtype=float)

    # 填充每个干扰区域（注意：这里使用数学上的闭区间 [start, end]）
    for i, (start_bin, end_bin) in enumerate(zip(params.pos_edge, params.neg_edge)):
        # 边界检查：确保闭区间 [start_bin, end_bin] 落在 [0, fenbianlv-1] 内
        if start_bin < 0 or end_bin >= params.fenbianlv or start_bin > end_bin:
            raise ValueError(
                f"区域 {i} 的边界非法: start={start_bin}, end={end_bin}, "
                f"有效范围 [0, {params.fenbianlv-1}]"
            )

        # 获取该区域的 JNR
        if params.sinr.size == 1:
            jnr_db = float(params.sinr.item())
        else:
            jnr_db = float(params.sinr[i])

        # 填充功率（绝对功率 = 底噪 + JNR）
        # Python 切片使用左闭右开 [start_bin, end_bin+1)，
        # 对应数学上的闭区间 [start_bin, end_bin]
        power_db[start_bin:end_bin+1] = params.menxian + jnr_db

    return power_db


def decode_semantic_auto(params: SemanticParams) -> np.ndarray:
    """自动选择单区域或多区域解码。

    判断规则：
    - 如果 pos_edge 为空或只有一个元素，使用单区域模式（原 decode_semantic）
    - 如果 pos_edge 有多个元素，使用多区域模式
    """
    if len(params.pos_edge) <= 1:
        # 单区域：使用原始实现
        from .decode import decode_semantic

        return decode_semantic(params)
    else:
        # 多区域：使用新实现
        return decode_semantic_multi_region(params)


def decode_file_auto(path: str | Path) -> Tuple[SemanticParams, np.ndarray]:
    """从 JSON 文件加载语义参数，并自动选择单/多区域解码。"""

    from .decode import load_semantic_file

    params = load_semantic_file(path)
    spectrum = decode_semantic_auto(params)
    return params, spectrum
