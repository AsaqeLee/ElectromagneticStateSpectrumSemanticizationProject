"""v2 语义编码的解码器。

根据 docs/semantic_encoding_requirements.md 中定义的参数：
- freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db;
- jammer_regions[start_bin, end_bin, jnr_db]；

恢复出一维功率谱向量（dB）。

支持两种输入格式：
1. JSON 格式（原有格式）
2. TXT 格式（键值对配置文件，方便不熟悉 JSON 的用户）
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Tuple, Union

import numpy as np

from ..core.schemas import (
    DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
    DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
    DEFAULT_SEMANTIC_NOISE_FLOOR_DB,
    DEFAULT_SEMANTIC_NUM_BINS,
    SemanticEncodingV2,
)


def _parse_txt_format(content: str) -> dict:
    """解析 TXT 格式的语义参数文件。
    
    TXT 格式示例：
    ```
    # 语义参数配置文件
    freq_min_mhz=30.0
    freq_max_mhz=2500.0
    num_bins=2471
    noise_floor_db=-80.0
    
    # 干扰区域列表
    [jammer_regions]
    100,200,20.5
    500,600,15.3
    ```
    
    返回：
        dict: 与 JSON 格式兼容的字典结构
    """
    result = {
        "freq_min_mhz": DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
        "freq_max_mhz": DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
        "num_bins": DEFAULT_SEMANTIC_NUM_BINS,
        "noise_floor_db": DEFAULT_SEMANTIC_NOISE_FLOOR_DB,
        "jammer_regions": [],
    }
    
    lines = content.strip().split('\n')
    in_jammer_section = False
    
    for line in lines:
        # 去除首尾空白
        line = line.strip()
        
        # 跳过空行和注释行
        if not line or line.startswith('#'):
            continue
        
        # 检测干扰区域段落标记
        if line == '[jammer_regions]':
            in_jammer_section = True
            continue
        
        # 解析干扰区域数据
        if in_jammer_section:
            # 格式：start_bin,end_bin,jnr_db
            parts = [p.strip() for p in line.split(',')]
            if len(parts) == 3:
                try:
                    start_bin = int(parts[0])
                    end_bin = int(parts[1])
                    jnr_db = float(parts[2])
                    result["jammer_regions"].append({
                        "start_bin": start_bin,
                        "end_bin": end_bin,
                        "jnr_db": jnr_db,
                    })
                except ValueError as e:
                    raise ValueError(f"干扰区域格式错误：'{line}' - {e}")
        else:
            # 解析基本参数（key=value 格式）
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                if key in result:
                    try:
                        # 根据字段类型转换
                        if key == 'num_bins':
                            result[key] = int(value)
                        else:  # freq_min_mhz, freq_max_mhz, noise_floor_db
                            result[key] = float(value)
                    except ValueError as e:
                        raise ValueError(f"参数 '{key}' 的值 '{value}' 格式错误 - {e}")
    
    return result


def _detect_file_format(path: Path) -> str:
    """检测文件格式（JSON 或 TXT）。
    
    检测策略：
    1. 文件扩展名为 .json → JSON 格式
    2. 文件扩展名为 .txt → TXT 格式
    3. 尝试 JSON 解析，成功则为 JSON
    4. 否则视为 TXT
    
    返回：
        str: 'json' 或 'txt'
    """
    # 根据扩展名判断
    ext = path.suffix.lower()
    if ext == '.json':
        return 'json'
    if ext == '.txt':
        return 'txt'
    
    # 尝试 JSON 解析
    try:
        content = path.read_text(encoding='utf-8')
        json.loads(content)
        return 'json'
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 'txt'


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


def load_semantic_v2_file(path: Union[str, Path]) -> SemanticEncodingV2:
    """从语义参数文件加载 v2 语义编码参数。
    
    支持两种格式：
    1. JSON 格式：标准 JSON 结构（原有格式）
    2. TXT 格式：键值对配置文件（方便不熟悉 JSON 的用户）
    
    文件格式自动识别，无需手动指定。
    
    参数：
        path: 文件路径（.json 或 .txt 扩展名）
        
    返回：
        SemanticEncodingV2: 解析后的语义编码参数
        
    异常：
        ValueError: 文件格式错误或参数不合法
        FileNotFoundError: 文件不存在
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 自动检测文件格式
    fmt = _detect_file_format(file_path)
    content = file_path.read_text(encoding="utf-8")
    
    if fmt == 'json':
        # JSON 格式
        data = json.loads(content)
    else:
        # TXT 格式
        data = _parse_txt_format(content)
    
    return SemanticEncodingV2.from_dict(data)


def decode_file_v2(path: Union[str, Path]) -> Tuple[SemanticEncodingV2, np.ndarray]:
    """加载并解码 v2 语义参数文件。"""

    params = load_semantic_v2_file(path)
    spectrum = decode_semantic_v2(params)
    return params, spectrum
