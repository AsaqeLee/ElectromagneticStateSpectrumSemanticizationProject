"""可视化语义恢复频谱，并可选择与参考谱进行对比。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover
    from ...semantics.decode import decode_file
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from semantics.decode import decode_file


def _load_reference(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            return data["freq_mhz"], data["power_db"]
    power = np.load(path)
    freq = np.linspace(30, 2500, power.size)
    return freq, power


def _build_semantic_axis(params) -> np.ndarray:
    return np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.fenbianlv)


def _validate_alignment(ref_axis: np.ndarray, semantic_axis: np.ndarray) -> None:
    if ref_axis.size != semantic_axis.size:
        raise SystemExit(
            f"参考谱长度 {ref_axis.size} 与语义谱长度 {semantic_axis.size} 不同，无法对齐绘制；请重采样或修正输入"
        )
    if not (np.all(np.diff(ref_axis) > 0) and np.all(np.diff(semantic_axis) > 0)):
        raise SystemExit("参考谱或语义谱频率轴非递增，数据源可能异常")
    ref_step = float(np.median(np.diff(ref_axis)))
    sem_step = float(np.median(np.diff(semantic_axis)))
    if not np.isclose(ref_step, sem_step, rtol=1e-3, atol=1e-6):
        raise SystemExit(
            f"频率分辨率不一致：参考 {ref_step:.6f} MHz, 语义 {sem_step:.6f} MHz；请先重采样"
        )
    if not np.isclose(ref_axis[0], semantic_axis[0], atol=ref_step * 2) or not np.isclose(
        ref_axis[-1], semantic_axis[-1], atol=ref_step * 2
    ):
        raise SystemExit(
            f"频率范围不匹配：参考 [{ref_axis[0]:.3f}, {ref_axis[-1]:.3f}] MHz, 语义 [{semantic_axis[0]:.3f}, {semantic_axis[-1]:.3f}] MHz"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制语义恢复频谱，可选与参考谱比较")
    parser.add_argument("--semantic", type=Path, required=True, help="语义 JSON")
    parser.add_argument("--reference", type=Path, help="可选，参考谱 npz/npy，用于对比")
    parser.add_argument("--png", type=Path, default=Path("data/semantic_plot.png"), help="输出图像路径")
    args = parser.parse_args()

    params, recovered = decode_file(args.semantic)
    freq_semantic = _build_semantic_axis(params)

    if recovered.size != freq_semantic.size:
        raise SystemExit(f"语义恢复长度 {recovered.size} 与频率轴 {freq_semantic.size} 不一致，输入参数可能有误")

    if args.reference:
        freq_ref, power_ref = _load_reference(args.reference)
        _validate_alignment(freq_ref, freq_semantic)
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
        axes[0].plot(freq_ref, power_ref, linewidth=0.7, label="Reference")
        axes[0].set_title("参考频谱")
        axes[1].plot(freq_semantic, recovered, linewidth=0.7, color="orange", label="Semantic recovery")
        axes[1].set_title("语义恢复频谱")
        axes[1].set_xlabel("Frequency (MHz)")
        for ax in axes:
            ax.set_ylabel("Power (dB)")
            ax.grid(True, alpha=0.3)
        fig.suptitle(f"语义文件：{args.semantic.name}")
    else:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(freq_semantic, recovered, linewidth=0.8)
        ax.set_title(f"语义恢复频谱：{args.semantic.name}")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        ax.grid(True, alpha=0.3)

    args.png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    plt.savefig(args.png, dpi=120)
    plt.close(fig)
    print(f"semantic plot saved to {args.png}")


if __name__ == "__main__":
    main()
