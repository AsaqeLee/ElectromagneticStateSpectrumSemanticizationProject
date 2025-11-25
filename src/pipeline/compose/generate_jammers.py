"""任务一：六类干扰信号数据集生成脚本（Python 版 jam.m）。

本脚本参考根目录下的 `jam.m`，生成仅含干扰的 IQ 数据集：

- 六类干扰：noise_fm / single_tone / multi_tone / comb / partial_band_noise / sweep；
- 支持按 JNR 扫描、每类/每档 JNR 生成若干样本；
- 输出为每个样本一个 `.npz` 文件，包含 IQ 及元数据。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ..signal.jammers import JAMMER_REGISTRY, JammerConfig, generate_jammer
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from signal.jammers import JAMMER_REGISTRY, JammerConfig, generate_jammer


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _plot_spectrogram(iq: np.ndarray, fs_hz: float, title: str, png_path: Path | None) -> None:
    """简单时频图预览，与 jam.m 的时频预览功能对应。"""

    from scipy.signal import spectrogram

    f, t, sxx = spectrogram(iq, fs_hz, nperseg=1024, noverlap=768, nfft=2048, mode="magnitude")
    power_db = 20.0 * np.log10(sxx + np.finfo(float).eps)

    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.pcolormesh(t * 1e3, f / 1e6, power_db, shading="auto")
    ax.set_xlabel("时间 (ms)")
    ax.set_ylabel("频率 (MHz)")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="幅度 (dB)")
    fig.tight_layout()
    if png_path is not None:
        _ensure_dir(png_path.parent)
        fig.savefig(png_path, dpi=150)
    plt.close(fig)


def generate_dataset(
    output_root: Path,
    length: int,
    fs_hz: float,
    jnr_values: Sequence[float],
    samples_per_jnr: int,
    fc_span_hz: float,
    preview_samples_per_jnr: int,
    spectrograms_per_type_to_save: int,
) -> None:
    """核心逻辑：按 jam.m 规范生成干扰数据集。"""

    rng = np.random.default_rng()
    jam_types = list(JAMMER_REGISTRY.keys())

    iq_root = output_root / "IQ_jammer_only"
    meta_root = output_root / "metadata_jammer_only"
    spec_root = output_root / "spectrograms_jammer_only"
    _ensure_dir(output_root)
    _ensure_dir(iq_root)
    _ensure_dir(meta_root)

    spectrogram_save_count = {jam_type: 0 for jam_type in jam_types}

    for jam_type in jam_types:
        type_iq_root = iq_root / jam_type
        type_meta_path = meta_root / f"{jam_type}_metadata.csv"
        _ensure_dir(type_iq_root)

        with type_meta_path.open("w", encoding="utf-8") as meta_f:
            meta_f.write("jam_type,jnr_db,sample_index,fc_hz,bandwidth_hz,scale_factor\n")

            for jnr in jnr_values:
                cfg = JammerConfig(length=length, sample_rate_hz=fs_hz, jnr_db=float(jnr))
                jnr_dir = type_iq_root / f"JNR{int(jnr):02d}"
                _ensure_dir(jnr_dir)

                for sample_idx in range(1, samples_per_jnr + 1):
                    fc = (rng.random() * 2.0 - 1.0) * fc_span_hz
                    iq, bw = generate_jammer(jam_type, fc, cfg, rng=rng)

                    peak_val = float(np.max(np.abs(iq))) if iq.size > 0 else 0.0
                    if peak_val == 0.0:
                        scale = 0.0
                        iq_scaled = iq.astype(np.complex128, copy=True)
                    else:
                        scale = 0.999 / peak_val
                        iq_scaled = iq * scale

                    need_preview = sample_idx <= preview_samples_per_jnr
                    need_save_spec = spectrogram_save_count[jam_type] < spectrograms_per_type_to_save
                    if need_preview or need_save_spec:
                        spec_path: Path | None = None
                        if need_save_spec:
                            type_spec_root = spec_root / jam_type
                            spec_index = spectrogram_save_count[jam_type] + 1
                            spec_path = type_spec_root / f"{jam_type}_JNR{int(jnr):02d}_{sample_idx:05d}_{spec_index:02d}.png"
                            spectrogram_save_count[jam_type] = spec_index
                        _plot_spectrogram(
                            iq_scaled,
                            fs_hz,
                            title=f"{jam_type} | JNR {jnr} dB | 样本 {sample_idx}",
                            png_path=spec_path,
                        )

                    # 保存为 npz，包含 IQ 与必要元数据
                    npz_name = f"{jam_type}_JNR{int(jnr):02d}_{sample_idx:05d}.npz"
                    npz_path = jnr_dir / npz_name
                    np.savez(
                        npz_path,
                        iq=iq_scaled.astype(np.complex128),
                        sample_rate_hz=fs_hz,
                        center_freq_hz=fc,
                        jam_type=jam_type,
                        jnr_db=float(jnr),
                        bandwidth_hz=float(bw),
                        scale_factor=float(scale),
                    )

                    meta_f.write(
                        f"{jam_type},{jnr},{sample_idx},{fc:.6e},{bw:.6e},{scale:.6e}\n"
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description="任务一：六类干扰信号数据集生成（Python 版 jam.m）")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/jammer_dataset"),
        help="输出根目录，默认 data/jammer_dataset",
    )
    parser.add_argument("--length", type=int, default=32768, help="每个样本的采样点数")
    parser.add_argument("--sample-rate", type=float, default=125e6, help="采样率 Hz，默认 125e6")
    parser.add_argument(
        "--jnr-start",
        type=float,
        default=15.0,
        help="JNR 起始值 dB（包含），默认 15",
    )
    parser.add_argument(
        "--jnr-stop",
        type=float,
        default=16.0,
        help="JNR 结束值 dB（包含），默认 16",
    )
    parser.add_argument(
        "--jnr-step",
        type=float,
        default=1.0,
        help="JNR 步长 dB，默认 1",
    )
    parser.add_argument(
        "--samples-per-jnr",
        type=int,
        default=10,
        help="每个干扰类型在每个 JNR 下的样本数，默认 10（可根据需要加大）",
    )
    parser.add_argument(
        "--fc-span",
        type=float,
        default=1e6,
        help="干扰中心频率偏移范围 Hz，将在 [-fc_span, fc_span] 内均匀采样，默认 1e6",
    )
    parser.add_argument(
        "--preview-samples-per-jnr",
        type=int,
        default=1,
        help="每个 JNR 预览时频图的样本数，默认 1",
    )
    parser.add_argument(
        "--spectrograms-per-type",
        type=int,
        default=3,
        help="每类干扰保存的时频图数量上限，默认 3",
    )
    args = parser.parse_args()

    jnr_values = np.arange(args.jnr_start, args.jnr_stop + 1e-9, args.jnr_step)
    generate_dataset(
        output_root=args.output_root,
        length=args.length,
        fs_hz=args.sample_rate,
        jnr_values=jnr_values,
        samples_per_jnr=args.samples_per_jnr,
        fc_span_hz=args.fc_span,
        preview_samples_per_jnr=args.preview_samples_per_jnr,
        spectrograms_per_type_to_save=args.spectrograms_per_type,
    )


if __name__ == "__main__":
    main()

