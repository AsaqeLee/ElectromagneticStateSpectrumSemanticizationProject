"""频谱可视化模块。

提供两种风格：
1. simple - 简洁风格，适合内部调试
2. premium - 高级风格，适合甲方交付
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, List

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MultipleLocator, AutoMinorLocator
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class PlotStyle(str, Enum):
    SIMPLE = "simple"
    PREMIUM = "premium"


# Premium风格配色方案
PREMIUM_COLORS = {
    "background": "#0a0a0f",
    "plot_bg": "#12121a",
    "grid": "#2a2a3a",
    "grid_minor": "#1a1a2a",
    "spectrum": "#00d4ff",
    "spectrum_fill": "#00d4ff",
    "accent": "#ff6b6b",
    "text": "#e0e0e0",
    "text_secondary": "#808090",
    "highlight": "#ffd700",
    "jammer_region": "#ff6b6b",
}


def plot_spectrum_simple(
    freq_mhz: np.ndarray,
    power_db: np.ndarray,
    title: str = "Spectrum",
    figsize: Tuple[int, int] = (12, 5),
    save_path: Optional[Path] = None,
    show: bool = False,
) -> plt.Figure:
    """简洁风格频谱图。"""
    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(freq_mhz, power_db, linewidth=0.8, color='#1f77b4')
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(freq_mhz.min(), freq_mhz.max())

    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


def plot_spectrum_premium(
    freq_mhz: np.ndarray,
    power_db: np.ndarray,
    title: str = "Electromagnetic Spectrum Analysis",
    subtitle: str = "",
    figsize: Tuple[int, int] = (14, 7),
    save_path: Optional[Path] = None,
    show: bool = False,
    jammer_regions: Optional[List[Tuple[float, float]]] = None,
    annotations: Optional[List[dict]] = None,
) -> plt.Figure:
    """高级风格频谱图，适合甲方交付。

    参数:
    - jammer_regions: 干扰区域列表 [(start_mhz, end_mhz), ...]
    - annotations: 标注列表 [{"freq": 500, "text": "Jammer", "power": -80}, ...]
    """
    # 创建图形
    fig = plt.figure(figsize=figsize, facecolor=PREMIUM_COLORS["background"])

    # 主绘图区域
    ax = fig.add_axes([0.08, 0.12, 0.88, 0.78])
    ax.set_facecolor(PREMIUM_COLORS["plot_bg"])

    # 绘制频谱
    ax.plot(
        freq_mhz, power_db,
        linewidth=0.6,
        color=PREMIUM_COLORS["spectrum"],
        alpha=0.9,
        zorder=10,
    )

    # 填充效果
    ax.fill_between(
        freq_mhz, power_db, power_db.min() - 10,
        alpha=0.15,
        color=PREMIUM_COLORS["spectrum_fill"],
        zorder=5,
    )

    # 干扰区域标记
    if jammer_regions:
        for start, end in jammer_regions:
            ax.axvspan(
                start, end,
                alpha=0.1,
                color=PREMIUM_COLORS["jammer_region"],
                zorder=1,
            )
            # 顶部标记条
            ax.axhline(
                y=power_db.max() + 2,
                xmin=(start - freq_mhz.min()) / (freq_mhz.max() - freq_mhz.min()),
                xmax=(end - freq_mhz.min()) / (freq_mhz.max() - freq_mhz.min()),
                color=PREMIUM_COLORS["jammer_region"],
                linewidth=3,
                alpha=0.8,
            )

    # 标注
    if annotations:
        for ann in annotations:
            ax.annotate(
                ann.get("text", ""),
                xy=(ann["freq"], ann.get("power", power_db.max())),
                xytext=(ann["freq"], ann.get("power", power_db.max()) + 8),
                fontsize=9,
                color=PREMIUM_COLORS["highlight"],
                ha='center',
                arrowprops=dict(
                    arrowstyle="->",
                    color=PREMIUM_COLORS["highlight"],
                    alpha=0.7,
                ),
                zorder=20,
            )

    # 网格样式
    ax.grid(True, which='major', color=PREMIUM_COLORS["grid"], linewidth=0.5, alpha=0.5)
    ax.grid(True, which='minor', color=PREMIUM_COLORS["grid_minor"], linewidth=0.3, alpha=0.3)

    # 刻度设置
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.xaxis.set_minor_locator(MultipleLocator(50))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))

    # 坐标轴样式
    ax.set_xlim(freq_mhz.min(), freq_mhz.max())
    y_min = power_db.min() - 5
    y_max = power_db.max() + 10
    ax.set_ylim(y_min, y_max)

    # 标签样式
    ax.set_xlabel(
        "Frequency (MHz)",
        fontsize=11,
        color=PREMIUM_COLORS["text"],
        labelpad=10,
    )
    ax.set_ylabel(
        "Power (dB)",
        fontsize=11,
        color=PREMIUM_COLORS["text"],
        labelpad=10,
    )

    # 刻度颜色
    ax.tick_params(
        colors=PREMIUM_COLORS["text_secondary"],
        which='both',
        labelsize=9,
    )

    # 边框颜色
    for spine in ax.spines.values():
        spine.set_color(PREMIUM_COLORS["grid"])
        spine.set_linewidth(0.5)

    # 标题
    fig.text(
        0.5, 0.96,
        title,
        fontsize=14,
        fontweight='bold',
        color=PREMIUM_COLORS["text"],
        ha='center',
    )

    if subtitle:
        fig.text(
            0.5, 0.92,
            subtitle,
            fontsize=10,
            color=PREMIUM_COLORS["text_secondary"],
            ha='center',
        )

    # 统计信息面板（不显示底噪，因为底噪是随机波动的环境噪声）
    stats_text = (
        f"Freq Range: {freq_mhz.min():.0f} - {freq_mhz.max():.0f} MHz\n"
        f"Power Range: {power_db.min():.1f} to {power_db.max():.1f} dB\n"
        f"Resolution: {(freq_mhz[1] - freq_mhz[0]):.2f} MHz\n"
        f"Data Points: {len(freq_mhz):,}"
    )

    # 信息框
    props = dict(
        boxstyle='round,pad=0.5',
        facecolor=PREMIUM_COLORS["plot_bg"],
        edgecolor=PREMIUM_COLORS["grid"],
        alpha=0.9,
    )
    ax.text(
        0.02, 0.97,
        stats_text,
        transform=ax.transAxes,
        fontsize=8,
        verticalalignment='top',
        color=PREMIUM_COLORS["text_secondary"],
        bbox=props,
        family='monospace',
    )

    # 保存
    if save_path:
        fig.savefig(
            save_path,
            dpi=200,
            bbox_inches='tight',
            facecolor=PREMIUM_COLORS["background"],
            edgecolor='none',
        )

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


def plot_comparison_premium(
    freq_mhz: np.ndarray,
    original: np.ndarray,
    recovered: np.ndarray,
    title: str = "Spectrum Comparison",
    figsize: Tuple[int, int] = (14, 8),
    save_path: Optional[Path] = None,
    show: bool = False,
) -> plt.Figure:
    """高级对比图，用于展示原始与恢复频谱的对比。"""
    fig = plt.figure(figsize=figsize, facecolor=PREMIUM_COLORS["background"])

    # 上图：两条曲线对比
    ax1 = fig.add_axes([0.08, 0.42, 0.88, 0.48])
    ax1.set_facecolor(PREMIUM_COLORS["plot_bg"])

    ax1.plot(
        freq_mhz, original,
        linewidth=0.8,
        color='#ff6b6b',
        alpha=0.8,
        label='Original',
        zorder=10,
    )
    ax1.plot(
        freq_mhz, recovered,
        linewidth=0.8,
        color='#4ecdc4',
        alpha=0.8,
        label='Recovered',
        zorder=11,
    )

    ax1.set_xlim(freq_mhz.min(), freq_mhz.max())
    ax1.set_ylabel("Power (dB)", fontsize=10, color=PREMIUM_COLORS["text"])
    ax1.grid(True, color=PREMIUM_COLORS["grid"], alpha=0.5)
    ax1.tick_params(colors=PREMIUM_COLORS["text_secondary"], labelsize=9)
    ax1.legend(
        loc='upper right',
        facecolor=PREMIUM_COLORS["plot_bg"],
        edgecolor=PREMIUM_COLORS["grid"],
        labelcolor=PREMIUM_COLORS["text"],
        fontsize=9,
    )

    for spine in ax1.spines.values():
        spine.set_color(PREMIUM_COLORS["grid"])

    # 下图：误差
    ax2 = fig.add_axes([0.08, 0.12, 0.88, 0.25])
    ax2.set_facecolor(PREMIUM_COLORS["plot_bg"])

    error = recovered - original
    ax2.fill_between(
        freq_mhz, error, 0,
        where=(error >= 0),
        alpha=0.6,
        color='#4ecdc4',
        label='Positive',
    )
    ax2.fill_between(
        freq_mhz, error, 0,
        where=(error < 0),
        alpha=0.6,
        color='#ff6b6b',
        label='Negative',
    )
    ax2.axhline(y=0, color=PREMIUM_COLORS["text_secondary"], linewidth=0.5)

    ax2.set_xlim(freq_mhz.min(), freq_mhz.max())
    ax2.set_xlabel("Frequency (MHz)", fontsize=10, color=PREMIUM_COLORS["text"])
    ax2.set_ylabel("Error (dB)", fontsize=10, color=PREMIUM_COLORS["text"])
    ax2.grid(True, color=PREMIUM_COLORS["grid"], alpha=0.5)
    ax2.tick_params(colors=PREMIUM_COLORS["text_secondary"], labelsize=9)

    for spine in ax2.spines.values():
        spine.set_color(PREMIUM_COLORS["grid"])

    # 标题和统计
    fig.text(
        0.5, 0.96,
        title,
        fontsize=14,
        fontweight='bold',
        color=PREMIUM_COLORS["text"],
        ha='center',
    )

    mae = np.mean(np.abs(error))
    max_err = np.max(np.abs(error))
    fig.text(
        0.5, 0.92,
        f"MAE: {mae:.2f} dB  |  Max Error: {max_err:.2f} dB",
        fontsize=10,
        color=PREMIUM_COLORS["text_secondary"],
        ha='center',
    )

    if save_path:
        fig.savefig(
            save_path,
            dpi=200,
            bbox_inches='tight',
            facecolor=PREMIUM_COLORS["background"],
        )

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


def plot_multi_segment_premium(
    stitched_freq: np.ndarray,
    stitched_power: np.ndarray,
    coverage_map: np.ndarray,
    segment_count: int,
    title: str = "Multi-Segment Spectrum Stitching",
    figsize: Tuple[int, int] = (14, 8),
    save_path: Optional[Path] = None,
    show: bool = False,
) -> plt.Figure:
    """高级多分段拼接图。"""
    fig = plt.figure(figsize=figsize, facecolor=PREMIUM_COLORS["background"])

    # 上图：拼接频谱
    ax1 = fig.add_axes([0.08, 0.42, 0.88, 0.48])
    ax1.set_facecolor(PREMIUM_COLORS["plot_bg"])

    ax1.plot(
        stitched_freq, stitched_power,
        linewidth=0.5,
        color=PREMIUM_COLORS["spectrum"],
        zorder=10,
    )
    ax1.fill_between(
        stitched_freq, stitched_power, stitched_power.min() - 5,
        alpha=0.1,
        color=PREMIUM_COLORS["spectrum_fill"],
    )

    ax1.set_xlim(stitched_freq.min(), stitched_freq.max())
    ax1.set_ylabel("Power (dB)", fontsize=10, color=PREMIUM_COLORS["text"])
    ax1.grid(True, color=PREMIUM_COLORS["grid"], alpha=0.5)
    ax1.tick_params(colors=PREMIUM_COLORS["text_secondary"], labelsize=9)

    for spine in ax1.spines.values():
        spine.set_color(PREMIUM_COLORS["grid"])

    # 下图：覆盖图
    ax2 = fig.add_axes([0.08, 0.12, 0.88, 0.25])
    ax2.set_facecolor(PREMIUM_COLORS["plot_bg"])

    # 用颜色表示覆盖次数
    colors = np.where(coverage_map == 0, '#ff6b6b',
             np.where(coverage_map == 1, '#4ecdc4', '#ffd700'))

    for i in range(len(stitched_freq) - 1):
        ax2.axvspan(
            stitched_freq[i], stitched_freq[i+1],
            ymin=0, ymax=1,
            color=colors[i],
            alpha=0.6,
        )

    ax2.set_xlim(stitched_freq.min(), stitched_freq.max())
    ax2.set_xlabel("Frequency (MHz)", fontsize=10, color=PREMIUM_COLORS["text"])
    ax2.set_ylabel("Coverage", fontsize=10, color=PREMIUM_COLORS["text"])
    ax2.set_yticks([])
    ax2.tick_params(colors=PREMIUM_COLORS["text_secondary"], labelsize=9)

    # 图例
    legend_elements = [
        mpatches.Patch(color='#ff6b6b', alpha=0.6, label='No coverage'),
        mpatches.Patch(color='#4ecdc4', alpha=0.6, label='Single'),
        mpatches.Patch(color='#ffd700', alpha=0.6, label='Overlap'),
    ]
    ax2.legend(
        handles=legend_elements,
        loc='upper right',
        facecolor=PREMIUM_COLORS["plot_bg"],
        edgecolor=PREMIUM_COLORS["grid"],
        labelcolor=PREMIUM_COLORS["text"],
        fontsize=8,
    )

    for spine in ax2.spines.values():
        spine.set_color(PREMIUM_COLORS["grid"])

    # 标题
    fig.text(
        0.5, 0.96,
        title,
        fontsize=14,
        fontweight='bold',
        color=PREMIUM_COLORS["text"],
        ha='center',
    )
    fig.text(
        0.5, 0.92,
        f"{segment_count} segments stitched  |  Coverage: {(coverage_map > 0).sum() / len(coverage_map) * 100:.1f}%",
        fontsize=10,
        color=PREMIUM_COLORS["text_secondary"],
        ha='center',
    )

    if save_path:
        fig.savefig(
            save_path,
            dpi=200,
            bbox_inches='tight',
            facecolor=PREMIUM_COLORS["background"],
        )

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig
