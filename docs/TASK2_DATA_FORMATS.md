# 任务2数据格式说明 - 频谱分段拼接

> **文件位置**: `spectrum_cli.py` → `task2_interactive()` (line 247-323)  
> **功能**: 将多个频谱分段拼接为完整宽带频谱  
> **典型场景**: 200 MHz 分段 → 30-2500 MHz 完整频谱

---

## 📥 输入数据格式

### 1. NPZ 文件格式 (NumPy 压缩包)

#### 文件扩展名
```
.npz
```

#### 必需字段

| 字段名 | 数据类型 | 形状 | 说明 | 示例 |
|--------|---------|------|------|------|
| `freq_mhz` | `np.ndarray` (float64) | `(N,)` | 频率轴（MHz） | `[30.0, 31.0, ..., 230.0]` |
| `power_db` | `np.ndarray` (float64) | `(N,)` | 功率谱（dB） | `[-80.0, -75.2, ..., -65.5]` |

#### 可选字段

| 字段名 | 数据类型 | 说明 | 默认值 |
|--------|---------|------|--------|
| `center_freq_mhz` | `float` | 分段中心频率（MHz） | `np.mean(freq_mhz)` |
| `bandwidth_mhz` | `float` | 分段带宽（MHz） | `freq_mhz.max() - freq_mhz.min()` |

#### 其他元数据（可选）
- 所有其他键都会被加载到 `metadata` 字典中
- 可以包含任意额外信息（如采集时间、设备ID等）

---

### 2. NPZ 文件示例

#### 创建示例文件

```python
import numpy as np

# 示例1: 基本格式（仅必需字段）
freq_mhz = np.linspace(30, 230, 2001)  # 30-230 MHz, 0.1 MHz 分辨率
power_db = -80.0 + np.random.randn(2001) * 5  # 底噪 + 随机波动

np.savez(
    "segment_30_230MHz.npz",
    freq_mhz=freq_mhz,
    power_db=power_db,
)

# 示例2: 完整格式（包含可选字段）
np.savez(
    "segment_200_400MHz.npz",
    freq_mhz=np.linspace(200, 400, 2001),
    power_db=-75.0 + np.random.randn(2001) * 5,
    center_freq_mhz=300.0,
    bandwidth_mhz=200.0,
    # 额外元数据
    timestamp="2025-01-25 10:30:00",
    device_id="RX-001",
    sample_rate_hz=250e6,
)
```

#### 读取示例文件

```python
import numpy as np

# 方法1: 手动读取
data = np.load("segment_30_230MHz.npz")
freq = data["freq_mhz"]
power = data["power_db"]

# 方法2: 使用项目工具（推荐）
from src.signal.stitcher import load_segment_from_npz
segment = load_segment_from_npz("segment_30_230MHz.npz")
print(f"中心频率: {segment.center_freq_mhz} MHz")
print(f"带宽: {segment.bandwidth_mhz} MHz")
```

---

### 3. 输入约束与验证

#### ✅ 合法条件

1. **频率轴单调递增**
   ```python
   assert np.all(np.diff(freq_mhz) > 0), "频率轴必须单调递增"
   ```

2. **数组长度匹配**
   ```python
   assert freq_mhz.shape == power_db.shape, "频率轴和功率谱长度必须相等"
   ```

3. **频率步长一致**
   - 所有分段的频率分辨率应相同（允许 0.1% 误差）
   - 系统会自动检查并报错

4. **分段数量要求**
   ```python
   assert len(segments) >= 2, "至少需要2个分段才能拼接"
   ```

#### ❌ 常见错误

| 错误类型 | 原因 | 解决方法 |
|---------|------|---------|
| `KeyError: 'freq_mhz'` | NPZ 文件缺少必需字段 | 检查文件是否包含 `freq_mhz` 和 `power_db` |
| `ValueError: 分段频率步长不一致` | 不同分段的分辨率不同 | 统一所有分段的频率分辨率 |
| `FileNotFoundError` | 文件路径错误 | 检查文件路径和文件名 |
| `ValueError: 至少需要2个分段` | 只加载了1个分段 | 加载至少2个分段 |

---

## 📤 输出数据格式

### 1. NPZ 文件（拼接结果）

#### 默认输出路径
```
data/cli_results/stitched_spectrum.npz
```

#### 输出字段

| 字段名 | 数据类型 | 形状 | 说明 | 示例值范围 |
|--------|---------|------|------|-----------|
| `freq_mhz` | `np.ndarray` (float64) | `(M,)` | 拼接后的频率轴（MHz） | `[30.0, ..., 2500.0]` |
| `power_db` | `np.ndarray` (float64) | `(M,)` | 拼接后的功率谱（dB） | `[-180.0, ..., -40.0]` |
| `coverage_map` | `np.ndarray` (int) | `(M,)` | 每个频点的覆盖次数 | `[0, 1, 2, 3, ...]` |

#### 读取拼接结果

```python
import numpy as np

# 加载拼接结果
result = np.load("data/cli_results/stitched_spectrum.npz")

freq_mhz = result["freq_mhz"]
power_db = result["power_db"]
coverage_map = result["coverage_map"]

print(f"频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
print(f"频点数: {len(freq_mhz)}")
print(f"最大覆盖: {coverage_map.max()} 段")
print(f"未覆盖点数: {np.sum(coverage_map == 0)}")
```

---

### 2. PNG 文件（频谱图，可选）

#### 默认输出路径
```
data/cli_results/stitched_spectrum.png
```

#### 图像参数
- **分辨率**: 150 DPI
- **尺寸**: 10×4 英寸（1500×600 像素）
- **X轴**: 频率（MHz）
- **Y轴**: 功率（dB）
- **标题**: `Stitched Spectrum (模式名)`

#### 示例图像说明
```
标题: Stitched Spectrum (MAX)
├─ X轴: 30 - 2500 MHz
├─ Y轴: -180 - -40 dB
└─ 曲线: 蓝色实线，线宽 0.8
```

---

### 3. 覆盖图（Coverage Map）详解

#### 含义
`coverage_map[i]` 表示第 `i` 个频点被多少个分段覆盖

#### 典型值

| 覆盖次数 | 含义 | 频谱质量 |
|---------|------|---------|
| 0 | 未被任何分段覆盖 | ❌ 使用填充值（默认 -180 dB） |
| 1 | 仅被1个分段覆盖 | ⚠️ 无冗余，可能受单次采集误差影响 |
| 2 | 被2个分段覆盖（重叠区） | ✅ 正常，拼接平滑 |
| 3+ | 被3个以上分段覆盖 | ✅✅ 高冗余，数据可靠 |

#### 可视化覆盖图

```python
import matplotlib.pyplot as plt

# 绘制覆盖图
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

# 功率谱
ax1.plot(freq_mhz, power_db, linewidth=0.8)
ax1.set_ylabel("Power (dB)")
ax1.grid(True, alpha=0.5)

# 覆盖图
ax2.fill_between(freq_mhz, 0, coverage_map, alpha=0.7)
ax2.set_xlabel("Frequency (MHz)")
ax2.set_ylabel("Coverage")
ax2.grid(True, alpha=0.5)

plt.tight_layout()
plt.savefig("coverage_analysis.png", dpi=150)
```

---

## ⚙️ 拼接模式说明

任务2支持 **3 种拼接模式**，用于处理频谱重叠区域：

### 模式 1: MAX（最大值）

**代码**: `StitchMode.MAX`

**算法**:
```python
# 伪代码
for each 频点:
    if 有多个分段覆盖:
        power[频点] = max(各分段功率)
```

**适用场景**:
- ✅ 干扰信号检测（保留最强信号）
- ✅ 峰值功率分析
- ❌ 不适合噪声抑制

**示例**:
```
频点 1000:
  分段A: -70 dB
  分段B: -65 dB
  拼接结果: -65 dB  ← 取最大值
```

---

### 模式 2: MEAN（简单平均）

**代码**: `StitchMode.MEAN`

**算法**:
```python
# 伪代码
for each 频点:
    if 有多个分段覆盖:
        power_linear = mean([10^(p/10) for p in 各分段功率])  # 线性域平均
        power[频点] = 10 * log10(power_linear)  # 转回 dB
```

**适用场景**:
- ✅ 降低随机噪声
- ✅ 平滑拼接边界
- ❌ 可能削弱真实干扰信号

**注意**:
- ⚠️ **必须在线性域平均**，不能直接对 dB 值求平均
- 错误: `mean([-70, -60]) = -65 dB` ❌
- 正确: `10*log10(mean([1e-7, 1e-6])) ≈ -63.46 dB` ✅

---

### 模式 3: WEIGHTED_MEAN（加权平均）

**代码**: `StitchMode.WEIGHTED_MEAN`

**算法**:
```python
# 伪代码
for each 频点:
    weights = [exp(-2 * (距离中心/半带宽)^2) for 各分段]  # 高斯权重
    power_linear = sum(w * 10^(p/10) for w, p in zip(weights, 各分段功率)) / sum(weights)
    power[频点] = 10 * log10(power_linear)
```

**权重分布**:
- 分段中心频率附近：权重 ≈ 1.0（完全信任）
- 分段边缘频率：权重 ≈ 0.14（部分信任）

**适用场景**:
- ✅ 边缘频谱质量较差时（如滤波器滚降）
- ✅ 最平滑的拼接效果
- ✅ 综合考虑信号强度和采集质量

**示例**:
```
频点 200 MHz:
  分段A（中心 130 MHz）: -70 dB, 权重 0.2
  分段B（中心 200 MHz）: -65 dB, 权重 1.0
  拼接结果: ≈ -65.5 dB  ← 更偏向分段B
```

---

## 📊 完整工作流程示例

### 场景: 拼接 30-2500 MHz 频谱（13 个 200 MHz 分段）

#### 步骤 1: 准备输入数据

```bash
data/segments/
├── seg_0_30_230MHz.npz      # 30-230 MHz
├── seg_1_200_400MHz.npz     # 200-400 MHz
├── seg_2_380_580MHz.npz     # 380-580 MHz
├── ...
└── seg_12_2300_2500MHz.npz  # 2300-2500 MHz
```

#### 步骤 2: 运行交互式CLI

```bash
python spectrum_cli.py

# 选择任务2
> 2

# 逐个加载分段
加载分段? (y/n) [默认: n]: y
npz 文件路径: data/segments/seg_0_30_230MHz.npz
✓ 已加载: 130.0 MHz, 200.0 MHz 带宽

加载分段? (y/n) [默认: n]: y
npz 文件路径: data/segments/seg_1_200_400MHz.npz
✓ 已加载: 300.0 MHz, 200.0 MHz 带宽

... (继续加载其他11个分段)

# 选择拼接模式
选择模式 (1/2/3) [默认: 1]: 1  # MAX模式

# 设置填充值
未覆盖区域填充值 (dB) [默认: -180.0]: -180

# 执行拼接
✓ 拼接成功
  频段: 30.00 - 2500.00 MHz
  频点数: 24701
  最大覆盖: 2 段

# 保存结果
保存结果? (y/n) [默认: y]: y
输出目录 [默认: data/cli_results]: data/results
✓ 已保存: data/results/stitched_spectrum.npz
✓ 频谱图已保存: data/results/stitched_spectrum.png
```

#### 步骤 3: 验证结果

```python
import numpy as np
import matplotlib.pyplot as plt

# 加载结果
result = np.load("data/results/stitched_spectrum.npz")
freq = result["freq_mhz"]
power = result["power_db"]
coverage = result["coverage_map"]

# 统计信息
print(f"频率范围: {freq.min():.2f} - {freq.max():.2f} MHz")
print(f"频率分辨率: {np.mean(np.diff(freq)):.4f} MHz")
print(f"功率范围: {power.min():.2f} - {power.max():.2f} dB")
print(f"平均覆盖: {coverage.mean():.2f} 段")
print(f"未覆盖点数: {np.sum(coverage == 0)} ({100*np.sum(coverage==0)/len(coverage):.2f}%)")

# 检查拼接边界
overlap_regions = np.where(coverage >= 2)[0]
print(f"重叠区域: {len(overlap_regions)} 个频点")
```

---

## 🔧 高级用法

### 1. 编程式拼接（不使用 CLI）

```python
from pathlib import Path
from src.signal.stitcher import load_segment_from_npz, stitch_segments, StitchMode

# 批量加载分段
segment_files = sorted(Path("data/segments").glob("seg_*.npz"))
segments = [load_segment_from_npz(f) for f in segment_files]

# 执行拼接
result = stitch_segments(
    segments=segments,
    mode=StitchMode.WEIGHTED_MEAN,  # 使用加权平均
    fill_value=-180.0,
)

# 保存结果
import numpy as np
np.savez(
    "output/stitched.npz",
    freq_mhz=result.freq_mhz,
    power_db=result.power_db,
    coverage_map=result.coverage_map,
)
```

---

### 2. 从 IQ 数据直接拼接

```python
from src.io.reader import load_iq_file
from src.signal.stitcher import stitch_from_iq_data
from src.core.schemas import SamplingConfig

# 加载 IQ 数据
iq_files = ["iq_130MHz.bin", "iq_300MHz.bin", "iq_500MHz.bin"]
iq_list = [load_iq_file(f, bin_dtype="int16") for f in iq_files]

# 配置采样参数
configs = [
    SamplingConfig(sample_rate_hz=250e6, center_freq_hz=130e6, fft_size=4096),
    SamplingConfig(sample_rate_hz=250e6, center_freq_hz=300e6, fft_size=4096),
    SamplingConfig(sample_rate_hz=250e6, center_freq_hz=500e6, fft_size=4096),
]

# 直接拼接（自动计算功率谱）
result = stitch_from_iq_data(
    iq_data_list=iq_list,
    configs=configs,
    mode=StitchMode.MAX,
    window="hann",
)
```

---

### 3. 批量拼接多个数据集

```python
import numpy as np
from pathlib import Path
from src.signal.stitcher import stitch_from_npz_files, StitchMode

# 场景：处理多个时间点的数据
timestamps = ["20250125_1000", "20250125_1100", "20250125_1200"]

for ts in timestamps:
    segment_dir = Path(f"data/{ts}/segments")
    segment_files = sorted(segment_dir.glob("*.npz"))
    
    result = stitch_from_npz_files(
        file_paths=segment_files,
        mode=StitchMode.MAX,
    )
    
    # 保存时间戳结果
    np.savez(
        f"output/stitched_{ts}.npz",
        freq_mhz=result.freq_mhz,
        power_db=result.power_db,
        coverage_map=result.coverage_map,
        timestamp=ts,
    )
```

---

## ⚠️ 常见问题与解决方案

### 问题 1: 拼接后出现明显断层

**症状**:
```
功率谱在 400 MHz 附近突然跳变 10 dB
```

**原因**:
- 不同分段的底噪基准不一致
- 采集增益设置不同

**解决方法**:
```python
# 方法1: 预处理时归一化底噪
for seg in segments:
    noise_floor = np.median(seg.power_db)  # 估计底噪
    seg.power_db -= noise_floor  # 归一化
    seg.power_db += target_noise_floor  # 统一到目标底噪

# 方法2: 使用 WEIGHTED_MEAN 模式平滑过渡
result = stitch_segments(segments, mode=StitchMode.WEIGHTED_MEAN)
```

---

### 问题 2: 覆盖图显示大片空白

**症状**:
```
coverage_map 中有连续的 0 值区域
```

**原因**:
- 分段频率范围不连续（有间隙）
- 分段加载顺序错误

**解决方法**:
```python
# 检查频率覆盖
for i, seg in enumerate(segments):
    print(f"分段 {i}: {seg.freq_mhz.min():.1f} - {seg.freq_mhz.max():.1f} MHz")

# 找出间隙
sorted_segs = sorted(segments, key=lambda s: s.center_freq_mhz)
for i in range(len(sorted_segs) - 1):
    gap = sorted_segs[i+1].freq_mhz.min() - sorted_segs[i].freq_mhz.max()
    if gap > 1.0:  # 间隙大于 1 MHz
        print(f"⚠️ 间隙检测: {gap:.1f} MHz 在 {sorted_segs[i].center_freq_mhz} MHz 附近")
```

---

### 问题 3: 内存不足（处理超大数据）

**症状**:
```
MemoryError: Unable to allocate array
```

**原因**:
- 频率分辨率过高（如 0.001 MHz → 2,470,000 个频点）
- 同时加载过多分段

**解决方法**:
```python
# 方法1: 降低频率分辨率
# 在生成分段时使用更大的分辨率（如 0.1 MHz 而非 0.01 MHz）

# 方法2: 分块拼接
def stitch_in_chunks(segments, chunk_size=5):
    results = []
    for i in range(0, len(segments), chunk_size):
        chunk = segments[i:i+chunk_size]
        result = stitch_segments(chunk, mode=StitchMode.MAX)
        results.append(result)
    
    # 将块结果再次拼接
    return stitch_segments(results, mode=StitchMode.MAX)
```

---

## 📚 相关文档

- [频谱拼接原理说明](./STITCHING_THEORY.md)
- [NPZ 文件格式规范](./NPZ_FORMAT_SPEC.md)
- [完整 API 参考](./API_REFERENCE.md)
- [代码审查报告](./CODE_REVIEW_REPORT.md)

---

## 🔗 代码位置索引

| 功能 | 文件 | 行号 |
|------|------|------|
| **任务2主函数** | `spectrum_cli.py` | 247-323 |
| **拼接核心逻辑** | `src/signal/stitcher.py` | 112-245 |
| **NPZ加载函数** | `src/signal/stitcher.py` | 285-309 |
| **拼接模式枚举** | `src/signal/stitcher.py` | 22-29 |
| **数据结构定义** | `src/signal/stitcher.py` | 33-65 |

---

**文档版本**: 1.0  
**最后更新**: 2025-01-25  
**维护者**: Electromagnetic State Project Team
