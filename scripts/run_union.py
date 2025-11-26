#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键运行任务二+任务三，并输出频谱“并集”结果。

功能概述：
- 任务二：从 data_segment 目录读取真实 .bin IQ 数据，拼接宽带参考频谱；
- 任务三：从 data_semantic/semantic.json 读取语义参数（支持 v1/v2），恢复语义频谱；
- 频谱对齐：在语义频轴上对齐两条谱线，参考谱与语义谱取“并集”，
  且所有“无参考覆盖”的点按语义底噪 noise_floor_db 处理；
- 输出：将对齐后的两条谱线保存到 output/union_spectrum.npz，并生成 PNG 图。

用法（在仓库根目录执行）：

    python scripts/run_task2_task3_union.py

可选参数可在 main() 中按需扩展。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

# 确保可以导入 src 包：将仓库根目录加入 sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.reader import BinDataType  # type: ignore
from src.signal.stitcher import (  # type: ignore
    StitchMode,
)
from src.pipeline.stitch.stitch_real_data import stitch_from_bin_directory  # type: ignore
from src.semantics.decode_multi import decode_file_auto  # type: ignore
from src.semantics.decode_v2 import (  # type: ignore
    decode_semantic_v2,
    load_semantic_v2_file,
)
from src.core.schemas import (  # type: ignore
    DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
    DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
    DEFAULT_SEMANTIC_NUM_BINS,
    DEFAULT_SEMANTIC_NOISE_FLOOR_DB,
)

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - 无图形环境时仅输出 npz
    plt = None


def _run_task2_stitch(
    input_dir: Path,
    fft_size: int = 262_144,
    mode: StitchMode = StitchMode.MAX,
    window: str = "hann",
    fill_value: float = -180.0,
):
    """运行任务二：从 .bin 目录拼接宽带频谱。"""

    stitched, segments = stitch_from_bin_directory(
        directory=input_dir,
        pattern="*.bin",
        bin_dtype=BinDataType.INT16,
        mode=mode,
        fft_size=fft_size,
        window=window,
        fill_value=fill_value,
    )
    if stitched.freq_mhz.size == 0:
        raise SystemExit("任务二拼接结果为空，请检查 data_segment 目录内容")
    return stitched


def _run_task3_decode(
    semantic_path: Path,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """运行任务三：从语义 JSON 恢复频谱。

    返回：
    - freq_semantic: 语义频轴（MHz）；
    - power_semantic: 语义恢复功率谱（dB）；
    - noise_floor_db: 语义底噪（dB）。
    """

    if not semantic_path.exists():
        raise SystemExit(f"语义 JSON 不存在: {semantic_path}")

    data = json.loads(semantic_path.read_text(encoding="utf-8"))

    # v2: SemanticEncodingV2 格式
    if isinstance(data, dict) and "jammer_regions" in data:
        params_v2 = load_semantic_v2_file(semantic_path)
        power_db = decode_semantic_v2(params_v2)
        freq_mhz = np.linspace(
            params_v2.freq_min_mhz,
            params_v2.freq_max_mhz,
            params_v2.num_bins,
        )
        noise_floor_db = float(params_v2.noise_floor_db)
        return freq_mhz, power_db, noise_floor_db

    # v1: 走自动解码（兼容单区域/多区域）
    params_v1, recovered = decode_file_auto(semantic_path)
    freq_mhz = np.linspace(
        params_v1.freq_min_mhz,
        params_v1.freq_max_mhz,
        params_v1.fenbianlv,
    )
    # SemanticParams.noise_floor_db 是 menxian 的别名；若不存在则退回全局默认
    noise_floor_db = float(
        getattr(params_v1, "noise_floor_db", DEFAULT_SEMANTIC_NOISE_FLOOR_DB)
    )
    return freq_mhz, recovered, noise_floor_db


def _resample_reference_to_semantic_axis(
    freq_ref: np.ndarray,
    power_ref: np.ndarray,
    freq_semantic: np.ndarray,
    noise_floor_db: float,
    coverage_map: Optional[np.ndarray] = None,
) -> np.ndarray:
    """将任务二参考谱重采样到任务三的语义频轴上。

    规则：
    - 频率轴统一使用 freq_semantic（语义轴，任务三为准）；
    - 对于参考谱中 coverage_map == 0 的点视为“无覆盖”，功率直接拉到 noise_floor_db；
    - 对于 freq_semantic 超出参考谱频率范围的区域，参考谱功率统一视为 noise_floor_db；
    - 其余点使用线性插值将参考谱映射到 freq_semantic 上。
    """

    if freq_ref.size == 0 or power_ref.size == 0:
        raise SystemExit("参考谱为空，无法进行对齐与并集操作")

    power = power_ref.astype(float).copy()

    # 利用 coverage_map 清理“无覆盖”区域
    if coverage_map is not None:
        if coverage_map.shape != power.shape:
            raise SystemExit(
                f"coverage_map 长度 {coverage_map.size} 与参考功率 {power.size} 不一致"
            )
        power[coverage_map == 0] = noise_floor_db

    # 确保参考频轴递增
    order = np.argsort(freq_ref)
    freq_sorted = freq_ref[order]
    power_sorted = power[order]

    # 插值到语义频轴
    ref_on_semantic = np.interp(freq_semantic, freq_sorted, power_sorted)

    # 超出参考频率范围的区域，按语义底噪填充
    mask_low = freq_semantic < freq_sorted[0]
    mask_high = freq_semantic > freq_sorted[-1]
    ref_on_semantic[mask_low | mask_high] = noise_floor_db

    return ref_on_semantic


def main() -> None:
    """入口：运行任务二+任务三，并输出频谱并集结果到 output/。"""

    # 路径约定（可按需修改）
    task2_input_dir = ROOT / "data_segment"
    task3_semantic_path = ROOT / "data_semantic" / "semantic.json"
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("运行任务二：拼接真实 .bin 频谱")
    print("=" * 80)
    stitched = _run_task2_stitch(task2_input_dir)
    print(
        f"任务二完成：参考频率范围 {stitched.freq_min_mhz:.2f} - "
        f"{stitched.freq_max_mhz:.2f} MHz, 点数 {stitched.freq_mhz.size}"
    )

    print("\n" + "=" * 80)
    print("运行任务三：语义参数恢复频谱")
    print("=" * 80)
    freq_sem, power_sem, noise_floor_db = _run_task3_decode(task3_semantic_path)
    print(
        f"任务三完成：语义频率范围 {freq_sem.min():.2f} - "
        f"{freq_sem.max():.2f} MHz, 点数 {freq_sem.size}, 底噪 {noise_floor_db:.2f} dB"
    )

    # 若语义频轴与默认约定不符，给出提示
    if not (
        np.isclose(freq_sem.min(), DEFAULT_SEMANTIC_FREQ_MIN_MHZ)
        and np.isclose(freq_sem.max(), DEFAULT_SEMANTIC_FREQ_MAX_MHZ)
        and freq_sem.size == DEFAULT_SEMANTIC_NUM_BINS
    ):
        print(
            f"  ⚠️ 语义轴与全局默认不同："
            f"[{freq_sem.min():.2f}, {freq_sem.max():.2f}] MHz, N={freq_sem.size}"
        )

    print("\n" + "=" * 80)
    print("对齐任务二/任务三频谱（并集，底噪以任务三为准）")
    print("=" * 80)
    power_ref_on_sem = _resample_reference_to_semantic_axis(
        freq_ref=stitched.freq_mhz,
        power_ref=stitched.power_db,
        freq_semantic=freq_sem,
        noise_floor_db=noise_floor_db,
        coverage_map=stitched.coverage_map,
    )

    # 保存 npz：包含语义频轴上的参考谱 & 语义谱
    union_npz_path = output_dir / "union_spectrum.npz"
    np.savez(
        union_npz_path,
        freq_mhz=freq_sem,
        reference_power_db=power_ref_on_sem,
        semantic_power_db=power_sem,
        noise_floor_db=float(noise_floor_db),
    )
    print(f"  ✓ 并集频谱数据已保存: {union_npz_path}")

    # 画图（如果 matplotlib 可用）
    if plt is not None:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(freq_sem, power_ref_on_sem, label="Task2 拼接参考谱", linewidth=0.6, alpha=0.8)
        ax.plot(freq_sem, power_sem, label="Task3 语义恢复谱", linewidth=0.8, alpha=0.8)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dB)")
        ax.set_title("任务二/任务三 频谱并集（轴=语义频轴，底噪=任务三）")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(loc="best", fontsize=9)
        fig.tight_layout()

        png_path = output_dir / "union_spectrum.png"
        plt.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  ✓ 并集频谱图已保存: {png_path}")
    else:
        print("  ⚠️ 未安装 matplotlib，仅输出 npz 数据")


if __name__ == "__main__":
    # 修复 Windows 控制台编码，避免中文输出报错
    if sys.platform == "win32":
        import io

        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )
        except (AttributeError, ValueError):
            pass

    main()
