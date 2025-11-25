"""任务三：频谱语义恢复模块。

主要功能：
- 频谱特征提取与语义标注
- 语义信息生成（幅度、频率、相位等）
- 语义恢复效果评估与可视化
- 支持多版本算法对比
"""

from .semantic_generate import generate_semantic_info
from .semantic_eval import evaluate_semantic_recovery
from .semantic_eval_v2 import evaluate_semantic_recovery_v2
from .semantic_plot import plot_semantic_comparison

__all__ = [
    'generate_semantic_info',
    'evaluate_semantic_recovery',
    'evaluate_semantic_recovery_v2',
    'plot_semantic_comparison'
]
