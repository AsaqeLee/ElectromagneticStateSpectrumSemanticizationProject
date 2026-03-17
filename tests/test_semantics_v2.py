from pathlib import Path
import json

import numpy as np

from src.core.schemas import SemanticEncodingV2
from src.semantics.decode_v2 import decode_semantic_v2, decode_file_v2, load_semantic_v2_file
import pytest


def test_decode_semantic_v2_basic():
    """v2 语义解码：两个不重叠区域的矩形窗恢复。"""

    data = {
        "freq_min_mhz": 30.0,
        "freq_max_mhz": 2500.0,
        "num_bins": 2471,
        "noise_floor_db": -80.0,
        "jammer_regions": [
            {"start_bin": 50, "end_bin": 90, "jnr_db": 25.0},
            {"start_bin": 470, "end_bin": 490, "jnr_db": 20.0},
        ],
    }

    params = SemanticEncodingV2.from_dict(data)
    power = decode_semantic_v2(params)

    assert power.shape == (params.num_bins,)
    # 区域外为底噪
    assert np.isclose(power[10], -80.0)
    # 区域1: -55 dB
    assert np.allclose(power[50:91], -55.0)
    # 区域2: -60 dB
    assert np.allclose(power[470:491], -60.0)


def test_decode_file_v2_round_trip(tmp_path):
    """decode_file_v2 能从 JSON 文件恢复与直接解码一致的功率谱。"""

    data = {
        "freq_min_mhz": 30.0,
        "freq_max_mhz": 2500.0,
        "num_bins": 256,
        "noise_floor_db": -80.0,
        "jammer_regions": [
            {"start_bin": 10, "end_bin": 20, "jnr_db": 15.0},
        ],
    }
    path = tmp_path / "semantic_v2.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    params, power = decode_file_v2(path)
    # 直接用 params 再解一次，结果应完全一致
    power2 = decode_semantic_v2(params)
    assert np.allclose(power, power2)


def test_load_semantic_v2_file_relaxed_allows_overlap(tmp_path):
    """宽松加载：允许 jammer_regions 无序/重叠（strict=False）。"""

    data = {
        "freq_min_mhz": 30.0,
        "freq_max_mhz": 2500.0,
        "num_bins": 256,
        "noise_floor_db": -80.0,
        "jammer_regions": [
            {"start_bin": 10, "end_bin": 30, "jnr_db": 5.0},
            {"start_bin": 20, "end_bin": 40, "jnr_db": 3.0},
        ],
    }
    path = tmp_path / "semantic_v2_overlap.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError):
        load_semantic_v2_file(path)  # strict=True（默认）

    params = load_semantic_v2_file(path, strict=False)
    assert params.num_bins == 256
    assert len(params.jammer_regions) == 2
