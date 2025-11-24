# 电磁态代码解释文档

## 1. 背景与目标

本仓库依照《频谱语义化表征与频谱恢复》spec 构建最小可行实现，围绕三个核心任务：

1. 任务 1：仿真或读取 IQ 数据，提供后续频谱计算基线；
2. 任务 2：在 30–225 MHz、225–2500 MHz 及若干 200 MHz 窗口下拼接参考频谱；
3. 任务 3：消费甲方给定的语义参数，恢复估计频谱并与参考谱对比。

整套代码定位为单机离线工具链，依赖 `miniconda3` 的 `xd_torch` 环境（Python 3.8.20）。

## 2. 依赖与运行方式

- 依赖文件：`requirements.txt`（NumPy/SciPy/h5py/matplotlib/PyYAML/pytest）。
- 激活方式：
  ```bash
  conda activate xd_torch
  pip install -r requirements.txt
  ```
- 测试指令（已验证）：`PYTHONIOENCODING=utf-8 conda run -n xd_torch pytest`

## 3. 目录与模块说明

| 目录 | 关键文件 | 说明 |
| --- | --- | --- |
| `src/core` | `schemas.py`, `config.py` | 定义采样/频段/语义/IQ dataclass 以及 `ProjectConfig` 与 `load_config`，所有模块共享统一数据结构；`config.py` 中的 `DEFAULT_WINDOW_CENTERS_MHZ` 固定了 13 个 200 MHz 采集中心频点（130～2400 MHz）。 |
| `src/io` | `reader.py` | 支持 `.npy/.npz/.h5` IQ 文件读取与切片，确保 `sample_rate_hz`、`center_freq_hz` 元数据就绪。 |
| `src/signal` | `segmentation.py`, `spectrum.py` | `segmentation` 生成频轴与掩码（30–225、225–2500、13 个 200 MHz 窗口）；`spectrum` 完成 FFT 功率谱、掩码聚合与拼接。 |
| `src/semantics` | `decode.py` | `SemanticParams` → 频谱：先构建底噪，再在 `[start,end]` 区间叠加 `sinr`，并依据 `pos_edge/neg_edge` 微调边缘。 |
| `src/pipeline` | `simulate_iq.py`, `analyze_comb.py`, `overlay_comb.py`, `stitch_multi.py`, `semantic_eval.py` | 任务 1/2/3 的主干 CLI 及调试脚本。`simulate_iq` 用于仿真 IQ 与 PSD 绘制；`analyze_comb` 分析单个 comb 采样；`overlay_comb` 叠加两个中心频点的 PSD；`stitch_multi` 从目录中拼接多分片宽带谱；`semantic_eval` 负责语义恢复评估。 |
| `src/viz` | `plots.py` | 绘制谱线及语义恢复对比的封装。 |
| `tests` | `test_segmentation.py` 等 | Pytest 级别验证，确保频段掩码、语义恢复、FFT 峰值等关键逻辑可靠。 |

## 4. 数据结构核心要点

- `SamplingConfig`：统一 FFT 尺寸、采样率、中心频率；`resolution_hz` 自动计算。
- `BandConfig`：以 MHz 为单位描述频段，提供 `contains` 方法减少重复判断。
- `SemanticParams`：严格校验 `start/end/fenbianlv/sinr` 的长度关系，避免语义参数越界。
- `IQData`：确保 IQ 数据为一维复数组，并携带 `sample_rate_hz`、`center_freq_hz`，同时暴露 `duration_seconds`、`num_samples`。
- `ProjectConfig`：聚合所有配置（采样、频段、窗口中心、输出目录），各 pipeline 只需依赖该对象即可获得一致行为。

## 5. 核心流程与算法

1. **频谱估计**（`signal.spectrum.compute_power_spectrum`）  
   - 取 FFT 大小，零填/截断补齐；
   - 使用 `scipy.signal.get_window`（默认 Hann）加窗，提高谱动态范围；
   - `fftshift` + `np.fft.fftfreq` 生成真实频轴，单位 MHz；
   - 计算功率（`|FFT|^2 / N`）后转 dB。

2. **频段掩码**（`signal.segmentation.segment_bands`）  
   - 针对 `BandConfig` 与 200 MHz 窗口分别生成掩码；
   - 每个掩码都在 `masks` 字典中标识为 `band::` 或 `window::` 前缀，便于后续灵活组合。

3. **分段拼接**  
   - 单文件分片拼接（`signal.spectrum.stitch_spectrum`）：  
     - 输入：频轴、掩码字典、各段功率；  
     - 逻辑：若段值只有单个元素则把掩码范围填同值，否则按位写入；初始值为 -180 dB，避免未覆盖区域出现 NaN。  
   - 多文件宽带拼接（`pipeline.stitch_multi`）：  
     - 从目录中读取多个 int16 I/Q 分片（命名包含中心频率，或使用 `--ignore-names` 按默认中心频率顺序绑定）；  
     - 对每段分别计算绝对频率上的 PSD，构造统一频率轴后在重叠区使用“取最大值”策略合并，最终得到 30–2500 MHz 的宽带功率谱。

4. **语义恢复**（`semantics.decode.decode_semantic`）  
   - 以 `menxian` 生成底噪数组；
   - `sinr` 为单值：全段加同样增益；数组：按位填充；
   - `pos_edge`、`neg_edge` 通过 ±`edge_delta`（取 `sinr` 绝对值最大值）调节边缘；
   - 输出的谱长度固定为 `fenbianlv`，便于直接与参考谱对齐。

5. **流水线脚本**  
   - `simulate_iq`：指定载波列表、噪声电平，输出 `npz`（含 IQ + 采样率），并可直接生成 PSD 图；  
   - `analyze_comb`：对指定 comb 采样文件执行 FFT，输出 PSD 图与谱峰位置/间隔等特性；  
   - `overlay_comb`：将两个不同中心频率的 comb 文件在统一绝对频率轴下叠加展示，用于验证分片在频域上的拼接关系；  
   - `stitch_multi`：从目录中读取多分片 IQ（例如 13 段 200 MHz 采集），按中心频率在绝对频率轴上拼接成宽带功率谱；  
   - `semantic_eval`：读取参考谱（`npy/npz`），载入语义 JSON，计算 MAE/RMSE/最大误差并输出报告。

## 6. 测试覆盖

- `tests/test_segmentation.py`：验证 `band::low` 存在且至少一个 200 MHz 窗口非空；同时检查 FFT 频轴范围正确。
- `tests/test_semantics.py`：构建简单语义参数，确认 `start` 区间的功率提升和边缘调整行为。
- `tests/test_spectrum.py`：对 1 MHz 正弦信号执行 FFT，断言峰值频率落在 1 MHz 附近。
- 运行命令：`PYTHONIOENCODING=utf-8 conda run -n xd_torch pytest`（若 Windows 控制台编码异常，可固定 `PYTHONIOENCODING`）。

## 7. 如何扩展

- **更复杂的语义规则**：目前 `sinr` 视为 dB 增益，若甲方提供更复杂描述（如多段形状、脉冲空洞），可在 `decode_semantic` 中替换为自定义片段生成函数。
- **多文件 IQ 拼接**：在 `pipeline/stitch_spectrum.py` 中扩展参数以接受目录列表，循环调用 `load_iq_file` 拼接多个时隙。
- **可视化增强**：`viz/plots.py` 已提供基础绘图，可在 Notebook 中加载 `npz` 结果调用 `plot_comparison`。
- **配置外化**：`core.config.load_config` 已支持 YAML/JSON，通过 CLI `--config` 传入即可覆盖默认采样率、FFT size、窗口配置。

## 8. 常见问题（FAQ）

1. **为什么 FFT 频轴是 MHz？**  
   需求关注宽频谱范围，直接以 MHz 为单位更直观，避免多次除以 1e6。

2. **参考谱与语义谱长度不一致怎么办？**  
   `semantic_eval` 中会截断到较短的一边；若需要精确对齐，保证 `fenbianlv` 与参考谱数组长度一致即可。

3. **如何导入自有数据？**  
   - 单文件场景：将 IQ 样本保存为 `.npz`，至少包含 `iq`（complex128 数组）、`sample_rate_hz`、`center_freq_hz` 三个键；随后执行 `python -m src.pipeline.stitch_spectrum --iq 自定义文件`。  
   - 多分片场景：将若干 `.bin` 文件置于同一目录，采用 int16 I/Q 交织存储，并以固定顺序对应 13 个中心频点（或按 `comb_130MHz_204.8MHz_xxx.bin` 格式命名）；随后执行 `python -m src.pipeline.stitch_multi --input-dir <目录> ...`。

通过上述模块化设计与中文注释，代码已具备可审计、可扩展的基础。Need 进一步深化时，可在 `docs/` 内追加更细的设计图或 Notebook 说明。
