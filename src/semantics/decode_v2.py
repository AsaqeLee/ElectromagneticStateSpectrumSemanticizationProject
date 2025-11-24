"""v2 语义编码的解码器。

根据 docs/semantic_encoding_requirements.md 中定义的参数：
- freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db;
- jammer_regions[start_bin, end_bin, jnr_db]；

恢复出一维功率谱向量（dB）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np

from ..core.schemas import SemanticEncodingV2


def decode_semantic_v2(params: SemanticEncodingV2) -> np.ndarray:
    """依据 v2 语义参数恢复功率谱。

    规则：
    - 以 noise_floor_db 作为底噪，初始化 length=num_bins 的谱线；
    - 对每个 jammer_region，将 [start_bin, end_bin] 之间的功率设置为
      noise_floor_db + jnr_db（矩形窗）。
    """

    params.validate()
    power = np.full(params.num_bins, params.noise_floor_db, dtype=float)
    for region in params.jammer_regions:
        power[region.start_bin : region.end_bin + 1] = params.noise_floor_db + region.jnr_db
    return power


def load_semantic_v2_file(path: str | Path) -> SemanticEncodingV2:
    """从 JSON 文件加载 v2 语义编码参数。"""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SemanticEncodingV2.from_dict(data)


def decode_file_v2(path: str | Path) -> Tuple[SemanticEncodingV2, np.ndarray]:
    """加载并解码 v2 语义参数文件。"""

    params = load_semantic_v2_file(path)
    spectrum = decode_semantic_v2(params)
    return params, spectrum

