#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""持续随机生成语义 TXT，专门用于联调 run_union_realtime.py。

用途：
- 默认每秒向 `data_semantic/` 写入一份新的 `semantic_时间戳.txt`；
- 同时刷新 `semantic.txt`，方便人工直接查看当前内容；
- 让 `scripts/run_union_realtime.py` 的语义签名稳定变化，便于定位“为何没有实时更新”。

设计原则：
- 只动语义输入，不碰 IQ；
- 默认写入真实 `data_semantic/`，更接近用户实际调用路径；
- 每次输出都显式包含 `num_bins=2471` 与 `noise_floor_db=-105.0`，
  避免再踩“默认值不清楚”的坑；
- 默认保留最近若干个带时间戳的文件，防止目录无限膨胀。
"""
from __future__ import annotations

import argparse
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEMANTIC_DIR = ROOT / "data_semantic"
STAMPED_FILE_RE = re.compile(
    r"^semantic_(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})(?:_[^.]+)?\.txt$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class JammerRegion:
    start_bin: int
    end_bin: int
    jnr_db: float


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


def _now_tag() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _build_regions(
    *,
    rng: random.Random,
    num_bins: int,
    region_count: int,
    min_width: int,
    max_width: int,
    min_jnr_db: float,
    max_jnr_db: float,
) -> List[JammerRegion]:
    regions: List[JammerRegion] = []
    max_attempts = max(region_count * 50, 100)

    for _ in range(max_attempts):
        if len(regions) >= region_count:
            break

        start_bin = rng.randint(0, max(num_bins - 2, 0))
        width = rng.randint(max(1, min_width), max(1, max_width))
        end_bin = min(start_bin + width, num_bins - 1)

        overlaps = False
        for region in regions:
            if not (end_bin < region.start_bin or start_bin > region.end_bin):
                overlaps = True
                break
        if overlaps:
            continue

        jnr_db = round(rng.uniform(min_jnr_db, max_jnr_db), 1)
        regions.append(
            JammerRegion(
                start_bin=int(start_bin),
                end_bin=int(end_bin),
                jnr_db=float(jnr_db),
            )
        )

    regions.sort(key=lambda item: (item.start_bin, item.end_bin))
    if not regions:
        regions.append(JammerRegion(start_bin=100, end_bin=150, jnr_db=2.0))
    return regions


def _render_semantic_text(
    *,
    regions: List[JammerRegion],
    num_bins: int,
    noise_floor_db: float,
    update_index: int,
) -> str:
    lines = [
        "# 自动生成的随机语义输入",
        f"# update_index={update_index}",
        "freq_min_mhz=30.0",
        "freq_max_mhz=2500.0",
        f"num_bins={int(num_bins)}",
        f"noise_floor_db={float(noise_floor_db):.1f}",
        "[jammer_regions]",
    ]
    for region in regions:
        lines.append(f"{region.start_bin},{region.end_bin},{region.jnr_db:.1f}")
    lines.append("")
    return "\n".join(lines)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _make_stamped_path(semantic_dir: Path, update_index: int) -> Path:
    base_name = f"semantic_{_now_tag()}.txt"
    path = semantic_dir / base_name
    if not path.exists():
        return path
    return semantic_dir / f"semantic_{_now_tag()}_{update_index:04d}.txt"


def _cleanup_old_stamped_files(semantic_dir: Path, keep_files: int) -> None:
    if keep_files <= 0 or not semantic_dir.exists():
        return

    stamped_files = [
        path
        for path in semantic_dir.iterdir()
        if path.is_file() and STAMPED_FILE_RE.match(path.name)
    ]
    stamped_files.sort(key=lambda item: (item.stat().st_mtime_ns, item.name), reverse=True)
    for old_path in stamped_files[keep_files:]:
        old_path.unlink(missing_ok=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每秒随机生成语义 TXT，联调 run_union_realtime.py")
    parser.add_argument(
        "--semantic-dir",
        type=Path,
        default=DEFAULT_SEMANTIC_DIR,
        help="语义输出目录，默认 data_semantic",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="更新间隔秒数，默认 1.0",
    )
    parser.add_argument(
        "--updates",
        type=int,
        default=0,
        help="更新次数；0 表示持续运行直到 Ctrl+C",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子；不传则每次运行不同",
    )
    parser.add_argument(
        "--num-bins",
        type=int,
        default=2471,
        help="写入语义文件的 num_bins，默认 2471",
    )
    parser.add_argument(
        "--noise-floor-db",
        type=float,
        default=-105.0,
        help="写入语义文件的 noise_floor_db，默认 -105.0",
    )
    parser.add_argument(
        "--min-regions",
        type=int,
        default=1,
        help="每次最少生成多少个干扰区，默认 1",
    )
    parser.add_argument(
        "--max-regions",
        type=int,
        default=3,
        help="每次最多生成多少个干扰区，默认 3",
    )
    parser.add_argument(
        "--min-width",
        type=int,
        default=10,
        help="单个干扰区最小宽度（bin），默认 10",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=80,
        help="单个干扰区最大宽度（bin），默认 80",
    )
    parser.add_argument(
        "--min-jnr-db",
        type=float,
        default=1.0,
        help="单个干扰区最小 jnr_db，默认 1.0",
    )
    parser.add_argument(
        "--max-jnr-db",
        type=float,
        default=12.0,
        help="单个干扰区最大 jnr_db，默认 12.0",
    )
    parser.add_argument(
        "--keep-files",
        type=int,
        default=10,
        help="最多保留多少个带时间戳的 semantic_*.txt；0 表示不清理，默认 10",
    )
    return parser.parse_args()


def main() -> int:
    _ensure_console_utf8()
    args = _parse_args()

    if args.interval <= 0.0:
        raise ValueError(f"--interval 必须 > 0，当前为 {args.interval}")
    if args.num_bins < 2:
        raise ValueError(f"--num-bins 必须 >= 2，当前为 {args.num_bins}")
    if args.min_regions <= 0 or args.max_regions <= 0:
        raise ValueError("--min-regions / --max-regions 必须 > 0")
    if args.min_regions > args.max_regions:
        raise ValueError("--min-regions 不能大于 --max-regions")
    if args.min_width <= 0 or args.max_width <= 0:
        raise ValueError("--min-width / --max-width 必须 > 0")
    if args.min_width > args.max_width:
        raise ValueError("--min-width 不能大于 --max-width")
    if args.min_jnr_db <= 0.0 or args.max_jnr_db <= 0.0:
        raise ValueError("--min-jnr-db / --max-jnr-db 必须 > 0")
    if args.min_jnr_db > args.max_jnr_db:
        raise ValueError("--min-jnr-db 不能大于 --max-jnr-db")
    if args.updates < 0:
        raise ValueError("--updates 不能为负数")

    semantic_dir = args.semantic_dir.resolve()
    rng = random.Random(args.seed)

    print("=" * 80)
    print("随机语义输入生成器启动")
    print(f"输出目录: {semantic_dir}")
    print(f"更新间隔: {float(args.interval):.1f} 秒")
    print(f"更新次数: {'持续运行' if int(args.updates) == 0 else int(args.updates)}")
    print(f"保留时间戳文件数: {int(args.keep_files)}")
    print(f"随机种子: {args.seed if args.seed is not None else '未固定'}")
    print("=" * 80)

    update_index = 0
    try:
        while True:
            update_index += 1
            region_count = rng.randint(int(args.min_regions), int(args.max_regions))
            regions = _build_regions(
                rng=rng,
                num_bins=int(args.num_bins),
                region_count=region_count,
                min_width=int(args.min_width),
                max_width=int(args.max_width),
                min_jnr_db=float(args.min_jnr_db),
                max_jnr_db=float(args.max_jnr_db),
            )
            content = _render_semantic_text(
                regions=regions,
                num_bins=int(args.num_bins),
                noise_floor_db=float(args.noise_floor_db),
                update_index=update_index,
            )

            semantic_txt_path = semantic_dir / "semantic.txt"
            stamped_path = _make_stamped_path(semantic_dir, update_index)
            _write_atomic(semantic_txt_path, content)
            _write_atomic(stamped_path, content)
            _cleanup_old_stamped_files(semantic_dir, int(args.keep_files))

            regions_desc = "; ".join(
                f"{region.start_bin},{region.end_bin},{region.jnr_db:.1f}"
                for region in regions
            )
            print(
                f"[UPDATE {update_index}] "
                f"wrote={stamped_path.name} "
                f"regions={len(regions)} "
                f"{regions_desc}"
            )

            if int(args.updates) > 0 and update_index >= int(args.updates):
                break
            time.sleep(float(args.interval))
    except KeyboardInterrupt:
        print("\n用户中断，随机语义输入生成器退出")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
