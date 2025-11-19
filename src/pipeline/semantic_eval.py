"""任务3：语义参数恢复频谱并评估误差"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:  # pragma: no cover
    from ..semantics.decode import decode_file
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


def main() -> None:
    parser = argparse.ArgumentParser(description="任务3：语义驱动频谱恢复评估")
    parser.add_argument("--reference", type=Path, required=True, help="参考频谱 npy/npz")
    parser.add_argument("--semantic", type=Path, required=True, help="语义参数 JSON")
    parser.add_argument("--report", type=Path, default=Path("data/semantic_eval.json"), help="输出 JSON 报告")
    args = parser.parse_args()

    freq_mhz, ref_power = _load_reference(args.reference)
    params, recovered = decode_file(args.semantic)
    target_len = min(ref_power.size, recovered.size)
    ref = ref_power[:target_len]
    rec = recovered[:target_len]
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
        "samples": target_len,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
