#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键运行任务二+任务三，并输出频谱“并集”结果。

功能概述：
- 任务二：从 data_segment 目录读取真实 .bin IQ 数据，拼接宽带参考频谱；
- 任务三：从 data_semantic/semantic.txt 或 data_semantic/semantic.json 读取 v2 语义参数，恢复语义频谱；
- 频谱对齐：在语义频轴上对齐两条谱线，参考谱与语义谱取“并集”，
  且所有“无参考覆盖”的点按语义底噪 noise_floor_db 处理；
- 输出：将 IQ/语义按频点取 max 合并为一条功率谱，并保存到 output/union_spectrum.npz；
  同时生成 PNG 图（颜色区分“当前频点由 IQ/语义哪一侧取到 max”）。

用法（在仓库根目录执行）：

    python scripts/run_union.py

主程序调用方式（示例）：

    from scripts.run_union import main as run_union_main

    ret = run_union_main()
    # 约定：成功返回 11（用于主程序判定“并集流程已完成”）
    if ret == 11:
        print("union ok")

可选参数可在 main() 中按需扩展。
"""
from __future__ import annotations

import os
import sys
from contextlib import suppress
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


def _ensure_console_utf8() -> None:
    """在 Windows 控制台下尽量切换到 UTF-8，避免中文输出触发编码异常。

    说明：
    - 该函数既支持 __main__ 直接执行，也支持被主程序 import 后调用 main() 的场景；
    - 使用 errors="replace" 兜底，避免因为不可编码字符导致流程被异常打断。
    """
    if sys.platform != "win32":  # pragma: no cover - 仅 Windows 生效
        return

    def _try_reconfigure(stream) -> None:
        if stream is None:
            return
        if getattr(stream, "closed", False):
            return
        if not hasattr(stream, "reconfigure"):
            return
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 某些非交互环境 stdout/stderr 可能不可用，保持原样即可
            return

    _try_reconfigure(sys.stdout)
    _try_reconfigure(sys.stderr)


def _ensure_stdio_open() -> None:
    """确保 stdout/stderr 可写，避免“打印时 I/O on closed file”。"""

    def _open_devnull_text():
        return open(os.devnull, "w", encoding="utf-8", errors="replace")

    def _ensure(attr: str, fallback_attr: str) -> None:
        stream = getattr(sys, attr, None)
        if stream is not None and not getattr(stream, "closed", False):
            return

        fallback = getattr(sys, fallback_attr, None)
        if fallback is not None and not getattr(fallback, "closed", False):
            setattr(sys, attr, fallback)
            return

        setattr(sys, attr, _open_devnull_text())

    _ensure("stdout", "__stdout__")
    _ensure("stderr", "__stderr__")


def _pick_semantic_file(semantic_path: Optional[Path]) -> Path:
    """选择语义文件路径。

    优先级：
    1) 调用方显式传入的 semantic_path；
    2) data_semantic/semantic.txt；
    3) data_semantic/semantic.json。
    """

    if semantic_path is not None:
        return semantic_path

    candidates = [
        ROOT / "data_semantic" / "semantic.txt",
        ROOT / "data_semantic" / "semantic.json",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        "语义文件不存在：未找到 data_semantic/semantic.txt 或 data_semantic/semantic.json；"
        "请创建其一，或在主程序中显式传入 semantic_path。"
    )


def _semantic_txt_has_num_bins(path: Path) -> bool:
    """判断 TXT 语义文件是否显式写了 num_bins=..."""
    if path.suffix.lower() != ".txt":
        return True

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return True

    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # 允许空格：num_bins = 2471
        if s.lower().replace(" ", "").startswith("num_bins="):
            return True
    return False


def _load_semantic_params_with_txt_default(path: Path):
    """加载语义参数，并处理 TXT 缺省 num_bins 的歧义。

    背景：
    - v2 语义的 jammer_regions 使用 start_bin/end_bin（索引），必须基于 num_bins 的频轴解释；
    - 若 TXT 文件未写 num_bins，本项目全局默认 num_bins=24701（0.1 MHz），
      但用户也可能按旧习惯写 1 MHz（num_bins=2471）的索引。

    策略（只在 TXT 且缺省 num_bins 时启用）：
    - 默认按 1 MHz（num_bins=2471）解释 start_bin/end_bin；
    - 并在控制台给出提示：如需 0.1 MHz，请在文件中显式写 num_bins=24701。
    """
    params_v2 = load_semantic_v2_file(path)

    if path.suffix.lower() == ".txt" and not _semantic_txt_has_num_bins(path):
        print(
            "  警告 semantic.txt 未显式指定 num_bins，将按 1 MHz (num_bins=2471) 解释 start_bin/end_bin；"
            "如需 0.1 MHz，请在文件中写 num_bins=24701。"
        )
        params_v2.num_bins = 2471

    return params_v2


def _semantic_power_on_axis(params_v2, freq_axis_mhz: np.ndarray) -> np.ndarray:
    """将语义 jammer_regions 映射到指定频率轴上（功率谱，dB）。

    规则：
    - axis 上默认填 noise_floor_db；
    - 对每个 region，在 [start_bin, end_bin] 对应的频率区间内，将功率抬升到 noise_floor_db+jnr_db；
    - 若 region 之间有重叠，取 max（更符合“功率取大”的直觉）。
    """
    params_v2.validate()
    noise_floor_db = float(params_v2.noise_floor_db)

    out = np.full_like(freq_axis_mhz, noise_floor_db, dtype=float)
    if freq_axis_mhz.size == 0:
        return out

    if params_v2.num_bins < 2:
        return out

    df_in_mhz = (float(params_v2.freq_max_mhz) - float(params_v2.freq_min_mhz)) / (
        float(params_v2.num_bins) - 1.0
    )

    for region in params_v2.jammer_regions:
        f0 = float(params_v2.freq_min_mhz) + float(region.start_bin) * df_in_mhz
        f1 = float(params_v2.freq_min_mhz) + float(region.end_bin) * df_in_mhz
        f_start = min(f0, f1)
        f_end = max(f0, f1)

        # 映射到输出频轴，包含端点
        i0 = int(np.searchsorted(freq_axis_mhz, f_start, side="left"))
        i1 = int(np.searchsorted(freq_axis_mhz, f_end, side="right")) - 1

        if i1 < 0 or i0 >= freq_axis_mhz.size:
            continue
        i0 = max(i0, 0)
        i1 = min(i1, freq_axis_mhz.size - 1)
        if i0 > i1:
            continue

        level = noise_floor_db + float(region.jnr_db)
        out[i0 : i1 + 1] = np.maximum(out[i0 : i1 + 1], level)

    return out


def _resample_to_df_mhz(
    freq_mhz: np.ndarray,
    power_db: np.ndarray,
    target_df_mhz: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """将一维频谱重采样到指定频率分辨率（MHz）。

    说明：
    - 主要用于“绘图分辨率调节”，避免改动频轴后导致 x/y 长度不匹配；
    - 使用线性插值（np.interp）。对语义谱这种分段常值数据，视觉上可能出现斜坡，
      但不会报错；若你需要严格阶梯形状，可再做零阶保持/最大池化。
    """

    if target_df_mhz <= 0:
        raise ValueError(f"plot_df_mhz 必须 > 0，当前为: {target_df_mhz}")
    if freq_mhz.ndim != 1 or power_db.ndim != 1:
        raise ValueError("freq_mhz/power_db 必须是一维数组")
    if freq_mhz.size != power_db.size:
        raise ValueError(f"freq_mhz 长度 {freq_mhz.size} 与 power_db 长度 {power_db.size} 不一致")
    if freq_mhz.size < 2:
        return freq_mhz.astype(float), power_db.astype(float)

    order = np.argsort(freq_mhz)
    f = freq_mhz[order].astype(float, copy=False)
    p = power_db[order].astype(float, copy=False)

    f_min = float(f[0])
    f_max = float(f[-1])
    # +0.5*df 用于包含右端点附近的点，避免尾部缺一格
    f_new = np.arange(f_min, f_max + target_df_mhz * 0.5, target_df_mhz, dtype=float)
    p_new = np.interp(f_new, f, p)
    return f_new, p_new


def _run_task2_stitch(
    input_dir: Path,
    fft_size: int = 262_144,
    mode: StitchMode = StitchMode.MAX,
    window: str = "hann",
    fill_value: float = -180.0,
    target_df_hz: Optional[float] = 100_000.0,
    time_agg_mode: str = "mean",
):
    """运行任务二：从 .bin 目录拼接宽带频谱。

    默认行为调整为：
    - 若提供 target_df_hz（默认为 100 kHz），则对每个 .bin 采用分段 FFT，
      以近似该频率分辨率计算功率谱（时间上做 mean/max 聚合）；
    - 若 target_df_hz 为 None，则退回到原先的“单次 FFT（fft_size 点）”模式。
    """

    try:
        stitched, segments = stitch_from_bin_directory(
            directory=input_dir,
            pattern="*.bin",
            bin_dtype=BinDataType.INT16,
            mode=mode,
            fft_size=fft_size,
            window=window,
            fill_value=fill_value,
            target_df_hz=target_df_hz,
            time_agg_mode=time_agg_mode,
        )
        if stitched.freq_mhz.size == 0:
            print(
                "  警告 任务二拼接结果为空，data_segment 目录可能没有有效 .bin 文件，"
                "将在并集阶段使用全底噪参考谱"
            )
        return stitched
    except (FileNotFoundError, ValueError) as e:
        # data_segment 目录为空或没有有效 .bin 文件
        print(f"  警告 任务二跳过：{e}")
        print("  将在并集阶段使用全底噪参考谱")
        # 返回空频谱对象
        from src.signal.stitcher import StitchedSpectrum
        return StitchedSpectrum(
            freq_mhz=np.array([]),
            power_db=np.array([]),
            coverage_map=np.array([]),
            segment_count=0,
            freq_min_mhz=0.0,
            freq_max_mhz=0.0,
            mode=mode,
            metadata={"empty": True, "reason": str(e)}
        )


def _run_task3_decode(
    semantic_path: Path,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """运行任务三：从语义文件（JSON/TXT）恢复频谱。

    返回：
    - freq_semantic: 语义频轴（MHz）；
    - power_semantic: 语义恢复功率谱（dB）；
    - noise_floor_db: 语义底噪（dB）。
    """

    if not semantic_path.exists():
        raise FileNotFoundError(f"语义文件不存在: {semantic_path}")

    params_v2 = load_semantic_v2_file(semantic_path)
    power_db = decode_semantic_v2(params_v2)
    freq_mhz = np.linspace(
        params_v2.freq_min_mhz,
        params_v2.freq_max_mhz,
        params_v2.num_bins,
    )
    noise_floor_db = float(params_v2.noise_floor_db)
    return freq_mhz, power_db, noise_floor_db


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
        raise ValueError("参考谱为空，无法进行对齐与并集操作")

    power = power_ref.astype(float).copy()

    # 利用 coverage_map 清理“无覆盖”区域
    if coverage_map is not None:
        if coverage_map.shape != power.shape:
            raise ValueError(f"coverage_map 长度 {coverage_map.size} 与参考功率 {power.size} 不一致")
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


def _run_union_impl(
    *,
    semantic_path: Optional[Path],
    plot_df_mhz: Optional[float],
) -> int:
    # 路径约定（可按需修改）
    task2_input_dir = ROOT / "data_segment"
    task3_semantic_path = _pick_semantic_file(semantic_path)
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("=" * 80)
        print("运行任务二：拼接真实 .bin 频谱")
        print("=" * 80)
        stitched = _run_task2_stitch(task2_input_dir)
        if stitched.freq_mhz.size == 0:
            print(
                "任务二未生成有效参考谱（data_segment 为空或拼接失败），"
                "后续并集将仅使用语义谱，并将参考谱视为全频带底噪"
            )
        else:
            print(
                f"任务二完成：参考频率范围 {stitched.freq_min_mhz:.2f} - "
                f"{stitched.freq_max_mhz:.2f} MHz, 点数 {stitched.freq_mhz.size}"
            )

        print("\n" + "=" * 80)
        print("运行任务三：语义参数恢复频谱")
        print("=" * 80)
        print(f"语义文件: {task3_semantic_path}")

        params_v2 = _load_semantic_params_with_txt_default(task3_semantic_path)
        params_v2.validate()
        noise_floor_db = float(params_v2.noise_floor_db)

        df_in_mhz = (
            (float(params_v2.freq_max_mhz) - float(params_v2.freq_min_mhz)) / float(params_v2.num_bins - 1)
            if params_v2.num_bins >= 2
            else float("nan")
        )
        print(
            "任务三完成："
            f"输入频率范围 {float(params_v2.freq_min_mhz):.2f} - {float(params_v2.freq_max_mhz):.2f} MHz, "
            f"点数 {int(params_v2.num_bins)}, 分辨率 {df_in_mhz:.6f} MHz, 底噪 {noise_floor_db:.2f} dB"
        )

        # 输出保存频轴：固定采用全局默认（当前为 0.1 MHz），避免语义输入分辨率改变导致下游数据维度漂移
        freq_out = np.linspace(
            DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
            DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
            DEFAULT_SEMANTIC_NUM_BINS,
        )
        df_out_mhz = (
            (DEFAULT_SEMANTIC_FREQ_MAX_MHZ - DEFAULT_SEMANTIC_FREQ_MIN_MHZ) / (DEFAULT_SEMANTIC_NUM_BINS - 1)
            if DEFAULT_SEMANTIC_NUM_BINS >= 2
            else float("nan")
        )
        print(
            "输出保存频轴："
            f"{DEFAULT_SEMANTIC_FREQ_MIN_MHZ:.2f} - {DEFAULT_SEMANTIC_FREQ_MAX_MHZ:.2f} MHz, "
            f"点数 {DEFAULT_SEMANTIC_NUM_BINS}, 分辨率 {df_out_mhz:.6f} MHz"
        )

        # 将语义区域映射到输出频轴（避免 start_bin/end_bin 因分辨率不同而“频段漂移”）
        power_sem_on_out = _semantic_power_on_axis(params_v2, freq_out)

        print("\n" + "=" * 80)
        print("对齐任务二/任务三频谱（并集，底噪以任务三为准）")
        print("=" * 80)
        if stitched.freq_mhz.size == 0:
            # 无参考谱时退化为全频带底噪作为占位参考谱，仍在输出频轴上输出并集结果
            power_ref_on_out = np.full_like(freq_out, noise_floor_db, dtype=float)
        else:
            power_ref_on_out = _resample_reference_to_semantic_axis(
                freq_ref=stitched.freq_mhz,
                power_ref=stitched.power_db,
                freq_semantic=freq_out,
                noise_floor_db=noise_floor_db,
                coverage_map=stitched.coverage_map,
            )

        # 合并：同一频点取 max 即可
        union_power_db = np.maximum(power_ref_on_out, power_sem_on_out)

        # 保存 npz：只保留两列数组（freq + power），便于下游统一读取
        union_npz_path = output_dir / "union_spectrum.npz"
        np.savez(
            union_npz_path,
            freq_mhz=freq_out,
            power_db=union_power_db,
        )
        print(f"  ✓ 并集频谱数据已保存: {union_npz_path}")

        # 画图（如果 matplotlib 可用）
        if plt is not None:
            fig, ax = plt.subplots(figsize=(12, 5))

            # 绘图分辨率调节：若指定 plot_df_mhz，则对 IQ 参考谱做重采样；语义谱按区域映射到绘图频轴
            freq_plot = freq_out
            ref_plot = power_ref_on_out
            if plot_df_mhz is not None:
                freq_plot, ref_plot = _resample_to_df_mhz(freq_out, power_ref_on_out, float(plot_df_mhz))

            sem_plot = _semantic_power_on_axis(params_v2, freq_plot)
            union_plot = np.maximum(ref_plot, sem_plot)

            # 颜色区分：当前频点由哪一侧取到 max
            take_iq = ref_plot >= sem_plot
            union_from_iq = np.where(take_iq, union_plot, np.nan)
            union_from_sem = np.where(~take_iq, union_plot, np.nan)

            ax.plot(
                freq_plot,
                union_from_iq,
                label="并集(取IQ侧max)",
                linewidth=0.8,
                alpha=0.9,
                color="#1f77b4",
            )
            ax.plot(
                freq_plot,
                union_from_sem,
                label="并集(取语义侧max)",
                linewidth=0.8,
                alpha=0.9,
                color="#ff7f0e",
            )
            ax.set_xlabel("Frequency (MHz)")
            ax.set_ylabel("Power (dB)")
            title = "任务二/任务三 频谱并集（按频点取max，颜色区分来源）"
            if plot_df_mhz is not None:
                title += f"  [plot_df={float(plot_df_mhz):.6f} MHz]"
            ax.set_title(title)
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.legend(loc="best", fontsize=9)
            fig.tight_layout()

            png_path = output_dir / "union_spectrum.png"
            plt.savefig(png_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"  ✓ 并集频谱图已保存: {png_path}")
        else:
            print("未安装 matplotlib，仅输出 npz 数据")
    except Exception as exc:
        # 避免使用不可编码的装饰符号，减少“打印错误信息也失败”的概率
        try:
            print(f"[ERROR] run_union 执行失败：{exc}", file=sys.stderr)
        except Exception:
            try:
                if sys.__stderr__ is not None and not getattr(sys.__stderr__, "closed", False):
                    sys.__stderr__.write(f"[ERROR] run_union 执行失败：{exc}\n")
            except Exception:
                pass
        raise

    return 11


def main(
    *,
    semantic_path: Optional[Path] = None,
    plot_df_mhz: Optional[float] = None,
    quiet: Optional[bool] = None,
) -> int:
    """入口：运行任务二+任务三，并输出频谱并集结果到 output/。

    返回值约定：
    - 成功返回 11；
    - 发生异常时抛出异常（由调用方处理），或在 __main__ 场景下由解释器返回非 0。
    """

    if quiet is None:
        # 被 import 调用时默认保持安静，避免污染调用方输出/日志。
        quiet = __name__ != "__main__"

    if not quiet:
        _ensure_console_utf8()
        _ensure_stdio_open()
        return _run_union_impl(semantic_path=semantic_path, plot_df_mhz=plot_df_mhz)

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sink = open(os.devnull, "w", encoding="utf-8", errors="replace")
    sys.stdout = sink
    sys.stderr = sink

    try:
        _ensure_console_utf8()
        _ensure_stdio_open()
        return _run_union_impl(semantic_path=semantic_path, plot_df_mhz=plot_df_mhz)
    finally:
        with suppress(Exception):
            sink.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr


if __name__ == "__main__":
    sys.exit(main(quiet=False))
