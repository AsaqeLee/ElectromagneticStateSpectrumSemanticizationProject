# CLI 干扰类型选择改动记录（Linus 视角）

- 日期：2025-11-26
- 相关文件：`scripts/spectrum_cli.py`

## 变更动机

- 交互式 CLI 中，用户需要手工输入 `noise_fm`、`single_tone` 等英文枚举字符串，既长又容易打错；
- 仓库整体风格希望减少“中文提示 + 英文/拼音混杂输入”的割裂感，在不破坏内部 API 的前提下改善交互体验。

## 具体改动

1. 新增干扰类型选项表

- 在 `scripts/spectrum_cli.py` 顶部新增常量：
  - `JAMMER_TYPE_CHOICES = [(内部英文标识, 中文描述), ...]`
  - 包含六类干扰：`noise_fm`、`single_tone`、`multi_tone`、`comb`、`partial_band_noise`、`sweep`
- 设计原则：
  - 对外交互展示中文描述 + 英文标识（括号中），方便理解和与文档对应；
  - 内部仍然使用既有英文 `jam_type` 字符串，以保持与原有 pipeline/测试完全兼容。

2. 重写任务一的干扰选择交互

- 在 `task1_interactive()` 中：
  - 原逻辑：提示可用类型字符串，循环中要求用户直接输入完整英文干扰类型名，并做字符串校验；
  - 新逻辑：首次展示一个数字菜单：
    - `1. 宽带调频噪声 (noise_fm)`
    - `2. 单音干扰 (single_tone)`
    - ...
  - 循环中：
    - 使用 `get_int("选择干扰类型编号", 2)` 读取编号（默认选 `single_tone`）；
    - 校验编号范围 `[1, len(JAMMER_TYPE_CHOICES)]`，超出则提示“无效编号”并重试；
    - 通过 `JAMMER_TYPE_CHOICES[type_index - 1][0]` 映射回内部 `jam_type`；
    - 其余参数（中心频率、JNR）保持原有交互与默认值。

- 逻辑上的不变量：
  - 生成的 `cfg.jammers` 列表依旧是 `JammerSpec(jam_type=..., center_freq_mhz=..., jnr_db=...)`；
  - 支持的干扰类型集合未变，只是输入方式从“字符串”变成“数字菜单 + 映射”。

## 验证

- 运行 `pytest tests/test_cli_bin_support.py -q`：
  - 结果：3 通过（3 passed），仅有与测试返回值风格相关的 PytestReturnNotNoneWarning，与本次改动无关。
  - 说明：导入路径、BIN 相关 CLI 支撑行为未被破坏。

## 对“命名风格统一”的讨论

- 当前改动只在 CLI 交互层减少了“必须手动输入英文枚举”的摩擦，并让用户界面以中文描述为主；
- 核心数据结构（如 `SemanticParams.yonghu/menxian/...`）未更名，以避免破坏既有 JSON/测试约定；
- 如果后续要进一步“统一命名风格”，建议路线是：
  - 不改已有字段名，而是在 API 层提供英文别名/包装；
  - 保持磁盘格式与现有测试严格兼容，逐步迁移，而不是一次性硬切。

