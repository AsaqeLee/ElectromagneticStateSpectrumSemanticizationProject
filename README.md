# 电磁态频谱语义化工程

> **Electromagnetic State Spectrum Semanticization Project**  
> 电磁频谱智能分析与语义化编码系统

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-34%20passed-brightgreen.svg)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-4%20layers-orange.svg)](#项目架构)

本项目实现《频谱语义化表征及频谱恢复》的完整工程体系，面向 **30–2500 MHz** 频段，提供从信号合成、频谱拼接到语义编码的端到端解决方案。

## 🎯 核心能力

### 1. 干扰信号功率谱合成

- **频率范围**: 30–2500 MHz（可配置）
- **频率分辨率**: 1.0 MHz（2471 个频点）
- **干扰类型**: 6 种（噪声调频、单音、多音、梳状谱、部分带宽噪声、扫频）
- **输出格式**: NPZ 功率谱文件 + PNG 可视化

### 2. 频谱分段拼接

- **拼接窗口**: 13 个 200 MHz 窗口（±100 MHz 半带宽）
- **窗口中心**: 130, 330, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400 MHz
- **拼接模式**: MAX（最大值）/ MEAN（平均值）/ FIRST（优先第一分段）
- **数据来源**: IQ `.bin` 文件（int16/float32）、NPZ 频谱文件

### 3. 语义参数频谱恢复

- **v1 格式**: `SemanticParams` - 单区域/多区域自动识别
- **v2 格式**: `SemanticEncodingV2` - 标准化多干扰区域编码
- **恢复精度**: 典型误差 < 3 dB（区域内）
- **应用场景**: 频谱压缩、传输、存储、对抗推演

## 🏗️ 项目架构

采用 **4 层模块化架构**，清晰分离核心逻辑、算法实现、业务流程和用户接口：

```
📦 electromagneticState/
├── 📂 src/
│   ├── 📁 core/                    # Layer 0: 核心数据结构与配置
│   │   ├── schemas.py              #   数据类定义（IQData, SemanticParams, SemanticEncodingV2）
│   │   └── config.py               #   全局配置（频段、窗口中心、默认参数）
│   │
│   ├── 📁 io/                      # Layer 1: 数据输入输出
│   │   └── reader.py               #   IQ 文件读取（.npy/.npz/.h5/.bin）
│   │
│   ├── 📁 signal/                  # Layer 1: 信号处理算法
│   │   ├── jammers.py              #   6 种干扰信号生成器
│   │   ├── spectrum.py             #   FFT 功率谱计算
│   │   ├── segmentation.py         #   频段窗口划分与掩码
│   │   ├── spectrum_composer.py    #   宽带频谱合成（任务一）
│   │   └── stitcher.py             #   分段频谱拼接（任务二）
│   │
│   ├── 📁 semantics/               # Layer 1: 语义编码与解码
│   │   ├── decode.py               #   v1 单区域语义解码
│   │   ├── decode_multi.py         #   v1 多区域/自动解码
│   │   ├── decode_v2.py            #   v2 标准化解码
│   │   └── edge_detect.py          #   边缘检测与自动编码
│   │
│   ├── 📁 pipeline/                # Layer 2: 业务流程编排
│   │   ├── compose/                #   任务一流程（频谱合成）
│   │   │   ├── compose_spectrum.py
│   │   │   └── generate_jammers.py
│   │   ├── stitch/                 #   任务二流程（频谱拼接）
│   │   │   ├── stitch_multi.py
│   │   │   └── stitch_real_data.py
│   │   ├── semantic/               #   任务三流程（语义恢复）
│   │   │   ├── semantic_eval.py    #     v1 评估
│   │   │   ├── semantic_eval_v2.py #     v2 评估
│   │   │   └── semantic_generate.py
│   │   └── utils/                  #   辅助工具
│   │
│   └── 📁 visualization/           # 可视化工具
│       └── viz/
│
├── 📂 tests/                       # 单元测试与集成测试
├── 📂 docs/                        # 项目文档
│   ├── USAGE_GUIDE.md              #   Python/Pipeline 使用指南
│   └── semantic_encoding_requirements.md
│
├── 📂 data/                        # 数据输出目录
├── 📂 data_semantic/               # 语义参数配置（10 个测试用例）
│
├── spectrum_cli.py                 # Layer 3: 交互式 CLI
├── spectrum_batch.py               # Layer 3: 批处理 CLI
├── README.md                       # 项目说明（本文档）
└── pyproject.toml                  # Python 项目配置
```

### 架构设计理念

- **Layer 0 (Core)**: 数据结构与常量，无业务逻辑
- **Layer 1 (Processing)**: 可复用的算法模块，单一职责
- **Layer 2 (Pipeline)**: 组合 Layer 1 完成业务流程
- **Layer 3 (CLI)**: 用户接口，调用 Pipeline 提供服务

**依赖方向**: `Layer 3 → Layer 2 → Layer 1 → Layer 0`（严格单向）

---

## ⚡ 快速开始

### 1. 环境准备

```bash
# 推荐使用 conda 管理环境
conda create -n electromagnetic-state python=3.11
conda activate electromagnetic-state

# 安装依赖
pip install -r requirements.txt

# （可选）安装开发工具
pip install -r requirements-dev.txt
```

**Python 版本**: 3.11+ （已在 Python 3.12.9 测试通过）

### 2. 快速验证

```bash
# 运行全部测试（34 个测试用例）
pytest -q

# 只运行核心功能测试
pytest tests/test_semantics_v2.py tests/test_io_reader.py -v
```

### 3. 一分钟体验

#### 方式一：交互式 CLI（推荐新手）

```bash
python spectrum_cli.py
```

选择任务一、二、三，按提示操作即可生成频谱。

#### 方式二：批处理 CLI（推荐自动化）

```bash
# 任务一：合成干扰频谱
python spectrum_batch.py compose \
  --jammer single_tone:500:25 \
  --jammer sweep:1500:20 \
  -o data/composed.npz \
  --plot data/composed.png

# 任务二：拼接真实 IQ 数据（需先准备 .bin 文件）
python spectrum_batch.py stitch \
  --input-dir data_segment \
  --pattern "*.bin" \
  --dtype int16 \
  --mode max \
  -o data/stitched.npz \
  --plot data/stitched.png

# 任务三：从语义参数恢复频谱
python spectrum_batch.py decode-v2 \
  --input data_semantic/semantic_case01.json \
  -o data/recovered.npz
```

#### 方式三：Python 脚本（推荐开发者）

```python
from src.signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
import numpy as np

# 创建配置
cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=1.0,
    noise_floor_db=-100.0,
)

# 添加干扰
add_jammer(cfg, "single_tone", 500.0, 25.0)
add_jammer(cfg, "sweep", 1500.0, 20.0)

# 生成频谱
rng = np.random.default_rng(42)
freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

# 保存结果
np.savez("data/my_spectrum.npz", freq_mhz=freq_mhz, power_db=power_db)
print(f"✓ 生成 {len(freq_mhz)} 个频点的频谱")
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

## 📚 详细文档

- **[使用指南](docs/USAGE_GUIDE.md)** - Python/Pipeline 详细使用方法
- **[语义编码规范](docs/semantic_encoding_requirements.md)** - v2 格式标准定义
- **[Bug 修复记录](BUG_FIX_SUMMARY.md)** - 详细调试过程与修复方案
- **[文档准确性审计](DOCUMENTATION_AUDIT_REPORT.md)** - 文档错误识别与修正报告

---

## 🔧 技术参数

### 频谱配置

| 参数                              | 值      | 说明               |
| --------------------------------- | ------- | ------------------ |
| `DEFAULT_SEMANTIC_FREQ_MIN_MHZ`   | 30.0    | 最小频率           |
| `DEFAULT_SEMANTIC_FREQ_MAX_MHZ`   | 2500.0  | 最大频率           |
| `DEFAULT_SEMANTIC_NUM_BINS`       | 2471    | 频点数量           |
| `DEFAULT_SEMANTIC_NOISE_FLOOR_DB` | -60.0   | 默认噪声底         |
| 频率分辨率                        | 1.0 MHz | (2500-30)/(2471-1) |

### 窗口中心（13 个）

```python
DEFAULT_WINDOW_CENTERS_MHZ = (
    130, 330, 400, 600, 800, 1000, 1200,
    1400, 1600, 1800, 2000, 2200, 2400
)
```

每个窗口半带宽: **±100 MHz**

### 支持的干扰类型

1. **noise_fm** - 噪声调频干扰
2. **single_tone** - 单音干扰
3. **multi_tone** - 多音干扰（3-20 个音调）
4. **comb** - 梳状谱干扰
5. **partial_band_noise** - 部分带宽噪声干扰
6. **sweep** - 扫频干扰

---

## 📊 项目状态

### ✅ 最近完成

- **[2025-11] 项目架构重构** - 完成 4 层模块化架构迁移
  - Layer 0: `core/` (schemas, config)
  - Layer 1: `io/`, `signal/`, `semantics/`
  - Layer 2: `pipeline/` (compose, stitch, semantic, utils)
  - Layer 3: CLI (spectrum_cli.py, spectrum_batch.py)
- **[2025-11] 全局变量清理** - 删除 10 个未使用的手动配置文件
  - 保留 10 个程序生成的语义测试用例 (`semantic_case01.json` ~ `semantic_case10.json`)
- **[2025-11] 频谱分析工具** - 完成图像差异分析报告生成
  - 识别合成数据与真实数据的功率校准问题
  - 建立拼接算法版本差异文档

### 📋 测试状态

- **总测试数**: 34 个
- **通过率**: 100% ✅ 所有测试通过
- **最近修复**: 噪声波动参数优化 (commit `7fc78d9`) - `test_high_frequency_jammer` 现已通过

### 🔄 当前分支

- **主分支**: `main`
- **开发分支**: `refactor/project-structure` (已完成重构，待合并)

---

## 🛠️ 开发者指南

### 模块依赖关系

```
CLI (Layer 3)
  ↓
Pipeline (Layer 2)
  ↓
Signal/Semantics/IO (Layer 1)
  ↓
Core (Layer 0)
```

### 推荐 API

**频谱合成**:

```python
from src.signal.spectrum_composer import compose_spectrum, add_jammer
```

**频谱拼接**:

```python
from src.signal.stitcher import stitch_segments
from src.pipeline.stitch.stitch_real_data import stitch_from_bin_directory
```

**语义解码**:

```python
from src.semantics.decode import decode_semantic          # v1 单区域
from src.semantics.decode_multi import decode_semantic_auto  # v1 自动模式
from src.semantics.decode_v2 import decode_semantic_v2      # v2 标准格式
```

**数据 IO**:

```python
from src.io.reader import load_iq_file, load_bin_segments
```

### 扩展开发

**新增干扰类型**:

1. 在 `src/signal/jammers.py` 添加生成函数 `xxx_jammer()`
2. 注册到 `JAMMER_REGISTRY` 字典
3. 更新 CLI 参数解析器

**新增语义编码策略**:

1. 在 `src/semantics/` 实现编码/解码函数
2. 在 `src/pipeline/semantic/` 创建评估流程
3. 添加对应的单元测试

---

## ❓ 常见问题

### Q1: 如何选择语义编码版本（v1 vs v2）？

**v1 格式** (`SemanticParams`):

- ✅ 兼容现有数据
- ✅ 支持单区域/多区域自动识别
- ⚠️ 结构相对复杂

**v2 格式** (`SemanticEncodingV2`) - **推荐**:

- ✅ 标准化多干扰区域编码
- ✅ 结构清晰，易于扩展
- ✅ 10 个测试用例参考 (`data_semantic/semantic_case*.json`)

### Q2: 频谱拼接模式如何选择？

| 模式      | 适用场景           | 优势             | 劣势             |
| --------- | ------------------ | ---------------- | ---------------- |
| **MAX**   | 干扰检测、峰值分析 | 保留所有干扰峰值 | 可能放大噪声     |
| **MEAN**  | 噪声抑制、平均功率 | 降低随机噪声影响 | 可能掩盖瞬时干扰 |
| **FIRST** | 优先级分段处理     | 简单快速         | 忽略后续分段信息 |

### Q3: 为什么默认频率范围是 30-2500 MHz？

这是基于项目需求和实际硬件能力设定的：

- **30 MHz**: 短波上限，避开高频噪声
- **2500 MHz**: 覆盖主要通信频段（包括 L/S 波段）
- **可自定义**: 通过配置参数调整 `freq_min_mhz` 和 `freq_max_mhz`

### Q4: 如何提高语义恢复精度？

1. **准确的边缘检测**: 确保 `pos_edge` 和 `neg_edge` 索引精确
2. **合理的 JNR 值**: 通常设置为 15-30 dB
3. **使用 v2 格式**: 更清晰的多区域定义
4. **验证频点数**: `num_bins` 必须与原始频谱一致 (2471)

### Q5: 测试失败如何排查？

```bash
# 1. 检查 Python 版本
python --version  # 需要 3.11+

# 2. 运行详细测试
pytest -v --tb=short

# 3. 只测试核心功能
pytest tests/test_semantics_v2.py -v

# 4. 查看失败详情
pytest tests/test_semantics_v2.py -vv --tb=long
```

### Q6: 如何处理大量 IQ 文件？

**批量拼接示例**:

```bash
# 方法一：使用 CLI
python spectrum_batch.py stitch \
  --input-dir data_segment \
  --pattern "*.bin" \
  --dtype int16 \
  --mode max \
  -o data/batch_stitched.npz

# 方法二：Python 脚本
from src.io.reader import load_bin_segments, BinDataType
segments = load_bin_segments("data_segment", "*.bin", BinDataType.INT16)
print(f"加载了 {len(segments)} 个分段")
```

---

## 📖 参考资源

### 核心文档

- **[Python/Pipeline 使用指南](docs/USAGE_GUIDE.md)** - 详细的 Python API 和 Pipeline 使用方法
- **[Bug 修复记录](BUG_FIX_SUMMARY.md)** - 详细调试过程与修复方案
- **[文档准确性审计](DOCUMENTATION_AUDIT_REPORT.md)** - 文档错误识别与修正报告

### 技术规范

- **[语义编码规范 v2](docs/semantic_encoding_requirements.md)** - `SemanticEncodingV2` 格式标准
- **[原始需求文档](docs/频谱语义化表征及频谱恢复.md)** - 项目背景与技术要求

### 示例配置

- `data_semantic/semantic_case01.json` ~ `semantic_case10.json` - 10 个语义编码测试用例
- `data/cli_results/jammer_config.json` - 干扰源配置示例

---

## 📬 联系与支持

如遇到问题或有改进建议，请：

1. 查阅 [USAGE_GUIDE.md](docs/USAGE_GUIDE.md) 详细文档
2. 检查 [常见问题](#常见问题) 章节
3. 查看项目 [Issues](../../issues) 或提交新问题

---

## 📄 许可证

本项目仅供**学习和研究**使用。

---

<div align="center">

**🔬 Electromagnetic State Spectrum Semanticization Project**

_电磁频谱智能分析 · 语义化编码 · 高效恢复_

</div>
