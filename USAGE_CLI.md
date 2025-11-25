# 电磁态频谱语义化工程 - CLI 使用指南

本指南面向**使用者**，说明如何通过命令行 CLI 完成三大任务：

1. 干扰信号功率谱合成（任务一）；  
2. 频谱分段拼接（任务二）；  
3. 语义参数频谱恢复（任务三，支持 v1/v2）。  

工程提供两类 CLI：

- `spectrum_cli.py`：交互式 CLI，适合人工调参与可视化；  
- `spectrum_batch.py`：批处理 CLI，适合脚本/自动化调用。  

---

## 一、交互式 CLI：`spectrum_cli.py`

### 1.1 启动

```bash
python spectrum_cli.py
```

你会看到类似主菜单：

```text
【主菜单】
  1. 任务一：干扰功率谱合成 (30-2500 MHz)
  2. 任务二：频谱分段拼接
  3. 任务三：语义参数频谱恢复
  4. 查看使用指南
  5. 退出
```

### 1.2 任务一：干扰功率谱合成

**目的**：在 30–2500 MHz 频段内任意组合六类干扰信号，生成宽带功率谱。  

**支持的干扰类型**：
- `noise_fm` - 噪声调频干扰  
- `single_tone` - 单音干扰  
- `multi_tone` - 多音干扰  
- `comb` - 梳状谱干扰  
- `partial_band_noise` - 部分带宽噪声干扰  
- `sweep` - 扫频干扰  

**交互流程概览**：
1. 设置频段范围（默认 `30–2500 MHz`）；  
2. 设置频率分辨率（默认 `1 MHz`）；  
3. 设置底噪功率（默认 `-120 dB`）；  
4. 添加一个或多个干扰（类型、中心频率、JNR）；  
5. 生成功率谱并选择是否保存为：
   - `.npz`（`freq_mhz`, `power_db`）；
   - `.png` 频谱图；
   - （可选）干扰配置 JSON。

输出文件示例：

- `composed_spectrum.npz` – 频谱数据（`freq_mhz`, `power_db`）；  
- `jammer_config.json` – 干扰配置记录；  
- `composed_spectrum.png` – 可视化图像。  

### 1.3 任务二：频谱分段拼接

**目的**：将多个 200 MHz 频谱分段拼接为完整宽带频谱。  

典型输入：来自任务一/真实数据的 `.npz` 分段文件或 `.bin` 分段文件。  

交互流程（典型）：

1. 逐个选择/加载频谱分段（`.npz`）；  
2. 选择拼接模式：  
   - `MAX` – 取最大值（适合干扰检测）；  
   - `MEAN` – 简单平均（降低噪声）；  
   - `WEIGHTED_MEAN` – 加权平均（窗口中心权重大）；  
3. 设置未覆盖区域填充值（如 `-180 dB`）；  
4. 执行拼接并保存。  

输出文件示例：

- `stitched_spectrum.npz` – 拼接后的宽带频谱和覆盖图；  
- `stitched_spectrum.png` – 频谱图像。  

> 对真实 `.bin` 数据的拼接，更推荐使用 `spectrum_batch.py stitch` 或 `src/pipeline/stitch_real_data.py`，交互式 CLI 适合快速试验/教学演示。

### 1.4 任务三：语义参数频谱恢复

**目的**：从语义化参数恢复功率谱，实现**“语义压缩 → 本地重构”**。  

CLI 支持两种语义格式：

- v1：`SemanticParams`（单区域 + pos_edge/neg_edge 边缘列表）；  
- v2：`SemanticEncodingV2`（多区域 `jammer_regions`）。  

在交互式任务三中，典型流程是：

1. 选择语义格式（v1/v2）（如果 CLI 已支持该开关）；  
2. 指定语义 JSON 文件；  
3. （可选）指定参考谱 `.npz` 用于对比；  
4. 恢复功率谱并保存结果（`.npz` + `.png`）。  

> 目前交互式 CLI 默认使用 v1 格式；v2 推荐通过 batch CLI 或 pipeline 调用，详见下一节。

---

## 二、批处理 CLI：`spectrum_batch.py`

批处理 CLI 提供四个子命令：

- `compose` – 干扰功率谱合成（任务一）；  
- `stitch` – 频谱分段拼接（任务二）；  
- `decode` – v1（`SemanticParams`）语义恢复；  
- `decode-v2` – v2（`SemanticEncodingV2`，`jammer_regions`）语义恢复。  

### 2.1 `compose` - 合成干扰功率谱

```bash
python spectrum_batch.py compose \
  --jammer single_tone:500:20 \
  --jammer sweep:1200:18 \
  -o data/composed.npz \
  --plot data/composed.png
```

关键参数：

- `--jammer type:freq:jnr`：干扰配置，可多次出现；  
- `--freq-min/--freq-max`：频段范围（默认 30–2500 MHz）；  
- `--resolution`：频率分辨率（默认 1 MHz）；  
- `--noise-floor`：底噪功率（默认 -120 dB）；  
- `--seed`：随机种子（可选，便于复现）；  
- `--show`：生成图后直接弹出窗口；  
- `--plot`：保存 PNG 图路径。  

输出：  
- `-o/--output` 指定的 `.npz` 文件（包含 `freq_mhz` 和 `power_db`）；  
- 可选 `--plot` 指定的 `.png` 文件。  

### 2.2 `stitch` - 频谱分段拼接

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

参数说明：

- `--input-dir`：包含分段 `.bin` 文件的目录；  
- `--pattern`：文件匹配模式（默认 `*.bin`）；  
- `--dtype`：数据类型（`int16/int8/float32/complex64`）；  
- `--mode`：拼接模式（`max/mean/weighted_mean`）；  
- `--fft-size`：FFT 点数（默认 8192/262144）；  
- `-o/--output`：输出 `.npz`（含 `freq_mhz`/`power_db`/`coverage_map`）；  
- `--plot`：输出 PNG 频谱图；  
- `--show`：是否在屏幕上显示图像。  

> `stitch` 内部调用 `src/pipeline/stitch_real_data.stitch_from_bin_directory`，后者基于 `src/io.reader.load_bin_segments` 统一处理 `.bin` 文件。  
> 文件命名建议采用类似 `single_130MHz_204.8MHz_11h14m22s.bin` 的格式，以便自动推断中心频率/带宽。

### 2.3 `decode` - 语义恢复（v1 / 自动多区域）

```bash
python spectrum_batch.py decode \
  --input data/demo_semantic_v1.json \
  -o data/recovered_v1.npz \
  --plot data/recovered_v1.png
```

行为说明：

- `--input`：v1 语义 JSON（字段结构与 `SemanticParams` 一致）；  
- 内部使用 `decode_semantic_auto`：  
  - 若 `pos_edge` 为空/单个 → 使用单区域 `decode_semantic`；  
  - 若 `pos_edge` 含多元素 → 使用 `decode_semantic_multi_region` 支持多区域；  
- `-o/--output`：输出恢复谱，npz 中包含 `freq_mhz` 和 `power_db`；  
- `--plot`/`--show`：可选图像输出/展示。  

### 2.4 `decode-v2` - 语义恢复（v2 / jammer_regions）

```bash
python spectrum_batch.py decode-v2 \
  --input data_semantic/semantic_case01.json \
  -o data/recovered_v2_case01.npz \
  --plot data/recovered_v2_case01.png
```

参数说明：

- `--input`：v2 语义 JSON，结构示例：

  ```json
  {
    "freq_min_mhz": 30.0,
    "freq_max_mhz": 2500.0,
    "num_bins": 2471,
    "noise_floor_db": -80.0,
    "jammer_regions": [
      {"start_bin": 50, "end_bin": 90, "jnr_db": 25.0},
      {"start_bin": 470, "end_bin": 490, "jnr_db": 20.0}
    ]
  }
  ```

- v2 解码使用 `decode_semantic_v2`：  
  - 初始化长度为 `num_bins` 的谱线为 `noise_floor_db`；  
  - 对每个区域 `[start_bin, end_bin]` 设置为 `noise_floor_db + jnr_db`。  

输出：  
- `.npz` – `freq_mhz` / `power_db`；  
- `.png` – 直观频谱图（如指定 `--plot`）。  

---

## 三、完整示例：从拼接到语义评估

1. **拼接参考谱**：

   ```bash
   python spectrum_batch.py stitch \
     --input-dir data_segment \
     --pattern "*.bin" \
     --dtype int16 \
     --mode max \
     --fft-size 262144 \
     -o data/stitched_30_2500.npz
   ```

2. **使用 v1 语义恢复并评估**：

   ```bash
   python spectrum_batch.py decode \
     --input data/demo_semantic_v1.json \
     -o data/recovered_v1.npz

   python -m src.pipeline.semantic_eval \
     --reference data/stitched_30_2500.npz \
     --semantic data/demo_semantic_v1.json \
     --report data/semantic_eval_v1.json
   ```

3. **使用 v2 语义恢复并评估**：

   ```bash
   # 生成 v2 测试语义
   python -m src.pipeline.semantic_generate --num-samples 10

   python spectrum_batch.py decode-v2 \
     --input data_semantic/semantic_case01.json \
     -o data/recovered_v2_case01.npz

   python -m src.pipeline.semantic_eval_v2 \
     --reference data/stitched_30_2500.npz \
     --semantic data_semantic/semantic_case01.json \
     --report data/semantic_eval_v2_case01.json
   ```

---

## 四、常见问题

**Q1: `stitch` 提示“未找到匹配文件”？**  
A: 检查 `--input-dir` 和 `--pattern`，确认目录存在且文件后缀/命名符合预期。此外，`.bin` 文件需要是交织 I/Q 格式（详见 `src/io/reader.py`）。  

**Q2: `decode` 和 `decode-v2` 有什么区别？**  
A:  
- `decode` 接收 v1 格式的语义 JSON（`SemanticParams`），并自动选择单/多区域解码；  
- `decode-v2` 接收 v2 格式（`SemanticEncodingV2` + `jammer_regions`），适合多区域、稀疏场景，是推荐的新格式。  

**Q3: 为何语义恢复与参考谱对不上？**  
A: 请检查：  
1. 参考谱的频率范围/分辨率是否与语义参数一致（`semantic_eval(_v2)` 会做严格校验）；  
2. `num_bins` 与 `fenbianlv`、`start/end`、`start_bin/end_bin` 的关系是否合理；  
3. 对于 v1，多区域参数应使用 `pos_edge/neg_edge` 成对定义。  

如需更细节的说明和示例，请参考：  
- `USAGE_GUIDE.md` – Python/pipeline 使用指南；  
- `docs/semantic_encoding_requirements.md` – v2 语义规范；  
- `FIXES_SUMMARY.md` – 核心修复点与设计决策。  

