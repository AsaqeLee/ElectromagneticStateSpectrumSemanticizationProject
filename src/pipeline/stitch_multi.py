"""多分片 IQ 频谱拼接 CLI：从指定文件夹中自动识别 *.bin 采样文件，并拼接宽带功率谱。

设计目标：
- 支持任意数量的分片（不仅是 2 段，13 段也可以）；
- 仅依赖文件名中的中心频率与采样率（如 comb_130MHz_204.8MHz_xxx.bin）；
- 当文件夹内分片不完整时，只拼接已有频段，其余频率范围保持为噪声底。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np

try:  # pragma: no cover - 兼容直接运行脚本
    from ..core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from ..core.schemas import IQData, SamplingConfig
    from ..signal.spectrum import compute_power_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from core.schemas import IQData, SamplingConfig
    from signal.spectrum import compute_power_spectrum


COMB_PATTERN = re.compile(
    r"(?P<prefix>.*?)(?P<center_mhz>\d+(?:\.\d+)?)MHz_(?P<fs_mhz>\d+(?:\.\d+)?)MHz_.*\.bin$",
    re.IGNORECASE,
)


def parse_comb_filename(path: Path) -> Tuple[float, float] | None:
    """从文件名推断中心频率与采样率（MHz）。

    例如：comb_130MHz_204.8MHz_11h01m58s.bin → (130.0, 204.8)
    """

    m = COMB_PATTERN.match(path.name)
    if not m:
        return None
    center = float(m.group("center_mhz"))
    fs = float(m.group("fs_mhz"))
    return center, fs


def load_int16_iq(path: Path) -> np.ndarray:
    """按 int16 I/Q 交织格式读取 .bin 文件。"""

    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2 != 0:
        raw = raw[:-1]
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    return i + 1j * q


def build_global_axis(freq_list: List[np.ndarray]) -> Tuple[np.ndarray, float]:
    """根据各分片频轴构造统一频率轴。"""

    if not freq_list:
        raise RuntimeError("没有可用频轴，无法拼接")
    step = float(freq_list[0][1] - freq_list[0][0])
    f_min = min(float(f[0]) for f in freq_list)
    f_max = max(float(f[-1]) for f in freq_list)
    # 加半个步长避免浮点误差导致右端缺 bin
    axis = np.arange(f_min, f_max + step / 2.0, step, dtype=float)
    return axis, step


def main() -> None:
    parser = argparse.ArgumentParser(description="多分片 IQ 频谱拼接")
    parser.add_argument("--input-dir", type=Path, required=True, help="包含 comb_*MHz_*.bin 的目录")
    parser.add_argument("--fft-size", type=int, default=262144, help="FFT 点数")
    parser.add_argument("--pattern", type=str, default="*.bin", help="文件匹配模式，默认 *.bin")
    parser.add_argument(
        "--ignore-names",
        action="store_true",
        help="忽略文件名中的中心频率，按默认中心频率列表 DEFAULT_WINDOW_CENTERS_MHZ 顺序分配",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=204.8e6,
        help="当 --ignore-names 为真时使用的采样率 Hz（所有分片共用），默认 204.8e6",
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("data/stitched_spectrum.npz"),
        help="输出 npz 路径（包含 freq_mhz 与 power_db）",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=Path("data/stitched_spectrum.png"),
        help="输出功率谱 PNG 路径",
    )
    parser.add_argument(
        "--min-freq",
        type=float,
        default=30.0,
        help="裁剪显示的最低频率 MHz（默认 30）",
    )
    parser.add_argument(
        "--max-freq",
        type=float,
        default=2500.0,
        help="裁剪显示的最高频率 MHz（默认 2500）",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    if not input_dir.is_dir():
        raise SystemExit(f"input-dir 不是有效目录: {input_dir}")

    files = sorted(input_dir.glob(args.pattern))
    segments_freq: List[np.ndarray] = []
    segments_power: List[np.ndarray] = []

    print(f"scan dir {input_dir}, pattern {args.pattern}")
    if args.ignore_names:
        if not files:
            raise SystemExit("no files found for stitching")
        if len(files) > len(DEFAULT_WINDOW_CENTERS_MHZ):
            raise SystemExit("more files than default window centers; please reduce or disable --ignore-names")
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

    if not segments_freq:
        raise SystemExit("未找到任何符合命名规则的 comb_*MHz_*.bin 文件，无法拼接")

    # 构造全局频率轴并初始化功率为噪声底
    global_axis, step = build_global_axis(segments_freq)
    global_power = np.full_like(global_axis, -180.0, dtype=float)

    # 对齐各分片频轴到全局频轴，并使用最大值策略合并
    for freq_mhz, power_db in zip(segments_freq, segments_power):
        idx = np.round((freq_mhz - global_axis[0]) / step).astype(int)
        valid = (idx >= 0) & (idx < global_power.size)
        idx = idx[valid]
        seg = power_db[valid]
        current = global_power[idx]
        global_power[idx] = np.maximum(current, seg)

    # 裁剪到指定频率范围（用于展示）
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
    main()
