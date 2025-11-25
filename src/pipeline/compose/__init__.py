"""任务一：干扰信号合成模块。

主要功能：
- 生成多种类型的干扰信号（单频音、线性调频、梳状谱等）
- 合成多干扰混合场景
- 演示干扰信号生成流程
"""

from .compose_spectrum import compose_interference_spectrum
from .generate_jammers import (
    generate_single_tone,
    generate_linear_chirp,
    generate_comb_spectrum,
    generate_multi_tone
)

__all__ = [
    'compose_interference_spectrum',
    'generate_single_tone',
    'generate_linear_chirp',
    'generate_comb_spectrum',
    'generate_multi_tone'
]
