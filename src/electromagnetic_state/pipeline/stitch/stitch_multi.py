"""??? IQ ???? CLI:??????????? *.bin ????,?????????

????:
- ?????????(??? 2 ?,13 ????);
- ????????????????(? comb_130MHz_204.8MHz_xxx.bin);
- ???????????,???????,?????????????
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - ????????
    from ...core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from ...core.schemas import IQData, SamplingConfig
    from ...signal.spectrum import compute_power_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from electromagnetic_state.core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from electromagnetic_state.core.schemas import IQData, SamplingConfig
    from electromagnetic_state.signal.spectrum import compute_power_spectrum


COMB_PATTERN = re.compile(
    r"(?P<prefix>.*?)(?P<center_mhz>\d+(?:\.\d+)?)MHz_(?P<fs_mhz>\d+(?:\.\d+)?)MHz_.*\.bin$",
    re.IGNORECASE,
)


def parse_comb_filename(path: Path) -> Optional[Tuple[float, float]]:
    """??????????????(MHz)?

    ??:comb_130MHz_204.8MHz_11h01m58s.bin  (130.0, 204.8)
    """

    m = COMB_PATTERN.match(path.name)
    if not m:
        return None
    center = float(m.group("center_mhz"))
    fs = float(m.group("fs_mhz"))
    return center, fs


def load_int16_iq(path: Path) -> np.ndarray:
    """? int16 I/Q ?????? .bin ???"""

    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2 != 0:
        raw = raw[:-1]
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    return i + 1j * q


def build_global_axis(freq_list: List[np.ndarray]) -> Tuple[np.ndarray, float]:
    """???????????????

    ?????????????????:
    - ????????????,??????/????;
    - ?? `np.arange` ???????,?????????,
      ???????????????????????
    """

    if not freq_list:
        raise RuntimeError("??????,????")
    if any(arr.size < 2 for arr in freq_list):
        raise RuntimeError("????????,????????")
    step = float(freq_list[0][1] - freq_list[0][0])
    f_min = min(float(f[0]) for f in freq_list)
    f_max = max(float(f[-1]) for f in freq_list)
    # ???????????????? bin
    axis = np.arange(f_min, f_max + step / 2.0, step, dtype=float)
    return axis, step


def _validate_freq_axes(freq_list: List[np.ndarray], sample_rates: List[float]) -> None:
    """??:????????????????????,???????

    ?????????,?????????"????":
    ?????????????????,?????????
    """

    base_step = float(freq_list[0][1] - freq_list[0][0])
    base_sr = sample_rates[0]
    for idx, freq in enumerate(freq_list):
        if not np.all(np.diff(freq) > 0):
            raise SystemExit(f"?? {idx} ??????,????????????")
        step = float(freq[1] - freq[0])
        if not np.isclose(step, base_step, rtol=1e-3, atol=1e-6):
            raise SystemExit(f"?? {idx} ???? {step:.6f} MHz ??? {base_step:.6f} MHz ???,??????")
        if not np.isclose(sample_rates[idx], base_sr, rtol=1e-4):
            raise SystemExit(f"?? {idx} ??? {sample_rates[idx]:.3f} Hz ??? {base_sr:.3f} Hz ???,??????")


def main() -> None:
    parser = argparse.ArgumentParser(description="??? IQ ????")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data_segment"),
        help="?? comb_*MHz_*.bin ???,?? data_segment",
    )
    parser.add_argument("--fft-size", type=int, default=262144, help="FFT ??")
    parser.add_argument("--pattern", type=str, default="*.bin", help="??????,?? *.bin")
    parser.add_argument(
        "--ignore-names",
        action="store_true",
        help="???????????,????????? DEFAULT_WINDOW_CENTERS_MHZ ????",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=204.8e6,
        help="? --ignore-names ????????? Hz(??????),?? 204.8e6",
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("data/stitched_spectrum.npz"),
        help="?? npz ??(?? freq_mhz ? power_db)",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=Path("data/stitched_spectrum.png"),
        help="????? PNG ??",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=30.0,
        help="????????? MHz(?? 30)",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=2500.0,
        help="????????? MHz(?? 2500)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    if not input_dir.is_dir():
        raise SystemExit(f"input-dir ??????: {input_dir}")

    files = sorted(input_dir.glob(args.pattern))
    segments_freq: List[np.ndarray] = []
    segments_power: List[np.ndarray] = []
    sample_rates: List[float] = []

    print(f"scan dir {input_dir}, pattern {args.pattern}")
    if args.ignore_names:
        if not files:
            raise SystemExit("no files found for stitching")
        expected = len(DEFAULT_WINDOW_CENTERS_MHZ)
        if len(files) > expected:
            raise SystemExit(
                f"--ignore-names ???? {expected} ?,?? {len(files)} ?;??????,???????????????"
            )
        if len(files) < expected:
            # ????,files ????? 13 ??? .bin ???
            # ???? DEFAULT_WINDOW_CENTERS_MHZ ?????,??
            # ????????,??????????????
            print(
                f"[WARN] 只找到 {len(files)} ? .bin ??,?? {expected} ?;"
                "将按文件排序依次绑定较低频率窗口, 默认缺少高频端窗口"
            )
        for idx, path in enumerate(files):
            center_mhz = DEFAULT_WINDOW_CENTERS_MHZ[idx]
            center_hz = center_mhz * 1e6
            fs_hz = float(args.sample_rate)
            print(f"load {path.name}: center={center_mhz} MHz, fs={fs_hz/1e6:.1f} MHz (ignore names)")

            samples = load_int16_iq(path)
            cfg = SamplingConfig(sample_rate_hz=fs_hz, center_freq_hz=center_hz, fft_size=args.fft_size)
            iq = IQData(samples=samples, sample_rate_hz=cfg.sample_rate_hz, center_freq_hz=cfg.center_freq_hz)
            freq_mhz, power_db = compute_power_spectrum(iq, cfg)
            segments_freq.append(freq_mhz)
            segments_power.append(power_db)
            sample_rates.append(fs_hz)
    else:
        for path in files:
            info = parse_comb_filename(path)
            if info is None:
                print(f"skip file (name not matched): {path.name}")
                continue
            center_mhz, fs_mhz = info
            center_hz = center_mhz * 1e6
            fs_hz = fs_mhz * 1e6
            print(f"load {path.name}: center={center_mhz} MHz, fs={fs_mhz} MHz")

            samples = load_int16_iq(path)
            cfg = SamplingConfig(sample_rate_hz=fs_hz, center_freq_hz=center_hz, fft_size=args.fft_size)
            iq = IQData(samples=samples, sample_rate_hz=cfg.sample_rate_hz, center_freq_hz=cfg.center_freq_hz)
            freq_mhz, power_db = compute_power_spectrum(iq, cfg)
            segments_freq.append(freq_mhz)
            segments_power.append(power_db)
            sample_rates.append(fs_hz)

    if not segments_freq:
        raise SystemExit("???????????? comb_*MHz_*.bin ??,????")

    _validate_freq_axes(segments_freq, sample_rates)

    # ?????????????????
    global_axis, step = build_global_axis(segments_freq)
    global_power = np.full_like(global_axis, -180.0, dtype=float)

    # ????????????,??????????
    for freq_mhz, power_db in zip(segments_freq, segments_power):
        idx = np.round((freq_mhz - global_axis[0]) / step).astype(int)
        valid = (idx >= 0) & (idx < global_power.size)
        idx = idx[valid]
        seg = power_db[valid]
        current = global_power[idx]
        global_power[idx] = np.maximum(current, seg)

    # ?????????(????)
    mask = (global_axis >= args.min_freq) & (global_axis <= args.max_freq)
    freq_cropped = global_axis[mask]
    power_cropped = global_power[mask]

    args.output_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output_npz, freq_mhz=freq_cropped, power_db=power_cropped)

    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(freq_cropped, power_cropped, linewidth=0.7)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title("Stitched spectrum")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    plt.savefig(args.output_png, dpi=120)
    plt.close(fig)

    print(f"stitched spectrum saved to {args.output_npz} and {args.output_png}")


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
