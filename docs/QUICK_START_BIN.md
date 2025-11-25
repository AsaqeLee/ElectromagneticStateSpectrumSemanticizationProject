# BIN 格式快速入门 - 5 分钟上手

## 🚀 快速开始

### 1️⃣ 准备 BIN 文件

将你的 `.bin` 文件放入目录（例如 `data/raw_segments/`）：

```
data/raw_segments/
├── single_100MHz_50MHz_test.bin
├── comb_150MHz_50MHz_test.bin
└── noise_200MHz_50MHz_test.bin
```

### 2️⃣ 启动主 CLI

```bash
python spectrum_cli.py
```

### 3️⃣ 选择任务二

```
【主菜单】
选择 [1/2/3/4/5]: 2
```

### 4️⃣ 选择 BIN 数据源

```
➤ 数据源选择
  1. 从 NPZ 文件逐个加载频谱分段
  2. 从 BIN 文件目录批量加载 IQ 数据  ← 选这个

选择数据源 (1/2) [默认: 1]: 2
```

### 5️⃣ 配置参数（使用默认值）

```
BIN 文件目录路径 [默认: data/raw_segments]: ⏎
文件匹配模式 [默认: *.bin]: ⏎
选择数据类型 (1-5) [默认: 1]: ⏎
FFT 点数 [默认: 8192]: ⏎
窗函数 [默认: hann]: ⏎
选择模式 (1/2/3) [默认: 1]: ⏎
未覆盖区域填充值 (dB) [默认: -180.0]: ⏎
```

### 6️⃣ 等待处理完成

```
✓ 拼接成功
  频段: 75.00 - 225.00 MHz
  频点数: 12288
  已拼接分段数: 3
```

### 7️⃣ 保存结果

```
保存结果? (y/n) [默认: y]: y
输出目录 [默认: data/cli_results]: ⏎

✓ 已保存: data/cli_results/stitched_spectrum.npz
✓ 频谱图已保存: data/cli_results/stitched_spectrum.png
```

---

## 📋 文件命名规范

### 标准格式

```
{干扰类型}_{中心频率}MHz_{带宽}MHz_{时间戳}.bin
```

### ✅ 正确示例

```
single_100MHz_50MHz_11h14m22s.bin      # 单音干扰
comb_130MHz_204.8MHz_test.bin          # 梳状干扰
noise_fm_200MHz_20MHz.bin              # 调频噪声
```

### ❌ 错误示例

```
data.bin                    # 缺少元数据
100_50.bin                  # 缺少单位
single_tone_test.bin        # 缺少频率信息
```

---

## 🔧 数据类型选择指南

| 你的数据来源 | 选择类型 |
|------------|---------|
| **HackRF / RTL-SDR** | int8 (选项 2) |
| **USRP / SDRPlay** | int16 (选项 1，默认) |
| **MATLAB 导出** | complex64 (选项 4) |
| **GNU Radio** | complex64 (选项 4) |
| **Python 生成** | complex128 (选项 5) |

---

## 💡 常见问题

### ❓ 找不到文件？

**检查清单**:
1. ✅ 路径是否正确？（Windows 用 `\` 或 `/`）
2. ✅ 文件扩展名是 `.bin` 吗？
3. ✅ 目录是否存在？

### ❓ 数据类型选错了？

**症状**: 拼接后频谱异常（全是噪声或幅度很大）

**解决**:
- HackRF 用 int8
- USRP 用 int16
- 不确定就试试 complex64

### ❓ 拼接效果不好？

**尝试调整**:
- FFT 点数 → 16384（更精细）
- 拼接模式 → WEIGHTED_MEAN（重叠区域多时）
- 窗函数 → blackman（边瓣抑制更好）

---

## 📚 详细文档

- **完整使用指南**: `docs/CLI_BIN_SUPPORT_GUIDE.md`
- **BIN 格式规范**: `docs/BIN_FORMAT_SUPPORT.md`
- **修改日志**: `docs/CHANGELOG_CLI_BIN_SUPPORT.md`

---

## 🎓 下一步

1. **生成测试数据**: 使用任务一生成 IQ 数据并保存为 bin
2. **学习语义编码**: 尝试任务三的参数编解码
3. **查看项目架构**: 阅读 `SNOW.md`

---

**祝你使用愉快！** 🎉

有问题？查看 `docs/` 目录中的详细文档。
