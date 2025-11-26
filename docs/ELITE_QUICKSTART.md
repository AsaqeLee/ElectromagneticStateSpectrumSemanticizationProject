# 🎨 Elite频谱可视化 - 5分钟快速上手

> **一键生成「甲方级别」高端频谱图**

---

## ⚡ 快速开始（3步）

### 步骤 1：运行演示（查看效果）

```bash
cd C:\Users\admin\custom_folder\donot\electromagneticState

# 安装依赖（如果还没有）
pip install matplotlib numpy

# 运行演示
python examples\demo_elite_visualization.py

# 查看生成的图片
explorer demo_output
```

**生成的图片：**
- `elite_spectrum_demo.png` - 基础Elite风格频谱图
- `elite_comparison_demo.png` - 原始vs恢复对比图
- `elite_high_density_demo.png` - 高密度干扰场景

---

### 步骤 2：在代码中使用

```python
from src.visualization.enhanced_plot import plot_spectrum_elite
import numpy as np
from pathlib import Path

# 准备数据
freq_mhz = np.linspace(30, 2500, 2471)
power_db = np.random.normal(-100, 1, len(freq_mhz))

# 添加干扰区域（可选）
jammer_regions = [
    {"start_mhz": 470, "end_mhz": 530, "jnr_db": 28.0},
    {"start_mhz": 1200, "end_mhz": 1300, "jnr_db": 18.0},
]

# 生成Elite风格图
plot_spectrum_elite(
    freq_mhz=freq_mhz,
    power_db=power_db,
    title="ELECTROMAGNETIC SPECTRUM ANALYSIS",
    subtitle="Multi-Jammer Detection | 30-2500 MHz",
    jammer_regions=jammer_regions,
    save_path=Path("output/my_spectrum_elite.png"),
)

print("✓ 图片已保存！")
```

---

### 步骤 3：集成到CLI（可选）

在 `scripts/spectrum_cli.py` 中修改：

```python
# 1. 导入Elite模块
from src.visualization.enhanced_plot import plot_spectrum_elite

# 2. 替换保存函数
def save_spectrum_png(freq_mhz, power_db, output_path, title=""):
    """使用Elite风格保存"""
    plot_spectrum_elite(
        freq_mhz=freq_mhz,
        power_db=power_db,
        title=title or "SPECTRUM ANALYSIS",
        save_path=output_path,
        enable_glow=True,
        enable_bands=True,
    )
    print(f"  ✓ Elite风格图已保存: {output_path}")

# 3. 运行CLI测试
# python scripts\spectrum_cli.py
```

---

## 🎨 配色方案（开箱即用）

```
背景：深空黑 #05050a
频谱：电光青 #00e5ff + 辉光效果
干扰：
  - 高危（JNR>=25dB）：红色 #ff3366
  - 警告（15-25dB）：橙色 #ffaa00
  - 低威胁（<15dB）：黄色 #ffd700
```

---

## 📊 效果对比

### 当前默认（Simple）
```
❌ 白色背景，缺乏科技感
❌ 单色曲线，无渐变
❌ 无干扰标注
```
![Simple Style](https://via.placeholder.com/400x200/ffffff/1f77b4?text=Simple+Style)

### Elite风格（新增）
```
✅ 深空黑背景 + 赛博朋克风
✅ 3层辉光效果
✅ 电光蓝渐变填充
✅ 智能干扰标注
✅ HUD风格信息面板
✅ 300 DPI高分辨率
```
![Elite Style](https://via.placeholder.com/400x200/05050a/00e5ff?text=Elite+Style+with+Glow)

---

## 🔧 常用参数

### 基础参数
```python
plot_spectrum_elite(
    freq_mhz,           # 频率数组
    power_db,           # 功率数组
    title="...",        # 主标题
    subtitle="...",     # 副标题（可选）
    save_path=Path(...),# 保存路径
)
```

### 高级参数
```python
plot_spectrum_elite(
    ...,
    jammer_regions=[    # 干扰区域（可选）
        {"start_mhz": 500, "end_mhz": 600, "jnr_db": 25.0},
    ],
    enable_glow=True,      # 辉光效果
    enable_bands=True,     # 频段划分
    enable_watermark=True, # 水印
)
```

---

## 💡 使用技巧

### 技巧 1：自动提取干扰区域
```python
# 从语义参数中提取
from src.semantics.decode_v2 import load_semantic_v2_file

params = load_semantic_v2_file("data_semantic/semantic_case01.json")

jammer_regions = []
for region in params.jammer_regions:
    start_bin = region.start_bin
    end_bin = region.end_bin
    jnr_db = region.jnr_db
    
    # 转换为MHz
    freq_range = (params.freq_max_mhz - params.freq_min_mhz)
    start_mhz = params.freq_min_mhz + start_bin * freq_range / params.num_bins
    end_mhz = params.freq_min_mhz + end_bin * freq_range / params.num_bins
    
    jammer_regions.append({
        "start_mhz": start_mhz,
        "end_mhz": end_mhz,
        "jnr_db": jnr_db
    })

plot_spectrum_elite(..., jammer_regions=jammer_regions)
```

### 技巧 2：批量生成
```python
# 批量处理多个频谱文件
from pathlib import Path
import numpy as np

input_dir = Path("data/spectrums")
output_dir = Path("output/elite_plots")
output_dir.mkdir(exist_ok=True)

for npz_file in input_dir.glob("*.npz"):
    data = np.load(npz_file)
    freq_mhz = data['freq_mhz']
    power_db = data['power_db']
    
    output_path = output_dir / f"{npz_file.stem}_elite.png"
    plot_spectrum_elite(
        freq_mhz, power_db,
        title=f"SPECTRUM: {npz_file.stem}",
        save_path=output_path
    )
    print(f"✓ {output_path}")
```

### 技巧 3：自定义配色
```python
from src.visualization.enhanced_plot import ELITE_COLORS

# 临时修改配色
ELITE_COLORS["spectrum_primary"] = "#ff00ff"  # 改为紫色
ELITE_COLORS["background"] = "#000000"        # 纯黑背景

plot_spectrum_elite(...)

# 恢复默认配色
from src.visualization.enhanced_plot import ELITE_COLORS
ELITE_COLORS["spectrum_primary"] = "#00e5ff"
```

---

## 📁 项目结构

```
electromagneticState/
├── src/visualization/
│   ├── spectrum_plot.py       # 原有：simple/premium
│   └── enhanced_plot.py       # 新增：elite风格 ⭐
│
├── examples/
│   └── demo_elite_visualization.py  # 使用演示 ⭐
│
├── docs/
│   ├── ELITE_VISUALIZATION_GUIDE.md  # 完整文档 ⭐
│   └── ELITE_QUICKSTART.md           # 本文档 ⭐
│
└── scripts/
    ├── spectrum_cli.py        # CLI入口（待集成）
    └── spectrum_batch.py      # 批处理CLI（待集成）
```

---

## 🚀 下一步

### 选项 A：快速体验
```bash
# 立即查看效果
python examples\demo_elite_visualization.py
explorer demo_output
```

### 选项 B：集成到项目
```bash
# 修改 scripts/spectrum_cli.py
# 按照"步骤3"的代码进行集成
# 重新运行CLI测试
python scripts\spectrum_cli.py
```

### 选项 C：深入定制
```bash
# 阅读完整文档
start docs\ELITE_VISUALIZATION_GUIDE.md

# 修改配色、样式、水印等
# 编辑 src/visualization/enhanced_plot.py
```

---

## ❓ 常见问题

### Q: 图片太大？
A: 降低DPI或关闭辉光
```python
plot_spectrum_elite(..., enable_glow=False)
# 或修改 enhanced_plot.py 中的 dpi=300 → dpi=150
```

### Q: 字体显示异常？
A: 系统自动使用 SimHei 或 Microsoft YaHei，无需手动配置

### Q: 如何去掉水印？
A: 
```python
plot_spectrum_elite(..., enable_watermark=False)
```

### Q: 如何导出矢量图？
A:
```python
save_path=Path("output/spectrum.svg")  # SVG矢量
# 或
save_path=Path("output/spectrum.pdf")  # PDF矢量
```

---

## 📞 获取帮助

- **完整文档**：`docs/ELITE_VISUALIZATION_GUIDE.md`
- **代码示例**：`examples/demo_elite_visualization.py`
- **源码**：`src/visualization/enhanced_plot.py`

---

**🎯 开始使用，3分钟见效！**

```bash
python examples\demo_elite_visualization.py
```
