"""电磁态频谱语义化工程 - Pipeline 编排层 (Layer 2)。

模块组织：
- compose/   - 任务一：干扰信号合成
- stitch/    - 任务二：频谱拼接
- semantic/  - 任务三：频谱语义恢复
- utils/     - 辅助工具
"""

# 导出子模块以支持便捷访问
from . import compose
from . import stitch
from . import semantic
from . import utils

__all__ = ['compose', 'stitch', 'semantic', 'utils']
