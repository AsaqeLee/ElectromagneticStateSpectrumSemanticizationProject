"""增强版电磁频谱可视化模块 - 甲方级别

提供三种风格：
1. simple - 基础风格（内部调试）
2. premium - 高级风格（标准交付）
3. elite - 顶级风格（重要客户/演示）
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Elite风格配色方案（赛博朋克 + 军工科技）
ELITE_COLORS = {
    # 背景层次
    "background": "#05050a",
    "plot_bg": "#0d0d15",
    "panel_bg": "#15152a",
    
    # 频谱主色（电光蓝渐变）
    "spectrum_primary": "#00e5ff",
    "spectrum_gradient_start": "#00d4ff",
    "spectrum_gradient_end": "#0091ff",
    "spectrum_glow": "#00ffff",
    
    # 干扰标记
    "jammer_critical": "#ff3366",
    "jammer_warning": "#ffaa00",
    "jammer_low": "#ffd700",
    
    # 网格与边框
    "grid_major": "#2a2a40",
    "grid_minor": "#1a1a28",
    "border": "#3a3a55",
    
    # 文本
    "text_title": "#ffffff",
    "text_primary": "#e8e8f0",
    "text_secondary": "#9090a0",
    "text_accent": "#00ffaa",
    
    # 功能色
    "highlight": "#ff00ff",
    "success": "#00ff88",
    "danger": "#ff3366",
}


def get_jammer_color(jnr_db: float) -> str:
    """根据JNR强度返回颜色"""
    if jnr_db >= 25:
        return ELITE_COLORS["jammer_critical"]
    elif jnr_db >= 15:
        return ELITE_COLORS["jammer_warning"]
    else:
        return ELITE_COLORS["jammer_low"]


def plot_spectrum_elite(
    freq_mhz: np.ndarray,
    power_db: np.ndarray,
    title: str = "ELECTROMAGNETIC SPECTRUM ANALYSIS",
    subtitle: str = "",
    figsize: Tuple[int, int] = (16, 8),
    save_path: Optional[Path] = None,
    show: bool = False,
    jammer_regions: Optional[List[Dict]] = None,
    enable_glow: bool = True,
    enable_bands: bool = True,
    enable_watermark: bool = True,
) -> plt.Figure:
    """顶级风格频谱图 - 甲方专用
    
    参数:
        freq_mhz: 频率数组 (MHz)
        power_db: 功率数组 (dB)
        title: 主标题
        subtitle: 副标题
        figsize: 图形大小
        save_path: 保存路径
        show: 是否显示
        jammer_regions: 干扰区域 [{"start_mhz": float, "end_mhz": float, "jnr_db": float}, ...]
        enable_glow: 启用辉光效果
        enable_bands: 启用频段标注
        enable_watermark: 启用水印
    """
    # 创建图形
    fig = plt.figure(figsize=figsize, facecolor=ELITE_COLORS["background"])
    
    # 主绘图区域
    ax = fig.add_axes([0.08, 0.12, 0.88, 0.78])
    ax.set_facecolor(ELITE_COLORS["plot_bg"])
    
    # === 频段背景（可选）===
    if enable_bands:
        bands = [
            (30, 300, "VHF/UHF", "#ff00ff"),
            (300, 1000, "L-Band", "#00ff88"),
            (1000, 2000, "S-Band", "#ffaa00"),
            (2000, 2500, "C-Band", "#00ffff"),
        ]
        
        for start, end, name, color in bands:
            if start >= freq_mhz.min() and end <= freq_mhz.max():
                ax.axvspan(start, end, alpha=0.05, color=color, zorder=1)
                # 频段标签
                ax.text(
                    (start + end) / 2, power_db.min() - 3,
                    name,
                    ha='center',
                    fontsize=8,
                    color=ELITE_COLORS["text_secondary"],
                    alpha=0.7,
                    style='italic',
                    weight='light'
                )
    
    # === 辉光效果（3层）===
    if enable_glow:
        # 外层辉光
        ax.plot(
            freq_mhz, power_db,
            linewidth=8,
            color=ELITE_COLORS["spectrum_glow"],
            alpha=0.05,
            zorder=7,
            solid_capstyle='round',
        )
        # 中层辉光
        ax.plot(
            freq_mhz, power_db,
            linewidth=4,
            color=ELITE_COLORS["spectrum_glow"],
            alpha=0.12,
            zorder=8,
            solid_capstyle='round',
        )
        # 内层辉光
        ax.plot(
            freq_mhz, power_db,
            linewidth=2,
            color=ELITE_COLORS["spectrum_primary"],
            alpha=0.25,
            zorder=9,
            solid_capstyle='round',
        )
    
    # === 主频谱线 ===
    ax.plot(
        freq_mhz, power_db,
        linewidth=1.2,
        color=ELITE_COLORS["spectrum_primary"],
        alpha=0.95,
        zorder=10,
        solid_capstyle='round',
    )
    
    # === 渐变填充 ===
    ax.fill_between(
        freq_mhz,
        power_db,
        power_db.min() - 10,
        alpha=0.20,
        color=ELITE_COLORS["spectrum_gradient_start"],
        zorder=5,
    )
    
    # === 干扰区域标记 ===
    if jammer_regions:
        for i, region in enumerate(jammer_regions):
            start_mhz = region.get("start_mhz", 0)
            end_mhz = region.get("end_mhz", 0)
            jnr_db = region.get("jnr_db", 0)
            
            color = get_jammer_color(jnr_db)
            
            # 背景高亮
            ax.axvspan(
                start_mhz, end_mhz,
                alpha=0.15,
                color=color,
                zorder=2,
            )
            
            # 顶部危险条
            ax.axhline(
                y=power_db.max() + 3,
                xmin=(start_mhz - freq_mhz.min()) / (freq_mhz.max() - freq_mhz.min()),
                xmax=(end_mhz - freq_mhz.min()) / (freq_mhz.max() - freq_mhz.min()),
                color=color,
                linewidth=4,
                alpha=0.9,
                solid_capstyle='round',
                zorder=15,
            )
            
            # 智能标注
            center_freq = (start_mhz + end_mhz) / 2
            # 找到中心频率处的功率值
            idx = np.argmin(np.abs(freq_mhz - center_freq))
            power_at_center = power_db[idx]
            
            ax.annotate(
                f"J-{i+1}\n{jnr_db:.1f} dB",
                xy=(center_freq, power_at_center),
                xytext=(center_freq, power_db.max() + 8),
                fontsize=9,
                color=ELITE_COLORS["text_accent"],
                ha='center',
                weight='bold',
                bbox=dict(
                    boxstyle='round,pad=0.4',
                    facecolor=ELITE_COLORS["panel_bg"],
                    edgecolor=color,
                    linewidth=1.5,
                    alpha=0.95,
                ),
                arrowprops=dict(
                    arrowstyle='->',
                    color=ELITE_COLORS["text_accent"],
                    lw=1.5,
                    alpha=0.8,
                    connectionstyle="arc3,rad=0.1",
                ),
                zorder=20,
            )
    
    # === 网格系统 ===
    ax.grid(
        True,
        which='major',
        color=ELITE_COLORS["grid_major"],
        linewidth=0.6,
        alpha=0.6,
        linestyle='-',
    )
    ax.grid(
        True,
        which='minor',
        color=ELITE_COLORS["grid_minor"],
        linewidth=0.3,
        alpha=0.4,
        linestyle=':',
    )
    
    # 刻度设置
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.xaxis.set_minor_locator(MultipleLocator(50))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    
    # === 坐标轴范围 ===
    ax.set_xlim(freq_mhz.min(), freq_mhz.max())
    y_min = power_db.min() - 8
    y_max = power_db.max() + 15
    ax.set_ylim(y_min, y_max)
    
    # === 标签样式 ===
    ax.set_xlabel(
        "Frequency (MHz)",
        fontsize=12,
        color=ELITE_COLORS["text_primary"],
        labelpad=12,
        weight='medium',
    )
    ax.set_ylabel(
        "Power Spectral Density (dB)",
        fontsize=12,
        color=ELITE_COLORS["text_primary"],
        labelpad=12,
        weight='medium',
    )
    
    # 刻度样式
    ax.tick_params(
        colors=ELITE_COLORS["text_secondary"],
        which='both',
        labelsize=9,
        width=0.5,
    )
    
    # 边框样式
    for spine in ax.spines.values():
        spine.set_color(ELITE_COLORS["border"])
        spine.set_linewidth(1)
    
    # === 主标题 ===
    fig.text(
        0.5, 0.96,
        title,
        fontsize=16,
        fontweight='bold',
        color=ELITE_COLORS["text_title"],
        ha='center',
        va='top',
    )
    
    # === 副标题 ===
    if subtitle:
        fig.text(
            0.5, 0.925,
            subtitle,
            fontsize=11,
            color=ELITE_COLORS["text_secondary"],
            ha='center',
            va='top',
            style='italic',
        )
    
    # === HUD风格信息面板 ===
    power_span = power_db.max() - power_db.min()
    jammer_count = len(jammer_regions) if jammer_regions else 0
    resolution = (freq_mhz[1] - freq_mhz[0]) if len(freq_mhz) > 1 else 1.0
    
    stats_text = (
        f"╔═══════════════════════════════╗\n"
        f"║  FREQUENCY RANGE              ║\n"
        f"║  {freq_mhz.min():.0f} - {freq_mhz.max():.0f} MHz               \n"
        f"║                               ║\n"
        f"║  POWER DYNAMICS               ║\n"
        f"║  Peak: {power_db.max():>7.1f} dB          ║\n"
        f"║  Floor: {power_db.min():>6.1f} dB          ║\n"
        f"║  Span: {power_span:>7.1f} dB          ║\n"
        f"║                               ║\n"
        f"║  SIGNAL ANALYSIS              ║\n"
        f"║  Jammers: {jammer_count:<2}                 ║\n"
        f"║  Resolution: {resolution:.2f} MHz       ║\n"
        f"║  Samples: {len(freq_mhz):,}            ║\n"
        f"╚═══════════════════════════════╝"
    )
    
    props = dict(
        boxstyle='round,pad=0.6',
        facecolor=ELITE_COLORS["panel_bg"],
        edgecolor=ELITE_COLORS["border"],
        alpha=0.95,
        linewidth=1,
    )
    
    ax.text(
        0.02, 0.97,
        stats_text,
        transform=ax.transAxes,
        fontsize=8.5,
        verticalalignment='top',
        color=ELITE_COLORS["text_primary"],
        bbox=props,
        family='monospace',
        linespacing=1.2,
    )
    
    # === 水印 ===
    if enable_watermark:
        fig.text(
            0.98, 0.02,
            "CLASSIFIED | SPECTRUM ANALYSIS SYSTEM v2.0",
            fontsize=7,
            color=ELITE_COLORS["text_secondary"],
            alpha=0.4,
            ha='right',
            va='bottom',
            family='monospace',
        )
    
    # === 保存 ===
    if save_path:
        fig.savefig(
            save_path,
            dpi=300,  # 高分辨率
            bbox_inches='tight',
            facecolor=ELITE_COLORS["background"],
            edgecolor='none',
        )
    
    if show:
        plt.show()
    else:
        plt.close(fig)
    
    return fig


def plot_comparison_elite(
    freq_mhz: np.ndarray,
    original: np.ndarray,
    recovered: np.ndarray,
    title: str = "SPECTRUM RECOVERY ANALYSIS",
    figsize: Tuple[int, int] = (16, 9),
    save_path: Optional[Path] = None,
    show: bool = False,
) -> plt.Figure:
    """Elite风格对比图"""
    fig = plt.figure(figsize=figsize, facecolor=ELITE_COLORS["background"])
    
    # 上图：频谱对比
    ax1 = fig.add_axes([0.08, 0.45, 0.88, 0.45])
    ax1.set_facecolor(ELITE_COLORS["plot_bg"])
    
    # 原始频谱（辉光效果）
    ax1.plot(freq_mhz, original, linewidth=3, color='#ff6b6b', alpha=0.1, zorder=7)
    ax1.plot(freq_mhz, original, linewidth=1, color='#ff3366', alpha=0.9, label='Original', zorder=10)
    
    # 恢复频谱（辉光效果）
    ax1.plot(freq_mhz, recovered, linewidth=3, color='#4ecdc4', alpha=0.1, zorder=8)
    ax1.plot(freq_mhz, recovered, linewidth=1, color='#00ffaa', alpha=0.9, label='Recovered', zorder=11, linestyle='--')
    
    ax1.set_xlim(freq_mhz.min(), freq_mhz.max())
    ax1.set_ylabel("Power (dB)", fontsize=11, color=ELITE_COLORS["text_primary"])
    ax1.grid(True, color=ELITE_COLORS["grid_major"], alpha=0.5)
    ax1.tick_params(colors=ELITE_COLORS["text_secondary"], labelsize=9)
    ax1.legend(
        loc='upper right',
        facecolor=ELITE_COLORS["panel_bg"],
        edgecolor=ELITE_COLORS["border"],
        labelcolor=ELITE_COLORS["text_primary"],
        fontsize=10,
        framealpha=0.95,
    )
    
    for spine in ax1.spines.values():
        spine.set_color(ELITE_COLORS["border"])
    
    # 下图：误差分析
    ax2 = fig.add_axes([0.08, 0.12, 0.88, 0.28])
    ax2.set_facecolor(ELITE_COLORS["plot_bg"])
    
    error = recovered - original
    ax2.fill_between(
        freq_mhz, error, 0,
        where=(error >= 0),
        alpha=0.6,
        color=ELITE_COLORS["success"],
        label='Positive Error',
    )
    ax2.fill_between(
        freq_mhz, error, 0,
        where=(error < 0),
        alpha=0.6,
        color=ELITE_COLORS["danger"],
        label='Negative Error',
    )
    ax2.axhline(y=0, color=ELITE_COLORS["text_secondary"], linewidth=1, linestyle='--')
    
    ax2.set_xlim(freq_mhz.min(), freq_mhz.max())
    ax2.set_xlabel("Frequency (MHz)", fontsize=11, color=ELITE_COLORS["text_primary"])
    ax2.set_ylabel("Error (dB)", fontsize=11, color=ELITE_COLORS["text_primary"])
    ax2.grid(True, color=ELITE_COLORS["grid_major"], alpha=0.5)
    ax2.tick_params(colors=ELITE_COLORS["text_secondary"], labelsize=9)
    ax2.legend(
        loc='upper right',
        facecolor=ELITE_COLORS["panel_bg"],
        edgecolor=ELITE_COLORS["border"],
        labelcolor=ELITE_COLORS["text_primary"],
        fontsize=9,
        framealpha=0.95,
    )
    
    for spine in ax2.spines.values():
        spine.set_color(ELITE_COLORS["border"])
    
    # 标题
    fig.text(
        0.5, 0.96,
        title,
        fontsize=16,
        fontweight='bold',
        color=ELITE_COLORS["text_title"],
        ha='center',
    )
    
    # 统计
    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error**2))
    max_err = np.max(np.abs(error))
    
    fig.text(
        0.5, 0.93,
        f"MAE: {mae:.2f} dB  |  RMSE: {rmse:.2f} dB  |  Max Error: {max_err:.2f} dB",
        fontsize=11,
        color=ELITE_COLORS["text_secondary"],
        ha='center',
    )
    
    # 水印
    fig.text(
        0.98, 0.02,
        "CLASSIFIED | SPECTRUM RECOVERY EVALUATION",
        fontsize=7,
        color=ELITE_COLORS["text_secondary"],
        alpha=0.4,
        ha='right',
        family='monospace',
    )
    
    if save_path:
        fig.savefig(
            save_path,
            dpi=300,
            bbox_inches='tight',
            facecolor=ELITE_COLORS["background"],
        )
    
    if show:
        plt.show()
    else:
        plt.close(fig)
    
    return fig
