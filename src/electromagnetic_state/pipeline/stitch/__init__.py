"""任务二：频谱拼接模块。

主要功能：
- 模拟窄带接收机多频段扫描
- 频谱段拼接与融合
- 支持真实IQ数据处理
"""

from . import stitch_real_data

__all__ = ['stitch_real_data']
