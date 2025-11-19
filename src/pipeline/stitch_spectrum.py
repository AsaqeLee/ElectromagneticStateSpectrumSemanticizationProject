"""任务2：拼接分片频谱，生成 30–2500 MHz 参考谱。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import numpy as np

try:  # pragma: no cover
    from ..core.config import default_config
    from ..io.reader import chunk_iq, load_iq_file
    from ..signal.segmentation import segment_bands
    from ..signal.spectrum import compute_power_spectrum, stitch_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from core.config import default_config
    from io.reader import chunk_iq, load_iq_file
    from signal.segmentation import segment_bands
    from signal.spectrum import compute_power_spectrum, stitch_spectrum


def _init_segments(masks: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    return {name: np.full(mask.sum(), -180.0, dtype=float) for name, mask in masks.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="任务2：拼接分片频谱")
    parser.add_argument("--iq", type=Path, required=True, help="任务1生成的 IQ 文件")
    parser.add_argument("--chunk-size", type=int, default=4096, help="每段 FFT 样本数")
    parser.add_argument("--output", type=Path, default=Path("data/demo_reference_spectrum.npz"), help="输出 npz")
    args = parser.parse_args()

    cfg = default_config()
    iq = load_iq_file(args.iq, sample_rate_hz=cfg.sampling.sample_rate_hz, center_freq_hz=cfg.sampling.center_freq_hz)
    masks = segment_bands(cfg.sampling, cfg.coarse_bands, cfg.window_centers_mhz)
    segments = _init_segments(masks)
    freq_axis = None

    for chunk in chunk_iq(iq, args.chunk_size):
        freq_axis, power_db = compute_power_spectrum(chunk, cfg.sampling)
        for name, mask in masks.items():
            current = segments[name]
            segment = power_db[mask]
            segments[name] = np.maximum(current, segment)

    if freq_axis is None:
        raise RuntimeError("未读取到任何样本")

    stitched = stitch_spectrum(freq_axis, segments, masks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output, freq_mhz=freq_axis, power_db=stitched)
    print(f"拼接完成 -> {args.output}")


if __name__ == "__main__":
    main()
