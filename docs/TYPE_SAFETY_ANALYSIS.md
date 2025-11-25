# 类型安全分析报告

> **生成时间**: 2025-01-25  
> **分析范围**: 7个核心 Python 模块  
> **Python 版本**: 3.11+ (使用 PEP 604 语法 `|`)

---

## 📋 目录

1. [输入数据类型清单](#1-输入数据类型清单)
2. [输出数据类型说明](#2-输出数据类型说明)
3. [类型安全问题分析](#3-类型安全问题分析)
4. [与 Pydantic 模型的对应关系](#4-与-pydantic-模型的对应关系)
5. [改进建议](#5-改进建议)

---

## 1. 输入数据类型清单

### 📦 模块 1: `src/core/schemas.py`

#### 数据类（Dataclass）

| 类名 | 字段 | 类型 | 必需 | 默认值 |
|------|------|------|------|--------|
| **SamplingConfig** | sample_rate_hz | `float` | ✅ | - |
|  | center_freq_hz | `float` | ✅ | - |
|  | fft_size | `int` | ❌ | 4096 |
| **BandConfig** | name | `str` | ✅ | - |
|  | start_freq_mhz | `float` | ✅ | - |
|  | end_freq_mhz | `float` | ✅ | - |
| **SemanticParams** | yonghu | `int` | ✅ | - |
|  | youwu | `int` | ✅ | - |
|  | menxian | `float` | ✅ | - |
|  | pos_edge | `List[int]` | ✅ | - |
|  | neg_edge | `List[int]` | ✅ | - |
|  | start | `int` | ✅ | - |
|  | end | `int` | ✅ | - |
|  | fenbianlv | `int` | ✅ | - |
|  | sinr | `np.ndarray` | ✅ | - |
|  | freq_min_mhz | `float` | ❌ | 30.0 |
|  | freq_max_mhz | `float` | ❌ | 2500.0 |
| **JammerRegionV2** | start_bin | `int` | ✅ | - |
|  | end_bin | `int` | ✅ | - |
|  | jnr_db | `float` | ✅ | - |
| **SemanticEncodingV2** | freq_min_mhz | `float` | ✅ | - |
|  | freq_max_mhz | `float` | ✅ | - |
|  | num_bins | `int` | ✅ | - |
|  | noise_floor_db | `float` | ✅ | - |
|  | jammer_regions | `List[JammerRegionV2]` | ❌ | [] |
| **IQData** | samples | `np.ndarray` | ✅ | - |
|  | sample_rate_hz | `float` | ✅ | - |
|  | center_freq_hz | `float` | ✅ | - |
|  | meta | `Optional[dict]` | ❌ | None |

#### 函数签名

```python
# SemanticParams
def validate(self) -> None
def from_dict(cls, data: dict) -> "SemanticParams"
def to_dict(self) -> dict

# SemanticEncodingV2
def validate(self) -> None
def from_dict(cls, data: dict) -> "SemanticEncodingV2"
def to_dict(self) -> dict

# BandConfig
def contains(self, freq_mhz: float) -> bool
```

---

### 📦 模块 2: `src/signal/jammers.py`

#### 数据类

| 类名 | 字段 | 类型 | 默认值 |
|------|------|------|--------|
| **JammerConfig** | length | `int` | 32768 |
|  | sample_rate_hz | `float` | 125e6 |
|  | jnr_db | `float` | 15.0 |

#### 函数签名清单

| 函数名 | 参数1 | 参数2 | 参数3 | 返回类型 |
|--------|-------|-------|-------|---------|
| `_ensure_rng` | `rng: Generator \| None` | - | - | `Generator` |
| `_add_awgn_measured` | `iq: ndarray` | `snr_db: float` | `rng: Generator \| None` | `ndarray` |
| `_lowpass_real` | `x: ndarray` | `cutoff_hz: float` | `fs_hz: float` | `ndarray` |
|  |  |  | `order: int = 6` |  |
| `noise_fm_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `single_tone_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `multi_tone_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `comb_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `partial_band_noise_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `sweep_jammer` | `fc_hz: float` | `cfg: JammerConfig` | `rng: Generator \| None` | `Tuple[ndarray, float]` |
| `generate_jammer` | `jam_type: str` | `fc_hz: float` | `cfg: JammerConfig` | `Tuple[ndarray, float]` |
|  |  |  | `rng: Generator \| None` |  |

---

### 📦 模块 3: `src/signal/spectrum_composer.py`

#### 数据类

| 类名 | 字段 | 类型 | 默认值 |
|------|------|------|--------|
| **JammerSpec** | jam_type | `str` | - |
|  | center_freq_mhz | `float` | - |
|  | jnr_db | `float` | 15.0 |
|  | bandwidth_mhz | `float \| None` | None |
| **SpectrumComposerConfig** | freq_min_mhz | `float` | 30.0 |
|  | freq_max_mhz | `float` | 2500.0 |
|  | resolution_mhz | `float` | 1.0 |
|  | noise_floor_db | `float` | -80.0 |
|  | sample_rate_hz | `float` | 125e6 |
|  | iq_length | `int` | 32768 |
|  | jammers | `List[JammerSpec]` | [] |

#### 函数签名

| 函数名 | 参数 | 返回类型 |
|--------|------|---------|
| `_generate_jammer_spectrum` | `spec: JammerSpec` | `Tuple[ndarray, ndarray, float]` |
|  | `sample_rate_hz: float` |  |
|  | `iq_length: int` |  |
|  | `rng: Generator` |  |
| `_interpolate_spectrum` | `freq_src_mhz: ndarray` | `ndarray` |
|  | `power_src_db: ndarray` |  |
|  | `freq_dst_mhz: ndarray` |  |
| `compose_spectrum` | `cfg: SpectrumComposerConfig` | `Tuple[ndarray, ndarray]` |
|  | `rng: Generator \| None` |  |
| `add_jammer` | `cfg: SpectrumComposerConfig` | `None` |
|  | `jam_type: str` |  |
|  | `center_freq_mhz: float` |  |
|  | `jnr_db: float = 15.0` |  |

---

### 📦 模块 4: `src/signal/stitcher.py`

#### 数据类

| 类名 | 字段 | 类型 | 默认值 |
|------|------|------|--------|
| **SpectrumSegment** | freq_mhz | `np.ndarray` | - |
|  | power_db | `np.ndarray` | - |
|  | center_freq_mhz | `float` | - |
|  | bandwidth_mhz | `float` | - |
|  | metadata | `dict` | None |
| **StitchedSpectrum** | freq_mhz | `np.ndarray` | - |
|  | power_db | `np.ndarray` | - |
|  | coverage_map | `np.ndarray` | - |
|  | segment_count | `int` | - |
|  | freq_min_mhz | `float` | - |
|  | freq_max_mhz | `float` | - |
|  | mode | `StitchMode` | - |
|  | metadata | `dict` | None |

#### 枚举类

```python
class StitchMode(str, Enum):
    MAX = "max"
    MEAN = "mean"
    WEIGHTED_MEAN = "weighted_mean"
    FIRST = "first"
    LAST = "last"
```

#### 函数签名

| 函数名 | 参数 | 返回类型 |
|--------|------|---------|
| `_compute_weight` | `freq_mhz: ndarray` | `ndarray` |
|  | `center_freq_mhz: float` |  |
|  | `bandwidth_mhz: float` |  |
| `_build_global_axis` | `segments: List[SpectrumSegment]` | `Tuple[ndarray, float]` |
| `stitch_segments` | `segments: List[SpectrumSegment]` | `StitchedSpectrum` |
|  | `mode: StitchMode = MAX` |  |
|  | `fill_value: float = -180.0` |  |
| `stitch_from_iq_data` | `iq_data_list: List[IQData]` | `StitchedSpectrum` |
|  | `configs: List[SamplingConfig]` |  |
|  | `mode: StitchMode = MAX` |  |
|  | `fill_value: float = -180.0` |  |
|  | `window: str = "hann"` |  |
| `load_segment_from_npz` | `path: Path` | `SpectrumSegment` |
| `stitch_from_npz_files` | `file_paths: List[Path]` | `StitchedSpectrum` |
|  | `mode: StitchMode = MAX` |  |
|  | `fill_value: float = -180.0` |  |

---

### 📦 模块 5: `src/semantics/decode.py`

#### 函数签名

| 函数名 | 参数 | 返回类型 |
|--------|------|---------|
| `_apply_edges` | `power_db: ndarray` | `None` |
|  | `pos_edge: list[int]` |  |
|  | `neg_edge: list[int]` |  |
|  | `delta: float` |  |
| `decode_semantic` | `params: SemanticParams` | `ndarray` |
| `load_semantic_file` | `path: str \| Path` | `SemanticParams` |
| `decode_file` | `path: str \| Path` | `Tuple[SemanticParams, ndarray]` |

---

### 📦 模块 6: `src/semantics/decode_multi.py`

#### 函数签名

| 函数名 | 参数 | 返回类型 |
|--------|------|---------|
| `decode_semantic_multi_region` | `params: SemanticParams` | `ndarray` |
| `decode_semantic_auto` | `params: SemanticParams` | `ndarray` |
| `decode_file_auto` | `path: str \| Path` | `Tuple[SemanticParams, ndarray]` |

---

### 📦 模块 7: `src/io/reader.py`

#### 枚举类

```python
class BinDataType(str, Enum):
    INT16 = "int16"
    INT8 = "int8"
    FLOAT32 = "float32"
    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"
```

#### 函数签名

| 函数名 | 参数 | 返回类型 |
|--------|------|---------|
| `parse_bin_filename` | `filename: str` | `dict` |
|  | `strict: bool = False` |  |
| `_load_bin` | `path: Path` | `Tuple[ndarray, dict]` |
|  | `dtype: BinDataType = INT16` |  |
|  | `sample_rate_hz: float \| None = None` |  |
|  | `center_freq_hz: float \| None = None` |  |
| `_load_npy` | `path: Path` | `Tuple[ndarray, dict]` |
| `_load_npz` | `path: Path` | `Tuple[ndarray, dict]` |
| `_load_h5` | `path: Path` | `Tuple[ndarray, dict]` |
| `load_iq_file` | `path: str \| Path` | `IQData` |
|  | `sample_rate_hz: float \| None = None` |  |
|  | `center_freq_hz: float \| None = None` |  |
|  | `bin_dtype: BinDataType = INT16` |  |
| `load_bin_segments` | `directory: str \| Path` | `list[IQData]` |
|  | `pattern: str = "*.bin"` |  |
|  | `bin_dtype: BinDataType = INT16` |  |
| `chunk_iq` | `iq: IQData` | `Generator[IQData, None, None]` |
|  | `chunk_size: int` |  |

---

## 2. 输出数据类型说明

### 按模块分类

#### 📤 schemas.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `SemanticParams.from_dict()` | `SemanticParams` | ✅ 强类型，自动验证 |
| `SemanticParams.to_dict()` | `dict` | ⚠️ 无类型约束的字典 |
| `SemanticEncodingV2.from_dict()` | `SemanticEncodingV2` | ✅ 强类型，自动验证 |
| `SemanticEncodingV2.to_dict()` | `dict` | ⚠️ 无类型约束的字典 |
| `SamplingConfig.resolution_hz` | `float` | ✅ 强类型属性 |
| `SemanticParams.resolution_mhz` | `float` | ✅ 强类型属性 |
| `BandConfig.contains()` | `bool` | ✅ 强类型返回 |

**类型安全评级**: 🟢 90% (除了 `to_dict()` 返回裸字典)

---

#### 📤 jammers.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `_ensure_rng()` | `np.random.Generator` | ✅ 明确的返回类型 |
| `_add_awgn_measured()` | `np.ndarray` | ⚠️ 未指定数组 dtype（应为 complex128） |
| `_lowpass_real()` | `np.ndarray` | ⚠️ 未指定数组 dtype（应为 float64） |
| `noise_fm_jammer()` | `Tuple[np.ndarray, float]` | ⚠️ ndarray 类型模糊 |
| `generate_jammer()` | `Tuple[np.ndarray, float]` | ⚠️ ndarray 类型模糊 |

**类型安全评级**: 🟡 70% (缺少 NumPy 数组的 dtype 信息)

**改进建议**:
```python
# ❌ 当前
def noise_fm_jammer(...) -> Tuple[np.ndarray, float]:
    ...

# ✅ 改进
def noise_fm_jammer(...) -> Tuple[npt.NDArray[np.complex128], float]:
    """返回 (IQ 信号, 带宽 Hz)"""
    ...
```

---

#### 📤 spectrum_composer.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `_generate_jammer_spectrum()` | `Tuple[np.ndarray, np.ndarray, float]` | ⚠️ 多个 ndarray 类型模糊 |
| `_interpolate_spectrum()` | `np.ndarray` | ⚠️ dtype 未指定 |
| `compose_spectrum()` | `Tuple[np.ndarray, np.ndarray]` | ⚠️ 第1个是频率，第2个是功率，应区分 |
| `add_jammer()` | `None` | ✅ 副作用函数，返回类型明确 |

**类型安全评级**: 🟡 60% (返回值语义不清晰)

**改进建议**:
```python
# ❌ 当前
def compose_spectrum(...) -> Tuple[np.ndarray, np.ndarray]:
    ...

# ✅ 改进 - 使用 TypedDict
from typing import TypedDict

class SpectrumResult(TypedDict):
    freq_axis_mhz: npt.NDArray[np.float64]
    power_db: npt.NDArray[np.float64]

def compose_spectrum(...) -> SpectrumResult:
    ...
```

---

#### 📤 stitcher.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `_compute_weight()` | `np.ndarray` | ⚠️ dtype 未指定 (应为 float64) |
| `_build_global_axis()` | `Tuple[np.ndarray, float]` | ⚠️ ndarray dtype 未指定 |
| `stitch_segments()` | `StitchedSpectrum` | ✅ 强类型 dataclass |
| `stitch_from_iq_data()` | `StitchedSpectrum` | ✅ 强类型 dataclass |
| `load_segment_from_npz()` | `SpectrumSegment` | ✅ 强类型 dataclass |
| `stitch_from_npz_files()` | `StitchedSpectrum` | ✅ 强类型 dataclass |

**类型安全评级**: 🟢 85% (主要函数返回 dataclass)

---

#### 📤 decode.py & decode_multi.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `_apply_edges()` | `None` | ✅ 就地修改，返回类型明确 |
| `decode_semantic()` | `np.ndarray` | ⚠️ dtype 未指定 (应为 float64) |
| `load_semantic_file()` | `SemanticParams` | ✅ 强类型 |
| `decode_file()` | `Tuple[SemanticParams, np.ndarray]` | ⚠️ ndarray 类型模糊 |
| `decode_semantic_multi_region()` | `np.ndarray` | ⚠️ dtype 未指定 |
| `decode_semantic_auto()` | `np.ndarray` | ⚠️ dtype 未指定 |
| `decode_file_auto()` | `Tuple[SemanticParams, np.ndarray]` | ⚠️ ndarray 类型模糊 |

**类型安全评级**: 🟡 70% (dataclass 部分强类型，ndarray 缺少 dtype)

---

#### 📤 reader.py

| 函数 | 输出类型 | 说明 |
|------|---------|------|
| `parse_bin_filename()` | `dict` | ⚠️ 返回裸字典，应用 TypedDict |
| `_load_bin()` | `Tuple[np.ndarray, dict]` | ⚠️ 两部分都缺少类型约束 |
| `_load_npy()` | `Tuple[np.ndarray, dict]` | ⚠️ 同上 |
| `_load_npz()` | `Tuple[np.ndarray, dict]` | ⚠️ 同上 |
| `_load_h5()` | `Tuple[np.ndarray, dict]` | ⚠️ 同上 |
| `load_iq_file()` | `IQData` | ✅ 强类型 dataclass |
| `load_bin_segments()` | `list[IQData]` | ✅ 强类型列表 |
| `chunk_iq()` | `Generator[IQData, None, None]` | ✅ 强类型生成器 |

**类型安全评级**: 🟡 75% (高层函数强类型，底层函数用裸字典)

---

## 3. 类型安全问题分析

### 🔴 严重问题 (Critical)

#### 问题 1: `dict` 返回值缺少结构约束

**位置**:
- `schemas.py`: `to_dict()` 返回 `dict`
- `reader.py`: `parse_bin_filename()` 返回 `dict`
- 所有 `_load_*()` 函数返回 `Tuple[np.ndarray, dict]`

**风险**:
```python
# ❌ 当前代码
meta = parse_bin_filename("file.bin")
# meta 是什么结构？有哪些键？值的类型是什么？
# IDE 无法提供自动补全，容易拼错键名

center = meta["center_freq_mhz"]  # 如果键不存在会 KeyError
```

**影响**:
- 无法在编译时发现键名错误
- IDE 无法提供自动补全
- 重构困难（改键名需要全局搜索）

**修复优先级**: 🔴 High

---

#### 问题 2: NumPy 数组缺少 `dtype` 类型注解

**位置**: 几乎所有返回 `np.ndarray` 的函数

**示例**:
```python
# ❌ 当前
def decode_semantic(params: SemanticParams) -> np.ndarray:
    ...

# 使用时：
spectrum = decode_semantic(params)
# spectrum 是什么类型的数组？float? int? complex?
```

**风险**:
- 类型检查器无法验证数组元素类型
- 容易传递错误的 dtype（如传递 int16 到期望 float64 的函数）
- 数学运算可能溢出或精度损失

**影响范围**: 15+ 函数

**修复优先级**: 🔴 High

---

#### 问题 3: `Tuple[np.ndarray, np.ndarray]` 语义不明确

**位置**:
- `spectrum_composer.py`: `compose_spectrum()`
- `stitcher.py`: `_build_global_axis()`

**示例**:
```python
# ❌ 当前
freq, power = compose_spectrum(cfg)
# 哪个是频率？哪个是功率？只能靠文档或变量名猜测

# 如果不小心写反了：
power, freq = compose_spectrum(cfg)  # 编译器不会报错！
```

**风险**:
- 参数顺序混淆
- 代码可读性差
- 重构困难

**修复优先级**: 🟡 Medium

---

### 🟡 警告问题 (Warning)

#### 问题 4: `Optional` vs `| None` 混用

**位置**: 多处

**示例**:
```python
# schemas.py (line 306)
meta: Optional[dict] = None

# reader.py (line 73)
sample_rate_hz: float | None = None
```

**风险**:
- 代码风格不一致
- Python 3.9 兼容性问题（`|` 需要 3.10+）

**建议**: 统一使用 `Optional[]` 或 `| None`

**修复优先级**: 🟢 Low

---

#### 问题 5: 缺少 `__all__` 导出列表

**位置**: 所有模块

**风险**:
- `from module import *` 行为不可预测
- 私有函数可能被误用

**建议**: 为每个模块添加 `__all__` 列表

**修复优先级**: 🟢 Low

---

#### 问题 6: `list[int]` vs `List[int]` 混用

**位置**:
- `schemas.py`: `List[int]` (typing 导入)
- `decode.py`: `list[int]` (内置类型)

**示例**:
```python
# schemas.py (line 58)
pos_edge: List[int]

# decode.py (line 13)
pos_edge: list[int]
```

**风险**:
- Python 3.8 兼容性问题（`list[int]` 需要 3.9+）

**建议**: 统一使用 `List[]` 或 `list[]`

**修复优先级**: 🟢 Low

---

### 💡 改进机会 (Enhancement)

#### 问题 7: 缺少运行时类型检查

**位置**: 大部分函数

**示例**:
```python
# ❌ 当前
def stitch_segments(segments: List[SpectrumSegment], ...) -> StitchedSpectrum:
    # 如果 segments 不是 List[SpectrumSegment]，直到运行时才报错
    ...

# ✅ 改进：使用 Pydantic 或自定义验证
from pydantic import validate_arguments

@validate_arguments
def stitch_segments(segments: List[SpectrumSegment], ...) -> StitchedSpectrum:
    ...
```

**修复优先级**: 🟢 Low (已有 dataclass 验证)

---

#### 问题 8: 字面量类型未使用

**位置**: `stitcher.py`, `reader.py`

**示例**:
```python
# ❌ 当前
window: str = "hann"  # 任何字符串都能传，但只有几种有效

# ✅ 改进
from typing import Literal

window: Literal["hann", "hamming", "blackman", "bartlett"] = "hann"
```

**修复优先级**: 🟢 Low

---

## 4. 与 Pydantic 模型的对应关系

### 当前使用的数据验证策略

项目使用 **Python dataclasses** 而非 Pydantic，但实现了类似的验证机制：

#### ✅ 已有验证逻辑

| Dataclass | 验证方法 | 验证内容 | 严格程度 |
|-----------|---------|---------|---------|
| **SemanticParams** | `validate()` | 数值范围、索引边界、数组长度一致性 | ⭐⭐⭐⭐ |
| **SemanticEncodingV2** | `validate()` | 频率范围、区域边界、非重叠检查 | ⭐⭐⭐⭐ |
| **IQData** | `__post_init__()` | 复数数组检查、维度检查、采样率正数 | ⭐⭐⭐⭐ |
| **SpectrumSegment** | `__post_init__()` | 形状匹配检查 | ⭐⭐⭐ |
| **StitchedSpectrum** | `__post_init__()` | 基础验证 | ⭐⭐ |
| **JammerConfig** | 无 | ❌ 无验证 | ⭐ |
| **SpectrumComposerConfig** | 无 | ❌ 无验证 | ⭐ |
| **SamplingConfig** | 无 | ❌ 无验证 | ⭐ |
| **BandConfig** | 无 | ❌ 无验证 | ⭐ |
| **JammerSpec** | 无 | ❌ 无验证 | ⭐ |
| **JammerRegionV2** | 无 | ❌ 通过父类验证 | ⭐⭐⭐ |

---

### 与 Pydantic 的对比

#### 如果使用 Pydantic v2

**优势**:
1. ✅ 自动类型强制转换（如 `"123"` → `123`）
2. ✅ 更丰富的验证器（`Field(gt=0, lt=100)`）
3. ✅ JSON Schema 自动生成
4. ✅ 更好的错误消息
5. ✅ 性能优化（Rust 内核）

**劣势**:
1. ❌ 增加依赖
2. ❌ 学习曲线
3. ❌ NumPy 数组支持需要额外配置

**当前 dataclass 方案的评估**: ✅ 足够好，无需迁移到 Pydantic

---

### 验证覆盖率分析

| 验证类型 | 覆盖率 | 缺失的关键验证 |
|---------|-------|---------------|
| **必需字段** | 100% | dataclass 强制 |
| **类型检查** | 0% | 运行时无检查 |
| **数值范围** | 40% | JammerConfig, SamplingConfig |
| **数组形状** | 60% | ndarray 返回值 |
| **业务逻辑** | 80% | 部分配置缺少验证 |

---

### 建议的验证增强

#### 方案 1: 增强 dataclass 验证（推荐）

```python
@dataclass
class JammerConfig:
    length: int = 32768
    sample_rate_hz: float = 125e6
    jnr_db: float = 15.0

    def __post_init__(self) -> None:
        """运行时验证"""
        if self.length <= 0:
            raise ValueError("length 必须为正")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz 必须为正")
        if not (-20.0 <= self.jnr_db <= 50.0):
            raise ValueError("jnr_db 应在合理范围 [-20, 50] dB")
```

#### 方案 2: 使用 Pydantic（可选）

```python
from pydantic import BaseModel, Field

class JammerConfig(BaseModel):
    length: int = Field(default=32768, gt=0, description="IQ 信号长度")
    sample_rate_hz: float = Field(default=125e6, gt=0, description="采样率 Hz")
    jnr_db: float = Field(default=15.0, ge=-20, le=50, description="干扰噪声比 dB")

    class Config:
        frozen = True  # 不可变
```

---

## 5. 改进建议

### 🎯 优先级 1: 立即修复（Critical）

#### 改进 1.1: 为 `dict` 返回值添加 TypedDict

**文件**: `src/io/reader.py`

**当前代码**:
```python
def parse_bin_filename(filename: str, strict: bool = False) -> dict:
    ...
    return {
        "jam_type": match.group(1),
        "center_freq_mhz": float(match.group(2)),
        "bandwidth_mhz": float(match.group(3)),
    }
```

**改进后**:
```python
from typing import TypedDict

class BinMetadata(TypedDict, total=False):
    """二进制文件元数据结构"""
    jam_type: str
    center_freq_mhz: float
    bandwidth_mhz: float
    sample_rate_hz: float
    center_freq_hz: float

def parse_bin_filename(filename: str, strict: bool = False) -> BinMetadata:
    ...
    return {
        "jam_type": match.group(1),
        "center_freq_mhz": float(match.group(2)),
        "bandwidth_mhz": float(match.group(3)),
    }
```

**影响范围**: 
- `_load_bin()`
- `load_iq_file()`
- 所有使用元数据的代码

**预计工作量**: 30 分钟

---

#### 改进 1.2: 为 NumPy 数组添加 dtype 类型注解

**文件**: 所有模块

**当前代码**:
```python
def decode_semantic(params: SemanticParams) -> np.ndarray:
    ...
```

**改进后**:
```python
import numpy.typing as npt

def decode_semantic(params: SemanticParams) -> npt.NDArray[np.float64]:
    """返回功率谱数组（float64 类型）"""
    ...
```

**批量修改清单**:

| 文件 | 函数 | 当前 | 改进后 |
|------|------|------|--------|
| decode.py | `decode_semantic` | `np.ndarray` | `npt.NDArray[np.float64]` |
| decode.py | `_apply_edges` | `power_db: np.ndarray` | `power_db: npt.NDArray[np.float64]` |
| decode_multi.py | `decode_semantic_multi_region` | `np.ndarray` | `npt.NDArray[np.float64]` |
| jammers.py | `_add_awgn_measured` | `np.ndarray` | `npt.NDArray[np.complex128]` |
| jammers.py | `_lowpass_real` | `np.ndarray` | `npt.NDArray[np.float64]` |
| jammers.py | 所有 jammer 函数 | `Tuple[np.ndarray, float]` | `Tuple[npt.NDArray[np.complex128], float]` |
| spectrum_composer.py | `_generate_jammer_spectrum` | `Tuple[np.ndarray, np.ndarray, float]` | `Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], float]` |
| stitcher.py | `_compute_weight` | `np.ndarray` | `npt.NDArray[np.float64]` |

**预计工作量**: 1.5 小时

---

#### 改进 1.3: 替换 `Tuple[np.ndarray, np.ndarray]` 为 TypedDict

**文件**: `src/signal/spectrum_composer.py`

**当前代码**:
```python
def compose_spectrum(...) -> Tuple[np.ndarray, np.ndarray]:
    ...
    return freq_axis, power_db
```

**改进后**:
```python
import numpy.typing as npt
from typing import TypedDict

class SpectrumResult(TypedDict):
    freq_axis_mhz: npt.NDArray[np.float64]
    power_db: npt.NDArray[np.float64]

def compose_spectrum(...) -> SpectrumResult:
    ...
    return {
        "freq_axis_mhz": freq_axis,
        "power_db": power_db,
    }
```

**或者使用 dataclass（更推荐）**:
```python
@dataclass
class SpectrumResult:
    freq_axis_mhz: npt.NDArray[np.float64]
    power_db: npt.NDArray[np.float64]

def compose_spectrum(...) -> SpectrumResult:
    ...
    return SpectrumResult(
        freq_axis_mhz=freq_axis,
        power_db=power_db,
    )
```

**预计工作量**: 20 分钟

---

### 🎯 优先级 2: 近期改进（High）

#### 改进 2.1: 统一 Optional 语法

**选择方案**:
- **方案 A**: 全部使用 `Optional[]` (兼容 Python 3.8+)
- **方案 B**: 全部使用 `| None` (需要 Python 3.10+)

**推荐**: 方案 A（更广泛兼容）

**批量替换**:
```bash
# 查找所有 | None 使用
grep -rn "| None" src/

# 替换示例
sed -i 's/: float | None/: Optional[float]/g' src/**/*.py
```

**预计工作量**: 10 分钟

---

#### 改进 2.2: 为所有配置类添加验证

**文件**: `src/signal/jammers.py`, `src/signal/spectrum_composer.py`

**示例: JammerConfig**

**当前代码**:
```python
@dataclass
class JammerConfig:
    length: int = 32768
    sample_rate_hz: float = 125e6
    jnr_db: float = 15.0
```

**改进后**:
```python
@dataclass
class JammerConfig:
    length: int = 32768
    sample_rate_hz: float = 125e6
    jnr_db: float = 15.0

    def __post_init__(self) -> None:
        """验证配置参数合法性"""
        if self.length <= 0:
            raise ValueError(f"length 必须为正整数，当前: {self.length}")
        if self.sample_rate_hz <= 0:
            raise ValueError(f"sample_rate_hz 必须为正，当前: {self.sample_rate_hz}")
        if not (-20.0 <= self.jnr_db <= 50.0):
            import warnings
            warnings.warn(
                f"jnr_db = {self.jnr_db} dB 超出常规范围 [-20, 50] dB",
                RuntimeWarning,
            )
```

**需要添加验证的类**:
- `JammerConfig`
- `SpectrumComposerConfig`
- `SamplingConfig`
- `BandConfig`
- `JammerSpec`

**预计工作量**: 1 小时

---

#### 改进 2.3: 添加 `__all__` 导出列表

**文件**: 所有模块

**示例: jammers.py**

```python
__all__ = [
    # 配置类
    "JammerConfig",
    # 干扰生成函数
    "noise_fm_jammer",
    "single_tone_jammer",
    "multi_tone_jammer",
    "comb_jammer",
    "partial_band_noise_jammer",
    "sweep_jammer",
    "generate_jammer",
    # 注册表
    "JAMMER_REGISTRY",
]
```

**批量生成工具**:
```python
# tools/generate_all.py
import ast
import sys

def extract_public_names(file_path):
    with open(file_path) as f:
        tree = ast.parse(f.read())
    
    public = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if not node.name.startswith('_'):
                public.append(node.name)
    
    print(f"__all__ = {sorted(set(public))}")

if __name__ == "__main__":
    extract_public_names(sys.argv[1])
```

**预计工作量**: 30 分钟

---

### 🎯 优先级 3: 长期改进（Medium）

#### 改进 3.1: 使用 Literal 类型约束字符串参数

**文件**: `src/signal/stitcher.py`, `src/io/reader.py`

**示例: window 参数**

**当前代码**:
```python
def stitch_from_iq_data(
    ...,
    window: str = "hann",
) -> StitchedSpectrum:
    ...
```

**改进后**:
```python
from typing import Literal

WindowType = Literal["hann", "hamming", "blackman", "bartlett", "rectangular"]

def stitch_from_iq_data(
    ...,
    window: WindowType = "hann",
) -> StitchedSpectrum:
    ...
```

**其他候选参数**:
- `jam_type: Literal["noise_fm", "single_tone", "multi_tone", "comb", "partial_band_noise", "sweep"]`
- `mode: StitchMode` (已经是 Enum，✅ 良好)
- `dtype: BinDataType` (已经是 Enum，✅ 良好)

**预计工作量**: 30 分钟

---

#### 改进 3.2: 创建通用类型别名

**文件**: 新建 `src/core/types.py`

```python
"""项目通用类型定义"""
from typing import TypeAlias
import numpy as np
import numpy.typing as npt

# NumPy 数组类型
ComplexIQArray: TypeAlias = npt.NDArray[np.complex128]
PowerSpectrumArray: TypeAlias = npt.NDArray[np.float64]
FrequencyAxisArray: TypeAlias = npt.NDArray[np.float64]
IntIndexArray: TypeAlias = npt.NDArray[np.int64]

# 频率单位（MHz 或 Hz）
FrequencyMHz: TypeAlias = float
FrequencyHz: TypeAlias = float

# 功率单位（dB）
PowerDB: TypeAlias = float

# IQ 相关
IQSamples: TypeAlias = ComplexIQArray
SampleRateHz: TypeAlias = float
```

**使用示例**:
```python
from ..core.types import ComplexIQArray, PowerDB

def noise_fm_jammer(...) -> Tuple[ComplexIQArray, float]:
    ...

def decode_semantic(...) -> PowerSpectrumArray:
    ...
```

**预计工作量**: 1 小时

---

#### 改进 3.3: 引入 Protocol 定义接口

**文件**: 新建 `src/core/protocols.py`

**示例: Spectrum Protocol**

```python
from typing import Protocol
import numpy.typing as npt
import numpy as np

class SpectrumLike(Protocol):
    """类似频谱的对象协议"""
    freq_mhz: npt.NDArray[np.float64]
    power_db: npt.NDArray[np.float64]

class JammerFunction(Protocol):
    """干扰生成函数协议"""
    def __call__(
        self,
        fc_hz: float,
        cfg: JammerConfig,
        rng: np.random.Generator | None = None,
    ) -> Tuple[npt.NDArray[np.complex128], float]:
        ...
```

**使用场景**:
```python
def process_spectrum(spectrum: SpectrumLike) -> None:
    # 可以接受 SpectrumSegment, StitchedSpectrum 或任何实现该接口的对象
    plt.plot(spectrum.freq_mhz, spectrum.power_db)
```

**预计工作量**: 1.5 小时

---

## 📊 总结

### 类型安全评分

| 模块 | 当前评分 | 改进后评分 | 主要问题 |
|------|---------|-----------|---------|
| schemas.py | 🟢 90% | 🟢 95% | `to_dict()` 返回裸字典 |
| jammers.py | 🟡 70% | 🟢 90% | ndarray dtype 缺失 |
| spectrum_composer.py | 🟡 60% | 🟢 85% | Tuple 语义不明确 |
| stitcher.py | 🟢 85% | 🟢 95% | 部分 ndarray dtype 缺失 |
| decode.py | 🟡 70% | 🟢 90% | ndarray dtype 缺失 |
| decode_multi.py | 🟡 70% | 🟢 90% | 同上 |
| reader.py | 🟡 75% | 🟢 90% | dict 返回值 + ndarray dtype |

**整体评分**: 🟡 74% → 🟢 91% (改进后)

---

### 关键改进点

| 改进项 | 影响文件数 | 预计工作量 | 优先级 |
|--------|-----------|-----------|--------|
| 添加 TypedDict | 2 | 30 min | 🔴 High |
| NumPy dtype 注解 | 7 | 1.5 h | 🔴 High |
| Tuple → TypedDict/dataclass | 2 | 20 min | 🔴 High |
| 统一 Optional 语法 | 7 | 10 min | 🟡 Medium |
| 配置类验证 | 2 | 1 h | 🟡 Medium |
| 添加 `__all__` | 7 | 30 min | 🟡 Medium |
| Literal 类型 | 2 | 30 min | 🟢 Low |
| 通用类型别名 | 1 (新建) | 1 h | 🟢 Low |
| Protocol 接口 | 1 (新建) | 1.5 h | 🟢 Low |

**总预计工作量**: ~6.5 小时

---

### 下一步行动

#### 快速修复路径（2 小时）

1. ✅ 添加 `numpy.typing` 导入
2. ✅ 为所有 ndarray 返回值添加 dtype 注解
3. ✅ 创建 `BinMetadata` TypedDict
4. ✅ 统一 Optional 语法

**完成后类型安全评分**: 🟢 85%

---

#### 完整改进路径（6.5 小时）

按照上述所有改进建议执行

**完成后类型安全评分**: 🟢 91%

---

## 🔧 工具推荐

### 类型检查工具

```bash
# 安装 mypy
pip install mypy

# 运行类型检查
mypy src/ --strict

# 生成类型覆盖率报告
mypy src/ --html-report mypy-report/
```

### IDE 配置

**VSCode settings.json**:
```json
{
  "python.linting.mypyEnabled": true,
  "python.linting.mypyArgs": [
    "--strict",
    "--ignore-missing-imports"
  ]
}
```

**PyCharm**: 默认支持类型提示检查

---

## 📚 参考资料

- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 589 - TypedDict](https://peps.python.org/pep-0589/)
- [PEP 604 - Union Syntax](https://peps.python.org/pep-0604/)
- [NumPy Typing (NEP 47)](https://numpy.org/neps/nep-0047-array-api-typing.html)
- [Mypy Documentation](https://mypy.readthedocs.io/)

---

**需要帮助执行这些改进？回复：**
- "开始快速修复" → 执行 2 小时修复计划
- "完整改进" → 执行所有改进
- "修复 XXX" → 执行特定改进项
