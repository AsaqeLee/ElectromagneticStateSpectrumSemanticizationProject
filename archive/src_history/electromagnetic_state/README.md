# src_history 归档说明

本目录用于存放从 `src/electromagnetic_state/` 中迁出的历史源码。

归档原则：

- 仅归档当前主链路已不再依赖的旧版 CLI、一次性分析脚本和实验性工具；
- 不归档 `run_union.py` / `run_union_realtime.py` 仍在使用的核心模块；
- 若后续需要恢复历史脚本，应优先以“参考实现”身份查看，而不是重新挂回主包导出。

2026-06-09 本次归档内容：

- `pipeline/stitch/stitch_multi.py`
  旧版多 `.bin` 拼接 CLI，已被 `pipeline/stitch/stitch_real_data.py` 和 `scripts/run_union.py` 主链路取代。
- `pipeline/utils/analyze_comb.py`
- `pipeline/utils/demo_resolution.py`
- `pipeline/utils/overlay_comb.py`
- `pipeline/utils/simulate_iq.py`
  以上均为一次性分析/演示工具，当前仓库主链路无直接依赖。
