# 电磁态频谱语义化工程 - 使用指南

## 概述

本工程实现了三个核心任务，基于 `jam.m` 的干扰信号生成方法：
1. **任务一**：在 30-2500 MHz 频段内任意组合生成干扰信号的功率谱
2. **任务二**：拼接 200MHz 频谱分段为完整宽带频谱
3. **任务三**：从语义参数恢复功率谱

---

## 快速开始

### 运行完整演示
```bash
python demo_all_tasks.py
```

### 运行单个任务

**任务一 - 生成干扰功率谱：**
```bash
python -m src.pipeline.compose_spectrum \
  --jammer single_tone:500:20 \
  --jammer multi_tone:1200:18 \
  --output-npz data/task1.npz \
  --output-png data/task1.png
```

**任务二 - 拼接频谱（先创建测试数据）：**
```bash
python test_task2_create_bins.py
python -m src.pipeline.stitch_multi \
  --input-dir data/test_segments \
  --fft-size 262144 \
  --output-npz data/task2.npz \
  --output-png data/task2.png
```

**任务三 - 语义恢复：**
```bash
python -m src.pipeline.semantic_eval \
  --reference data/task1.npz \
  --semantic data/demo_semantic.json \
  --report data/task3_report.json
```

---

## 任务一：干扰信号功率谱合成

### 支持的干扰类型
| 类型 | 描述 | 带宽范围 |
|------|------|---------|
| `noise_fm` | 噪声调频干扰 | 50-1000 kHz |
| `single_tone` | 单音干扰 | 24 kHz |
| `multi_tone` | 多音干扰 | 3-20 音调 |
| `comb` | 梳状谱干扰 | 100-500 kHz/齿 |
| `partial_band_noise` | 部分带宽噪声 | 100 kHz-20 MHz |
| `sweep` | 扫频干扰 | 1-20 MHz |

### 使用示例

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
np.savez("output.npz", freq_mhz=freq_mhz, power_db=power_db)
```

---

## 任务二：频谱分段拼接

### 数据格式要求
- **文件名**：`comb_<中心频率>MHz_<采样率>MHz_<时间戳>.bin`
- **数据格式**：int16 I/Q 交织（`I1, Q1, I2, Q2, ...`）

### 拼接模式
- `MAX` - 取最大值（默认，适用于干扰检测）
- `MEAN` - 简单平均（降低噪声）
- `WEIGHTED_MEAN` - 加权平均（中心权重高）

### 使用示例

```python
from src.signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
import numpy as np

segments = []
for npz_file in Path("data").glob("segment_*.npz"):
    data = np.load(npz_file)
    seg = SpectrumSegment(
        freq_mhz=data["freq_mhz"],
        power_db=data["power_db"],
        center_freq_mhz=float(data["center_freq_mhz"]),
        bandwidth_mhz=float(data["bandwidth_mhz"]),
    )
    segments.append(seg)

stitched = stitch_segments(segments, mode=StitchMode.MAX)
np.savez("stitched.npz", freq_mhz=stitched.freq_mhz, power_db=stitched.power_db)
```

---

## 任务三：语义参数频谱恢复

### 语义参数说明

```json
{
  "yonghu": 1,          // 用户编号
  "youwu": 1,           // 是否存在干扰 (0/1)
  "menxian": -110.0,    // 底噪功率 dB
  "pos_edge": [500],    // 正边缘索引
  "neg_edge": [700],    // 负边缘索引
  "start": 470,         // 干扰起始索引
  "end": 1470,          // 干扰结束索引
  "fenbianlv": 2471,    // 频点数量
  "sinr": [15.0],       // 干扰信噪比 dB
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0
}
```

### 使用示例

```python
from src.semantics.decode import decode_semantic
from src.core.schemas import SemanticParams
import numpy as np

params = SemanticParams(
    yonghu=1, youwu=1, menxian=-120.0,
    pos_edge=[500], neg_edge=[700],
    start=470, end=1470, fenbianlv=2471,
    sinr=np.array([15.0]),
    freq_min_mhz=30.0, freq_max_mhz=2500.0,
)

recovered_power = decode_semantic(params)
```

---

## 关键文件说明

| 文件 | 功能 |
|------|------|
| `src/signal/jammers.py` | 干扰信号生成（对应 jam.m） |
| `src/signal/spectrum_composer.py` | 任务一核心模块 |
| `src/signal/stitcher.py` | 任务二核心模块 |
| `src/semantics/decode.py` | 任务三核心模块 |
| `demo_all_tasks.py` | 完整演示脚本 |
| `test_task2_create_bins.py` | 生成测试 .bin 文件 |

---

## 常见问题

**Q: Windows 控制台中文乱码？**
A: 已修复，所有 CLI 脚本自动处理编码。

**Q: 任务二需要什么数据？**
A: 需要 int16 格式的 IQ 采集文件。可运行 `python test_task2_create_bins.py` 生成测试数据。

**Q: 语义恢复误差较大？**
A: 这是正常的，语义化表征牺牲精度换取数据压缩。根据文档，误差不超过感知分辨率即可接受。

---

## 运行测试

```bash
pytest tests/ -v
```

所有核心功能均已通过单元测试验证。
