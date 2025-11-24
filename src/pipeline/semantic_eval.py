"""任务3：语义参数恢复频谱并评估误差"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:  # pragma: no cover
    from ..semantics.decode import decode_file
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from semantics.decode import decode_file


def _load_reference(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """加载参考频谱。

    - 若为 npz，则优先使用其中保存的 freq_mhz/power_db；
    - 若为 npy，则仅视为功率数组，频率轴按 30–2500 MHz 作线性插值生成，
      主要用于快速 demo，而非严格物理刻度。
    """
    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            return data["freq_mhz"], data["power_db"]
    power = np.load(path)
    freq = np.linspace(30, 2500, power.size)
    return freq, power


def _build_semantic_axis(params) -> np.ndarray:
    """根据语义参数构造频率轴，保证与语义谱长度一致。"""
    return np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.fenbianlv)


def _validate_alignment(ref_axis: np.ndarray, semantic_axis: np.ndarray) -> None:
    """防止静默错位：频率轴长度与步长必须一致，否则终止。"""

    if ref_axis.size != semantic_axis.size:
        raise SystemExit(
            f"参考谱长度 {ref_axis.size} 与语义谱长度 {semantic_axis.size} 不同，无法对齐评估；请确保分辨率一致或先重采样"
        )
    if not (np.all(np.diff(ref_axis) > 0) and np.all(np.diff(semantic_axis) > 0)):
        raise SystemExit("参考谱或语义谱频率轴非递增，数据源可能有误")
    ref_step = float(np.median(np.diff(ref_axis)))
    sem_step = float(np.median(np.diff(semantic_axis)))
    if not np.isclose(ref_step, sem_step, rtol=1e-3, atol=1e-6):
        raise SystemExit(
            f"频率分辨率不匹配：参考 {ref_step:.6f} MHz, 语义 {sem_step:.6f} MHz；请重采样后再评估"
        )
    if not np.isclose(ref_axis[0], semantic_axis[0], atol=ref_step * 2) or not np.isclose(
        ref_axis[-1], semantic_axis[-1], atol=ref_step * 2
    ):
        raise SystemExit(
            f"频率范围不匹配：参考 [{ref_axis[0]:.3f}, {ref_axis[-1]:.3f}] MHz, 语义 [{semantic_axis[0]:.3f}, {semantic_axis[-1]:.3f}] MHz"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="任务3：语义驱动频谱恢复评估")
    parser.add_argument("--reference", type=Path, required=True, help="参考频谱 npy/npz")
    parser.add_argument("--semantic", type=Path, required=True, help="语义参数 JSON")
    parser.add_argument("--report", type=Path, default=Path("data/semantic_eval.json"), help="输出 JSON 报告")
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
    params, recovered = decode_file(args.semantic)
    freq_semantic = _build_semantic_axis(params)
    _validate_alignment(freq_mhz, freq_semantic)

    if recovered.size != freq_semantic.size:
        raise SystemExit(f"语义恢复长度 {recovered.size} 与频率轴 {freq_semantic.size} 不一致，可能输入参数错误")

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
        "yonghu": params.yonghu,
        "youwu": params.youwu,
        "mae_db": mae,
        "rmse_db": rmse,
        "max_err_db": max_err,
        "samples": freq.size,
        "band_min_mhz": args.band_min,
        "band_max_mhz": args.band_max,
        "semantic_freq_min_mhz": params.freq_min_mhz,
        "semantic_freq_max_mhz": params.freq_max_mhz,
        "semantic_resolution_mhz": params.resolution_mhz,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
