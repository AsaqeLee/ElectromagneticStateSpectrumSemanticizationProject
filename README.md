# 电磁态频谱语义化工程

本仓库实现《频谱语义化表征与频谱恢复》的基础工程，最初在 `miniconda3` 中的 `xd_torch` 环境（Python 3.8.20）下开发，目前已在 Python 3.12.9 下通过 `pytest` 全量单元测试，推荐使用 Python 3.11 及以上版本。所有脚本均以中文注释，遵循 spec 中的 10 步任务拆解。

## 快速开始

```bash
# 进入工程根目录并激活 conda 环境
conda activate xd_torch

# 安装依赖
pip install -r requirements.txt

# 运行单元测试，验证核心逻辑
pytest
```

## 目录结构

- `src/core`: 配置与数据结构定义；`config.py` 负责频段/路径配置（含 13 个 200 MHz 采集中心频点），`schemas.py` 提供 dataclass。  
- `src/io`: `reader.py` 封装 IQ 数据读取，支持 `.npy/.npz/.h5/.bin`。  
- `src/signal`: 频段切分与功率谱算法（FFT、频轴生成、分片拼接、干扰合成）。  
- `src/semantics`: 语义参数编码/解码（`decode.py`, `decode_multi.py`, `edge_detect.py`）。  
- `src/pipeline`: 任务 1~3 及调试用脚本级流水线，可直接通过 `python -m src.pipeline.xxx` 调用：  
  - `simulate_iq.py`：生成仿真 IQ，并可直接绘制 PSD；  
  - `analyze_comb.py`：对单个 comb 采样文件做频谱与特性分析；  
  - `overlay_comb.py`：在同一坐标轴上叠加多段 PSD（例如 130/330 MHz 两段）；  
  - `stitch_multi.py`：从目录中读取多分片 IQ，拼接出宽带功率谱；  
  - `semantic_eval.py`：读取参考谱与语义 JSON，执行语义恢复评估。  
- `src/viz`: 常用绘图函数（单谱线、参考/恢复对比）。  
- `tests`: Pytest 测试，校验频段划分、语义恢复与频谱计算接口。

## 任务与模块对应关系（统一术语）

为避免不同文档/脚本中对同一任务使用不同称呼，这里给出统一约定：

| 任务   | 名称                 | 核心模块/脚本                                                   |
|--------|----------------------|------------------------------------------------------------------|
| 任务一 | 干扰信号功率谱合成   | `src/signal/spectrum_composer.py`, `src/pipeline/compose_spectrum.py`, `spectrum_cli.py` |
| 任务二 | 频谱分段拼接         | `src/signal/stitcher.py`, `src/pipeline/stitch_multi.py`, `spectrum_cli.py`              |
| 任务三 | 语义参数频谱恢复     | `src/semantics/decode.py`, `src/semantics/decode_multi.py`, `src/pipeline/semantic_eval.py`, `spectrum_cli.py` |

后续文档与 CLI 输出中提到“任务一/二/三”时，均对应上表中的名称和模块。

## 开发者简要指南

从工程依赖关系上看，本项目采用自下而上的分层结构：

```text
顶层入口
  ├── spectrum_cli.py        # 交互式 CLI（任务 1/2/3）
  ├── spectrum_batch.py      # 批处理 CLI（compose/stitch/decode 子命令）
  └── demo_all_tasks.py      # 全流程 Demo
          ↓
src/pipeline/                # 任务级流水线（组合 core/signal/semantics/io）
          ↓
src/signal/                  # 信号与频谱算法（干扰生成、FFT、分段拼接等）
src/semantics/               # 语义编码/解码与边缘检测
src/io/                      # IQ 数据读取与切片
src/core/                    # 基础数据结构与项目配置
```

简单约定：

- `core` 不依赖其它业务模块；  
- `signal/semantics/io` 只依赖 `core`，不反向依赖 `pipeline` 或顶层脚本；  
- `pipeline` 组合 `core/signal/semantics/io` 提供任务级 API；  
- 顶层 `spectrum_cli.py` / `spectrum_batch.py` 只做参数解析与交互，不直接调用带 `_` 前缀的内部 helper。  

针对扩展场景：

- **新增干扰类型**：在 `src/signal/jammers.py` 中实现 `xxx_jammer`，并在 `JAMMER_REGISTRY` 中注册；CLI 与文档会自动列出新类型。  
- **新增语义编码策略**：在 `src/semantics/edge_detect.py` 或新模块实现 `auto_encode_*`；对应解码逻辑放在 `decode_multi.py` 或新的 `decode_v2.py` 中，并通过新的 `semantic_eval_v2.py` 接入 pipeline。  
- **对外稳定 API**：优先通过 `compose_spectrum`、`stitch_segments`、`decode_semantic`/`decode_semantic_multi_region`、`load_iq_file` 等函数调用；以下划线 `_` 开头的函数视为内部实现，后续版本不保证兼容。  

## 运行流水线示例

```bash
# 所有脚本均在 src 布局下，通过 python -m src.pipeline.xxx 调用

# 1. 生成仿真 IQ 并绘制功率谱密度（任务1）
python -m src.pipeline.simulate_iq \
  --output data/demo_iq.npz \
  --plot-psd \
  --psd-output data/demo_iq_psd.png

# 2. 多分片采样数据：从 data_segment 目录下拼接 30–2500 MHz 参考功率谱
#    假定 data_segment 下按顺序放置 13 段 int16 I/Q 分片（顺序对应 130、330、400…2400 MHz 中心频点）
python -m src.pipeline.stitch_multi \
  --input-dir data_segment \
  --pattern "*.bin" \
  --fft-size 262144 \
  --ignore-names \
  --sample-rate 204.8e6 \
  --min-freq 30 \
  --max-freq 2500 \
  --output-npz data/stitched_30_2500.npz \
  --output-png data/stitched_30_2500.png

# 3. 根据 JSON 语义参数恢复频谱并评估误差（任务3）
python -m src.pipeline.semantic_eval \
  --reference data/stitched_30_2500.npz \
  --semantic data/demo_semantic.json \
  --report data/semantic_eval.json
```

所有命令行脚本均会输出结果文件路径与基础统计量，便于后续可视化或集成测试。
