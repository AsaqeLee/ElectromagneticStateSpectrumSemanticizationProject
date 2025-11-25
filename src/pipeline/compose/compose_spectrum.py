"""任务一：在 30-2500 MHz 频段内任意组合生成干扰功率谱。

演示如何使用 spectrum_composer 模块在宽带频段内组合多个干扰信号。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:  # pragma: no cover
    from ..signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
except ImportError:  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src"))
    from signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum


def parse_jammer_spec(spec_str: str) -> tuple[str, float, float]:
    """解析干扰配置字符串。

    格式：jam_type:center_freq_mhz:jnr_db
    例如：single_tone:500:20
    """
    parts = spec_str.split(":")
    if len(parts) != 3:
        raise ValueError(f"干扰配置格式错误，应为 'jam_type:center_freq_mhz:jnr_db'，实际：{spec_str}")
    jam_type = parts[0]
    center_freq_mhz = float(parts[1])
    jnr_db = float(parts[2])
    return jam_type, center_freq_mhz, jnr_db


def load_jammer_config_file(path: Path) -> list[tuple[str, float, float]]:
    """从 JSON 文件加载干扰配置。

    JSON 格式示例：
    {
        "jammers": [
            {"type": "single_tone", "center_freq_mhz": 500, "jnr_db": 20},
            {"type": "multi_tone", "center_freq_mhz": 1200, "jnr_db": 18}
        ]
    }
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    jammers = []
    for j in data.get("jammers", []):
        jammers.append((j["type"], float(j["center_freq_mhz"]), float(j["jnr_db"])))
    return jammers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="任务一：在 30-2500 MHz 频段内任意组合生成干扰功率谱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  # 通过命令行参数添加干扰
  python -m src.pipeline.compose_spectrum \\
    --jammer single_tone:500:20 \\
    --jammer multi_tone:1200:18 \\
    --jammer sweep:1800:22 \\
    --output-npz data/composed_spectrum.npz \\
    --output-png data/composed_spectrum.png

  # 从JSON配置文件加载干扰
  python -m src.pipeline.compose_spectrum \\
    --config-file data/jammer_config.json \\
    --output-npz data/composed_spectrum.npz
        """,
    )
    parser.add_argument(
        "--jammer",
        action="append",
        dest="jammers",
        metavar="TYPE:FREQ:JNR",
        help="添加干扰，格式：jam_type:center_freq_mhz:jnr_db，可多次使用",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        help="从 JSON 文件加载干扰配置",
    )
    parser.add_argument(
        "--freq-min",
        type=float,
        default=30.0,
        help="频段下限 MHz（默认 30）",
    )
    parser.add_argument(
        "--freq-max",
        type=float,
        default=2500.0,
        help="频段上限 MHz（默认 2500）",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=1.0,
        help="频率分辨率 MHz（默认 1.0）",
    )
    parser.add_argument(
        "--noise-floor",
        type=float,
        default=-120.0,
        help="底噪功率 dB（默认 -120）",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=125e6,
        help="IQ 采样率 Hz（默认 125e6）",
    )
    parser.add_argument(
        "--iq-length",
        type=int,
        default=32768,
        help="IQ 信号长度（默认 32768）",
    )
    parser.add_argument(
        "--output-npz",
        type=Path,
        default=Path("data/composed_spectrum.npz"),
        help="输出 npz 路径（包含 freq_mhz 与 power_db）",
    )
    parser.add_argument(
        "--output-png",
        type=Path,
        default=Path("data/composed_spectrum.png"),
        help="输出功率谱 PNG 路径",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（可选，用于复现）",
    )
    args = parser.parse_args()

    # 创建配置
    cfg = SpectrumComposerConfig(
        freq_min_mhz=args.freq_min,
        freq_max_mhz=args.freq_max,
        resolution_mhz=args.resolution,
        noise_floor_db=args.noise_floor,
        sample_rate_hz=args.sample_rate,
        iq_length=args.iq_length,
    )

    # 加载干扰配置
    jammer_specs = []
    if args.config_file:
        if not args.config_file.exists():
            raise SystemExit(f"配置文件不存在: {args.config_file}")
        jammer_specs.extend(load_jammer_config_file(args.config_file))

    if args.jammers:
        for spec_str in args.jammers:
            jammer_specs.append(parse_jammer_spec(spec_str))

    if not jammer_specs:
        raise SystemExit("未指定任何干扰，请使用 --jammer 或 --config-file 添加干扰")

    # 添加干扰到配置
    for jam_type, center_freq_mhz, jnr_db in jammer_specs:
        add_jammer(cfg, jam_type, center_freq_mhz, jnr_db)
        print(f"添加干扰: {jam_type} @ {center_freq_mhz} MHz, JNR={jnr_db} dB")

    # 生成功率谱
    rng = np.random.default_rng(args.seed)
    print(f"生成功率谱: {args.freq_min}-{args.freq_max} MHz, 分辨率 {args.resolution} MHz")
    freq_mhz, power_db = compose_spectrum(cfg, rng=rng)

    # 保存结果
    args.output_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.output_npz, freq_mhz=freq_mhz, power_db=power_db)
    print(f"功率谱已保存: {args.output_npz}")

    # 绘图
    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(freq_mhz, power_db, linewidth=0.8)
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dB)")
    ax.set_title(f"Composed Spectrum: {len(jammer_specs)} Jammers")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(args.freq_min, args.freq_max)
    fig.tight_layout()
    plt.savefig(args.output_png, dpi=150)
    plt.close(fig)
    print(f"功率谱图已保存: {args.output_png}")

    # 打印统计信息
    print(f"\n功率谱统计:")
    print(f"  频率范围: {freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz")
    print(f"  频点数量: {freq_mhz.size}")
    print(f"  功率范围: {power_db.min():.2f} - {power_db.max():.2f} dB")
    print(f"  底噪水平: {args.noise_floor:.2f} dB")


if __name__ == "__main__":
    main()
