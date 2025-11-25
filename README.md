# 电磁态频谱语义化工程

本仓库实现《频谱语义化表征及频谱恢复》的基础工程，围绕 30–2500 MHz 频段提供完整的三大能力：

1. **任务一：干扰信号功率谱合成**（Jammer Spectrum Composition）  
   在 30–2500 MHz 内任意组合六类干扰信号（noise_fm / single_tone / multi_tone / comb / partial_band_noise / sweep），生成宽带干扰功率谱。
2. **任务二：频谱分段拼接**（Segmented Spectrum Stitching）  
   将多个 200 MHz 频段的采样/功率谱分段（通常为 int16 I/Q `.bin` 文件）拼接为一张 30–2500 MHz 宽带功率谱。
3. **任务三：语义参数频谱恢复**（Semantic Spectrum Reconstruction）  
   根据语义化参数在本地恢复功率谱，并和参考谱进行误差评估，支持：
   - v1：单区域语义（`SemanticParams`）；
   - v2：多区域语义（`SemanticEncodingV2` + `jammer_regions`）。

工程特点：

- 全中文文档与注释；
- 明确的数据结构（dataclass）和模块分层；
- 命令行 CLI + Python pipeline 双入口；
- 针对关键 bug（Nyquist、索引精度、边缘增强）的单元测试与修复记录。

> 推荐 Python 版本：**3.11+**。目前在 Python 3.12.9 下已通过 `pytest` 全量测试。

---

## 快速开始

### 1. 环境准备

```bash
# 建议使用 conda 管理环境
conda create -n electromagnetic-state python=3.11
conda activate electromagnetic-state

# 安装运行依赖
pip install -r requirements.txt

# （可选）安装开发/测试工具
pip install -r requirements-dev.txt

# 或使用 pyproject（需要较新 pip）
pip install -e ".[dev]"
```

### 2. 运行测试

```bash
pytest -q
```

如需只验证新增的语义/IO 相关测试：

```bash
pytest tests/test_semantics_multi_region.py \
       tests/test_semantics_v2.py \
       tests/test_io_reader.py -q
```

---

## 使用方式总览

本工程提供两类入口：

- 顶层 CLI（推荐给使用者）：
  - `spectrum_cli.py` – 交互式 CLI（任务一/二/三）；
  - `spectrum_batch.py` – 批处理 CLI（compose / stitch / decode / decode‑v2）。
- Python 模块 / pipeline（推荐给开发者与集成方）：
  - `src/pipeline/*.py` – 可通过 `python -m src.pipeline.xxx` 调用；
  - 直接导入 `src.signal` / `src.semantics` / `src.io` 下的函数。

下面分 CLI 与 Pipeline 两种方式给出典型用法。

### 3. 交互式 CLI（推荐快速体验）

```bash
python spectrum_cli.py
```

主菜单：

- 任务一：干扰功率谱合成（配置频段、底噪、干扰类型/Fc/JNR，生成并保存 npz + PNG）；
- 任务二：频谱分段拼接（加载多个频谱 npz 或分段文件，选择拼接模式，生成宽带谱）；
- 任务三：语义参数频谱恢复（从 JSON 加载语义参数，恢复功率谱并与参考谱对比）。

> 详细交互步骤、字段说明请见 `USAGE_CLI.md`。

### 4. 批处理 CLI：`spectrum_batch.py`

#### 4.1 任务一：干扰功率谱合成（compose）

```bash
# 组合两个干扰，生成宽带频谱并保存 npz
python spectrum_batch.py compose \
  --jammer single_tone:500:20 \
  --jammer sweep:1200:18 \
  -o data/composed.npz \
  --plot data/composed.png
```

#### 4.2 任务二：频谱分段拼接（stitch）

```bash
python spectrum_batch.py stitch \
  --input-dir data_segment \
  --pattern "*.bin" \
  --dtype int16 \
  --mode max \
  --fft-size 262144 \
  -o data/stitched_30_2500.npz \
  --plot data/stitched_30_2500.png
```

其中：

- `input-dir` 指向包含多个 200 MHz 分段 `.bin` 文件的目录；
- 文件名建议符合 `single_130MHz_204.8MHz_xxx.bin` 这类规范，便于自动推断中心频率与带宽。

#### 4.3 任务三：语义恢复（v1 / v2）

**v1（兼容旧格式，单区域或多区域自动判断）**：

```bash
python spectrum_batch.py decode \
  --input data/demo_semantic_v1.json \
  -o data/recovered_v1.npz
```

内部会使用 `decode_semantic_auto`：

- 若 `pos_edge` 为空/单个 → 使用 v1 `decode_semantic`；
- 若 `pos_edge` 有多个 → 使用 `decode_semantic_multi_region` 支持多区域。

**v2（推荐的多区域语义编码格式）**：

```bash
python spectrum_batch.py decode-v2 \
  --input data_semantic/semantic_case01.json \
  -o data/recovered_v2_case01.npz
```

v2 JSON 结构参见 `docs/semantic_encoding_requirements.md`：  
`freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db/jammer_regions`。

---

## Pipeline 示例（Python 模块方式）

以下示例假定你在工程根目录，且环境中已能导入 `src.*`。

### 1. 任务一：干扰功率谱合成

```python
from src.signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
import numpy as np

cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=1.0,
    noise_floor_db=-120.0,
)

add_jammer(cfg, "single_tone", 500.0, 20.0)
add_jammer(cfg, "sweep", 1800.0, 22.0)

freq_mhz, power_db = compose_spectrum(cfg, rng=np.random.default_rng(42))
np.savez("data/task1_composed.npz", freq_mhz=freq_mhz, power_db=power_db)
```

或使用 pipeline CLI：

```bash
python -m src.pipeline.compose_spectrum \
  --jammer single_tone:500:20 \
  --jammer sweep:1800:22 \
  --output-npz data/task1_composed.npz \
  --output-png data/task1_composed.png
```

### 2. 任务二：频谱分段拼接（真实 .bin 数据）

```python
from pathlib import Path
from src.io.reader import BinDataType
from src.signal.stitcher import StitchMode
from src.pipeline.stitch_real_data import stitch_from_bin_directory

stitched, segments = stitch_from_bin_directory(
    directory=Path("data_segment"),
    pattern="*.bin",
    bin_dtype=BinDataType.INT16,
    mode=StitchMode.MAX,
    fft_size=262144,
)

np.savez(
    "data/task2_stitched.npz",
    freq_mhz=stitched.freq_mhz,
    power_db=stitched.power_db,
    coverage_map=stitched.coverage_map,
)
```

### 3. 任务三：语义参数频谱恢复与评估

#### 3.1 v1：`SemanticParams` + `decode_semantic`

```python
import numpy as np
from src.core.schemas import SemanticParams
from src.semantics.decode import decode_semantic

params = SemanticParams(
    yonghu=1,
    youwu=1,
    menxian=-120.0,
    pos_edge=[500],
    neg_edge=[700],
    start=470,
    end=1470,
    fenbianlv=2471,
    sinr=np.array([15.0]),
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
)

power_db = decode_semantic(params)
```

评估（v1 自动模式）：

```bash
python -m src.pipeline.semantic_eval \
  --reference data/stitched_30_2500.npz \
  --semantic data/demo_semantic_v1.json \
  --report data/semantic_eval_v1.json
```

#### 3.2 v2：`SemanticEncodingV2` + `decode_semantic_v2`

```python
import numpy as np
from src.core.schemas import SemanticEncodingV2, JammerRegionV2
from src.semantics.decode_v2 import decode_semantic_v2

params_v2 = SemanticEncodingV2(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    num_bins=2471,
    noise_floor_db=-80.0,
    jammer_regions=[
        JammerRegionV2(start_bin=50, end_bin=90, jnr_db=25.0),
        JammerRegionV2(start_bin=470, end_bin=490, jnr_db=20.0),
    ],
)

power_db_v2 = decode_semantic_v2(params_v2)
```

评估（v2）：

```bash
python -m src.pipeline.semantic_eval_v2 \
  --reference data/stitched_30_2500.npz \
  --semantic data_semantic/semantic_case01.json \
  --report data/semantic_eval_v2_case01.json
```

---

## 目录结构

简要说明各模块职责：

- `src/core`
  - `schemas.py`：核心数据结构（`SamplingConfig`, `BandConfig`, `IQData`, `SemanticParams`, `SemanticEncodingV2` 等）；
  - `config.py`：项目级配置（频段、窗口中心等）。
- `src/io`
  - `reader.py`：IQ 文件读取（`.npy/.npz/.h5/.bin`）、批量加载分段、切片。
- `src/signal`
  - `jammers.py`：六类干扰信号生成（Python 版 `jam.m`）；
  - `spectrum.py`：FFT + 功率谱计算；
  - `segmentation.py`：频段掩码生成与 200 MHz 窗口划分；
  - `spectrum_composer.py`：任务一核心——宽带干扰功率谱合成；
  - `stitcher.py`：任务二核心——分段频谱拼接。
- `src/semantics`
  - `decode.py`：v1 单区域语义解码；
  - `decode_multi.py`：多区域/自动模式解码（基于 `SemanticParams`）；
  - `decode_v2.py`：v2 `SemanticEncodingV2` 解码；
  - `edge_detect.py`：边缘检测与简化自动编码 `auto_encode_semantic`。
- `src/pipeline`
  - `compose_spectrum.py`：任务一 pipeline；
  - `stitch_multi.py` / `stitch_real_data.py`：任务二 pipeline（模拟/真实数据）；
  - `semantic_eval.py`：任务三 v1 评估；
  - `semantic_eval_v2.py`：任务三 v2 评估；
  - 其它 demo/工具脚本（`generate_jammers.py`, `semantic_generate.py` 等）。
- `src/viz` / `src/visualization`
  - 辅助绘图、频谱对比可视化。
- `tests`
  - 核心算法、语义解码、pipeline 的单元测试与端到端测试。

---

## 开发者说明（简要）

- 模块依赖方向：  
  `core` → `io/signal/semantics` → `pipeline` → 顶层 CLI。
- 新增干扰类型：  
  在 `src/signal/jammers.py` 添加 `xxx_jammer` 函数，并注册到 `JAMMER_REGISTRY`。
- 新增语义编码策略：  
  在 `src/semantics/edge_detect.py` 或新的 `encode_v2.py` 中实现编码函数，解码逻辑放在 `decode_multi`/`decode_v2`，再通过 `semantic_eval(_v2)` 接入 pipeline。
- 对外推荐 API：
  - 合成：`compose_spectrum`；
  - 拼接：`stitch_segments` / `stitch_from_bin_directory`；
  - 语义解码：`decode_semantic` / `decode_semantic_auto` / `decode_semantic_v2`；
  - IO：`load_iq_file` / `load_bin_segments`。

---

## 常见问题

### Q1: 支持哪些干扰信号类型？

A: 工程支持六种干扰类型：

- `noise_fm` - 噪声调频干扰
- `single_tone` - 单音干扰
- `multi_tone` - 多音干扰（3-20 个音调）
- `comb` - 梳状谱干扰
- `partial_band_noise` - 部分带宽噪声干扰
- `sweep` - 扫频干扰

### Q2: 如何选择语义编码版本（v1 vs v2）？

A:

- **v1**：适用于单干扰区域或简单场景，使用 `SemanticParams` 结构，兼容现有数据
- **v2**（推荐）：支持多干扰区域，使用 `SemanticEncodingV2` + `JammerRegionV2`，结构更清晰

### Q3: 频谱拼接时如何处理重叠区域？

A: 提供三种拼接模式（`StitchMode`）：

- `MAX` - 取最大值（默认，适合干扰检测）
- `MEAN` - 取平均值（适合噪声抑制）
- `FIRST` - 优先使用第一个分段

### Q4: 为什么功率谱范围是 30-2500 MHz？

A: 这是基于实际设备采样能力和应用场景设定的默认范围。可以通过配置 `freq_min_mhz` 和 `freq_max_mhz` 参数自定义频段范围。

### Q5: 测试失败怎么办？

A:

```bash
# 运行完整测试
pytest -v

# 只运行核心功能测试
pytest tests/test_semantics_v2.py tests/test_io_reader.py -v

# 检查 Python 版本（需要 3.11+）
python --version
```

---

## 参考文档

更详细的设计思路和修复说明可参考：

- `FIXES_SUMMARY.md` - 核心问题修复记录与设计决策
- `USAGE_CLI.md` - CLI 详细使用指南
- `docs/semantic_encoding_requirements.md` - v2 语义编码规范
- `docs/频谱语义化表征及频谱恢复.md` - 原始需求文档

---

## 许可证

本项目仅供学习和研究使用。
