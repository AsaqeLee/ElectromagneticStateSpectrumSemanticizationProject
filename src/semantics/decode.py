"""将语义参数解码为功率谱。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np

from ..core.schemas import SemanticParams


def _apply_edges(power_db: np.ndarray, pos_edge: list[int], neg_edge: list[int], delta: float) -> None:
    """根据正/负边缘列表微调谱线，以凸显跃迁。

    边缘增强应该是小幅度调整（3-5dB），用于标记频谱跳变位置，
    而不是直接等于干扰功率。这里使用 10% 的 delta 作为边缘增强量。
    """
    edge_boost = min(delta * 0.1, 5.0)  # 限制在5dB以内

    for idx in pos_edge:
        if 0 <= idx < power_db.size:
            power_db[idx] = power_db[idx] + edge_boost
    for idx in neg_edge:
        if 0 <= idx < power_db.size:
            power_db[idx] = power_db[idx] - edge_boost


def decode_semantic(params: SemanticParams) -> np.ndarray:
    """依据语义参数恢复功率谱。

    规则：
    - 以 menxian 构造底噪；
    - 在 [start, end] 范围内叠加 sinr（单值视为常数，数组按位对齐）；
    - pos_edge/neg_edge 位置分别上抬/下压，以强调边缘。

    注意：
    - 本函数只在“语义坐标系”下恢复一维谱线，不关心具体物理频率；
    - 实际频率轴由上层根据 `freq_min_mhz/freq_max_mhz/fenbianlv` 构造，
      这样可以在不改变语义格式的前提下适配不同带宽场景。
    """

    params.validate()
    power_db = np.full(params.fenbianlv, params.menxian, dtype=float)
    segment_len = params.end - params.start + 1
    if params.sinr.size == 1:
        boost = float(params.sinr.item())
        power_db[params.start : params.end + 1] += boost
        edge_delta = abs(boost)
    else:
        boost = params.sinr[:segment_len]
        power_db[params.start : params.end + 1] += boost
        edge_delta = float(np.max(np.abs(boost)))
    _apply_edges(power_db, params.pos_edge, params.neg_edge, edge_delta)
    return power_db


def load_semantic_file(path: str | Path) -> SemanticParams:
    """从 JSON 文件加载语义参数。"""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SemanticParams.from_dict(data)


def decode_file(path: str | Path) -> Tuple[SemanticParams, np.ndarray]:
    """加载并解码语义参数文件。"""

    params = load_semantic_file(path)
    spectrum = decode_semantic(params)
    return params, spectrum
