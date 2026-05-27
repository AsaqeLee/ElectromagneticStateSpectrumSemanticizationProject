#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实时监视 IQ/语义数据，并持续更新输出频谱文件。

设计原则：
- “数据更新”和“绘图刷新”分离；
- 有新 IQ / 新语义时才重新计算频谱；
- 默认只做实时计算与落盘，不强依赖图形界面；
- 若显式启用绘图，图窗保持常驻：语义超时则回退到 IQ；没有 IQ 时则继续显示语义。

运行方式：

    python scripts/run_union_realtime.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

 
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
SRC_ROOT = ROOT / "src"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import run_union  # noqa: E402


SEMANTIC_FILENAME_RE = re.compile(
    r"^semantic_(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_[^.]+)?\.(txt|json)$",
    re.IGNORECASE,
)
IQ_DIRNAME_TIME_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})$",
    re.IGNORECASE,
)


def _ensure_console_utf8() -> None:
    if sys.platform != "win32":
        return

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or getattr(stream, "closed", False):
            continue
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue


def _import_live_pyplot():
    try:
        import matplotlib

        backend = os.environ.get("MPLBACKEND", "TkAgg")
        matplotlib.use(backend, force=True)

        import matplotlib.pyplot as pyplot

        return pyplot
    except Exception as exc:  # pragma: no cover - 依赖本机 GUI 环境
        raise RuntimeError(
            "无法启用实时绘图后端。请确认本机已安装可交互的 matplotlib backend，"
            "必要时手工设置环境变量 MPLBACKEND=TkAgg 或 QtAgg。"
        ) from exc


def _save_snapshot_npz(
    snapshot: run_union.UnionSpectrumSnapshot,
    output_path: Path,
) -> None:
    """原子更新输出 npz，避免实时写入过程中留下半截文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_path.open("wb") as handle:
        np.savez(
            handle,
            freq_mhz=snapshot.freq_mhz,
            power_db=snapshot.power_db,
            jnr_db=snapshot.jnr_db,
        )
    tmp_path.replace(output_path)


def _parse_semantic_receive_time(path: Path) -> Optional[datetime]:
    match = SEMANTIC_FILENAME_RE.match(path.name)
    if match is None:
        return None
    return datetime.strptime(match.group("ts"), "%Y-%m-%d_%H-%M-%S")


def _semantic_age_seconds(path: Optional[Path], now_ts: float) -> Optional[float]:
    if path is None:
        return None

    receive_time = _parse_semantic_receive_time(path)
    if receive_time is not None:
        age = now_ts - receive_time.timestamp()
        return max(float(age), 0.0)

    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    age = now_ts - float(stat.st_mtime)
    return max(float(age), 0.0)


def _semantic_signature(path: Optional[Path]) -> Optional[Tuple[str, int, int]]:
    if path is None:
        return None
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return (path.name, int(stat.st_size), int(stat.st_mtime_ns))


def _parse_iq_receive_time(iq_dir: Path) -> Optional[datetime]:
    """从 IQ 目录名尾部解析采集时间。

    兼容示例：
    - `data_segment_2026-05-18_20-10-11`
    """
    match = IQ_DIRNAME_TIME_RE.search(iq_dir.name)
    if match is None:
        return None
    return datetime.strptime(match.group("ts"), "%Y-%m-%d_%H-%M-%S")


def _iq_age_seconds(iq_dir: Path, now_ts: float) -> Optional[float]:
    """返回 IQ 目录名时间戳对应的“年龄”。

    约定：
    - 若目录名不带可解析时间戳，返回 `None`；
      这表示保留旧行为：IQ 持续视为可用，不做“过期”裁决。
    """
    receive_time = _parse_iq_receive_time(iq_dir)
    if receive_time is None:
        return None

    age = now_ts - receive_time.timestamp()
    return max(float(age), 0.0)


def _iq_signature(iq_dir: Path) -> Tuple[Tuple[str, int, int], ...]:
    if not iq_dir.exists():
        return tuple()

    signature = []
    for path in sorted(iq_dir.glob("*.bin")):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        signature.append((path.name, int(stat.st_size), int(stat.st_mtime_ns)))
    return tuple(signature)


def _pick_latest_semantic_file(semantic_dir: Path) -> Optional[Path]:
    if not semantic_dir.exists():
        return None

    timestamped: list[Tuple[datetime, Path]] = []
    for path in semantic_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".txt", ".json"}:
            continue
        if path.name.endswith(".tmp"):
            continue

        receive_time = _parse_semantic_receive_time(path)
        if receive_time is not None:
            timestamped.append((receive_time, path))

    if timestamped:
        timestamped.sort(key=lambda item: (item[0], item[1].name))
        return timestamped[-1][1]

    for fallback in (semantic_dir / "semantic.txt", semantic_dir / "semantic.json"):
        if fallback.exists():
            return fallback
    return None


def _select_display_power(
    snapshot: run_union.UnionSpectrumSnapshot,
    *,
    iq_dir: Path,
    semantic_fresh_seconds: float,
    now_ts: float,
) -> Tuple[np.ndarray, str, str, str]:
    iq_age_s = _iq_age_seconds(iq_dir, now_ts)
    semantic_age_s = _semantic_age_seconds(snapshot.semantic_path, now_ts)
    iq_is_fresh = snapshot.has_iq and (
        iq_age_s is None or iq_age_s <= float(semantic_fresh_seconds)
    )
    semantic_is_fresh = (
        snapshot.has_semantic
        and semantic_age_s is not None
        and semantic_age_s <= float(semantic_fresh_seconds)
    )

    if iq_is_fresh and semantic_is_fresh:
        return snapshot.power_db, "IQ+语义", "tab:green", "IQ/语义都新鲜，显示并集"

    if iq_is_fresh:
        return snapshot.power_iq_dbm, "IQ", "tab:blue", "语义未更新，回退到 IQ"

    if semantic_is_fresh:
        return snapshot.power_semantic_dbm, "语义", "tab:orange", "IQ 未更新，回退到语义"

    if snapshot.has_iq:
        return snapshot.power_iq_dbm, "IQ", "tab:blue", "IQ 时间未知/已过期，但继续显示 IQ"

    if snapshot.has_semantic:
        return snapshot.power_semantic_dbm, "语义", "tab:orange", "仅语义，或 IQ 不可用"

    raise ValueError("当前没有任何可显示的数据源")


def _render_plot(
    *,
    pyplot,
    ax,
    line,
    snapshot: run_union.UnionSpectrumSnapshot,
    display_power: np.ndarray,
    mode_label: str,
    line_color: str,
    status_label: str,
) -> None:
    line.set_data(snapshot.freq_mhz, display_power)
    line.set_color(line_color)
    line.set_label(mode_label)

    ax.relim()
    ax.autoscale_view()
    ax.set_xlim(float(snapshot.freq_mhz[0]), float(snapshot.freq_mhz[-1]))
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dBm @ 1MHz RBW)")
    ax.set_title(f"实时电磁态势频谱 - {mode_label} | {status_label}")
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best")

    pyplot.draw()
    pyplot.pause(0.001)


def _fmt_timing_ms(value: object) -> object:
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return value


def main() -> int:
    _ensure_console_utf8()

    parser = argparse.ArgumentParser(description="实时监视 IQ/语义并持续更新 union_spectrum.npz")
    parser.add_argument(
        "--semantic-dir",
        type=Path,
        default=ROOT / "data_semantic",
        help="语义文件目录（默认 data_semantic）",
    )
    parser.add_argument(
        "--iq-dir",
        type=Path,
        default=ROOT / "data_segment",
        help="IQ 数据目录（默认 data_segment）",
    )
    parser.add_argument(
        "--semantic-fresh-seconds",
        type=float,
        default=3.0,
        help="语义被视为“新鲜”的秒数窗口（默认 3 秒）",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.2,
        help="目录轮询间隔秒数（默认 0.2）",
    )
    parser.add_argument(
        "--segment-fft-size",
        type=int,
        default=512,
        help="IQ 分段 FFT 点数（默认 512）",
    )
    parser.add_argument(
        "--time-agg-mode",
        type=str,
        default="mean",
        choices=["mean", "max"],
        help="IQ 分段 FFT 的时间聚合方式（默认 mean）",
    )
    parser.add_argument(
        "--noise-floor-dbm-1mhz",
        type=float,
        default=run_union.DEFAULT_NOISE_FLOOR_DBM_1MHZ,
        help="输出绝对底噪基准 dBm@1MHz（默认 -105）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "union_spectrum.npz",
        help="实时输出 npz 路径（默认 output/union_spectrum.npz）",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="显式启用实时绘图；默认不打开图窗",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试输出；默认静默运行",
    )
    args = parser.parse_args()

    def debug_print(*values: object, **kwargs: object) -> None:
        if args.debug:
            print(*values, **kwargs)

    pyplot = None
    fig = None
    ax = None
    line = None

    if args.plot:
        # 只有真的要显示图窗时，才抢占交互式 backend。
        os.environ.setdefault("MPLBACKEND", "TkAgg")
        pyplot = _import_live_pyplot()
        pyplot.ion()

        fig, ax = pyplot.subplots(figsize=(13, 5))
        (line,) = ax.plot([], [], linewidth=0.9)
        ax.set_title("实时电磁态势频谱 - 等待数据")
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Power (dBm @ 1MHz RBW)")
        ax.grid(True, alpha=0.3, linestyle="--")
        fig.tight_layout()

    last_iq_sig: Optional[Tuple[Tuple[str, int, int], ...]] = None
    last_sem_sig: Optional[Tuple[str, int, int]] = None
    last_render_key: Optional[Tuple[object, ...]] = None
    snapshot: Optional[run_union.UnionSpectrumSnapshot] = None
    iq_cache = run_union.IQSpectrumCache()

    debug_print("=" * 80)
    debug_print("实时并集频谱监视已启动")
    debug_print(f"IQ 目录: {args.iq_dir}")
    debug_print(f"语义目录: {args.semantic_dir}")
    debug_print(f"输出文件: {args.output}")
    debug_print(f"IQ/语义新鲜窗口: {float(args.semantic_fresh_seconds):.1f} 秒")
    if args.plot:
        debug_print("模式: 实时保存 + 实时绘图")
        debug_print("关闭图窗或 Ctrl+C 可退出")
    else:
        debug_print("模式: 仅实时保存，不打开图窗")
        debug_print("Ctrl+C 可退出")
    debug_print("=" * 80)

    try:
        while True:
            loop_t0 = time.perf_counter()
            scan_t0 = time.perf_counter()
            iq_sig = _iq_signature(args.iq_dir)
            semantic_path = _pick_latest_semantic_file(args.semantic_dir)
            sem_sig = _semantic_signature(semantic_path)
            scan_ms = (time.perf_counter() - scan_t0) * 1000.0

            should_recompute = (
                snapshot is None
                or iq_sig != last_iq_sig
                or sem_sig != last_sem_sig
            )

            if should_recompute:
                try:
                    recompute_t0 = time.perf_counter()
                    snapshot = run_union.compute_union_snapshot(
                        semantic_path=semantic_path,
                        iq_dir=args.iq_dir,
                        iq_cache=iq_cache,
                        segment_fft_size=int(args.segment_fft_size),
                        time_agg_mode=str(args.time_agg_mode),
                        noise_floor_dbm_1mhz=float(args.noise_floor_dbm_1mhz),
                        allow_missing_semantic=True,
                        verbose=False,
                    )
                    recompute_ms = (time.perf_counter() - recompute_t0) * 1000.0
                    last_iq_sig = iq_sig
                    last_sem_sig = sem_sig
                    save_t0 = time.perf_counter()
                    _save_snapshot_npz(snapshot, args.output)
                    save_ms = (time.perf_counter() - save_t0) * 1000.0
                    loop_ms = (time.perf_counter() - loop_t0) * 1000.0

                    debug_print(
                        "[UPDATE] "
                        f"IQ={'Y' if snapshot.has_iq else 'N'}, "
                        f"SEM={'Y' if snapshot.has_semantic else 'N'}, "
                        f"semantic_file={snapshot.semantic_path.name if snapshot.semantic_path else 'None'}, "
                        f"iq_cache_hits={snapshot.stitched.metadata.get('cache_hits', 'n/a')}, "
                        f"iq_mem_hits={snapshot.stitched.metadata.get('memory_cache_hits', 'n/a')}, "
                        f"iq_disk_hits={snapshot.stitched.metadata.get('disk_cache_hits', 'n/a')}, "
                        f"iq_cache_misses={snapshot.stitched.metadata.get('cache_misses', 'n/a')}, "
                        f"scan_ms={scan_ms:.3f}, "
                        f"recompute_ms={recompute_ms:.3f}, "
                        f"save_ms={save_ms:.3f}, "
                        f"loop_ms={loop_ms:.3f}, "
                        f"task2_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_total_ms', 'n/a'))}, "
                        f"task2_scan_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_scan_ms', 'n/a'))}, "
                        f"task2_disk_load_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_disk_load_ms', 'n/a'))}, "
                        f"task2_miss_compute_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_miss_compute_ms', 'n/a'))}, "
                        f"task2_miss_disk_save_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_miss_disk_save_ms', 'n/a'))}, "
                        f"task2_stitch_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('task2_stitch_ms', 'n/a'))}, "
                        f"semantic_resolve_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('semantic_resolve_ms', 'n/a'))}, "
                        f"semantic_stage_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('semantic_stage_ms', 'n/a'))}, "
                        f"aggregate_stage_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('aggregate_stage_ms', 'n/a'))}, "
                        f"union_stage_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('union_stage_ms', 'n/a'))}, "
                        f"snapshot_total_ms={_fmt_timing_ms(snapshot.stitched.metadata.get('snapshot_total_ms', 'n/a'))}, "
                        f"saved={args.output}"
                    )
                except Exception as exc:
                    debug_print(f"[WARN] 更新频谱缓存失败：{exc}")

            if snapshot is None or (not snapshot.has_iq and not snapshot.has_semantic):
                if pyplot is not None and ax is not None:
                    ax.set_title("实时电磁态势频谱 - 等待 IQ/语义数据")
                    pyplot.pause(float(args.poll_interval))
                else:
                    time.sleep(float(args.poll_interval))
                continue

            now_ts = time.time()
            display_power, mode_label, line_color, status_label = _select_display_power(
                snapshot,
                iq_dir=args.iq_dir,
                semantic_fresh_seconds=float(args.semantic_fresh_seconds),
                now_ts=now_ts,
            )
            iq_age_s = _iq_age_seconds(args.iq_dir, now_ts)
            semantic_age_s = _semantic_age_seconds(snapshot.semantic_path, now_ts)
            iq_fresh = (
                snapshot.has_iq
                and (iq_age_s is None or iq_age_s <= float(args.semantic_fresh_seconds))
            )
            semantic_fresh = (
                semantic_age_s is not None and semantic_age_s <= float(args.semantic_fresh_seconds)
            )
            render_key = (
                mode_label,
                line_color,
                status_label,
                tuple(last_iq_sig or ()),
                last_sem_sig,
                bool(iq_fresh),
                bool(semantic_fresh),
            )

            if pyplot is not None and ax is not None and line is not None and render_key != last_render_key:
                _render_plot(
                    pyplot=pyplot,
                    ax=ax,
                    line=line,
                    snapshot=snapshot,
                    display_power=display_power,
                    mode_label=mode_label,
                    line_color=line_color,
                    status_label=status_label,
                )
                last_render_key = render_key

            if pyplot is not None and fig is not None:
                if not pyplot.fignum_exists(fig.number):
                    debug_print("\n图窗已关闭，实时保存退出")
                    break
                pyplot.pause(float(args.poll_interval))
            else:
                time.sleep(float(args.poll_interval))
    except KeyboardInterrupt:
        debug_print("\n用户中断，实时保存退出")
    finally:
        if pyplot is not None:
            pyplot.ioff()
            if fig is not None and pyplot.fignum_exists(fig.number):
                pyplot.close(fig)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
