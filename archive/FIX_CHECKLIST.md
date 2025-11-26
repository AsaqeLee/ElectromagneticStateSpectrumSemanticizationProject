# 代码修复检查清单

> 基于 CODE_REVIEW_REPORT.md，按优先级排列

---

## ⏰ 阶段1：立即修复（预计 1-2 天）

### ✅ Task 1.1: 完善 SemanticParams.validate()

**文件**: `src/core/schemas.py:92-107`  
**优先级**: 🔴 Critical  
**预计时间**: 30 分钟

- [ ] 添加 `pos_edge` 索引边界验证
- [ ] 添加 `neg_edge` 索引边界验证
- [ ] 添加 `pos_edge/neg_edge` 长度一致性检查
- [ ] 调整检查顺序（freq 范围检查提前）
- [ ] 修改 `from_dict()` 自动调用 `validate()`
- [ ] 编写单元测试验证边界条件

**验证命令**:
```bash
pytest tests/test_schemas.py::test_semantic_params_validate -v
```

---

### ✅ Task 1.2: reader.py 添加异常处理

**文件**: `src/io/reader.py:65-124`  
**优先级**: 🔴 Critical  
**预计时间**: 45 分钟

**子任务**:
- [ ] `_load_bin()`: 添加文件存在性检查
- [ ] `_load_bin()`: 添加文件大小预检查
- [ ] `_load_bin()`: 验证交织格式长度（必须为偶数）
- [ ] `_load_bin()`: 添加 IOError/PermissionError 捕获
- [ ] `_load_npy()`: 添加异常处理
- [ ] `_load_npz()`: 修复字典推导式（见 Task 1.3）
- [ ] `_load_h5()`: 添加异常处理
- [ ] 编写测试用例（空文件、损坏文件、权限错误）

**验证命令**:
```bash
pytest tests/test_io_reader.py::test_load_bin_error_handling -v
```

---

### ✅ Task 1.3: 修复 _load_npz 字典推导式

**文件**: `src/io/reader.py:140`  
**优先级**: 🔴 Critical  
**预计时间**: 20 分钟

- [ ] 替换不安全的 `.item()` 调用
- [ ] 处理标量、单元素、多元素数组的不同情况
- [ ] 添加 IOError 异常处理
- [ ] 测试包含多维数组的 npz 文件

**验证命令**:
```bash
pytest tests/test_io_reader.py::test_load_npz_multidim_meta -v
```

---

### ✅ Task 1.4: stitcher.py 添加范围预检查

**文件**: `src/signal/stitcher.py:145-169`  
**优先级**: 🔴 Critical  
**预计时间**: 30 分钟

- [ ] 在拼接前检查每个分段与全局轴的重叠
- [ ] 如果完全超出范围，抛出 ValueError
- [ ] 如果重叠率 < 50%，发出 warning
- [ ] 添加测试用例（完全超出、部分超出）

**验证命令**:
```bash
pytest tests/test_stitcher.py::test_stitch_out_of_range -v
```

---

### ✅ Task 1.5: 添加 decode_multi.py 边界注释

**文件**: `src/semantics/decode_multi.py:60-64, 73`  
**优先级**: 🔴 Critical  
**预计时间**: 10 分钟

- [ ] 添加闭区间语义说明注释
- [ ] 说明 `[start:end+1]` 与数学闭区间的对应关系
- [ ] 对比 `decode.py` 的差异并注释原因

**验证**: 代码审查

---

## ⏰ 阶段2：近期修复（预计 1 周）

### ⚡ Task 2.1: _ensure_rng 类型验证

**文件**: `src/signal/jammers.py:32-33`  
**优先级**: ⚡ Warning  
**预计时间**: 15 分钟

- [ ] 添加 `isinstance()` 类型检查
- [ ] 提供清晰的错误消息和使用建议
- [ ] 测试传入错误类型（int, list, None）

---

### ⚡ Task 2.2: 更新 spectrum_composer.py 注释

**文件**: `src/signal/spectrum_composer.py:83-88`  
**优先级**: ⚡ Warning  
**预计时间**: 10 分钟

- [ ] 修正注释：说明是相对功率（[-∞, 0] dB）而非 [0, 1]
- [ ] 添加后续恢复绝对功率的说明

---

### ⚡ Task 2.3: decode.py 边缘增强限制

**文件**: `src/semantics/decode.py:24-26`  
**优先级**: ⚡ Warning  
**预计时间**: 20 分钟

- [ ] `_apply_edges()` 添加 `noise_floor_db` 参数
- [ ] 负边缘增强后检查不低于 `noise_floor - 3dB`
- [ ] 更新调用处传入 `params.menxian`
- [ ] 测试边缘case（底噪 -120dB, 边缘增强 5dB）

---

### ⚡ Task 2.4: SemanticEncodingV2 自动排序

**文件**: `src/core/schemas.py:195-202`  
**优先级**: ⚡ Warning  
**预计时间**: 25 分钟

**选择方案**:
- [ ] 方案A：`from_dict()` 自动排序 `jammer_regions`
- [ ] 方案B：`validate()` 验证排序并给出明确错误
- [ ] 推荐：**方案A**（用户友好）

**实现**:
- [ ] 在 `from_dict()` 中添加 `regions.sort(key=lambda r: r.start_bin)`
- [ ] 在 `validate()` 中验证排序（防止手动构造未排序对象）
- [ ] 添加测试用例（未排序输入）

---

### ⚡ Task 2.5: parse_bin_filename strict 模式

**文件**: `src/io/reader.py:40-62`  
**优先级**: ⚡ Warning  
**预计时间**: 20 分钟

- [ ] 添加 `strict: bool = False` 参数
- [ ] strict=True 时抛出明确的 ValueError
- [ ] 错误消息包含格式说明和示例
- [ ] 在 `load_iq_file()` 中使用 strict 模式并捕获异常

---

### ⚡ Task 2.6-2.12: 其他警告修复

| Task | 文件 | 内容 | 时间 |
|------|------|------|------|
| 2.6 | stitcher.py:107 | `np.arange` → `np.linspace` | 15min |
| 2.7 | spectrum_composer.py:146 | 移除重复检查 | 5min |
| 2.8 | decode.py:51 | 添加数组长度检查 | 10min |
| 2.9 | jammers.py:90,134,159 | 统一 `rng.integers()` 行为 | 20min |
| 2.10 | reader.py:144 | `_load_h5()` 异常处理 | 15min |
| 2.11 | - | 修复 searchsorted 边界对齐 | 30min |
| 2.12 | - | fenbianlv=1 边界禁止 | 10min |

---

## ⏰ 阶段3：长期改进（预计 2-4 周）

### 💡 Task 3.1: 提取硬编码常量

**文件**: `src/signal/jammers.py`  
**优先级**: 💡 Minor  
**预计时间**: 2 小时

- [ ] 扩展 `JammerConfig` 添加干扰类型特定参数
- [ ] 更新所有 jammer 函数使用配置参数
- [ ] 添加配置示例和文档
- [ ] 向后兼容测试

---

### 💡 Task 3.2: 添加 __all__ 导出列表

**文件**: 所有模块  
**优先级**: 💡 Minor  
**预计时间**: 1 小时

- [ ] `src/core/schemas.py`
- [ ] `src/signal/jammers.py`
- [ ] `src/signal/spectrum_composer.py`
- [ ] `src/signal/stitcher.py`
- [ ] `src/semantics/decode*.py`
- [ ] `src/io/reader.py`

---

### 💡 Task 3.3: 补充单元测试

**优先级**: 💡 Minor  
**预计时间**: 1 周

**测试覆盖**:
- [ ] `test_schemas.py`: 边界条件（fenbianlv=1, 空边缘，sinr长度）
- [ ] `test_io_reader.py`: 异常情况（文件不存在、损坏、权限）
- [ ] `test_stitcher.py`: 边界case（超出范围、重叠、空分段）
- [ ] `test_decode.py`: 边缘增强限制、sinr 长度匹配
- [ ] `test_spectrum_composer.py`: Nyquist 边界、JNR 范围

**目标覆盖率**: 85%+

---

### 💡 Task 3.4: 提取验证逻辑

**优先级**: 💡 Minor  
**预计时间**: 3 小时

- [ ] 创建 `src/core/validators.py`
- [ ] 实现 `validate_bin_index()`
- [ ] 实现 `validate_bin_range()`
- [ ] 实现 `validate_index_array()`
- [ ] 重构现有代码使用新验证器
- [ ] 编写验证器单元测试

---

### 💡 Task 3.5: 策略模式重构拼接器

**文件**: `src/signal/stitcher.py`  
**优先级**: 💡 Minor  
**预计时间**: 4 小时

- [ ] 定义 `StitchStrategy` Protocol
- [ ] 实现 `MaxStitchStrategy`
- [ ] 实现 `MeanStitchStrategy`
- [ ] 实现 `FirstStitchStrategy`
- [ ] 重构 `stitch_segments()` 使用策略
- [ ] 确保向后兼容
- [ ] 性能测试（确保无回归）

---

### 💡 Task 3.6: 实现完整编码器

**优先级**: 💡 Minor  
**预计时间**: 2 周

**目标**: 从频谱自动提取语义参数

- [ ] 设计编码算法（边缘检测、区域分割、JNR 估计）
- [ ] 实现 v1 编码器
- [ ] 实现 v2 编码器
- [ ] 编码-解码闭环测试
- [ ] 误差分析和优化
- [ ] 文档和使用示例

---

### 💡 Task 3.7: 补充 API 文档

**优先级**: 💡 Minor  
**预计时间**: 1 周

创建 `docs/API_REFERENCE.md`:
- [ ] 核心数据结构详解
- [ ] 函数签名和参数说明
- [ ] 边界条件行为
- [ ] 错误处理规范
- [ ] 使用示例
- [ ] 常见陷阱和最佳实践

---

## 📊 进度跟踪

### 阶段1（Critical）

| Task | 状态 | 负责人 | 完成日期 |
|------|------|--------|---------|
| 1.1 SemanticParams.validate() | ⬜ Pending | - | - |
| 1.2 reader.py 异常处理 | ⬜ Pending | - | - |
| 1.3 _load_npz 修复 | ⬜ Pending | - | - |
| 1.4 stitcher.py 预检查 | ⬜ Pending | - | - |
| 1.5 decode_multi.py 注释 | ⬜ Pending | - | - |

**阶段1完成标准**: 所有 Critical 问题修复，pytest 通过

---

### 阶段2（Warning）

| Task | 状态 | 负责人 | 完成日期 |
|------|------|--------|---------|
| 2.1 _ensure_rng 验证 | ⬜ Pending | - | - |
| 2.2-2.5 注释和文档 | ⬜ Pending | - | - |
| 2.6-2.12 其他警告 | ⬜ Pending | - | - |

**阶段2完成标准**: 所有 Warning 问题修复，代码审查通过

---

### 阶段3（Minor）

| Task | 状态 | 负责人 | 完成日期 |
|------|------|--------|---------|
| 3.1 提取常量 | ⬜ Pending | - | - |
| 3.2 __all__ | ⬜ Pending | - | - |
| 3.3 单元测试 | ⬜ Pending | - | - |
| 3.4 验证逻辑 | ⬜ Pending | - | - |
| 3.5 策略模式 | ⬜ Pending | - | - |
| 3.6 编码器 | ⬜ Pending | - | - |
| 3.7 API 文档 | ⬜ Pending | - | - |

**阶段3完成标准**: 代码质量评分达到 8.5/10，测试覆盖率 85%+

---

## 🎯 预期成果

### 阶段1完成后

- ✅ 消除所有运行时崩溃风险
- ✅ 数据验证完整性达到 95%+
- ✅ 文件 IO 异常处理覆盖 100%

### 阶段2完成后

- ✅ 代码可读性提升 30%
- ✅ 错误消息准确性提升 50%
- ✅ 边界条件处理完备

### 阶段3完成后

- ✅ 代码质量评分: 7.5 → 8.5
- ✅ 测试覆盖率: 未知 → 85%+
- ✅ 可维护性显著提升
- ✅ 功能完整性（编码-解码闭环）

---

## 📝 使用说明

### 如何使用本清单

1. **按阶段执行**: 严格按照阶段1→2→3的顺序
2. **完成标记**: 勾选 `[ ]` → `[x]` 表示完成
3. **验证命令**: 每个 task 完成后运行验证命令
4. **代码审查**: 关键修改需要 peer review
5. **更新文档**: 修复完成后更新 CHANGELOG.md

### Git 提交规范

```bash
# 阶段1
git commit -m "fix(schemas): add edge index validation to SemanticParams.validate() [C1]"

# 阶段2
git commit -m "refactor(reader): improve error handling in _load_bin() [W2]"

# 阶段3
git commit -m "feat(validators): extract common validation logic [M4]"
```

### 测试命令

```bash
# 运行所有测试
pytest -v

# 运行特定模块测试
pytest tests/test_schemas.py -v

# 运行覆盖率检查
pytest --cov=src --cov-report=html

# 运行类型检查
mypy src/
```

---

**创建日期**: 2025-01-25  
**最后更新**: -  
**状态**: ⬜ Not Started

**下一步行动**: 开始阶段1 - Task 1.1
