# 电磁态频谱语义化工程 - 使用指南（Python / Pipeline）

本指南面向**开发者和集成方**，说明如何通过 Python 模块和 `src/pipeline` 脚本使用本工程，完成三大任务：

1. 任务一：干扰信号功率谱合成；
2. 任务二：频谱分段拼接；
3. 任务三：语义参数频谱恢复（v1 / v2）。

若只关心交互式 CLI，请参考 `USAGE_CLI.md` 或直接运行 `python spectrum_cli.py`。

---

## 0. 环境与导入约定

### 0.1 环境准备

```bash
conda activate electromagnetic-state  # 或其它 Python 3.11+ 环境

pip install -r requirements.txt       # 运行依赖
pip install -r requirements-dev.txt   # 开发/测试依赖（可选）
```

### 0.2 Python 导入约定

在仓库根目录下运行 Python/脚本，使用：

```python
from src.signal import ...
from src.semantics import ...
from src.io import ...
from src.core import ...
```

> 后续如改为安装为包（`pip install -e .`），可换成标准包名导入，这不影响本指南中示例的逻辑。

---

## 1. 任务一：干扰信号功率谱合成

目标：在 30–2500 MHz 频段内，组合多种干扰（noise_fm / single_tone / …），得到宽带功率谱 `freq_mhz, power_db`。

### 1.1 使用信号模块（推荐）

```python
from src.signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
import numpy as np

# 1）构造配置
cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=1.0,
    noise_floor_db=-120.0,
    sample_rate_hz=125e6,
    iq_length=32768,
)

# 2）添加干扰
add_jammer(cfg, "single_tone", 500.0, 20.0)
add_jammer(cfg, "multi_tone", 1200.0, 18.0)
add_jammer(cfg, "sweep", 1800.0, 22.0)

# 3）生成功率谱
rng = np.random.default_rng(42)
freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

np.savez("data/task1_composed.npz", freq_mhz=freq_mhz, power_db=power_db)
```

### 1.2 使用 pipeline 脚本

```bash
python -m src.pipeline.compose_spectrum \
  --jammer single_tone:500:20 \
  --jammer multi_tone:1200:18 \
  --jammer sweep:1800:22 \
  --output-npz data/task1_composed.npz \
  --output-png data/task1_composed.png
```

参数说明：

- `--jammer TYPE:FREQ:JNR`：干扰配置，支持多次出现；
- `--freq-min/--freq-max`：频段范围（MHz）；
- `--resolution`：频率分辨率（MHz）；
- `--noise-floor`：底噪功率（dB）；
- `--sample-rate/--iq-length`：内部生成 IQ 时使用的采样参数。

---

## 2. 任务二：频谱分段拼接

目标：将多个 200 MHz 频段的采样/功率谱分段拼接为 30–2500 MHz 宽带谱。

典型来源：真实设备采样 `.bin` 文件（int16 交织 I/Q）。

### 2.1 使用 IO + stitcher 拼接（纯 Python）

```python
from pathlib import Path

from src.io.reader import load_bin_segments, BinDataType
from src.core.schemas import SamplingConfig
from src.signal.spectrum import compute_power_spectrum
from src.signal.stitcher import SpectrumSegment, stitch_segments, StitchMode

# 1）加载 .bin 分段（自动按中心频率排序）
iq_segments = load_bin_segments("data_segment", pattern="*.bin", bin_dtype=BinDataType.INT16)

segments = []
for iq in iq_segments:
    cfg = SamplingConfig(
        sample_rate_hz=iq.sample_rate_hz,
        center_freq_hz=iq.center_freq_hz,
        fft_size=262144,
    )
    freq_mhz, power_db = compute_power_spectrum(iq, cfg)
    seg = SpectrumSegment(
        freq_mhz=freq_mhz,
        power_db=power_db,
        center_freq_mhz=iq.center_freq_hz / 1e6,
        bandwidth_mhz=iq.sample_rate_hz / 1e6,
        metadata=iq.meta,
    )
    segments.append(seg)

# 2）拼接（MAX 模式）
stitched = stitch_segments(segments, mode=StitchMode.MAX, fill_value=-180.0)

np.savez(
    "data/task2_stitched.npz",
    freq_mhz=stitched.freq_mhz,
    power_db=stitched.power_db,
    coverage_map=stitched.coverage_map,
)
```

### 2.2 使用 `stitch_real_data` pipeline

```python
from pathlib import Path
from src.io.reader import BinDataType
from src.signal.stitcher import StitchMode
from src.pipeline.stitch_real_data import stitch_from_bin_directory
import numpy as np

stitched, segments = stitch_from_bin_directory(
    directory=Path("data_segment"),
    pattern="*.bin",
    bin_dtype=BinDataType.INT16,
    mode=StitchMode.MAX,
    fft_size=262144,
)

np.savez(
    "data/task2_stitched_real.npz",
    freq_mhz=stitched.freq_mhz,
    power_db=stitched.power_db,
    coverage_map=stitched.coverage_map,
)
```

### 2.3 使用 batch CLI（推荐自动化）

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

---

## 3. 任务三：语义参数频谱恢复（v1 / v2）

### 3.1 v1：`SemanticParams` + `decode_semantic` / `decode_semantic_auto`

#### 3.1.1 单区域语义恢复

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

#### 3.1.2 多区域 / 自动模式

```python
from src.semantics.decode_multi import decode_semantic_multi_region, decode_semantic_auto

# 多区域参数：使用 pos_edge/neg_edge 成对定义多个区域
params_multi = SemanticParams(
    yonghu=1,
    youwu=1,
    menxian=-80.0,
    pos_edge=[50, 470],
    neg_edge=[70, 490],
    start=0,
    end=0,
    fenbianlv=2471,
    sinr=np.array([25.0, 20.0]),
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
)

power_multi = decode_semantic_multi_region(params_multi)

# 自动模式：根据 pos_edge 数量自动选择 decode_semantic 或 multi_region
power_auto = decode_semantic_auto(params_multi)
```

#### 3.1.3 v1 评估 pipeline

```bash
python -m src.pipeline.semantic_eval \
  --reference data/stitched_30_2500.npz \
  --semantic data/demo_semantic_v1.json \
  --report data/semantic_eval_v1.json
```

> 注意：`semantic_eval` 内部已使用 `decode_file_auto`，会根据 pos_edge 判别单/多区域。

### 3.2 v2：`SemanticEncodingV2` + `decode_semantic_v2`

#### 3.2.1 直接构造 v2 结构

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

power_v2 = decode_semantic_v2(params_v2)
```

#### 3.2.2 从 JSON 文件加载并解码

```python
from src.semantics.decode_v2 import decode_file_v2

params_v2, power_v2 = decode_file_v2("data_semantic/semantic_case01.json")
```

#### 3.2.3 v2 评估 pipeline

```bash
python -m src.pipeline.semantic_eval_v2 \
  --reference data/stitched_30_2500.npz \
  --semantic data_semantic/semantic_case01.json \
  --report data/semantic_eval_v2_case01.json
```

### 3.3 自动编码（实验性）

`src/semantics/edge_detect.py` 提供了一个简化版自动编码器：

```python
from src.semantics.edge_detect import auto_encode_semantic

params_dict = auto_encode_semantic(power_db)
params_v1 = SemanticParams.from_dict(params_dict)
power_rec = decode_semantic_auto(params_v1)
```

> 这是一个“示范性编码器”，用于展示边缘检测与语义参数结构，不代表最终生产策略。

---

## 4. 最佳实践与常见场景

### 4.1 完整工作流示例

以下是一个完整的端到端工作流，涵盖三个任务：

```python
from pathlib import Path
import numpy as np

from src.signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
from src.pipeline.stitch_real_data import stitch_from_bin_directory
from src.io.reader import BinDataType
from src.signal.stitcher import StitchMode
from src.semantics.decode_v2 import decode_file_v2
from src.semantics.edge_detect import auto_encode_semantic
from src.core.schemas import SemanticParams
from src.semantics.decode_multi import decode_semantic_auto

# ========== 任务一：合成参考频谱 ==========
print("步骤 1: 生成参考频谱...")
cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=1.0,
    noise_floor_db=-80.0,
)
add_jammer(cfg, "single_tone", 450.0, 25.0)
add_jammer(cfg, "sweep", 850.0, 23.0)

rng = np.random.default_rng(42)
freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
np.savez("data/reference_spectrum.npz", freq_mhz=freq_mhz, power_db=power_db)
print(f"  ✓ 参考频谱已保存（{len(freq_mhz)} 个频点）")

# ========== 任务二：拼接真实数据（如果有）==========
if Path("data_segment").exists():
    print("\n步骤 2: 拼接真实采样数据...")
    stitched, segments = stitch_from_bin_directory(
        directory=Path("data_segment"),
        pattern="*.bin",
        bin_dtype=BinDataType.INT16,
        mode=StitchMode.MAX,
        fft_size=262144,
    )
    np.savez(
        "data/stitched_real.npz",
        freq_mhz=stitched.freq_mhz,
        power_db=stitched.power_db,
    )
    print(f"  ✓ 拼接完成（{len(segments)} 个分段）")
else:
    print("\n步骤 2: 跳过（无真实数据）")

# ========== 任务三：语义编码与恢复 ==========
print("\n步骤 3: 自动语义编码...")
params_dict = auto_encode_semantic(power_db)
params = SemanticParams.from_dict(params_dict)
print(f"  ✓ 检测到 {len(params.pos_edge)} 个干扰区域")

print("\n步骤 4: 从语义参数恢复频谱...")
power_recovered = decode_semantic_auto(params)
error = np.mean(np.abs(power_db - power_recovered))
print(f"  ✓ 恢复完成，平均误差: {error:.2f} dB")

# 保存结果
np.savez("data/recovered_spectrum.npz", freq_mhz=freq_mhz, power_db=power_recovered)
print("\n✅ 完整工作流结束！")
```

### 4.2 批量处理多个文件

```python
from pathlib import Path
from src.semantics.decode_v2 import decode_file_v2

# 批量处理多个语义参数文件
semantic_dir = Path("data_semantic")
output_dir = Path("data/batch_decoded")
output_dir.mkdir(exist_ok=True)

for json_file in semantic_dir.glob("*.json"):
    print(f"处理: {json_file.name}")
    try:
        params, power_db = decode_file_v2(json_file)
        output_file = output_dir / f"{json_file.stem}_recovered.npz"

        # 生成频率轴
        freq_mhz = np.linspace(
            params.freq_min_mhz,
            params.freq_max_mhz,
            params.num_bins
        )

        np.savez(output_file, freq_mhz=freq_mhz, power_db=power_db)
        print(f"  ✓ 已保存: {output_file.name}")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
```

### 4.3 自定义干扰合成

```python
from src.signal.spectrum_composer import SpectrumComposerConfig, JammerSpec, compose_spectrum

# 精细控制每个干扰参数
cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=0.5,  # 更高分辨率
    noise_floor_db=-100.0,  # 更低底噪
    sample_rate_hz=125e6,
    iq_length=65536,  # 更长的 IQ 序列
)

# 使用 JammerSpec 直接添加
cfg.jammers = [
    JammerSpec("noise_fm", 400.0, 20.0),
    JammerSpec("comb", 1000.0, 22.0),
    JammerSpec("partial_band_noise", 1500.0, 18.0),
]

rng = np.random.default_rng(123)  # 固定种子以重现结果
freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
```

### 4.4 频谱对比与可视化

```python
import matplotlib.pyplot as plt

# 加载参考谱和恢复谱
ref_data = np.load("data/reference_spectrum.npz")
rec_data = np.load("data/recovered_spectrum.npz")

freq_mhz = ref_data["freq_mhz"]
power_ref = ref_data["power_db"]
power_rec = rec_data["power_db"]

# 绘制对比图
fig, axes = plt.subplots(2, 1, figsize=(12, 8))

# 原始频谱
axes[0].plot(freq_mhz, power_ref, linewidth=0.8, label="参考频谱")
axes[0].set_ylabel("功率 (dB)")
axes[0].set_title("参考频谱")
axes[0].grid(True, alpha=0.3)
axes[0].legend()

# 恢复频谱 + 误差
axes[1].plot(freq_mhz, power_rec, linewidth=0.8, label="恢复频谱", color="orange")
axes[1].plot(freq_mhz, power_ref - power_rec, linewidth=0.5, label="误差", color="red", alpha=0.6)
axes[1].set_xlabel("频率 (MHz)")
axes[1].set_ylabel("功率 (dB)")
axes[1].set_title("恢复频谱与误差")
axes[1].grid(True, alpha=0.3)
axes[1].legend()

plt.tight_layout()
plt.savefig("data/comparison.png", dpi=150)
plt.show()
```

### 4.5 错误处理与调试

```python
from src.core.schemas import SemanticParams
from src.semantics.decode_multi import decode_semantic_auto

# 从 JSON 加载语义参数
import json

try:
    with open("data/semantic_params.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    params = SemanticParams.from_dict(data)

    # 验证参数
    params.validate()
    print("✓ 参数验证通过")

    # 恢复频谱
    power_db = decode_semantic_auto(params)
    print(f"✓ 恢复成功，输出长度: {len(power_db)}")

except FileNotFoundError:
    print("✗ 文件不存在")
except ValueError as e:
    print(f"✗ 参数验证失败: {e}")
except Exception as e:
    print(f"✗ 未知错误: {e}")
```

---

## 5. 常见问题

### Q1: 如何调整频谱分辨率？

A: 通过 `resolution_mhz` 参数控制：

```python
# 低分辨率（快速）
cfg = SpectrumComposerConfig(resolution_mhz=10.0)  # 10 MHz/点

# 高分辨率（精细）
cfg = SpectrumComposerConfig(resolution_mhz=0.1)   # 0.1 MHz/点
```

### Q2: 语义恢复误差过大怎么办？

A: 检查以下几点：

1. `fenbianlv`（num_bins）是否与原始频谱一致
2. 边缘索引（pos_edge/neg_edge）是否准确
3. JNR 值是否合理（通常 15-30 dB）
4. 是否使用了正确的解码版本（v1/v2）

### Q3: 如何处理大量分段文件？

A: 使用 `load_bin_segments` 批量加载：

```python
from src.io.reader import load_bin_segments, BinDataType

# 自动加载并按中心频率排序
segments = load_bin_segments(
    "data_segment",
    pattern="*.bin",
    bin_dtype=BinDataType.INT16
)
print(f"加载了 {len(segments)} 个分段")
```

### Q4: 能否导出为其他格式？

A: 当前支持 NPZ 格式，可手动转换：

```python
# NPZ → CSV
data = np.load("spectrum.npz")
import pandas as pd
df = pd.DataFrame({
    "freq_mhz": data["freq_mhz"],
    "power_db": data["power_db"]
})
df.to_csv("spectrum.csv", index=False)

# NPZ → MAT (需要 scipy)
from scipy.io import savemat
savemat("spectrum.mat", data)
```

---

## 6. 总结

- 若你希望通过 Python 脚本/Notebook 直接控制流程，优先使用：
  - `compose_spectrum`（任务一）；
  - `stitch_segments` / `stitch_from_bin_directory`（任务二）；
  - `decode_semantic` / `decode_semantic_auto` / `decode_semantic_v2` + `semantic_eval(_v2)`（任务三）。
- 若只需要命令行方式批处理，则使用 `spectrum_batch.py` 的 `compose` / `stitch` / `decode` / `decode-v2` 子命令即可。

更详细的场景说明、CLI 交互细节请参考：

- `USAGE_CLI.md` – 面向 CLI 用户的详细说明；
- `FIXES_SUMMARY.md` – 核心修复点与设计决策；
- `docs/semantic_encoding_requirements.md` – v2 语义编码规范；
- `docs/频谱语义化表征及频谱恢复.md` – 原始语义表征与恢复文档。
