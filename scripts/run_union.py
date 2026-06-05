#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键运行任务二+任务三，并输出频谱“并集”结果。

功能概述：
- 任务二：从 data_segment 目录读取真实 .bin IQ 数据，拼接宽带参考频谱；
- 任务三：从 data_semantic/semantic.txt 或 data_semantic/semantic.json 读取 v2 语义参数，恢复语义频谱；
- 频谱对齐：在语义频轴上对齐两条谱线，参考谱与语义谱取“并集”，
  且所有“无参考覆盖”的点按 `noise_floor_dbm_1mhz`（dBm@1MHz）作为底噪处理；
- 输出：将 IQ/语义按频点取 max 合并为一条功率谱，并保存到 output/union_spectrum.npz；
  可选生成 PNG 图（颜色区分“当前频点由 IQ/语义哪一侧取到 max”），默认关闭绘图以提速。

输出单位说明（重要）：
- 本脚本输出的 `power_db` 现在约定为 **dBm @ 1MHz RBW**；
- 导出的 `freq_mhz` 不再表示“1MHz 频箱中心点”，而表示 **1MHz 区间左边界**；
  例如 `freq_mhz=30` 对应功率区间 `[30, 31)` MHz；
- 绝对刻度通过“噪声底噪对齐”的方式标定：将参考谱的噪声低分位对齐到 `noise_floor_dbm_1mhz`（默认 -105 dBm）。
  这能保证底噪基准正确，但严格的“绝对功率”仍依赖前端链路一致性与更完善的校准体系。
- 导出的 `jnr_db` 与 `decode_semantic_v2()` 保持同一口径，表示“高于底噪多少 dB”，不再做 `J/N` 线性域换算。

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
import re
import sys
import hashlib
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

# 绝对功率（dBm）基准：默认 -105 dBm @ 1MHz RBW
DEFAULT_NOISE_FLOOR_DBM_1MHZ = -105.0

# 输出频轴工程约定：1 MHz；freq_mhz 表示每个 1MHz 区间的左边界标签
DEFAULT_OUTPUT_DF_MHZ = 1.0
DEFAULT_OUTPUT_RBW_MHZ = 1.0

JNR_FLOOR_DB = -200.0

NOISE_EST_PERCENTILE = 20.0
POWER_EPS = 1e-12

# 该脚本可选生成 PNG，但不需要任何 GUI 后端。
# 关键点：绘图是可选路径；但一旦启用绘图，依赖的部分模块可能会 import matplotlib.pyplot。
# 如果不提前固定 backend，Windows 下可能自动选中 Qt 后端并产生 DPI 警告噪音。
os.environ.setdefault("MPLBACKEND", "Agg")

# 将源码目录加入 sys.path，避免把仓库根目录暴露成可导入包空间
ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from electromagnetic_state.io.reader import BinDataType, load_iq_file, parse_bin_filename  # type: ignore
from electromagnetic_state.signal.stitcher import (  # type: ignore
    StitchMode,
    SpectrumSegment,
    StitchedSpectrum,
    stitch_segments,
)
from electromagnetic_state.signal.spectrum import compute_power_spectrum, compute_segmented_power_spectrum  # type: ignore
from electromagnetic_state.pipeline.stitch.stitch_real_data import stitch_from_bin_directory  # type: ignore
from electromagnetic_state.semantics.decode_v2 import (  # type: ignore
    decode_semantic_v2,
    load_semantic_v2_file,
)
from electromagnetic_state.core.schemas import (  # type: ignore
    DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
    DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
    SamplingConfig,
)


SEMANTIC_TIMESTAMPED_NAME_RE = re.compile(
    r"^semantic_(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_[^.]+)?\.(txt|json)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UnionSpectrumSnapshot:
    """一次性计算后的频谱快照。"""

    freq_mhz: np.ndarray
    power_db: np.ndarray
    jnr_db: np.ndarray
    power_iq_dbm: np.ndarray
    power_semantic_dbm: np.ndarray
    has_iq: bool
    has_semantic: bool
    stitched: object
    semantic_path: Optional[Path]
    semantic_params: Optional[object]
    semantic_input_df_mhz: float
    semantic_noise_floor_db: Optional[float]
    output_df_mhz: float
    target_noise_floor_dbm_1mhz: float


@dataclass
class IQSpectrumCacheEntry:
    """单个 IQ 文件的频谱缓存条目。"""

    signature: Tuple[str, int, int]
    segment_fft_size: int
    time_agg_mode: str
    segment: SpectrumSegment


@dataclass
class IQSpectrumCache:
    """实时 IQ 频谱缓存。

    设计目的：
    - 13 个大 `.bin` 文件不应在每次更新时全量重读、全量 FFT；
    - 按文件名维持缓存，只有签名变化的文件才重算；
    - 与 `run_union_realtime.py` 组合使用时，可将“语义变化 / 单文件 IQ 变化”的更新压到 <1s。
    """

    entries_by_name: Dict[str, IQSpectrumCacheEntry] = field(default_factory=dict)
    disk_cache_dir: Path = field(default_factory=lambda: ROOT / "output" / "iq_segment_cache")


def _estimate_noise_floor_db(
    power_db: np.ndarray,
    *,
    percentile: float = NOISE_EST_PERCENTILE,
    valid_mask: Optional[np.ndarray] = None,
) -> float:
    """估计底噪（相对 dB）。

    说明：
    - 这里的“底噪”用于做绝对刻度对齐（noise_floor_dbm_1mhz）；
    - 使用低分位数（默认 20%）比均值更鲁棒，避免被强干扰拉高。
    """
    if power_db.size == 0:
        return float("nan")

    values = power_db
    if valid_mask is not None:
        if valid_mask.shape != power_db.shape:
            raise ValueError(f"valid_mask 形状 {valid_mask.shape} 与 power_db {power_db.shape} 不一致")
        values = power_db[valid_mask]
        if values.size == 0:
            values = power_db

    p = float(percentile)
    p = 0.0 if p < 0.0 else 100.0 if p > 100.0 else p
    return float(np.percentile(values.astype(float, copy=False), p))


def _aggregate_reference_to_rbw_axis(
    *,
    freq_ref_mhz: np.ndarray,
    power_ref_db: np.ndarray,
    coverage_map: Optional[np.ndarray],
    freq_out_mhz: np.ndarray,
    rbw_mhz: float,
    noise_fill_db: float,
) -> np.ndarray:
    """将参考谱聚合到输出频轴，并近似为 rbw_mhz 的区间功率测量。

    设计取舍（工程化而非教科书）：
    - 输出轴为 1MHz 栅格；参考谱典型为 0.4MHz（Fs=204.8MHz, NFFT=512）；
    - `freq_out_mhz[i]` 表示区间左边界，因此这里按 [f, f+rbw_mhz) 左闭右开窗口聚合；
    - 若该窗口内无有效覆盖点，则回退为 noise_fill_db（不做“多 bin 噪声叠加”）。
    """
    if rbw_mhz <= 0:
        raise ValueError(f"rbw_mhz 必须为正，当前: {rbw_mhz}")
    if freq_ref_mhz.size == 0 or power_ref_db.size == 0:
        raise ValueError("参考谱为空，无法聚合到输出频轴")
    if freq_ref_mhz.shape != power_ref_db.shape:
        raise ValueError(f"freq_ref_mhz {freq_ref_mhz.shape} 与 power_ref_db {power_ref_db.shape} 不一致")
    if coverage_map is not None and coverage_map.shape != power_ref_db.shape:
        raise ValueError(f"coverage_map {coverage_map.shape} 与 power_ref_db {power_ref_db.shape} 不一致")

    order = np.argsort(freq_ref_mhz)
    f_ref = freq_ref_mhz[order].astype(float, copy=False)
    p_ref_db = power_ref_db[order].astype(float, copy=False)
    cov = coverage_map[order] if coverage_map is not None else None

    p_ref_lin = 10.0 ** (p_ref_db / 10.0)
    noise_lin = 10.0 ** (float(noise_fill_db) / 10.0)

    out_lin = np.empty_like(freq_out_mhz, dtype=float)
    out_lin.fill(noise_lin)

    for i, f0 in enumerate(freq_out_mhz.astype(float, copy=False)):
        left = int(np.searchsorted(f_ref, f0, side="left"))
        right = int(np.searchsorted(f_ref, f0 + float(rbw_mhz), side="left"))
        if right <= left:
            out_lin[i] = noise_lin
            continue

        if cov is None:
            out_lin[i] = float(p_ref_lin[left:right].sum())
            continue

        valid = cov[left:right] > 0
        if not np.any(valid):
            out_lin[i] = noise_lin
            continue
        out_lin[i] = float(p_ref_lin[left:right][valid].sum())

    return 10.0 * np.log10(out_lin + POWER_EPS)


def _maybe_import_pyplot():
    """按需导入 matplotlib，并尽量避免 Qt 相关噪音。

    说明：
    - 被 import 调用时默认 quiet=True，通常不需要绘图；因此这里不应在模块 import 阶段就引入 GUI 依赖。
    - 本脚本仅保存 PNG，不需要交互式窗口；优先使用 Agg 后端可避免 Qt/DPI 警告与无 GUI 环境崩溃。
    """
    try:
        import matplotlib

        # 必须在 import pyplot 之前设置 backend；若外部已配置则保持原样即可
        with suppress(Exception):
            matplotlib.use("Agg")

        import matplotlib.pyplot as pyplot

        return pyplot
    except Exception:  # pragma: no cover - 无图形环境/未安装时仅输出 npz
        return None


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
    2) data_semantic/ 下最新的时间戳语义文件（semantic_YYYY-MM-DD_HH-MM-SS.*）；
    3) data_semantic/semantic.txt；
    4) data_semantic/semantic.json。
    """

    if semantic_path is not None:
        return semantic_path

    semantic_dir = ROOT / "data_semantic"
    timestamped: list[Tuple[datetime, Path]] = []
    if semantic_dir.exists():
        for path in semantic_dir.iterdir():
            if not path.is_file():
                continue
            match = SEMANTIC_TIMESTAMPED_NAME_RE.match(path.name)
            if match is None:
                continue
            timestamped.append(
                (
                    datetime.strptime(match.group("ts"), "%Y-%m-%d_%H-%M-%S"),
                    path,
                )
            )

    if timestamped:
        timestamped.sort(key=lambda item: (item[0], item[1].name))
        return timestamped[-1][1]

    candidates = [
        semantic_dir / "semantic.txt",
        semantic_dir / "semantic.json",
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


def _load_semantic_params_with_txt_default(path: Path, *, verbose: bool = True):
    """加载语义参数，并处理 TXT 缺省 num_bins 的歧义。

    背景：
    - v2 语义的 jammer_regions 使用 start_bin/end_bin（索引），必须基于 num_bins 的频轴解释；
    - 若 TXT 文件未写 num_bins，本项目全局默认 num_bins=24701（0.1 MHz），
      但用户也可能按旧习惯写 1 MHz（num_bins=2471）的索引。

    策略（只在 TXT 且缺省 num_bins 时启用）：
    - 默认按 1 MHz（num_bins=2471）解释 start_bin/end_bin；
    - 并在控制台给出提示：如需 0.1 MHz，请在文件中显式写 num_bins=24701。
    """
    # 语义输入可能来自“未经处理的上游接口输出”，常见问题：
    # - jammer_regions 无序；
    # - jammer_regions 可重叠（加载阶段先放行，后续仍按 decode_v2 的覆盖语义解释）。
    # 因此这里使用 strict=False 宽松加载，避免在文件加载阶段直接失败。
    params_v2 = load_semantic_v2_file(path, strict=False)

    if path.suffix.lower() == ".txt" and not _semantic_txt_has_num_bins(path):
        if verbose:
            print(
                "  警告 semantic.txt 未显式指定 num_bins，将按 1 MHz (num_bins=2471) 解释 start_bin/end_bin；"
                "如需 0.1 MHz，请在文件中写 num_bins=24701。"
            )
        params_v2.num_bins = 2471

    return params_v2


def _semantic_power_on_axis(
    params_v2,
    freq_axis_mhz: np.ndarray,
    *,
    override_noise_floor_db: Optional[float] = None,
) -> np.ndarray:
    """将语义 jammer_regions 映射到指定频率轴上（绝对功率，dB/dBm）。

    语义口径与 `decode_semantic_v2()` 保持一致：
    - 先以 `noise_floor_db` 作为底噪初始化整条谱线；
    - `freq_axis_mhz` 的每个点表示区间左边界，因此按区间重叠关系做映射；
    - 对每个 jammer_region，将覆盖到的输出区间直接设置为 `noise_floor_db + jnr_db`；
    - 不再把 `jnr_db` 解释为 `J/N`，也不做线性域叠加。
    """
    noise_floor_db = (
        float(override_noise_floor_db)
        if override_noise_floor_db is not None
        else float(params_v2.noise_floor_db)
    )

    out = np.full_like(freq_axis_mhz, noise_floor_db, dtype=float)
    if freq_axis_mhz.size == 0:
        return out

    if params_v2.num_bins < 2:
        return out

    df_out_mhz = (
        float(freq_axis_mhz[1] - freq_axis_mhz[0])
        if freq_axis_mhz.size >= 2
        else float(DEFAULT_OUTPUT_DF_MHZ)
    )
    out_first_start_mhz = float(freq_axis_mhz[0])
    out_last_stop_mhz = float(freq_axis_mhz[-1]) + df_out_mhz
    df_in_mhz = (float(params_v2.freq_max_mhz) - float(params_v2.freq_min_mhz)) / (
        float(params_v2.num_bins) - 1.0
    )

    for region in params_v2.jammer_regions:
        start_bin = int(region.start_bin)
        end_bin = int(region.end_bin)
        if start_bin > end_bin:
            start_bin, end_bin = end_bin, start_bin

        f0 = float(params_v2.freq_min_mhz) + float(start_bin) * df_in_mhz
        f1 = float(params_v2.freq_min_mhz) + float(end_bin) * df_in_mhz
        region_start_mhz = min(f0, f1)
        region_stop_mhz = max(f0, f1) + df_in_mhz
        if region_stop_mhz <= out_first_start_mhz or region_start_mhz >= out_last_stop_mhz:
            continue

        # 输出轴的每个标签表示 [f, f+df_out) 区间左边界；只要区间有重叠就视为命中。
        i0 = int(np.searchsorted(freq_axis_mhz, region_start_mhz, side="right")) - 1
        i1_excl = int(np.searchsorted(freq_axis_mhz, region_stop_mhz, side="left"))
        i0 = max(i0, 0)
        i1_excl = min(i1_excl, freq_axis_mhz.size)
        if i0 >= i1_excl:
            continue

        out[i0:i1_excl] = float(noise_floor_db) + float(region.jnr_db)
    return out


def _power_dbm_to_semantic_jnr_db(
    power_dbm: np.ndarray,
    *,
    noise_floor_dbm: float,
    floor_db: float = JNR_FLOOR_DB,
) -> np.ndarray:
    """将绝对功率转换为与 `decode_semantic_v2()` 一致的 `jnr_db` 口径。

    这里的 `jnr_db` 表示“高于底噪多少 dB”，不是 `J/N` 的线性域换算结果。
    对于不高于底噪的点，继续输出 `floor_db` 作为“无干扰”哨兵值。
    """
    if power_dbm.size == 0:
        return power_dbm.astype(float)

    delta_db = power_dbm.astype(float, copy=False) - float(noise_floor_dbm)
    out = np.full_like(power_dbm, float(floor_db), dtype=float)
    mask = delta_db > 0.0
    out[mask] = delta_db[mask]
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


def _make_output_axis() -> Tuple[np.ndarray, float]:
    """构造工程约定的 1 MHz 输出频轴。

    注意：
    - `freq_out[i]` 表示第 i 个 1MHz 区间的左边界；
    - 例如 `freq_out[i] == 30` 表示 `[30, 31)` MHz；
    - 最后一个标签的右边界隐含为 `freq_out[-1] + DEFAULT_OUTPUT_DF_MHZ`。
    """
    output_num_bins = int(
        round((DEFAULT_SEMANTIC_FREQ_MAX_MHZ - DEFAULT_SEMANTIC_FREQ_MIN_MHZ) / DEFAULT_OUTPUT_DF_MHZ)
    ) + 1
    freq_out = np.linspace(
        DEFAULT_SEMANTIC_FREQ_MIN_MHZ,
        DEFAULT_SEMANTIC_FREQ_MAX_MHZ,
        output_num_bins,
    )
    df_out_mhz = (
        (DEFAULT_SEMANTIC_FREQ_MAX_MHZ - DEFAULT_SEMANTIC_FREQ_MIN_MHZ) / (output_num_bins - 1)
        if output_num_bins >= 2
        else float("nan")
    )
    return freq_out, float(df_out_mhz)


def _make_empty_stitched_spectrum(
    *,
    mode: StitchMode,
    reason: str,
) -> StitchedSpectrum:
    return StitchedSpectrum(
        freq_mhz=np.array([]),
        power_db=np.array([]),
        coverage_map=np.array([]),
        segment_count=0,
        freq_min_mhz=0.0,
        freq_max_mhz=0.0,
        mode=mode,
        metadata={"empty": True, "reason": reason},
    )


def _iq_file_signature(path: Path) -> Tuple[str, int, int]:
    stat = path.stat()
    return (path.name, int(stat.st_size), int(stat.st_mtime_ns))


def _iq_disk_cache_path(
    *,
    cache_dir: Path,
    source_path: Path,
    segment_fft_size: int,
    time_agg_mode: str,
) -> Path:
    source_key = str(source_path.resolve()).encode("utf-8", errors="replace")
    digest = hashlib.sha1(source_key).hexdigest()[:16]
    filename = f"{source_path.stem}.segfft{int(segment_fft_size)}.{time_agg_mode}.{digest}.npz"
    return cache_dir / filename


def _load_segment_from_disk_cache(
    *,
    cache_dir: Path,
    source_path: Path,
    signature: Tuple[str, int, int],
    segment_fft_size: int,
    time_agg_mode: str,
) -> Optional[SpectrumSegment]:
    cache_path = _iq_disk_cache_path(
        cache_dir=cache_dir,
        source_path=source_path,
        segment_fft_size=int(segment_fft_size),
        time_agg_mode=str(time_agg_mode),
    )
    if not cache_path.exists():
        return None

    try:
        with np.load(cache_path, allow_pickle=False) as data:
            cached_name = str(data["source_name"].item())
            cached_size = int(data["source_size"].item())
            cached_mtime_ns = int(data["source_mtime_ns"].item())
            cached_nfft = int(data["segment_fft_size"].item())
            cached_agg = str(data["time_agg_mode"].item())
            if (
                cached_name != signature[0]
                or cached_size != int(signature[1])
                or cached_mtime_ns != int(signature[2])
                or cached_nfft != int(segment_fft_size)
                or cached_agg != str(time_agg_mode)
            ):
                return None

            return SpectrumSegment(
                freq_mhz=np.array(data["freq_mhz"], copy=True),
                power_db=np.array(data["power_db"], copy=True),
                center_freq_mhz=float(data["center_freq_mhz"].item()),
                bandwidth_mhz=float(data["bandwidth_mhz"].item()),
                metadata={
                    "source_bin_name": cached_name,
                    "cache_source": "disk",
                },
            )
    except Exception:
        return None


def _save_segment_to_disk_cache(
    *,
    cache_dir: Path,
    source_path: Path,
    signature: Tuple[str, int, int],
    segment_fft_size: int,
    time_agg_mode: str,
    segment: SpectrumSegment,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _iq_disk_cache_path(
        cache_dir=cache_dir,
        source_path=source_path,
        segment_fft_size=int(segment_fft_size),
        time_agg_mode=str(time_agg_mode),
    )
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with tmp_path.open("wb") as handle:
        np.savez(
            handle,
            source_name=np.array(signature[0]),
            source_size=np.array(int(signature[1]), dtype=np.int64),
            source_mtime_ns=np.array(int(signature[2]), dtype=np.int64),
            segment_fft_size=np.array(int(segment_fft_size), dtype=np.int64),
            time_agg_mode=np.array(str(time_agg_mode)),
            center_freq_mhz=np.array(float(segment.center_freq_mhz), dtype=np.float64),
            bandwidth_mhz=np.array(float(segment.bandwidth_mhz), dtype=np.float64),
            freq_mhz=np.asarray(segment.freq_mhz, dtype=np.float64),
            power_db=np.asarray(segment.power_db, dtype=np.float64),
        )
    tmp_path.replace(cache_path)


def _compute_iq_spectrum_segment(
    path: Path,
    *,
    fft_size: int,
    window: str,
    time_agg_mode: str,
    segment_fft_size: int,
    default_sample_rate_hz: float,
) -> SpectrumSegment:
    sr_override: Optional[float] = None
    meta_guess = parse_bin_filename(path.name, strict=False)
    if "bandwidth_mhz" not in meta_guess:
        sr_override = float(default_sample_rate_hz)

    iq = load_iq_file(
        path,
        bin_dtype=BinDataType.INT16,
        sample_rate_hz=sr_override,
    )
    cfg = SamplingConfig(
        sample_rate_hz=iq.sample_rate_hz,
        center_freq_hz=iq.center_freq_hz,
        fft_size=fft_size,
    )

    if int(segment_fft_size) > 0:
        target_df_hz = float(iq.sample_rate_hz) / float(segment_fft_size)
        freq_mhz, power_db = compute_segmented_power_spectrum(
            iq,
            cfg,
            target_df_hz=target_df_hz,
            window=window,
            time_agg_mode=time_agg_mode,
        )
    else:
        freq_mhz, power_db = compute_power_spectrum(iq, cfg, window=window)

    return SpectrumSegment(
        freq_mhz=freq_mhz,
        power_db=power_db,
        center_freq_mhz=iq.center_freq_hz / 1e6,
        bandwidth_mhz=iq.sample_rate_hz / 1e6,
        metadata=iq.meta,
    )


def _run_task2_stitch_cached(
    input_dir: Path,
    *,
    iq_cache: IQSpectrumCache,
    fft_size: int = 262_144,
    mode: StitchMode = StitchMode.MAX,
    window: str = "hann",
    fill_value: float = -180.0,
    time_agg_mode: str = "mean",
    segment_fft_size: int = 512,
    default_sample_rate_hz: float = 204.8e6,
    quiet: bool = False,
) -> StitchedSpectrum:
    """运行任务二（缓存版）。

    说明：
    - 按文件名维护缓存，只在文件签名变化时重算该文件的频谱；
    - 对当前目录仍存在的所有 `.bin` 做一次轻量扫描，然后复用/重算；
    - 最终仍走原有 `stitch_segments()`，保证输出格式与拼接行为不变。
    """
    try:
        task2_t0 = time.perf_counter()
        scan_t0 = time.perf_counter()
        files = sorted(input_dir.glob("*.bin"))
        scan_ms = (time.perf_counter() - scan_t0) * 1000.0
        if not files:
            raise FileNotFoundError(f"目录 {input_dir} 中未找到匹配 *.bin 的文件")

        current_names = {path.name for path in files}
        stale_names = [name for name in iq_cache.entries_by_name if name not in current_names]
        for name in stale_names:
            iq_cache.entries_by_name.pop(name, None)

        segments: list[SpectrumSegment] = []
        memory_cache_hits = 0
        disk_cache_hits = 0
        cache_misses = 0
        disk_load_ms = 0.0
        miss_compute_ms = 0.0
        miss_disk_save_ms = 0.0

        for path in files:
            signature = _iq_file_signature(path)
            entry = iq_cache.entries_by_name.get(path.name)
            if (
                entry is not None
                and entry.signature == signature
                and entry.segment_fft_size == int(segment_fft_size)
                and entry.time_agg_mode == str(time_agg_mode)
            ):
                segment = entry.segment
                memory_cache_hits += 1
            else:
                disk_load_t0 = time.perf_counter()
                segment = _load_segment_from_disk_cache(
                    cache_dir=iq_cache.disk_cache_dir,
                    source_path=path,
                    signature=signature,
                    segment_fft_size=int(segment_fft_size),
                    time_agg_mode=str(time_agg_mode),
                )
                disk_load_ms += (time.perf_counter() - disk_load_t0) * 1000.0
                if segment is not None:
                    disk_cache_hits += 1
                else:
                    compute_t0 = time.perf_counter()
                    segment = _compute_iq_spectrum_segment(
                        path,
                        fft_size=fft_size,
                        window=window,
                        time_agg_mode=time_agg_mode,
                        segment_fft_size=int(segment_fft_size),
                        default_sample_rate_hz=float(default_sample_rate_hz),
                    )
                    miss_compute_ms += (time.perf_counter() - compute_t0) * 1000.0
                    save_t0 = time.perf_counter()
                    _save_segment_to_disk_cache(
                        cache_dir=iq_cache.disk_cache_dir,
                        source_path=path,
                        signature=signature,
                        segment_fft_size=int(segment_fft_size),
                        time_agg_mode=str(time_agg_mode),
                        segment=segment,
                    )
                    miss_disk_save_ms += (time.perf_counter() - save_t0) * 1000.0
                    cache_misses += 1
                iq_cache.entries_by_name[path.name] = IQSpectrumCacheEntry(
                    signature=signature,
                    segment_fft_size=int(segment_fft_size),
                    time_agg_mode=str(time_agg_mode),
                    segment=segment,
                )
            segments.append(segment)

        if not segments:
            return _make_empty_stitched_spectrum(mode=mode, reason="未生成任何有效 IQ 分段")

        segments.sort(key=lambda seg: seg.center_freq_mhz)
        stitch_t0 = time.perf_counter()
        stitched = stitch_segments(segments, mode=mode, fill_value=fill_value)
        stitch_ms = (time.perf_counter() - stitch_t0) * 1000.0
        task2_total_ms = (time.perf_counter() - task2_t0) * 1000.0
        stitched.metadata["cache_hits"] = int(memory_cache_hits + disk_cache_hits)
        stitched.metadata["memory_cache_hits"] = int(memory_cache_hits)
        stitched.metadata["disk_cache_hits"] = int(disk_cache_hits)
        stitched.metadata["cache_misses"] = int(cache_misses)
        stitched.metadata["task2_scan_ms"] = float(scan_ms)
        stitched.metadata["task2_disk_load_ms"] = float(disk_load_ms)
        stitched.metadata["task2_miss_compute_ms"] = float(miss_compute_ms)
        stitched.metadata["task2_miss_disk_save_ms"] = float(miss_disk_save_ms)
        stitched.metadata["task2_stitch_ms"] = float(stitch_ms)
        stitched.metadata["task2_total_ms"] = float(task2_total_ms)
        return stitched
    except (FileNotFoundError, ValueError) as e:
        if not quiet:
            print(f"  警告 任务二跳过：{e}")
            print("  将在并集阶段使用全底噪参考谱")
        return _make_empty_stitched_spectrum(mode=mode, reason=str(e))


def _run_task2_stitch(
    input_dir: Path,
    fft_size: int = 262_144,
    mode: StitchMode = StitchMode.MAX,
    window: str = "hann",
    fill_value: float = -180.0,
    time_agg_mode: str = "mean",
    segment_fft_size: int = 512,
    default_sample_rate_hz: float = 204.8e6,
    target_df_hz: Optional[float] = None,
    quiet: bool = False,
):
    """运行任务二：从 .bin 目录拼接宽带频谱。

    默认行为（性能优先）：
    - 默认采用“分段 FFT + 时间聚合”的方式，并固定 NFFT=512（工程约定）；
    - 若 segment_fft_size <= 0 且提供了 target_df_hz，则按 target_df_hz 推导 NFFT；
    - 若两者都不提供（或 target_df_hz=None），则退回到“单次 FFT（fft_size 点）”模式。
    """

    try:
        task2_t0 = time.perf_counter()
        if int(segment_fft_size) > 0:
            stitched, segments = stitch_from_bin_directory(
                directory=input_dir,
                pattern="*.bin",
                bin_dtype=BinDataType.INT16,
                mode=mode,
                fft_size=fft_size,
                window=window,
                fill_value=fill_value,
                segment_fft_size=int(segment_fft_size),
                time_agg_mode=time_agg_mode,
                default_sample_rate_hz=float(default_sample_rate_hz),
                quiet=quiet,
            )
        elif target_df_hz is not None:
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
                default_sample_rate_hz=float(default_sample_rate_hz),
                quiet=quiet,
            )
        else:
            stitched, segments = stitch_from_bin_directory(
                directory=input_dir,
                pattern="*.bin",
                bin_dtype=BinDataType.INT16,
                mode=mode,
                fft_size=fft_size,
                window=window,
                fill_value=fill_value,
                default_sample_rate_hz=float(default_sample_rate_hz),
                quiet=quiet,
            )
        if stitched.freq_mhz.size == 0:
            if not quiet:
                print(
                    "  警告 任务二拼接结果为空，data_segment 目录可能没有有效 .bin 文件，"
                    "将在并集阶段使用全底噪参考谱"
                )
        stitched.metadata["task2_total_ms"] = float((time.perf_counter() - task2_t0) * 1000.0)
        return stitched
    except (FileNotFoundError, ValueError) as e:
        # data_segment 目录为空或没有有效 .bin 文件
        if not quiet:
            print(f"  警告 任务二跳过：{e}")
            print("  将在并集阶段使用全底噪参考谱")
        return _make_empty_stitched_spectrum(mode=mode, reason=str(e))


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


def compute_union_snapshot(
    *,
    semantic_path: Optional[Path] = None,
    iq_dir: Optional[Path] = None,
    iq_cache: Optional[IQSpectrumCache] = None,
    segment_fft_size: int = 512,
    time_agg_mode: str = "mean",
    noise_floor_dbm_1mhz: float = DEFAULT_NOISE_FLOOR_DBM_1MHZ,
    allow_missing_semantic: bool = False,
    verbose: bool = True,
) -> UnionSpectrumSnapshot:
    """计算当前可显示的 IQ/语义/并集频谱快照。

    设计目的：
    - 保持 `main()` 的一次性离线接口不变；
    - 给实时绘图场景提供一个“只算数据、不保存 PNG”的复用入口；
    - 允许调用方选择“语义缺失是否视为错误”。
    """

    snapshot_t0 = time.perf_counter()
    task2_input_dir = Path(iq_dir) if iq_dir is not None else ROOT / "data_segment"
    freq_out, df_out_mhz = _make_output_axis()
    target_noise_floor_dbm = float(noise_floor_dbm_1mhz)

    task2_t0 = time.perf_counter()
    if iq_cache is None:
        stitched = _run_task2_stitch(
            task2_input_dir,
            segment_fft_size=int(segment_fft_size),
            time_agg_mode=str(time_agg_mode),
            quiet=not verbose,
        )
    else:
        stitched = _run_task2_stitch_cached(
            task2_input_dir,
            iq_cache=iq_cache,
            segment_fft_size=int(segment_fft_size),
            time_agg_mode=str(time_agg_mode),
            quiet=not verbose,
        )
    task2_outer_ms = (time.perf_counter() - task2_t0) * 1000.0
    has_iq = stitched.freq_mhz.size > 0

    semantic_resolve_t0 = time.perf_counter()
    resolved_semantic_path: Optional[Path] = None
    if semantic_path is not None:
        resolved_semantic_path = Path(semantic_path)
    elif not allow_missing_semantic:
        resolved_semantic_path = _pick_semantic_file(None)
    else:
        for candidate in (
            ROOT / "data_semantic" / "semantic.txt",
            ROOT / "data_semantic" / "semantic.json",
        ):
            if candidate.exists():
                resolved_semantic_path = candidate
                break
    semantic_resolve_ms = (time.perf_counter() - semantic_resolve_t0) * 1000.0

    params_v2 = None
    semantic_noise_floor_db: Optional[float] = None
    semantic_input_df_mhz = float("nan")
    has_semantic = False
    power_sem_on_out_dbm = np.full_like(freq_out, target_noise_floor_dbm, dtype=float)

    semantic_stage_t0 = time.perf_counter()
    if resolved_semantic_path is not None:
        if not resolved_semantic_path.exists():
            if not allow_missing_semantic:
                raise FileNotFoundError(f"语义文件不存在: {resolved_semantic_path}")
        else:
            params_v2 = _load_semantic_params_with_txt_default(
                resolved_semantic_path,
                verbose=verbose,
            )
            semantic_noise_floor_db = float(params_v2.noise_floor_db)
            semantic_input_df_mhz = (
                (float(params_v2.freq_max_mhz) - float(params_v2.freq_min_mhz)) / float(params_v2.num_bins - 1)
                if params_v2.num_bins >= 2
                else float("nan")
            )
            power_sem_on_out_dbm = _semantic_power_on_axis(
                params_v2,
                freq_out,
                override_noise_floor_db=target_noise_floor_dbm,
            )
            has_semantic = True
    semantic_stage_ms = (time.perf_counter() - semantic_stage_t0) * 1000.0

    aggregate_stage_t0 = time.perf_counter()
    if not has_iq:
        power_ref_on_out_dbm = np.full_like(freq_out, target_noise_floor_dbm, dtype=float)
    else:
        valid_mask = stitched.coverage_map > 0 if stitched.coverage_map.size == stitched.power_db.size else None
        noise_fill_db = _estimate_noise_floor_db(stitched.power_db, valid_mask=valid_mask)
        power_ref_on_out_rel = _aggregate_reference_to_rbw_axis(
            freq_ref_mhz=stitched.freq_mhz,
            power_ref_db=stitched.power_db,
            coverage_map=stitched.coverage_map,
            freq_out_mhz=freq_out,
            rbw_mhz=DEFAULT_OUTPUT_RBW_MHZ,
            noise_fill_db=noise_fill_db,
        )
        noise_ref_out_db = _estimate_noise_floor_db(power_ref_on_out_rel)
        cal_offset_db = target_noise_floor_dbm - float(noise_ref_out_db)
        power_ref_on_out_dbm = power_ref_on_out_rel + float(cal_offset_db)
    aggregate_stage_ms = (time.perf_counter() - aggregate_stage_t0) * 1000.0

    union_stage_t0 = time.perf_counter()
    union_power_dbm = np.maximum(power_ref_on_out_dbm, power_sem_on_out_dbm)
    union_jnr_db = _power_dbm_to_semantic_jnr_db(
        union_power_dbm,
        noise_floor_dbm=target_noise_floor_dbm,
    )
    union_stage_ms = (time.perf_counter() - union_stage_t0) * 1000.0
    snapshot_total_ms = (time.perf_counter() - snapshot_t0) * 1000.0

    stitched.metadata["task2_outer_ms"] = float(task2_outer_ms)
    stitched.metadata["semantic_resolve_ms"] = float(semantic_resolve_ms)
    stitched.metadata["semantic_stage_ms"] = float(semantic_stage_ms)
    stitched.metadata["aggregate_stage_ms"] = float(aggregate_stage_ms)
    stitched.metadata["union_stage_ms"] = float(union_stage_ms)
    stitched.metadata["snapshot_total_ms"] = float(snapshot_total_ms)

    return UnionSpectrumSnapshot(
        freq_mhz=freq_out,
        power_db=union_power_dbm,
        jnr_db=union_jnr_db,
        power_iq_dbm=power_ref_on_out_dbm,
        power_semantic_dbm=power_sem_on_out_dbm,
        has_iq=has_iq,
        has_semantic=has_semantic,
        stitched=stitched,
        semantic_path=resolved_semantic_path,
        semantic_params=params_v2,
        semantic_input_df_mhz=semantic_input_df_mhz,
        semantic_noise_floor_db=semantic_noise_floor_db,
        output_df_mhz=df_out_mhz,
        target_noise_floor_dbm_1mhz=target_noise_floor_dbm,
    )


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
    enable_plot: bool,
    segment_fft_size: int,
    time_agg_mode: str,
    noise_floor_dbm_1mhz: float,
) -> int:
    output_dir = ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("=" * 80)
        print("运行任务二：拼接真实 .bin 频谱")
        print("=" * 80)
        snapshot = compute_union_snapshot(
            semantic_path=semantic_path,
            segment_fft_size=int(segment_fft_size),
            time_agg_mode=str(time_agg_mode),
            noise_floor_dbm_1mhz=float(noise_floor_dbm_1mhz),
            allow_missing_semantic=False,
            verbose=True,
        )
        stitched = snapshot.stitched
        if not snapshot.has_iq:
            print(
                "任务二未生成有效参考谱（data_segment 为空或拼接失败），"
                "后续并集将仅使用语义谱，并将参考谱视为全频带底噪"
            )
        else:
            print(
                f"任务二完成：参考频率范围 {stitched.freq_min_mhz:.2f} - "
                f"{stitched.freq_max_mhz:.2f} MHz, 点数 {stitched.freq_mhz.size}"
            )
            if stitched.freq_mhz.size >= 2:
                df_ref_mhz = float(stitched.freq_mhz[1] - stitched.freq_mhz[0])
                print(f"参考谱分辨率（约）：Δf={df_ref_mhz:.6f} MHz")

        print("\n" + "=" * 80)
        print("运行任务三：语义参数恢复频谱")
        print("=" * 80)
        if snapshot.semantic_path is None or snapshot.semantic_params is None:
            raise FileNotFoundError("未能解析有效语义文件")

        print(f"语义文件: {snapshot.semantic_path}")
        print(
            "任务三完成："
            f"输入频率范围 {float(snapshot.semantic_params.freq_min_mhz):.2f} - "
            f"{float(snapshot.semantic_params.freq_max_mhz):.2f} MHz, "
            f"点数 {int(snapshot.semantic_params.num_bins)}, "
            f"分辨率 {snapshot.semantic_input_df_mhz:.6f} MHz, "
            f"语义底噪字段 {float(snapshot.semantic_noise_floor_db):.2f} dB"
        )
        print(
            "输出绝对功率标定："
            f"底噪基准 {float(snapshot.target_noise_floor_dbm_1mhz):.2f} dBm @ 1MHz RBW"
        )
        print(
            "输出保存频轴（区间左边界）："
            f"{DEFAULT_SEMANTIC_FREQ_MIN_MHZ:.2f} - {DEFAULT_SEMANTIC_FREQ_MAX_MHZ:.2f} MHz, "
            f"点数 {snapshot.freq_mhz.size}, 分辨率 {snapshot.output_df_mhz:.6f} MHz, "
            f"例如 30 MHz 表示 [30, 31) MHz"
        )

        print("\n" + "=" * 80)
        print("对齐任务二/任务三频谱（并集，底噪以绝对基准为准）")
        print("=" * 80)

        # 保存 npz：默认保留 (freq_mhz, power_db)；其中 freq_mhz 表示 1MHz 区间左边界。
        # 同时输出与 decode_v2 一致口径的 jnr_db。
        union_npz_path = output_dir / "union_spectrum.npz"
        np.savez(
            union_npz_path,
            freq_mhz=snapshot.freq_mhz,
            power_db=snapshot.power_db,
            jnr_db=snapshot.jnr_db,
        )
        print(f"  ✓ 并集频谱数据已保存: {union_npz_path}")

        if enable_plot:
            # 画图（如果 matplotlib 可用）
            pyplot = _maybe_import_pyplot()
            if pyplot is not None:
                fig, ax = pyplot.subplots(figsize=(12, 5))

                # 绘图分辨率调节：若指定 plot_df_mhz，则对 IQ 参考谱做重采样；语义谱按区域映射到绘图频轴
                freq_plot = snapshot.freq_mhz
                ref_plot = snapshot.power_iq_dbm
                if plot_df_mhz is not None:
                    freq_plot, ref_plot = _resample_to_df_mhz(
                        snapshot.freq_mhz,
                        snapshot.power_iq_dbm,
                        float(plot_df_mhz),
                    )

                sem_plot = (
                    _semantic_power_on_axis(
                        snapshot.semantic_params,
                        freq_plot,
                        override_noise_floor_db=snapshot.target_noise_floor_dbm_1mhz,
                    )
                    if snapshot.has_semantic and snapshot.semantic_params is not None
                    else np.full_like(freq_plot, snapshot.target_noise_floor_dbm_1mhz, dtype=float)
                )
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
                ax.set_xlabel("Frequency Interval Start (MHz)")
                ax.set_ylabel("Power (dBm @ 1MHz RBW)")
                title = "任务二/任务三 频谱并集（dBm@1MHz，按 1MHz 左闭右开区间取 max）"
                if plot_df_mhz is not None:
                    title += f"  [plot_df={float(plot_df_mhz):.6f} MHz]"
                ax.set_title(title)
                ax.grid(True, alpha=0.3, linestyle="--")
                ax.legend(loc="best", fontsize=9)
                fig.tight_layout()

                png_path = output_dir / "union_spectrum.png"
                pyplot.savefig(png_path, dpi=150, bbox_inches="tight")
                pyplot.close(fig)
                print(f"  ✓ 并集频谱图已保存: {png_path}")
            else:
                print("未安装 matplotlib，仅输出 npz 数据")
        else:
            print("绘图已禁用，仅输出 npz 数据")
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
    enable_plot: Optional[bool] = None,
    segment_fft_size: int = 512,
    time_agg_mode: str = "mean",
    noise_floor_dbm_1mhz: float = DEFAULT_NOISE_FLOOR_DBM_1MHZ,
) -> int:
    """入口：运行任务二+任务三，并输出频谱并集结果到 output/。

    返回值约定：
    - 成功返回 11；
    - 发生异常时抛出异常（由调用方处理），或在 __main__ 场景下由解释器返回非 0。
    """

    if quiet is None:
        # 被 import 调用时默认保持安静，避免污染调用方输出/日志。
        quiet = __name__ != "__main__"

    if enable_plot is None:
        # 性能优先：默认不绘图。需要 PNG 时由调用方显式传入 enable_plot=True。
        enable_plot = False

    if not quiet:
        _ensure_console_utf8()
        _ensure_stdio_open()
        return _run_union_impl(
            semantic_path=semantic_path,
            plot_df_mhz=plot_df_mhz,
            enable_plot=bool(enable_plot),
            segment_fft_size=int(segment_fft_size),
            time_agg_mode=str(time_agg_mode),
            noise_floor_dbm_1mhz=float(noise_floor_dbm_1mhz),
        )

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sink = open(os.devnull, "w", encoding="utf-8", errors="replace")
    sys.stdout = sink
    sys.stderr = sink

    try:
        _ensure_console_utf8()
        _ensure_stdio_open()
        return _run_union_impl(
            semantic_path=semantic_path,
            plot_df_mhz=plot_df_mhz,
            enable_plot=bool(enable_plot),
            segment_fft_size=int(segment_fft_size),
            time_agg_mode=str(time_agg_mode),
            noise_floor_dbm_1mhz=float(noise_floor_dbm_1mhz),
        )
    finally:
        with suppress(Exception):
            sink.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr


if __name__ == "__main__":
    sys.exit(main(quiet=False, enable_plot=True))
