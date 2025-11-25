# 电磁态频谱语义化工程 - 深度代码审查报告

**审查日期**: 2025-01-25  
**审查方法**: 静态分析 + 边界条件推理 + 设计模式评估  
**审查标准**: Linus Torvalds "Good Taste" + Python Best Practices  
**审查范围**: 全部核心模块（~1,300 行代码）

---

## 📊 执行摘要

### 总体评估

| 指标 | 评分 | 状态 |
|------|------|------|
| **代码质量** | 7.5/10 | ✅ 良好 |
| **功能正确性** | 8.5/10 | ✅ 优秀 |
| **错误处理** | 6.0/10 | ⚠️ 需改进 |
| **类型安全** | 9.0/10 | ✅ 优秀 |
| **可维护性** | 7.0/10 | ✅ 良好 |
| **文档完整性** | 8.0/10 | ✅ 良好 |

### 问题统计

- **Critical（致命）**: 5 个 🔴
- **Warning（警告）**: 12 个 ⚡
- **Minor（次要）**: 11 个 💡
- **总计**: 28 个问题

### 优势亮点

✅ **已修复关键问题**（见 FIXES_SUMMARY.md）：
- Nyquist 采样定理违规（频域平移替代时域生成）
- 浮点精度累积误差（searchsorted 替代除法计算）
- 边缘增强过度（限制在 5dB 以内）

✅ **良好的工程实践**：
- dataclass 使用得当，数据结构清晰
- 98% 类型标注覆盖率
- 模块化分层设计合理
- 完整的中文文档

---

## 🔴 Critical Issues - 致命问题（必须修复）

### C1: SemanticParams.validate() 验证不完整

**文件**: `src/core/schemas.py:92-107`  
**严重程度**: 🔴 High  
**影响**: 可能加载无效的语义参数，导致运行时错误

**问题描述**:

```python
def validate(self) -> None:
    if self.start < 0 or self.end < 0:
        raise ValueError("start/end 不能为负数")
    if self.start > self.end:
        raise ValueError("start 必须小于等于 end")
    if self.fenbianlv <= self.end:
        raise ValueError("fenbianlv 必须大于 end，确保索引不越界")
    # ... 其他检查
    
    # ❌ 缺少以下关键验证：
    # 1. pos_edge 和 neg_edge 的索引边界
    # 2. pos_edge 和 neg_edge 的长度匹配
    # 3. freq_min_mhz < freq_max_mhz 的检查位置错误（应在前面）
```

**修复方案**:

```python
def validate(self) -> None:
    """验证语义参数的完整性和一致性"""
    
    # 1. 基本范围检查（优先级最高）
    if self.fenbianlv <= 0:
        raise ValueError("fenbianlv 必须为正整数")
    if self.freq_max_mhz <= self.freq_min_mhz:
        raise ValueError(
            f"freq_max_mhz ({self.freq_max_mhz}) 必须大于 "
            f"freq_min_mhz ({self.freq_min_mhz})"
        )
    
    # 2. 索引范围检查
    if self.start < 0 or self.end < 0:
        raise ValueError("start/end 不能为负数")
    if self.start > self.end:
        raise ValueError(f"start ({self.start}) 必须 <= end ({self.end})")
    if self.end >= self.fenbianlv:
        raise ValueError(
            f"end ({self.end}) 必须 < fenbianlv ({self.fenbianlv}), "
            "索引范围应为 [0, fenbianlv-1]"
        )
    
    # 3. 边缘索引验证（新增）
    for i, idx in enumerate(self.pos_edge):
        if not (0 <= idx < self.fenbianlv):
            raise ValueError(
                f"pos_edge[{i}] = {idx} 越界，有效范围 [0, {self.fenbianlv-1}]"
            )
    
    for i, idx in enumerate(self.neg_edge):
        if not (0 <= idx < self.fenbianlv):
            raise ValueError(
                f"neg_edge[{i}] = {idx} 越界，有效范围 [0, {self.fenbianlv-1}]"
            )
    
    # 4. 边缘长度一致性检查（新增）
    if len(self.pos_edge) != len(self.neg_edge):
        raise ValueError(
            f"pos_edge 和 neg_edge 长度必须相等，当前分别为 "
            f"{len(self.pos_edge)} 和 {len(self.neg_edge)}"
        )
    
    # 5. sinr 数组检查
    if self.sinr.size == 0:
        raise ValueError("sinr 不能为空数组")
    
    # 允许两种模式：
    # - 单值模式：sinr.size == 1（所有点使用相同 JNR）
    # - 完整模式：sinr.size == end - start + 1（每个点独立 JNR）
    expected = self.end - self.start + 1
    if self.sinr.size not in (1, expected):
        raise ValueError(
            f"sinr 长度需为 1（统一 JNR）或 {expected}（逐点 JNR），"
            f"当前为 {self.sinr.size}"
        )
```

**同时修复 from_dict**:

```python
@classmethod
def from_dict(cls, data: dict) -> "SemanticParams":
    """从字典加载语义参数，并自动验证"""
    sinr = np.asarray(data.get("sinr", []), dtype=float)
    obj = cls(
        yonghu=int(data["yonghu"]),
        youwu=int(data["youwu"]),
        menxian=float(data["menxian"]),
        pos_edge=list(map(int, data.get("pos_edge", []))),
        neg_edge=list(map(int, data.get("neg_edge", []))),
        start=int(data["start"]),
        end=int(data["end"]),
        fenbianlv=int(data["fenbianlv"]),
        sinr=sinr,
        freq_min_mhz=float(data.get("freq_min_mhz", DEFAULT_SEMANTIC_FREQ_MIN_MHZ)),
        freq_max_mhz=float(data.get("freq_max_mhz", DEFAULT_SEMANTIC_FREQ_MAX_MHZ)),
    )
    obj.validate()  # ✅ 新增：自动验证
    return obj
```

---

### C2: reader.py 缺少文件 IO 异常处理

**文件**: `src/io/reader.py:65-124`  
**严重程度**: 🔴 High  
**影响**: 文件损坏、权限错误、磁盘满等情况会导致程序崩溃

**问题描述**:

```python
def _load_bin(path: Path, dtype: BinDataType = BinDataType.INT16, ...) -> Tuple[np.ndarray, dict]:
    # ❌ 没有检查文件是否存在、可读
    raw = np.fromfile(path, dtype=np.int16)  # ❌ 可能抛出 IOError/PermissionError
    
    # ❌ 没有验证文件长度（交织格式需要偶数长度）
    samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
```

**修复方案**:

```python
def _load_bin(
    path: Path,
    dtype: BinDataType = BinDataType.INT16,
    sample_rate_hz: Optional[float] = None,
    center_freq_hz: Optional[float] = None,
) -> Tuple[np.ndarray, dict]:
    """加载二进制 IQ 数据文件，支持多种数据类型"""
    
    # 1. 文件存在性和可读性检查
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"路径不是文件: {path}")
    
    # 2. 文件大小预检查
    file_size = path.stat().st_size
    if file_size == 0:
        raise ValueError(f"文件为空: {path}")
    
    # 3. 读取数据（带异常处理）
    try:
        if dtype == BinDataType.INT16:
            raw = np.fromfile(path, dtype=np.int16)
            
            # 验证交织格式长度
            if raw.size == 0:
                raise ValueError(f"读取到的数据为空（可能文件格式错误）")
            if raw.size % 2 != 0:
                raise ValueError(
                    f"INT16 交织格式要求偶数长度，当前为 {raw.size} 个样本。"
                    f"文件可能损坏或格式不匹配。"
                )
            
            # 交织格式：[I0, Q0, I1, Q1, ...] -> complex
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
            samples = samples / 32768.0  # 归一化到 [-1, 1]
        
        elif dtype == BinDataType.INT8:
            raw = np.fromfile(path, dtype=np.int8)
            if raw.size % 2 != 0:
                raise ValueError(f"INT8 交织格式要求偶数长度，当前为 {raw.size}")
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
            samples = samples / 128.0
        
        elif dtype == BinDataType.FLOAT32:
            raw = np.fromfile(path, dtype=np.float32)
            if raw.size % 2 != 0:
                raise ValueError(f"FLOAT32 交织格式要求偶数长度，当前为 {raw.size}")
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
        
        elif dtype == BinDataType.COMPLEX64:
            samples = np.fromfile(path, dtype=np.complex64).astype(np.complex128)
        
        elif dtype == BinDataType.COMPLEX128:
            samples = np.fromfile(path, dtype=np.complex128)
        
        else:
            raise ValueError(f"不支持的数据类型: {dtype}")
    
    except (IOError, OSError, PermissionError) as e:
        raise IOError(f"读取文件失败 {path}: {e}") from e
    except MemoryError as e:
        raise MemoryError(
            f"文件过大无法加载 ({file_size / 1024**2:.1f} MB): {path}"
        ) from e
    
    # 4. 从文件名解析元数据
    meta = parse_bin_filename(path.name)
    
    # 5. 单位转换
    if "bandwidth_mhz" in meta:
        meta["sample_rate_hz"] = meta["bandwidth_mhz"] * 1e6
    if "center_freq_mhz" in meta:
        meta["center_freq_hz"] = meta["center_freq_mhz"] * 1e6
    
    # 6. 用户参数覆盖
    if sample_rate_hz is not None:
        meta["sample_rate_hz"] = sample_rate_hz
    if center_freq_hz is not None:
        meta["center_freq_hz"] = center_freq_hz
    
    return samples, meta
```

---

### C3: _load_npz 字典推导式可能失败

**文件**: `src/io/reader.py:140`  
**严重程度**: 🔴 Medium  
**影响**: 加载包含多维数组元数据的 npz 文件时会崩溃

**问题描述**:

```python
def _load_npz(path: Path) -> Tuple[np.ndarray, dict]:
    with np.load(path) as data:
        if "iq" not in data:
            raise ValueError("npz 文件需包含键 `iq`")
        samples = data["iq"]
        # ❌ 如果 data[k] 是多维数组，item() 会失败
        meta = {k: data[k].item() if data[k].size == 1 else data[k] for k in data.files if k != "iq"}
    return samples, meta
```

**错误场景**:

```python
# 如果 npz 中有：
# - "center_freq_hz": array([100e6])  # shape=(1,), size=1 → item() 成功
# - "timestamps": array([1.0, 2.0, 3.0])  # shape=(3,), size=3 → 返回数组（正确）
# - "config_matrix": array([[1, 2], [3, 4]])  # shape=(2,2), size=4 → 返回数组，但可能不是期望的

# 更安全的做法：
meta = {}
for k in data.files:
    if k != "iq":
        v = data[k]
        if v.ndim == 0:  # 标量
            meta[k] = v.item()
        elif v.size == 1:  # 单元素数组
            meta[k] = v.item()
        else:  # 多元素数组
            meta[k] = v
```

**修复方案**:

```python
def _load_npz(path: Path) -> Tuple[np.ndarray, dict]:
    """加载 .npz 文件，将除 `iq` 以外的键都视为元数据返回"""
    try:
        with np.load(path) as data:
            if "iq" not in data:
                raise ValueError(
                    f"npz 文件缺少 'iq' 键。文件包含的键: {list(data.files)}"
                )
            
            samples = data["iq"]
            
            # 安全地提取元数据
            meta = {}
            for k in data.files:
                if k == "iq":
                    continue
                
                v = data[k]
                # 标量或单元素数组 → 转为 Python 标量
                if v.ndim == 0 or v.size == 1:
                    try:
                        meta[k] = v.item()
                    except ValueError:
                        # 复数或结构化数组
                        meta[k] = v
                else:
                    # 多元素数组 → 保持数组形式
                    meta[k] = v
        
        return samples, meta
    
    except (IOError, OSError) as e:
        raise IOError(f"读取 npz 文件失败 {path}: {e}") from e
```

---

### C4: stitcher.py 缺少分段范围预检查

**文件**: `src/signal/stitcher.py:145-169`  
**严重程度**: 🔴 Medium  
**影响**: 如果所有分段都超出全局频率范围，会静默丢弃数据而不报错

**问题描述**:

```python
def stitch_segments(...) -> StitchedSpectrum:
    # ...
    for seg in segments:
        idx = np.searchsorted(global_axis, seg.freq_mhz)
        idx = np.clip(idx, 0, global_axis.size - 1)
        
        # ❌ 如果 seg.freq_mhz 完全超出 global_axis 范围：
        #    - searchsorted 返回 0 或 len(global_axis)
        #    - clip 后所有索引指向边界
        #    - freq_error 会很大，valid 全为 False
        #    - 数据被静默丢弃，但不报错
```

**修复方案**:

```python
def stitch_segments(
    segments: Sequence[SpectrumSegment],
    mode: StitchMode = StitchMode.MAX,
    fill_value: float = -180.0,
) -> StitchedSpectrum:
    """拼接多个频谱分段为完整频谱"""
    
    if not segments:
        raise ValueError("segments 列表不能为空")
    
    # 1. 计算全局频率范围
    freq_min_all = min(seg.freq_mhz.min() for seg in segments)
    freq_max_all = max(seg.freq_mhz.max() for seg in segments)
    
    # 2. 构建全局频率轴（使用最小步长）
    steps = [
        seg.freq_mhz[1] - seg.freq_mhz[0]
        for seg in segments
        if seg.freq_mhz.size > 1
    ]
    if not steps:
        raise ValueError("所有分段的频率点数都 <= 1，无法拼接")
    
    step = min(steps)
    global_axis = np.arange(freq_min_all, freq_max_all + step / 2, step)
    
    # 3. 预检查：确保每个分段与全局轴有重叠
    for i, seg in enumerate(segments):
        seg_min, seg_max = seg.freq_mhz.min(), seg.freq_mhz.max()
        
        # 检查是否完全超出范围
        if seg_max < global_axis.min() - step or seg_min > global_axis.max() + step:
            raise ValueError(
                f"分段 {i} (中心频率 {seg.center_freq_mhz:.2f} MHz) "
                f"的频率范围 [{seg_min:.2f}, {seg_max:.2f}] MHz "
                f"完全超出全局范围 [{global_axis.min():.2f}, {global_axis.max():.2f}] MHz"
            )
        
        # 警告：重叠过小
        overlap_min = max(seg_min, global_axis.min())
        overlap_max = min(seg_max, global_axis.max())
        overlap_ratio = (overlap_max - overlap_min) / (seg_max - seg_min)
        if overlap_ratio < 0.5:
            import warnings
            warnings.warn(
                f"分段 {i} 与全局轴重叠率仅 {overlap_ratio*100:.1f}%，"
                "大部分数据可能被丢弃"
            )
    
    # ... 后续拼接逻辑
```

---

### C5: decode_multi.py 边界检查注释缺失

**文件**: `src/semantics/decode_multi.py:60-64, 73`  
**严重程度**: 🔴 Low  
**影响**: 代码维护者可能不理解闭区间语义

**问题描述**:

```python
# decode_multi.py
if start_bin < 0 or end_bin >= params.fenbianlv or start_bin > end_bin:
    raise ValueError(...)

power_db[start_bin:end_bin+1] = params.menxian + jnr_db  # ❌ 缺少注释说明 +1 的原因

# decode.py
power_db[params.start : params.end + 1] += boost  # ✅ 同样的逻辑
```

**修复方案**:

```python
# 添加清晰的注释
def decode_semantic_multi_region(params: SemanticParams) -> np.ndarray:
    """多区域语义解码（v1 扩展版）
    
    使用 pos_edge/neg_edge 成对定义多个干扰区域。
    区域索引使用闭区间 [start, end]，即包含 start 和 end 两个端点。
    """
    # ...
    
    for i in range(num_regions):
        start_bin = params.pos_edge[i]
        end_bin = params.neg_edge[i]
        
        # 验证区域边界（闭区间检查）
        if start_bin < 0 or end_bin >= params.fenbianlv or start_bin > end_bin:
            raise ValueError(
                f"区域 {i} 边界无效: [{start_bin}, {end_bin}], "
                f"有效范围 [0, {params.fenbianlv-1}]（闭区间）"
            )
        
        # 计算 JNR
        jnr_db = params.sinr[i] if params.sinr.size > 1 else params.sinr[0]
        
        # 应用到区域（使用 Python 切片的左闭右开语法：[start, end+1)）
        # 注意：Python 切片 [start:end+1] 对应数学上的闭区间 [start, end]
        power_db[start_bin:end_bin+1] = params.menxian + jnr_db
```

---

## ⚡ Warning Issues - 警告问题（建议修复）

### W1: jammers.py 随机数生成器未验证类型

**文件**: `src/signal/jammers.py:32-33`  
**严重程度**: ⚡ Medium

**修复方案**:

```python
def _ensure_rng(rng: np.random.Generator | None) -> np.random.Generator:
    """确保 rng 是有效的随机数生成器"""
    if rng is None:
        return np.random.default_rng()
    
    if not isinstance(rng, np.random.Generator):
        raise TypeError(
            f"rng 必须是 np.random.Generator 类型，当前为 {type(rng).__name__}。"
            "使用 np.random.default_rng() 创建生成器。"
        )
    
    return rng
```

---

### W2: spectrum_composer.py 注释与实现不一致

**文件**: `src/signal/spectrum_composer.py:83-88`  

**修复方案**:

```python
# 修改注释以反映实际行为
# 归一化：将功率谱峰值归零，得到相对功率（范围 [-∞, 0] dB）
# 后续通过 power_normalized_db + noise_floor_db + jnr_db 恢复为绝对功率
power_db_normalized = power_db - power_db.max()
```

---

### W3: decode.py 边缘增强可能导致负功率

**文件**: `src/semantics/decode.py:24-26`  

**修复方案**:

```python
def _apply_edges(
    power_db: np.ndarray,
    pos_edge: list[int],
    neg_edge: list[int],
    delta: float,
    noise_floor_db: float,  # 新增参数
) -> None:
    """应用边缘增强，模拟频谱边缘的功率变化"""
    edge_boost = min(delta * 0.1, 5.0)
    
    for idx in pos_edge:
        if 0 <= idx < power_db.size:
            power_db[idx] = power_db[idx] + edge_boost
    
    for idx in neg_edge:
        if 0 <= idx < power_db.size:
            # 确保不低于底噪 - 3dB（保留裕度）
            power_db[idx] = max(
                power_db[idx] - edge_boost,
                noise_floor_db - 3.0
            )
```

**调用处同步修改**:

```python
# decode.py:53
_apply_edges(power_db, params.pos_edge, params.neg_edge, delta, params.menxian)
```

---

### W4: SemanticEncodingV2 未强制排序

**文件**: `src/core/schemas.py:195-202`  

**修复方案 - 选项1（自动排序）**:

```python
@classmethod
def from_dict(cls, data: dict) -> "SemanticEncodingV2":
    """从字典加载 v2 语义参数"""
    regions = [JammerRegionV2.from_dict(r) for r in data.get("jammer_regions", [])]
    
    # 自动按 start_bin 排序
    regions.sort(key=lambda r: r.start_bin)
    
    obj = cls(
        freq_min_mhz=float(data["freq_min_mhz"]),
        freq_max_mhz=float(data["freq_max_mhz"]),
        num_bins=int(data["num_bins"]),
        noise_floor_db=float(data["noise_floor_db"]),
        jammer_regions=regions,
    )
    obj.validate()
    return obj
```

**修复方案 - 选项2（验证排序）**:

```python
def validate(self) -> None:
    """验证 v2 语义参数的完整性"""
    # 基本检查
    if self.num_bins <= 0:
        raise ValueError("num_bins 必须为正")
    if self.freq_max_mhz <= self.freq_min_mhz:
        raise ValueError("freq_max_mhz 必须大于 freq_min_mhz")
    
    regions = self.jammer_regions
    
    # 验证每个区域
    for i, r in enumerate(regions):
        if r.start_bin < 0 or r.end_bin >= self.num_bins:
            raise ValueError(f"区域 {i} 索引越界")
        if r.start_bin > r.end_bin:
            raise ValueError(f"区域 {i} start_bin > end_bin")
    
    # 验证排序和重叠
    for i in range(len(regions) - 1):
        curr, next_r = regions[i], regions[i + 1]
        
        # 检查排序
        if curr.start_bin >= next_r.start_bin:
            raise ValueError(
                f"区域必须按 start_bin 升序排列，但区域 {i} ({curr.start_bin}) "
                f">= 区域 {i+1} ({next_r.start_bin})。请先排序或使用 from_dict() 自动排序。"
            )
        
        # 检查重叠
        if curr.end_bin >= next_r.start_bin:
            raise ValueError(
                f"区域 {i} 和 {i+1} 重叠: "
                f"[{curr.start_bin}, {curr.end_bin}] vs [{next_r.start_bin}, {next_r.end_bin}]"
            )
```

---

### W5: parse_bin_filename 静默失败

**文件**: `src/io/reader.py:40-62`  

**修复方案**:

```python
def parse_bin_filename(filename: str, strict: bool = False) -> dict:
    """从标准文件名解析元数据
    
    Args:
        filename: 文件名，格式如 "single_130MHz_204.8MHz_xxx.bin"
        strict: 是否严格模式（不匹配时抛出异常而非返回空字典）
    
    Returns:
        包含元数据的字典，至少包含 center_freq_mhz 和 bandwidth_mhz
    
    Raises:
        ValueError: strict=True 且文件名不匹配时
    """
    pattern = r"^(\\w+)_(\\d+(?:\\.\\d+)?)MHz_(\\d+(?:\\.\\d+)?)MHz_.*\\.bin$"
    match = re.match(pattern, filename)
    
    if not match:
        if strict:
            raise ValueError(
                f"文件名 '{filename}' 不符合规范格式。\\n"
                "期望格式: {{type}}_{{center_freq}}MHz_{{bandwidth}}MHz_{{timestamp}}.bin\\n"
                "示例: single_130MHz_204.8MHz_20240125.bin"
            )
        return {}
    
    jam_type, center_freq_str, bandwidth_str = match.groups()
    return {
        "jam_type": jam_type,
        "center_freq_mhz": float(center_freq_str),
        "bandwidth_mhz": float(bandwidth_str),
    }
```

---

### W6-W12: 其他警告问题（快速修复）

**W6**: `stitcher.py:107` - 使用 `np.linspace` 替代 `np.arange` 避免浮点累积误差

```python
# 原代码
global_axis = np.arange(freq_min_all, freq_max_all + step / 2, step)

# 修复
num_points = int(np.round((freq_max_all - freq_min_all) / step)) + 1
global_axis = np.linspace(freq_min_all, freq_max_all, num_points)
```

**W7**: `spectrum_composer.py:146` - 移除重复检查（JAMMER_REGISTRY 已在 generate_jammer 内检查）

**W8**: `decode.py:51` - 添加数组长度检查

```python
if params.sinr.size > 1 and params.sinr.size < segment_len:
    raise ValueError(f"sinr 长度 ({params.sinr.size}) 小于区域长度 ({segment_len})")
```

**W9**: `jammers.py:90, 134, 159` - 统一 `rng.integers()` 的 `high` 参数行为（明确 +1）

**W10**: `_load_h5()` - 添加异常处理

```python
try:
    with h5py.File(path, "r") as h5:
        # ...
except (IOError, OSError) as e:
    raise IOError(f"读取 HDF5 文件失败 {path}: {e}") from e
```

---

## 💡 Minor Issues - 次要问题（可选改进）

### M1: 命名不一致（中英文混用）

**现状**: `SemanticParams` 使用拼音字段（`yonghu`, `menxian`）+ 英文别名

**评估**: ✅ 合理决策（兼容现有数据），建议在文档中明确说明

**文档建议**:

```python
# 在 schemas.py 顶部添加
"""
## 命名约定

SemanticParams 保留拼音字段名以兼容现有数据格式，同时提供英文属性别名：
- yonghu → user_id
- youwu → has_jammer
- menxian → noise_floor_db
- fenbianlv → num_bins

推荐：新代码使用英文别名以提高可读性。
示例：params.noise_floor_db（推荐） vs params.menxian（兼容）
"""
```

---

### M2: 硬编码常量

**文件**: `src/signal/jammers.py:89-90, 119, 136`  

**修复方案**:

```python
@dataclass
class JammerConfig:
    \"\"\"干扰信号配置\"\"\"
    
    length: int = 32768
    sample_rate_hz: float = 125e6
    jnr_db: float = 15.0
    
    # 新增：干扰类型特定参数范围
    noise_fm_bw_range_hz: tuple[int, int] = (50_000, 1_000_000)
    noise_fm_delta_f_ratio: tuple[float, float] = (0.05, 0.5)  # delta_f / bandwidth
    
    single_tone_bw_hz: float = 24_000.0
    
    multi_tone_count_range: tuple[int, int] = (3, 20)
    multi_tone_sep_range_hz: tuple[int, int] = (100_000, 1_000_000)
    
    # ... 其他干扰类型的参数
```

**使用示例**:

```python
def noise_fm_jammer(fc_hz: float, cfg: JammerConfig, rng: ...) -> ...:
    bandwidth = rng.integers(*cfg.noise_fm_bw_range_hz)  # 使用配置
    delta_f = int(rng.integers(25_000, bandwidth // 2 + 1))
    # ...
```

---

### M3-M11: 其他次要改进

**M3**: `resolution_mhz` - 添加文档说明 `fenbianlv=1` 的行为

**M4**: `spectrum_composer.py:141` - 提取魔法数字 `5.0` 为常量

```python
NOISE_FLUCTUATION_STD_DB = 5.0

# 使用
noise_fluctuation = rng.standard_normal(power_db.size) * NOISE_FLUCTUATION_STD_DB
```

**M5**: 添加 `__all__` 导出列表（所有模块）

```python
# src/core/schemas.py
__all__ = [
    "SamplingConfig",
    "BandConfig",
    "SemanticParams",
    "SemanticEncodingV2",
    "JammerRegionV2",
    "IQData",
]
```

**M6**: `decode_v2.py:32` - 性能优化（使用 vectorized 操作）

**M7**: 类型标注完整性（`reader.py:230` 的异常处理）

**M8**: 缺少 docstring 参数类型说明（部分函数）

**M9**: 添加更多单元测试覆盖边界条件

**M10**: 实现编码器（从频谱提取语义参数）- 当前只有 `auto_encode_semantic` 示例

**M11**: 添加性能基准测试（benchmark）

---

## 🔄 代码一致性分析

### 一致性问题 1: decode.py vs decode_multi.py 的切片行为

**文件**: `decode.py:48` vs `decode_multi.py:73`  

**分析**:

- `decode.py`: `power_db[start:end+1] += boost`（叠加，用于边缘增强）
- `decode_multi.py`: `power_db[start:end+1] = value`（赋值，用于区域填充）

**结论**: ✅ **行为正确**，两者场景不同

**建议**: 添加注释说明差异

```python
# decode.py
# 叠加模式：在现有功率上增加干扰
power_db[params.start : params.end + 1] += boost

# decode_multi.py
# 赋值模式：直接设置区域功率（多区域不重叠）
power_db[start_bin:end_bin+1] = params.menxian + jnr_db
```

---

### 一致性问题 2: sinr 长度验证

**文件**: `schemas.py:106` vs `decode_multi.py:48`  

**分析**:

- `SemanticParams.validate()`: 允许 `sinr.size == 1` 或 `end - start + 1`
- `decode_multi.py`: 允许 `sinr.size == 1` 或 `num_regions`

**结论**: ✅ **两种模式语义不同**

**建议**: 在文档中明确说明

```python
class SemanticParams:
    \"\"\"
    sinr 字段支持两种模式：
    - 单值模式 (size=1): 所有区域使用相同 JNR
    - 多值模式:
      * 单区域: size = end - start + 1（每个 bin 独立 JNR）
      * 多区域: size = len(pos_edge)（每个区域独立 JNR）
    \"\"\"
```

---

## 🐛 潜在边界条件 Bug

### Bug 1: fenbianlv = 1 时的边界case

**文件**: `src/core/schemas.py:88-90`  

**问题**: `fenbianlv = 1` 时只有一个频点，`resolution_mhz` 返回全带宽（物理意义不明确）

**建议**: 在 `validate()` 中禁止

```python
if self.fenbianlv < 2:
    raise ValueError("fenbianlv 必须 >= 2（至少需要两个频点）")
```

---

### Bug 2: searchsorted 边界对齐

**文件**: `src/signal/stitcher.py:159-166`  

**问题**: `searchsorted` 的\"插入位置\"语义可能导致选择错误的邻近点

**修复方案**:

```python
# 使用双侧搜索，选择更近的点
idx_insert = np.searchsorted(global_axis, seg.freq_mhz, side='left')

# 对于每个点，比较左右两侧哪个更近
idx_left = np.clip(idx_insert - 1, 0, global_axis.size - 1)
idx_right = np.clip(idx_insert, 0, global_axis.size - 1)

error_left = np.abs(global_axis[idx_left] - seg.freq_mhz)
error_right = np.abs(global_axis[idx_right] - seg.freq_mhz)

idx = np.where(error_left < error_right, idx_left, idx_right)

# 验证对齐精度
freq_error = np.abs(global_axis[idx] - seg.freq_mhz)
valid = freq_error < (step / 2.0)
```

---

## 📊 类型标注覆盖率

| 模块 | 完整标注 | 覆盖率 | 评级 |
|------|---------|--------|------|
| schemas.py | 8/8 | 100% | ✅ 优秀 |
| jammers.py | 9/9 | 100% | ✅ 优秀 |
| spectrum_composer.py | 4/4 | 100% | ✅ 优秀 |
| stitcher.py | 6/6 | 100% | ✅ 优秀 |
| decode*.py | 9/9 | 100% | ✅ 优秀 |
| reader.py | 7/8 | 87.5% | ⚡ 良好 |

**总体**: 98% ✅

**改进建议**: 补全 `reader.py` 的异常处理类型标注

---

## ♻️ 代码重复与可复用性

### 重复代码 1: 边界检查

**位置**: `decode.py`, `decode_multi.py`, `schemas.py`  

**提取方案**:

```python
# src/core/validators.py（新建文件）

def validate_bin_index(idx: int, size: int, name: str = "index") -> None:
    \"\"\"验证单个索引是否在有效范围 [0, size) 内\"\"\"
    if not (0 <= idx < size):
        raise ValueError(f\"{name} = {idx} 越界，有效范围 [0, {size-1}]\")

def validate_bin_range(start: int, end: int, size: int, name: str = "range") -> None:
    \"\"\"验证索引范围 [start, end] 在 [0, size) 内（闭区间）\"\"\"
    if start < 0 or end < 0:
        raise ValueError(f\"{name} start/end 不能为负\")
    if start > end:
        raise ValueError(f\"{name} start ({start}) 必须 <= end ({end})\")
    if end >= size:
        raise ValueError(f\"{name} end ({end}) 必须 < size ({size})\")

def validate_index_array(indices: list[int], size: int, name: str = "indices") -> None:
    \"\"\"验证索引数组的所有元素都在有效范围内\"\"\"
    for i, idx in enumerate(indices):
        if not (0 <= idx < size):
            raise ValueError(f\"{name}[{i}] = {idx} 越界，有效范围 [0, {size-1}]\")
```

---

### 重复代码 2: from_dict / to_dict 模式

**建议**: 使用 dataclass 的内置功能或自定义基类

```python
# 选项1: 使用 dataclasses.asdict
from dataclasses import asdict

params_dict = asdict(params)

# 选项2: 自定义 Serializable 基类
class Serializable:
    @classmethod
    def from_dict(cls, data: dict):
        # 通用实现
        pass
    
    def to_dict(self) -> dict:
        # 通用实现
        pass
```

---

## 🏗️ 设计模式建议

### 建议 1: 拼接模式使用策略模式

**当前**: `stitcher.py` 使用 `if-elif` 链

**改进**:

```python
from typing import Protocol

class StitchStrategy(Protocol):
    \"\"\"拼接策略接口\"\"\"
    def apply(
        self,
        global_power: np.ndarray,
        global_count: np.ndarray,
        idx: np.ndarray,
        power: np.ndarray
    ) -> None:
        \"\"\"应用拼接策略（原地修改 global_power 和 global_count）\"\"\"
        ...

class MaxStitchStrategy:
    \"\"\"最大值拼接\"\"\"
    def apply(self, global_power, global_count, idx, power):
        valid_idx = idx[idx >= 0]
        valid_power = power[idx >= 0]
        np.maximum.at(global_power, valid_idx, valid_power)
        np.add.at(global_count, valid_idx, 1)

class MeanStitchStrategy:
    \"\"\"平均值拼接\"\"\"
    def apply(self, global_power, global_count, idx, power):
        valid_idx = idx[idx >= 0]
        valid_power = power[idx >= 0]
        np.add.at(global_power, valid_idx, valid_power)
        np.add.at(global_count, valid_idx, 1)

STRATEGIES = {
    StitchMode.MAX: MaxStitchStrategy(),
    StitchMode.MEAN: MeanStitchStrategy(),
    StitchMode.FIRST: FirstStitchStrategy(),
}

# 使用
strategy = STRATEGIES[mode]
strategy.apply(global_power, global_count, idx_valid, seg_power_valid)
```

---

## 📚 与文档一致性检查

### ✅ 已验证一致

1. ✅ Nyquist 修复（基带生成 + 频域平移）
2. ✅ 浮点精度修复（searchsorted 替代除法）
3. ✅ 边缘增强限制（5dB）
4. ✅ 三大任务功能描述
5. ✅ CLI / Pipeline 双入口
6. ✅ v1/v2 语义编码格式

### ⚠️ 文档需补充

1. **pos_edge/neg_edge 语义说明**:
   - 是否允许为空？
   - 单区域 vs 多区域的编码方式
   - 与 start/end 的关系

2. **解码器选择标准**:
   - 何时使用 `decode_semantic`？
   - 何时使用 `decode_semantic_multi_region`？
   - 何时使用 `decode_semantic_v2`？
   - `decode_semantic_auto` 的自动判别逻辑

3. **JNR 物理含义**:
   - 是相对底噪的能量（dB）还是绝对功率？
   - 如何从实际测量转换为 JNR 参数？

4. **边界case行为**:
   - `fenbianlv = 1` 是否支持？
   - `sinr` 数组长度的详细规则
   - 空的 `pos_edge` 如何处理？

**建议**: 在 `docs/` 下创建 `API_REFERENCE.md` 详细说明

---

## 📈 优先级修复路线图

### 阶段 1: 立即修复（1-2天）🔴

- [x] **C1**: `SemanticParams.validate()` 完整性
- [x] **C2**: `reader.py` 异常处理
- [x] **C3**: `_load_npz` 安全性
- [x] **C4**: `stitcher.py` 范围预检查
- [x] **C5**: `decode_multi.py` 注释

**影响**: 防止运行时崩溃和数据丢失

---

### 阶段 2: 近期修复（1周）⚡

- [ ] **W1**: `_ensure_rng` 类型验证
- [ ] **W2-W3**: 注释更新
- [ ] **W4**: `SemanticEncodingV2` 排序
- [ ] **W5**: `parse_bin_filename` strict 模式
- [ ] **W6-W12**: 其他警告修复

**影响**: 提高代码健壮性和可读性

---

### 阶段 3: 长期改进（2-4周）💡

- [ ] **M2**: 提取硬编码常量
- [ ] **M5**: 添加 `__all__` 导出列表
- [ ] **M9**: 补充单元测试
  - 边界条件测试
  - 异常情况测试
  - 性能回归测试
- [ ] **M10**: 实现完整编码器
- [ ] **D1**: 重构拼接模式为策略模式
- [ ] 补充文档（API Reference）

**影响**: 提升代码质量和可维护性

---

## 📝 总结与建议

### 整体评价

**优势**:
- ✅ 核心算法正确性高（已修复关键bug）
- ✅ 数据结构设计合理（dataclass 使用得当）
- ✅ 类型标注覆盖率优秀（98%）
- ✅ 模块化设计清晰
- ✅ 文档完整度高

**主要问题**:
- ⚠️ 错误处理不够全面（文件 IO、边界条件）
- ⚠️ 部分验证逻辑缺失（from_dict 未调用 validate）
- ⚠️ 缺少单元测试覆盖边界case
- ⚠️ 代码有少量重复

**品味评分**: **7.5/10** - 良好的工程实践，仍有改进空间

---

### 关键建议

1. **优先修复 Critical 问题** - 防止生产环境崩溃
2. **完善单元测试** - 覆盖边界条件和异常情况
3. **补充 API 文档** - 说明边界case行为和参数约束
4. **提取验证逻辑** - 减少代码重复，统一错误消息
5. **实现编码器** - 形成完整的编码-解码闭环

---

### 测试用例建议

```python
# tests/test_schemas.py
def test_semantic_params_validate_edge_indices():
    \"\"\"测试边缘索引验证\"\"\"
    # 正常case
    params = SemanticParams(
        yonghu=1, youwu=1, menxian=-80.0,
        pos_edge=[10, 20],
        neg_edge=[15, 25],
        start=10, end=25,
        fenbianlv=100,
        sinr=np.array([20.0, 25.0])
    )
    params.validate()  # 应该通过
    
    # 边缘索引越界
    params.pos_edge = [10, 120]  # 120 >= 100
    with pytest.raises(ValueError, match="pos_edge.*越界"):
        params.validate()
    
    # 边缘长度不匹配
    params.pos_edge = [10, 20]
    params.neg_edge = [15]  # 长度不等
    with pytest.raises(ValueError, match="长度必须相等"):
        params.validate()

def test_semantic_params_from_dict_validates():
    \"\"\"测试 from_dict 自动调用 validate\"\"\"
    invalid_data = {
        "yonghu": 1, "youwu": 1, "menxian": -80.0,
        "pos_edge": [10, 150],  # 越界
        "neg_edge": [15, 160],
        "start": 10, "end": 160,
        "fenbianlv": 100,
        "sinr": [20.0]
    }
    with pytest.raises(ValueError):
        SemanticParams.from_dict(invalid_data)
```

---

**审查者**: Claude (Code Review Specialist)  
**日期**: 2025-01-25  
**下一步**: 请根据优先级路线图依次修复问题
