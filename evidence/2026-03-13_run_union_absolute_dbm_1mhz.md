# 2026-03-13：run_union 输出改为绝对功率 dBm @ 1MHz RBW（底噪 -105 dBm 标定）

## 0. 前置说明

- **日期**：2026-03-13（Asia/Shanghai）
- **目标**：将 `scripts/run_union.py` 输出的 `output/union_spectrum.npz` 纵轴从“相对 dB”改为 **dBm @ 1MHz RBW**，并以已知底噪 **-105 dBm @ 1MHz RBW** 作为绝对刻度基准。
- **关键约束**：
  - 当前 IQ `.bin` 数据链路未做“射频链路/ADC 绝对标定”，因此所谓“绝对 dBm”只能通过某个基准点对齐（本次用噪声底噪）。
  - 输出频轴工程约定固定 **30–2500 MHz，Δf=1 MHz，2471 点**，避免下游维度漂移。

## 1. 变更内容（实现口径）

### 1.1 输出单位

`output/union_spectrum.npz`：
- `freq_mhz`：MHz
- `power_db`：**dBm @ 1MHz RBW**（注意键名仍为 `power_db`，但口径已切换）

### 1.2 参考谱（任务二）如何变成 dBm@1MHz

步骤：
1. 用任务二得到拼接参考谱 `stitched.freq_mhz / stitched.power_db`（原先为相对 dB）。
2. 先估计参考谱底噪（相对 dB）：对覆盖点做低分位（默认 20%）。
3. 将参考谱聚合到输出 1MHz 栅格：对每个输出频点 `f`，在 `[f-0.5, f+0.5] MHz` 窗口内，对参考谱功率做**线性域求和**，近似得到 **1MHz RBW 的功率口径**（相对 dB）。
4. 再次估计聚合后参考谱的底噪低分位（相对 dB），并计算标定偏置：

   `cal_offset_db = (-105 dBm) - noise_ref_out_db`

5. 得到参考谱 dBm：

   `power_ref_dbm = power_ref_out_rel + cal_offset_db`

### 1.3 语义谱（任务三）如何对齐到 dBm@1MHz

- 不再使用语义文件中 `noise_floor_db` 作为输出底噪；
- 统一以 `noise_floor_dbm_1mhz=-105` 作为底噪；
- 频段抬升仍采用原有语义含义：`level = noise_floor_dbm_1mhz + jnr_db`（dB 加法）。

### 1.4 并集规则

- 输出为 `max(参考谱 dBm, 语义谱 dBm)`，逐频点取最大值。

## 2. 验证方法（可复现）

运行：

```powershell
python scripts\run_union.py
python -c "import numpy as np; d=np.load('output/union_spectrum.npz'); p=d['power_db']; print('p20', float(np.percentile(p,20)), 'min', float(p.min()), 'max', float(p.max()))"
```

期望：
- `p20` 接近 `-105`（允许少量浮动，取决于样本与干扰覆盖情况）
- `min` 通常为 `-105`（因为语义/参考缺省填底噪）

## 3. 已知局限与风险

1. **这是“噪声底噪对齐”的绝对刻度**：底噪数值正确，但不等价于完整射频链路标定；若前端增益/衰减档变化或链路频响明显，强干扰/强信号的 dBm 仍可能存在系统偏差。
2. **RBW 口径为工程近似**：对 1MHz 输出频点做窗口线性求和更接近 RBW，但仍不等价于频谱仪的模拟 RBW 滤波器与检波器定义。

## 4. 相关文件

- 代码：`scripts/run_union.py`
- 输出：`output/union_spectrum.npz`

