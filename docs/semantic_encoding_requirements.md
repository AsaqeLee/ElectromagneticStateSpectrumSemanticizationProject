# 频谱语义编码器接口需求规范 v2.0

## 文档目的

本文档定义**解码器**（我方）对**编码器**（对方）的接口要求。
编码器需要从原始频谱中提取以下信息，以便解码器能够无损或近似恢复频谱。

---

## 1. 核心需求：最小必要信息集

频谱恢复的本质是重建一个**分段常数函数**：

```
power(freq) = {
    noise_floor_db,                    当 freq 在空白区域
    noise_floor_db + jnr_db[i],        当 freq 在第 i 个干扰区域
}
```

因此，编码器需要提取：

### 1.1 全局参数（4 个字段 - 使用项目默认值）

| 字段名           | 类型  | 说明            | 默认值 |
| ---------------- | ----- | --------------- | ------ |
| `freq_min_mhz`   | float | 频谱下限（MHz） | 30.0   |
| `freq_max_mhz`   | float | 频谱上限（MHz） | 2500.0 |
| `num_bins`       | int   | 频谱离散点数量  | 2471   |
| `noise_floor_db` | float | 底噪功率（dB）  | -60.0  |

**说明**：

- 这些是项目的标准配置，对应 `DEFAULT_SEMANTIC_*` 常量
- 频率分辨率：(2500 - 30) / (2471 - 1) = **1.0 MHz**
- 编码器应使用这些默认值以保证兼容性

### 1.2 干扰区域列表（每个区域 3 个字段）

每个干扰区域定义为一个字典：

| 字段名      | 类型  | 说明                         | 示例 |
| ----------- | ----- | ---------------------------- | ---- |
| `start_bin` | int   | 干扰起始索引（0-based）      | 50   |
| `end_bin`   | int   | 干扰结束索引（包含）         | 90   |
| `jnr_db`    | float | 信噪比（相对底噪的增益，dB） | 25.0 |

**注意**：

- 如果频谱中有 N 个不连续的干扰区域，需要提取 N 个这样的字典
- 区域之间可以不连续（例如：80-120 MHz, 500-520 MHz）
- 区域之间的空白部分自动填充为 `noise_floor_db`

---

## 2. 数据格式规范

### 2.1 JSON Schema

```json
{
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0,
  "num_bins": 2471,
  "noise_floor_db": -60.0,
  "jammer_regions": [
    {
      "start_bin": 50,
      "end_bin": 90,
      "jnr_db": 25.0
    },
    {
      "start_bin": 470,
      "end_bin": 490,
      "jnr_db": 20.0
    }
  ]
}
```

### 2.2 字段约束

#### 全局参数约束

- `freq_max_mhz > freq_min_mhz`
- `num_bins >= 2`
- `noise_floor_db` 范围：典型值在 [-100, -20] dB（取决于环境）

#### 干扰区域约束

- `0 <= start_bin < end_bin < num_bins`
- `jnr_db > 0`（干扰功率必须高于底噪）
- 区域之间**不能重叠**：`regions[i].end_bin < regions[i+1].start_bin`
- 区域按 `start_bin` **升序排列**

---

## 3. 示例数据

### 示例 1：单个连续干扰区域

**场景**：500-1500 MHz 有一个宽带干扰，JNR = 20 dB

```json
{
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0,
  "num_bins": 2471,
  "noise_floor_db": -60.0,
  "jammer_regions": [
    {
      "start_bin": 470,
      "end_bin": 1470,
      "jnr_db": 20.0
    }
  ]
}
```

**恢复结果**：

- 30-500 MHz: -60 dB（底噪）
- 500-1500 MHz: -40 dB（底噪 + JNR = -60 + 20）
- 1500-2500 MHz: -60 dB（底噪）

---

### 示例 2：多个不连续干扰区域

**场景**：5 个分散的干扰信号

```json
{
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0,
  "num_bins": 2471,
  "noise_floor_db": -60.0,
  "jammer_regions": [
    {
      "start_bin": 50,
      "end_bin": 90,
      "jnr_db": 25.0,
      "comment": "80-81 MHz, 单音干扰"
    },
    {
      "start_bin": 470,
      "end_bin": 490,
      "jnr_db": 20.0,
      "comment": "500-520 MHz, 窄带噪声"
    },
    {
      "start_bin": 570,
      "end_bin": 690,
      "jnr_db": 22.0,
      "comment": "600-720 MHz, 调频干扰"
    },
    {
      "start_bin": 1470,
      "end_bin": 1770,
      "jnr_db": 18.0,
      "comment": "1500-1800 MHz, 梳状干扰"
    },
    {
      "start_bin": 2170,
      "end_bin": 2270,
      "jnr_db": 15.0,
      "comment": "2200-2300 MHz, 部分带噪声"
    }
  ]
}
```

**恢复结果**：

- 干扰区域：5 个独立的台阶
- 空白区域（约 76%）：保持底噪 -60 dB
- 干扰区域（约 24%）：功率范围 -45 dB 到 -35 dB

---

### 示例 3：无干扰场景

**场景**：纯底噪频谱

```json
{
  "freq_min_mhz": 30.0,
  "freq_max_mhz": 2500.0,
  "num_bins": 2471,
  "noise_floor_db": -60.0,
  "jammer_regions": []
}
```

**恢复结果**：

- 整个 30-2500 MHz 均为 -60 dB

---

## 4. bin 索引与频率的转换关系

编码器需要理解 bin 索引与实际频率的对应关系：

### 4.1 频率 → bin 索引

```python
def freq_to_bin(freq_mhz: float, freq_min: float, freq_max: float, num_bins: int) -> int:
    """将频率（MHz）转换为 bin 索引"""
    resolution = (freq_max - freq_min) / (num_bins - 1)
    bin_index = int(round((freq_mhz - freq_min) / resolution))
    return bin_index
```

**示例**：

- 频率范围：30-2500 MHz
- 点数：2471
- 分辨率：(2500 - 30) / (2471 - 1) ≈ 1.0 MHz

| 频率（MHz） | bin 索引 | 计算                     |
| ----------- | -------- | ------------------------ |
| 30.0        | 0        | (30 - 30) / 1.0 = 0      |
| 80.0        | 50       | (80 - 30) / 1.0 = 50     |
| 500.0       | 470      | (500 - 30) / 1.0 = 470   |
| 2500.0      | 2470     | (2500 - 30) / 1.0 = 2470 |

### 4.2 bin 索引 → 频率

```python
def bin_to_freq(bin_index: int, freq_min: float, freq_max: float, num_bins: int) -> float:
    """将 bin 索引转换为频率（MHz）"""
    resolution = (freq_max - freq_min) / (num_bins - 1)
    freq_mhz = freq_min + bin_index * resolution
    return freq_mhz
```

---

## 5. 编码器需要实现的算法

编码器的核心任务是**信号检测与区域分割**：

### 5.1 推荐算法流程

```python
def encode_spectrum(freq_mhz: np.ndarray, power_db: np.ndarray) -> dict:
    """
    从原始频谱提取语义参数

    输入:
        freq_mhz: 频率轴（MHz），一维数组
        power_db: 功率谱（dB），一维数组

    输出:
        语义参数字典
    """
    # 1. 估计底噪（例如：10th percentile）
    noise_floor_db = np.percentile(power_db, 10)

    # 2. 设定检测门限（例如：底噪 + 6dB）
    threshold_db = noise_floor_db + 6.0

    # 3. 二值化：检测哪些 bin 超过门限
    is_jammer = power_db > threshold_db

    # 4. 连通域分析：找出连续的干扰区域
    regions = find_contiguous_regions(is_jammer)

    # 5. 提取每个区域的参数
    jammer_regions = []
    for start_bin, end_bin in regions:
        # 计算该区域的平均功率
        region_power = power_db[start_bin:end_bin+1].mean()
        jnr_db = region_power - noise_floor_db

        jammer_regions.append({
            "start_bin": int(start_bin),
            "end_bin": int(end_bin),
            "jnr_db": float(jnr_db)
        })

    # 6. 构造输出
    return {
        "freq_min_mhz": float(freq_mhz[0]),
        "freq_max_mhz": float(freq_mhz[-1]),
        "num_bins": len(freq_mhz),
        "noise_floor_db": float(noise_floor_db),
        "jammer_regions": jammer_regions
    }
```

### 5.2 关键参数

编码器需要调整的参数：

| 参数         | 说明                       | 推荐值          |
| ------------ | -------------------------- | --------------- |
| 底噪估计方法 | 如何从频谱估计底噪         | 10th percentile |
| 检测门限     | 超过此值认为是干扰         | 底噪 + 6 dB     |
| 最小区域宽度 | 忽略小于此宽度的区域       | 5 个 bin        |
| 区域合并距离 | 相邻区域距离小于此值则合并 | 3 个 bin        |

---

## 6. 质量评估

### 6.1 编码质量指标

解码器将通过以下指标评估编码质量：

```python
def evaluate_encoding_quality(original_power: np.ndarray,
                               recovered_power: np.ndarray) -> dict:
    """评估编码-解码的质量"""

    # 1. 平均绝对误差（MAE）
    mae = np.mean(np.abs(original_power - recovered_power))

    # 2. 最大误差
    max_error = np.max(np.abs(original_power - recovered_power))

    # 3. 均方根误差（RMSE）
    rmse = np.sqrt(np.mean((original_power - recovered_power) ** 2))

    # 4. 压缩率
    original_size = original_power.nbytes
    encoded_size = estimate_json_size(semantic_params)
    compression_ratio = original_size / encoded_size

    return {
        "mae_db": mae,
        "max_error_db": max_error,
        "rmse_db": rmse,
        "compression_ratio": compression_ratio
    }
```

### 6.2 质量要求

| 指标      | 目标值 | 说明             |
| --------- | ------ | ---------------- |
| MAE       | < 2 dB | 平均误差小于 2dB |
| Max Error | < 5 dB | 最大误差小于 5dB |
| 压缩率    | > 50:1 | 至少压缩 50 倍   |

---

## 7. 特殊情况处理

### 7.1 无干扰场景

如果整个频谱都是底噪：

```json
{
  "noise_floor_db": -60.0,
  "jammer_regions": []
}
```

### 7.2 满频段干扰

如果整个频段都是干扰：

```json
{
  "noise_floor_db": -60.0,
  "jammer_regions": [{ "start_bin": 0, "end_bin": 2470, "jnr_db": 30.0 }]
}
```

### 7.3 功率渐变区域

对于功率逐渐变化的区域（例如扫频干扰），有两种处理方式：

**方式 1：分段近似**（推荐）

```json
{
  "jammer_regions": [
    { "start_bin": 100, "end_bin": 199, "jnr_db": 20.0 },
    { "start_bin": 200, "end_bin": 299, "jnr_db": 25.0 },
    { "start_bin": 300, "end_bin": 399, "jnr_db": 30.0 }
  ]
}
```

**方式 2：取平均值**（简化）

```json
{
  "jammer_regions": [{ "start_bin": 100, "end_bin": 399, "jnr_db": 25.0 }]
}
```

---

## 8. 接口验证

### 8.1 编码器输出验证

编码器团队需要确保输出满足以下条件：

```python
def validate_semantic_params(params: dict) -> bool:
    """验证语义参数的合法性"""

    # 1. 必需字段检查
    required_fields = ["freq_min_mhz", "freq_max_mhz", "num_bins",
                       "noise_floor_db", "jammer_regions"]
    for field in required_fields:
        if field not in params:
            raise ValueError(f"缺少必需字段: {field}")

    # 2. 频率范围检查
    if params["freq_max_mhz"] <= params["freq_min_mhz"]:
        raise ValueError("freq_max_mhz 必须大于 freq_min_mhz")

    # 3. bin 数量检查
    if params["num_bins"] < 2:
        raise ValueError("num_bins 必须 >= 2")

    # 4. 区域有效性检查
    regions = params["jammer_regions"]
    for i, region in enumerate(regions):
        # 字段完整性
        if not all(k in region for k in ["start_bin", "end_bin", "jnr_db"]):
            raise ValueError(f"区域 {i} 缺少必需字段")

        # 边界检查
        if not (0 <= region["start_bin"] < region["end_bin"] < params["num_bins"]):
            raise ValueError(f"区域 {i} 边界非法")

        # JNR 正值检查
        if region["jnr_db"] <= 0:
            raise ValueError(f"区域 {i} 的 jnr_db 必须 > 0")

    # 5. 区域排序与重叠检查
    for i in range(len(regions) - 1):
        if regions[i]["end_bin"] >= regions[i+1]["start_bin"]:
            raise ValueError(f"区域 {i} 和 {i+1} 重叠或未排序")

    return True
```

### 8.2 端到端测试

编码器团队应提供测试用例：

```python
# 生成测试频谱
freq_mhz = np.linspace(30, 2500, 2471)
power_db = generate_test_spectrum()

# 编码
semantic_params = encoder.encode(freq_mhz, power_db)

# 验证格式
validate_semantic_params(semantic_params)

# 解码
recovered_power = decoder.decode(semantic_params)

# 评估质量
quality = evaluate_encoding_quality(power_db, recovered_power)
print(f"MAE: {quality['mae_db']:.2f} dB")
print(f"Max Error: {quality['max_error_db']:.2f} dB")
print(f"Compression: {quality['compression_ratio']:.1f}:1")
```

---

## 9. 总结

### 9.1 编码器需要提供的输出

**4 个全局字段**：

1. `freq_min_mhz` - 频率下限
2. `freq_max_mhz` - 频率上限
3. `num_bins` - 点数
4. `noise_floor_db` - 底噪

**N 个区域，每个 3 个字段**：

1. `start_bin` - 起始索引
2. `end_bin` - 结束索引
3. `jnr_db` - 信噪比

**总计**：4 + 3N 个字段

### 9.2 解码器恢复算法

```python
power = np.full(num_bins, noise_floor_db)
for region in jammer_regions:
    power[region["start_bin"]:region["end_bin"]+1] = \
        noise_floor_db + region["jnr_db"]
```

**6 行代码，O(N)复杂度。**

### 9.3 关键优势

1. **简洁**：最少字段，无冗余
2. **通用**：支持任意数量的不连续区域
3. **高效**：解码算法极其简单
4. **可扩展**：未来可在区域字典内添加更多属性（如调制类型、带宽等）

---

## 10. 联系方式与反馈

如有疑问，请提供：

1. 具体的测试用例（频谱数据）
2. 编码器输出的 JSON
3. 遇到的问题描述

我们将验证接口兼容性并提供反馈。
