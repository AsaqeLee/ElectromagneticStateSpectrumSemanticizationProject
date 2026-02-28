# 2026-02-28：run_union（任务二+任务三并集）性能测试报告（512 点分段 FFT，默认不绘图，输出 1MHz/2471 点）

## 0. 前置说明（可审计）

- **测试日期**：2026-02-28
- **目标**：在不绘图的前提下，将“FFT + 频谱拼接（30–2500MHz）+ 语义并集 + 输出文件”的热路径耗时压到 **≤ 50ms**（工程目标）。
- **结论先行**：在“同进程热启动”条件下，当前实现 **满足 ≤50ms**；但**每次新起 Python 进程的冷启动**因为 `numpy/scipy` 导入成本，**远超 50ms**（约秒级），这不是 FFT 本身的问题。

## 1. 测试对象与输入数据

### 1.1 软件对象

- 脚本：`scripts/run_union.py`
- 基准脚本：`scripts/bench_run_union.py`
- 关键参数：
  - 采样率默认：**204.8 MHz**
  - 分段 FFT：**NFFT=512**（每个 `.bin` 文件按 `num_chunks = ceil(num_samples/NFFT)` 自动分段；本次数据为 130048 点 → 254 段）
  - 时间聚合：`mean`（更快，且更贴近“态势”平滑需求）
  - 输出频轴：**30–2500 MHz，1 MHz 分辨率，共 2471 点**
  - 绘图：默认关闭（`enable_plot=False`）

### 1.2 输入数据（真实 `.bin`）

- `data_segment/*.bin` 共 **13** 个分段文件
- 文件命名：`{center}MHz.bin`（例如 `130MHz.bin`、`2400MHz.bin`）
- 单文件大小：`520192` bytes（INT16 交织 I/Q）
- 单文件样本数：
  - INT16 交织长度：`520192 / 2 = 260096` 个 int16
  - 复数 IQ 点数：`260096 / 2 = 130048` 个 complex64（注：实际运行中按加载后的样本长度为准）
  - 对应分段数（本次数据）：
    - NFFT=512 → `130048 / 512 = 254` 段
    - NFFT=256 → `130048 / 256 = 508` 段

> 备注：即使未来数据是 131072 点（512×256）或存在尾段不足，分段 FFT 逻辑也会对最后不足段做 0 填充，不影响输出维度与拼接逻辑。

## 2. 测试环境

- OS：Windows（PowerShell）
- Python：3.12.9
- NumPy：2.1.3
- SciPy：1.16.2
- CPU：Intel(R) Xeon(R) Gold 6144 CPU @ 3.50GHz

## 3. 测试方法（热启动 vs 冷启动）

### 3.1 热启动（同进程，符合系统集成预期）

基准脚本会在**同一 Python 进程**内重复调用：

- `run_union.main(quiet=True, enable_plot=False, segment_fft_size=NFFT)`
- 预热 `warmup` 次，使 OS 文件缓存与 FFT 路径稳定
- 重复 `repeat` 次，统计 mean / p95 / max

复现命令：

```powershell
python scripts\bench_run_union.py --repeat 30 --warmup 3
```

### 3.2 冷启动（每次新起进程，属于“脚本单次运行”开销）

复现命令（示例）：

```powershell
powershell -NoProfile -Command "(Measure-Command { python scripts\run_union.py | Out-Null }).TotalMilliseconds"
```

## 4. 测试结果

### 4.1 热启动结果（满足 ≤50ms 目标）

`scripts/bench_run_union.py --repeat 30 --warmup 3` 的一次稳定输出为：

- **NFFT=256**
  - mean：**42.893 ms**
  - p95 ：**45.530 ms**
  - max ：**45.899 ms**
- **NFFT=512（选定方案）**
  - mean：**39.917 ms**
  - p95 ：**42.399 ms**
  - max ：**42.838 ms**

结论：在热启动路径下，**NFFT=512 / 256 段**方案端到端耗时稳定低于 50ms。

### 4.2 冷启动结果（不可能 ≤50ms）

在本机一次测量中：

- `python scripts\run_union.py` 的整进程耗时约 **2024 ms**

结论：**冷启动瓶颈在 Python 解释器启动 + numpy/scipy 导入**，不是 FFT 算法本身。想要工程上 ≤50ms，必须用“常驻进程/服务化/内嵌调用”等方式避免冷启动。

## 5. 瓶颈分析（问题出现在哪里）

用 `cProfile` 做一次粗定位（结论稳定）：

- **任务二（真实 `.bin`）耗时占大头**
  - `load_bin_segments()`：读取 13 个文件 + INT16→complex64 转换
  - `compute_segmented_power_spectrum()`：分段窗函数 + 批量 FFT + 功率计算
- `np.savez()`：写 `union_spectrum.npz` 约毫秒级（偶尔受磁盘/杀软/系统调度影响）
- 任务三（语义恢复）耗时很小，不是瓶颈

## 6. 工程上进一步“极限压缩”的办法（如果你要把 P99 也压到 <50ms）

按性价比排序（越上面越值得做）：

1. **不要每帧/每次都写盘**：让调用方直接拿到 `freq_mhz/power_db` 数组，按需落盘（I/O 抖动是 P99 的常见来源）。
2. **常驻进程**：把 `run_union` 嵌进服务/进程（或 GUI 主程序）里跑，避免每次启动 Python 与导入 SciPy。
3. **缓存窗函数**：对固定 `window=hann, NFFT=512`，窗函数可缓存复用，避免重复构造。
4. **减少无意义的格式开销**：`.npz` 是 zip 容器；如果下游允许，改用 `.npy`（固定 shape）或共享内存/内存映射，延迟与抖动都会更小。
5. **并行化（谨慎）**：13 个分段可并行 FFT，但对 512 点小 FFT，线程调度可能得不偿失；建议先用基准确认再上多核。

## 7. 验收点（本次已达成）

- [x] 选择方案：**512 点 FFT，256 段**
- [x] 采样率默认：**204.8MHz**
- [x] 输出文件分辨率：**1MHz（2471 点）**
- [x] 默认不绘图（避免 PNG 开销与 matplotlib 依赖）
- [x] 热启动端到端耗时：**<50ms**
- [x] 单元测试：`pytest -q` 全通过
