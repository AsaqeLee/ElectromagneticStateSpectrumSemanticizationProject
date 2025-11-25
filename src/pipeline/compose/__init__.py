"""任务一：干扰信号合成模块。

主要功能：
- 生成多种类型的干扰信号（单频音、线性调频、梳状谱等）
- 合成多干扰混合场景
- 演示干扰信号生成流程
"""

# 这些模块主要是命令行工具，暴露 main 函数供 python -m 调用
from . import compose_spectrum
from . import generate_jammers  
from . import jammer_demo

__all__ = ['compose_spectrum', 'generate_jammers', 'jammer_demo']
