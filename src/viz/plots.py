"""常用绘图工具。"""
from __future__ import annotations

from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# 尽量使用系统中可用的中文字体，避免中文字符缺失告警
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def plot_spectrum(freq_mhz: np.ndarray, power_db: np.ndarray, title: str = "功率谱", ax: Optional[plt.Axes] = None) -> plt.Axes:
    ax = ax or plt.gca()
    ax.plot(freq_mhz, power_db, linewidth=0.8)
    ax.set_xlabel("频率 (MHz)")
    ax.set_ylabel("功率 (dB)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    return ax


def plot_comparison(freq_mhz: np.ndarray, reference: np.ndarray, recovered: np.ndarray, title: str = "语义恢复对比") -> plt.Figure:
    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    plot_spectrum(freq_mhz, reference, title="参考频谱", ax=axes[0])
    plot_spectrum(freq_mhz, recovered, title="语义恢复频谱", ax=axes[1])
    fig.suptitle(title)
    fig.tight_layout()
    return fig
