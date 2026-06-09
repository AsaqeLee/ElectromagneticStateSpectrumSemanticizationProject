# 2026-06-09 `src/electromagnetic_state` 归档与乱码修复记录

## 目标

- 将 `src/electromagnetic_state` 下已脱离当前主链路的历史代码迁入 `archive/`；
- 修复仍在主链路中的乱码注释，降低误读成本。

## 依据

当前主链路以以下模块为核心：

- `scripts/run_union.py`
- `scripts/run_union_realtime.py`
- `src/electromagnetic_state/io/reader.py`
- `src/electromagnetic_state/signal/spectrum.py`
- `src/electromagnetic_state/signal/stitcher.py`
- `src/electromagnetic_state/pipeline/stitch/stitch_real_data.py`
- `src/electromagnetic_state/semantics/decode_v2.py`

通过仓库内引用检索确认：

- `pipeline/stitch/stitch_multi.py` 无主链路引用，仅在 `pipeline/stitch/__init__.py` 中暴露；
- `pipeline/utils/*.py` 仅在 `pipeline/utils/__init__.py` 中暴露，无主链路引用；
- `signal/spectrum_composer.py` 仍是有效功能模块，仅存在局部乱码注释，不应归档。

## 实际变更

### 1. 迁入归档

迁移到 `archive/src_history/electromagnetic_state/`：

- `pipeline/stitch/stitch_multi.py`
- `pipeline/utils/analyze_comb.py`
- `pipeline/utils/demo_resolution.py`
- `pipeline/utils/overlay_comb.py`
- `pipeline/utils/simulate_iq.py`

### 2. 活跃源码修复

- `src/electromagnetic_state/signal/spectrum_composer.py`
  - 修复 docstring 中“初始化为���噪”为“初始化为底噪”。

### 3. 包导出收敛

- `src/electromagnetic_state/pipeline/stitch/__init__.py`
  - 不再导出已归档的 `stitch_multi`。
- `src/electromagnetic_state/pipeline/utils/__init__.py`
  - 改为归档说明占位，不再导入历史工具模块。

## 风险说明

- 这次是破坏性归档：如果有人仍通过 `electromagnetic_state.pipeline.stitch.stitch_multi`
  或 `electromagnetic_state.pipeline.utils.*` 直接运行历史脚本，路径会失效；
- 但从当前仓库主链路和现有引用看，这些模块已不再承担核心功能。

## 迁移说明

无迁移，直接替换。
