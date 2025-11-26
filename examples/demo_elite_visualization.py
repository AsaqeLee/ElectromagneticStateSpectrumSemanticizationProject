"""
Elite级别频谱可视化使用指南

演示如何使用增强版可视化模块生成「甲方级别」的高端频谱图
"""

import numpy as np
from pathlib import Path
from src.visualization.enhanced_plot import (
    plot_spectrum_elite,
    plot_comparison_elite,
    ELITE_COLORS
)

def demo_basic_spectrum():
    """示例1：基础频谱图（Elite风格）"""
    print("示例1：生成基础Elite风格频谱图...")
    
    # 生成模拟数据
    freq_mhz = np.linspace(30, 2500, 2471)
    noise_floor = -100
    power_db = np.random.normal(noise_floor, 1.0, len(freq_mhz))
    
    # 添加3个干扰信号
    # 干扰1: 500MHz, JNR=28dB
    idx1 = np.where((freq_mhz >= 470) & (freq_mhz <= 530))[0]
    power_db[idx1] = noise_floor + 28 + np.random.normal(0, 0.5, len(idx1))
    
    # 干扰2: 1200MHz, JNR=18dB
    idx2 = np.where((freq_mhz >= 1150) & (freq_mhz <= 1250))[0]
    power_db[idx2] = noise_floor + 18 + np.random.normal(0, 0.5, len(idx2))
    
    # 干扰3: 1800MHz, JNR=12dB
    idx3 = np.where((freq_mhz >= 1750) & (freq_mhz <= 1850))[0]
    power_db[idx3] = noise_floor + 12 + np.random.normal(0, 0.5, len(idx3))
    
    # 定义干扰区域（用于标注）
    jammer_regions = [
        {"start_mhz": 470, "end_mhz": 530, "jnr_db": 28.0},
        {"start_mhz": 1150, "end_mhz": 1250, "jnr_db": 18.0},
        {"start_mhz": 1750, "end_mhz": 1850, "jnr_db": 12.0},
    ]
    
    # 生成Elite风格图
    plot_spectrum_elite(
        freq_mhz=freq_mhz,
        power_db=power_db,
        title="ELECTROMAGNETIC SPECTRUM ANALYSIS",
        subtitle="Multi-Jammer Detection | 30-2500 MHz | Resolution 1.0 MHz",
        jammer_regions=jammer_regions,
        enable_glow=True,        # 启用辉光效果
        enable_bands=True,       # 启用频段标注
        enable_watermark=True,   # 启用水印
        save_path=Path("demo_output/elite_spectrum_demo.png"),
    )
    
    print("✓ Elite风格频谱图已保存到: demo_output/elite_spectrum_demo.png")


def demo_comparison():
    """示例2：原始 vs 恢复对比图"""
    print("\n示例2：生成Elite风格对比图...")
    
    # 原始频谱
    freq_mhz = np.linspace(30, 2500, 2471)
    original = np.random.normal(-100, 1, len(freq_mhz))
    idx = np.where((freq_mhz >= 500) & (freq_mhz <= 700))[0]
    original[idx] = -100 + 25 + np.random.normal(0, 0.5, len(idx))
    
    # 恢复频谱（模拟有误差）
    recovered = original.copy()
    recovered += np.random.normal(0, 0.8, len(recovered))  # 添加恢复误差
    
    # 生成对比图
    plot_comparison_elite(
        freq_mhz=freq_mhz,
        original=original,
        recovered=recovered,
        title="SPECTRUM RECOVERY ANALYSIS",
        save_path=Path("demo_output/elite_comparison_demo.png"),
    )
    
    print("✓ Elite风格对比图已保存到: demo_output/elite_comparison_demo.png")


def demo_high_density_jammers():
    """示例3：高密度干扰场景"""
    print("\n示例3：生成高密度干扰场景图...")
    
    freq_mhz = np.linspace(30, 2500, 2471)
    power_db = np.random.normal(-120, 0.5, len(freq_mhz))
    
    # 模拟10个干扰源
    jammer_regions = []
    for i in range(10):
        center = 200 + i * 220
        start = center - 30
        end = center + 30
        jnr = 30 - i * 2  # 递减强度
        
        idx = np.where((freq_mhz >= start) & (freq_mhz <= end))[0]
        power_db[idx] = -120 + jnr + np.random.normal(0, 0.3, len(idx))
        
        jammer_regions.append({
            "start_mhz": start,
            "end_mhz": end,
            "jnr_db": jnr
        })
    
    plot_spectrum_elite(
        freq_mhz=freq_mhz,
        power_db=power_db,
        title="HIGH-DENSITY JAMMER ENVIRONMENT",
        subtitle="10 Active Jammers Detected | Threat Level: CRITICAL",
        jammer_regions=jammer_regions,
        save_path=Path("demo_output/elite_high_density_demo.png"),
    )
    
    print("✓ 高密度干扰场景图已保存到: demo_output/elite_high_density_demo.png")


def demo_cli_integration():
    """示例4：如何在CLI中集成"""
    print("\n示例4：CLI集成代码示例\n")
    
    code = """
# 在 scripts/spectrum_cli.py 中替换 save_spectrum_png 函数

from src.visualization.enhanced_plot import plot_spectrum_elite

def save_spectrum_elite_png(
    freq_mhz: np.ndarray, 
    power_db: np.ndarray, 
    output_path: Path, 
    title: str = "",
    jammer_regions: Optional[List[Dict]] = None
) -> None:
    \"\"\"使用Elite风格保存频谱图（甲方专用）\"\"\"
    try:
        plot_spectrum_elite(
            freq_mhz=freq_mhz,
            power_db=power_db,
            title=title or "ELECTROMAGNETIC SPECTRUM ANALYSIS",
            subtitle=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            jammer_regions=jammer_regions,
            save_path=output_path,
            enable_glow=True,
            enable_bands=True,
            enable_watermark=True,
        )
        print(f"  ✓ Elite风格频谱图已保存: {output_path}")
    except Exception as e:
        print(f"  ⚠️ 保存频谱图失败: {e}")


# 在任务一（合成频谱）中调用
png_path = output_dir / "composed_spectrum_elite.png"

# 提取干扰区域信息
jammer_regions = []
for jammer in cfg.jammers:
    # 根据干扰类型和参数估算频率范围
    jammer_regions.append({
        "start_mhz": jammer.center_freq_mhz - 50,  # 示例
        "end_mhz": jammer.center_freq_mhz + 50,
        "jnr_db": jammer.jnr_db
    })

save_spectrum_elite_png(
    freq_mhz, 
    power_db, 
    png_path, 
    title=f"COMPOSED SPECTRUM ({len(cfg.jammers)} JAMMERS)",
    jammer_regions=jammer_regions
)
"""
    
    print(code)
    print("\n💡 提示：将上述代码集成到CLI中即可生成Elite风格图")


def print_color_palette():
    """显示配色方案"""
    print("\n" + "="*60)
    print("ELITE配色方案")
    print("="*60)
    
    print("\n【背景层次】")
    print(f"  background:    {ELITE_COLORS['background']}")
    print(f"  plot_bg:       {ELITE_COLORS['plot_bg']}")
    print(f"  panel_bg:      {ELITE_COLORS['panel_bg']}")
    
    print("\n【频谱主色】")
    print(f"  spectrum_primary: {ELITE_COLORS['spectrum_primary']}")
    print(f"  spectrum_glow:    {ELITE_COLORS['spectrum_glow']}")
    
    print("\n【干扰标记】")
    print(f"  jammer_critical: {ELITE_COLORS['jammer_critical']} (JNR >= 25dB)")
    print(f"  jammer_warning:  {ELITE_COLORS['jammer_warning']} (15 <= JNR < 25dB)")
    print(f"  jammer_low:      {ELITE_COLORS['jammer_low']} (JNR < 15dB)")
    
    print("\n【文本层次】")
    print(f"  text_title:     {ELITE_COLORS['text_title']}")
    print(f"  text_primary:   {ELITE_COLORS['text_primary']}")
    print(f"  text_secondary: {ELITE_COLORS['text_secondary']}")
    print(f"  text_accent:    {ELITE_COLORS['text_accent']}")
    
    print("\n【功能色】")
    print(f"  success: {ELITE_COLORS['success']}")
    print(f"  danger:  {ELITE_COLORS['danger']}")
    print(f"  highlight: {ELITE_COLORS['highlight']}")


if __name__ == "__main__":
    print("="*60)
    print("ELITE级别频谱可视化演示")
    print("="*60)
    
    # 创建输出目录
    output_dir = Path("demo_output")
    output_dir.mkdir(exist_ok=True)
    
    # 运行所有示例
    demo_basic_spectrum()
    demo_comparison()
    demo_high_density_jammers()
    demo_cli_integration()
    print_color_palette()
    
    print("\n" + "="*60)
    print("演示完成！查看 demo_output/ 目录下的生成图片")
    print("="*60)
