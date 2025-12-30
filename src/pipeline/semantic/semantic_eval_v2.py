"""任务3(v2)：基于 v2 语义编码恢复频谱并评估误差。

v2 语义格式参见 `docs/semantic_encoding_requirements.md`，使用
`freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db/jammer_regions`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

try:  # pragma: no cover
    from ...semantics.decode_v2 import decode_file_v2
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from semantics.decode_v2 import decode_file_v2


def _load_reference(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """加载参考频谱。

    - 若为 npz，则优先使用其中保存的 freq_mhz/power_db；
    - 若为 npy，则仅视为功率数组，频率轴按 30–2500 MHz 作线性插值生成。

    v1 评估脚本删除后，在此内置一份供 v2 评估复用。
    """
    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            return data["freq_mhz"], data["power_db"]
    power = np.load(path)
    freq = np.linspace(30, 2500, power.size)
    return freq, power


def _load_reference_with_coverage(
    path: Path,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    """加载参考频谱，并在存在 coverage_map 时一并返回。

    - npz: 读取 freq_mhz/power_db，若存在 coverage_map 一并返回；
    - npy: 退化为 _load_reference 行为（频轴按 30–2500 MHz 均匀插值），无 coverage。
    """

    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            freq = data["freq_mhz"]
            power = data["power_db"]
            coverage = data.get("coverage_map")
            return freq, power, coverage

    freq, power = _load_reference(path)
    return freq, power, None


def _resample_reference_to_semantic_axis(
    freq_ref: np.ndarray,
    power_ref: np.ndarray,
    freq_semantic: np.ndarray,
    noise_floor_db: float,
    coverage_map: Optional[np.ndarray] = None,
) -> np.ndarray:
    """将参考谱重采样到语义频轴上，按“并集 + 底噪以任务三为准”的规则对齐。

    规则：
    - 频率轴统一使用语义轴 freq_semantic（任务三的频谱轴）；
    - 对于参考谱中 coverage_map 为 0 的点视为“无覆盖”，其功率强制设置为 noise_floor_db；
    - 在 freq_semantic 超出参考谱频率范围的区域，参考谱功率统一视为 noise_floor_db；
    - 其余点使用线性插值将参考谱映射到 freq_semantic 上。
    """

    if freq_ref.size == 0 or power_ref.size == 0:
        raise SystemExit("参考谱为空，无法进行语义评估")

    power = power_ref.astype(float).copy()

    # 若存在覆盖图，则将“无覆盖”点的功率直接拉到语义底噪
    if coverage_map is not None:
        if coverage_map.shape != power.shape:
            raise SystemExit(
                f"coverage_map 长度 {coverage_map.size} 与参考功率 {power.size} 不一致"
            )
        power[coverage_map == 0] = noise_floor_db

    # 确保频率轴单调递增
    order = np.argsort(freq_ref)
    freq_sorted = freq_ref[order]
    power_sorted = power[order]

    # 线性插值到语义频轴
    ref_on_semantic = np.interp(freq_semantic, freq_sorted, power_sorted)

    # 超出参考频率范围的区域，统一视为“无参考覆盖”，按语义底噪填充
    mask_low = freq_semantic < freq_sorted[0]
    mask_high = freq_semantic > freq_sorted[-1]
    ref_on_semantic[mask_low | mask_high] = noise_floor_db

    return ref_on_semantic


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

    # 1. 加载参考频谱（任务二输出）和语义恢复结果（任务三输出）
    freq_ref, ref_power, coverage = _load_reference_with_coverage(args.reference)
    params, recovered = decode_file_v2(args.semantic)
    freq_semantic = np.linspace(params.freq_min_mhz, params.freq_max_mhz, params.num_bins)

    if recovered.size != freq_semantic.size:
        raise SystemExit(
            f"语义恢复长度 {recovered.size} 与频率轴 {freq_semantic.size} 不一致，可能输入参数错误"
        )

    # 2. 将参考谱重采样到语义频轴上：
    #    - 频率轴使用任务三的 freq_semantic（即“全局语义轴”）；
    #    - 参考谱与语义谱取“并集”，但底噪以语义参数的 noise_floor_db 为准。
    ref_on_semantic = _resample_reference_to_semantic_axis(
        freq_ref=freq_ref,
        power_ref=ref_power,
        freq_semantic=freq_semantic,
        noise_floor_db=params.noise_floor_db,
        coverage_map=coverage,
    )

    freq = freq_semantic
    ref = ref_on_semantic
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
    # Fix Windows console encoding for CLI use
    if sys.platform == "win32":
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    
    main()
