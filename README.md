# 电磁态频谱语义化工程

本仓库实现《频谱语义化表征与频谱恢复》的基础工程，默认运行环境为 `miniconda3` 中的 `xd_torch`，当前 Python 版本 3.8.20。所有脚本均以中文注释，遵循 spec 中的 10 步任务拆解。

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
- `src/io`: `reader.py` 封装 IQ 数据读取，支持 `.npy/.npz/.h5`。  
- `src/signal`: 频段切分与功率谱算法（FFT、频轴生成、分片拼接）。  
- `src/semantics`: `decode.py` 根据语义参数恢复频谱。  
- `src/pipeline`: 任务 1~3 及调试用脚本级流水线，可直接通过 `python -m src.pipeline.xxx` 调用：  
  - `simulate_iq.py`：任务 1，生成仿真 IQ，并可直接绘制 PSD；  
  - `analyze_comb.py`：对单个 comb 采样文件做频谱与特性分析；  
  - `overlay_comb.py`：在同一坐标轴上叠加多段 PSD（例如 130/330 MHz 两段）；  
  - `stitch_multi.py`：从目录中读取多分片 IQ，拼接出宽带功率谱；  
  - `semantic_eval.py`：任务 3，读取参考谱与语义 JSON，执行语义恢复评估。  
- `src/viz`: 常用绘图函数（单谱线、参考/恢复对比）。  
- `tests`: Pytest 测试，校验频段划分、语义恢复与频谱计算接口。

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
