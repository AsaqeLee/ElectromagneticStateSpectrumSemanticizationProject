# 频谱语义最小信息集分析

## 当前方案问题诊断

### 当前 SemanticParams 结构（11个字段）

```python
yonghu: int              # 用户ID
youwu: int               # 是否有干扰 0/1
menxian: float           # 底噪功率 dB
pos_edge: List[int]      # 正边缘索引
neg_edge: List[int]      # 负边缘索引
start: int               # 干扰起始索引
end: int                 # 干扰结束索引
fenbianlv: int           # 频谱点数
sinr: np.ndarray         # 信噪比 dB
freq_min_mhz: float      # 频率下限
freq_max_mhz: float      # 频率上限
```

### decode_semantic 实际使用的字段

```python
def decode_semantic(params):
    # 1. 创建底噪
    power_db = np.full(params.fenbianlv, params.menxian)  # ✓ fenbianlv, menxian

    # 2. 填充干扰区域
    power_db[params.start : params.end + 1] += params.sinr  # ✓ start, end, sinr

    # 3. 边缘增强（可选）
    _apply_edges(power_db, params.pos_edge, params.neg_edge, ...)  # ⚠️ 可选

    # freq_min/max 用于上层构造频率轴（✓ 必需）
```

---

## 冗余信息分析

### 1. **yonghu (用户ID)** - ❌ 完全冗余
- **使用次数**: 0
- **判断**: 业务标识，与频谱恢复无关

### 2. **youwu (是否有干扰)** - ❌ 冗余
- **使用次数**: 0
- **可推断**: `start != end` 或 `sinr != 0` 即表示有干扰
- **判断**: 可以从其他字段推断，不需要单独存储

### 3. **pos_edge / neg_edge** - ⚠️ 重复信息
- **实际含义**:
  - `pos_edge = [start]`  # 干扰上升沿
  - `neg_edge = [end]`    # 干扰下降沿
- **当前用途**: 边缘增强（`_apply_edges` 在边缘加减3-5dB）
- **问题**:
  1. 这是 start/end 的重复表示
  2. 边缘增强是人为美化，不是物理真实
  3. 真实频谱在边缘处不会有这种凸起/凹陷
- **判断**: 如果只做边缘美化，可以直接用 start/end 计算，不需要单独存储

### 4. **sinr vs 绝对功率** - ⚠️ 编码方式问题
- **当前**: `sinr` = 相对底噪的增益（dB）
- **恢复**: `jammer_power = menxian + sinr`
- **问题**: 增加了一次加法计算
- **替代**: 直接存储干扰的绝对功率 `jammer_power_db`
- **判断**: 看业务需求，如果经常需要知道 JNR，保留 sinr；否则用绝对功率更直接

---

## 最小必要信息集

### 方案 A: 最简版本（单干扰区域）

```python
{
    # 频率轴定义
    "freq_min_mhz": 30.0,
    "freq_max_mhz": 2500.0,
    "num_bins": 2471,

    # 底噪功率
    "noise_floor_db": -80.0,

    # 干扰区域（如果没有干扰，start=end=0, power=noise）
    "jammer_start_bin": 470,
    "jammer_end_bin": 1470,
    "jammer_power_db": -60.0,  # 绝对功率，或者用 jammer_jnr_db = 20.0
}
```

**字段数**: 7个（相比当前11个，减少36%）

### 方案 B: 支持多干扰区域

```python
{
    # 频率轴定义
    "freq_min_mhz": 30.0,
    "freq_max_mhz": 2500.0,
    "num_bins": 2471,

    # 底噪功率
    "noise_floor_db": -80.0,

    # 干扰区域列表
    "jammers": [
        {"start_bin": 470, "end_bin": 1470, "power_db": -60.0},
        {"start_bin": 2000, "end_bin": 2200, "power_db": -55.0},
    ]
}
```

**字段数**: 4个全局 + N×3个干扰区域

### 方案 C: 保留相对编码（JNR）

如果业务上需要明确知道信噪比：

```python
{
    "freq_min_mhz": 30.0,
    "freq_max_mhz": 2500.0,
    "num_bins": 2471,
    "noise_floor_db": -80.0,

    "jammers": [
        {"start_bin": 470, "end_bin": 1470, "jnr_db": 20.0},  # 相对编码
    ]
}
```

恢复时：`power = noise + jnr`

---

## 恢复算法对比

### 当前实现（复杂）

```python
def decode_semantic(params: SemanticParams) -> np.ndarray:
    params.validate()  # 11个字段的校验
    power_db = np.full(params.fenbianlv, params.menxian, dtype=float)
    segment_len = params.end - params.start + 1
    if params.sinr.size == 1:
        boost = float(params.sinr.item())
        power_db[params.start : params.end + 1] += boost
        edge_delta = abs(boost)
    else:
        boost = params.sinr[:segment_len]
        power_db[params.start : params.end + 1] += boost
        edge_delta = float(np.max(np.abs(boost)))
    _apply_edges(power_db, params.pos_edge, params.neg_edge, edge_delta)
    return power_db
```

**问题**:
- 16行代码
- 处理 sinr 的两种情况（标量/数组）
- 边缘增强逻辑
- 大量字段访问

### 最简实现（清晰）

```python
def decode_minimal(semantic: dict) -> np.ndarray:
    """从最简语义恢复频谱"""
    # 初始化为底噪
    power = np.full(semantic["num_bins"], semantic["noise_floor_db"])

    # 填充干扰区域
    for jammer in semantic.get("jammers", []):
        start, end = jammer["start_bin"], jammer["end_bin"]
        power[start:end+1] = jammer["power_db"]  # 或 noise + jammer["jnr_db"]

    return power
```

**改进**:
- **6行代码**（减少62%）
- 无特殊情况处理
- 逻辑直接清晰
- 自然支持多干扰区域

---

## 核心洞察

### 1. 频谱的数据结构本质

**频谱 = 分段常数函数**

```
power(freq) = {
    noise_floor,          if freq in background
    jammer_power,         if freq in jammer_region
}
```

这就是**游程编码（Run-Length Encoding）**的自然场景。

### 2. "好品味"的数据结构

> "Bad programmers worry about the code. Good programmers worry about data structures and their relationships."

当前设计的问题：
- **信息重复**: pos_edge/neg_edge = [start]/[end]
- **特殊情况**: sinr 要处理标量/数组两种情况
- **人为复杂**: 边缘增强不是物理本质

好的设计：
- **消除冗余**: 每个信息只存储一次
- **无特殊情况**: 单干扰和多干扰用同一结构
- **反映本质**: 频谱 = 底噪 + 干扰区域列表

### 3. 压缩率

假设 2471 个频点：
- **原始数据**: 2471 × 8 bytes = 19,768 bytes
- **当前语义**: ~200 bytes（11个字段 + 元数据）
- **最简语义**: ~80 bytes（4个全局 + 1个干扰区域）
- **压缩率**: 原始数据的 0.4%

---

## 建议

### 立即可做（向后兼容）

1. **标记冗余字段**:
   - `yonghu` → 移到外层元数据
   - `youwu` → 改为计算属性：`has_jammer = (start != end)`

2. **简化边缘处理**:
   - 如果 `pos_edge` 为空，自动设为 `[start]`
   - 如果 `neg_edge` 为空，自动设为 `[end]`

### 重构方案（破坏性）

设计新的 `MinimalSemanticParams`:

```python
@dataclass
class JammerRegion:
    start_bin: int
    end_bin: int
    jnr_db: float  # 相对底噪的信噪比

@dataclass
class MinimalSemanticParams:
    # 频率轴
    freq_min_mhz: float
    freq_max_mhz: float
    num_bins: int

    # 底噪
    noise_floor_db: float

    # 干扰列表
    jammers: List[JammerRegion]

    def to_spectrum(self) -> np.ndarray:
        """直接恢复频谱"""
        power = np.full(self.num_bins, self.noise_floor_db)
        for jam in self.jammers:
            power[jam.start_bin:jam.end_bin+1] = self.noise_floor_db + jam.jnr_db
        return power
```

**优势**:
- 7个字段 → 5个字段（单干扰）
- 代码量减少 60%
- 逻辑清晰，无特殊情况
- 自然支持多干扰

---

## 结论

**真正必需的信息**:

1. **频率轴定义** (3个): `freq_min`, `freq_max`, `num_bins`
2. **底噪功率** (1个): `noise_floor_db`
3. **干扰区域** (每个3个): `start_bin`, `end_bin`, `jnr_db`

**总计**: 最少 **7个字段**（单干扰），或 **4 + 3N 个字段**（N个干扰）

**可以删除的**:
- `yonghu` (用户ID) - 移到外层
- `youwu` (是否有干扰) - 可推断
- `pos_edge` / `neg_edge` - 就是 `[start]` / `[end]`，信息重复

**简化收益**:
- 字段数减少 36%
- 代码复杂度减少 60%
- 消除所有特殊情况处理
- 自然支持多干扰区域
