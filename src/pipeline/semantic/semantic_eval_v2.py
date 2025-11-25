"""任务3(v2)：基于 v2 语义编码恢复频谱并评估误差。

v2 语义格式参见 `docs/semantic_encoding_requirements.md`，使用
`freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db/jammer_regions`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:  # pragma: no cover
    from .semantic_eval import _load_reference, _validate_alignment
    from ...semantics.decode_v2 import decode_file_v2
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from pipeline.semantic.semantic_eval import _load_reference, _validate_alignment
    from semantics.decode_v2 import decode_file_v2


def main() -> None:
    parser = argparse.ArgumentParser(description="任务3(v2)：v2 语义驱动频谱恢复评估")
    parser.add_argument("--reference", type=Path, required=True, help="参考频谱 npy/npz")
    parser.add_argument("--semantic", type=Path, required=True, help="v2 语义参数 JSON")
    parser.add_argument(
        "--report", type=Path, default=Path("data/semantic_eval_v2.json"), help="输出 JSON 报告"
    )
    parser.add_argument(
        "--band-min",
        type=float,
        default=None,
        help="评估频段下限 MHz（默认不裁剪）",
    )
    parser.add_argument(
        "--band-max",
        type=float,
        default=None,
        help="评估频段上限 MHz（默认不裁剪）",
    )
    args = parser.parse_args()

    freq_mhz, ref_power = _load_reference(args.reference)
    params, recovered = decode_file_v2(args.semantic)
    freq_semantic = np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.num_bins)
    _validate_alignment(freq_mhz, freq_semantic)

    if recovered.size != freq_semantic.size:
        raise SystemExit(
            f"语义恢复长度 {recovered.size} 与频率轴 {freq_semantic.size} 不一致，可能输入参数错误"
        )

    freq = freq_mhz
    ref = ref_power
    rec = recovered

    if args.band_min is not None or args.band_max is not None:
        mask = np.ones_like(freq, dtype=bool)
        if args.band_min is not None:
            mask &= freq >= args.band_min
        if args.band_max is not None:
            mask &= freq <= args.band_max
        freq = freq[mask]
        ref = ref[mask]
        rec = rec[mask]

    diff = rec - ref
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    max_err = float(np.max(np.abs(diff)))
    report = {
        "mae_db": mae,
        "rmse_db": rmse,
        "max_err_db": max_err,
        "samples": freq.size,
        "band_min_mhz": args.band_min,
        "band_max_mhz": args.band_max,
        "semantic_freq_min_mhz": params.freq_min_mhz,
        "semantic_freq_max_mhz": params.freq_max_mhz,
        "semantic_num_bins": params.num_bins,
        "semantic_noise_floor_db": params.noise_floor_db,
        "num_regions": len(params.jammer_regions),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

