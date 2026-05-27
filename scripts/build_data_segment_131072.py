#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 13 个 131072 复数点的测试 bin 文件。

目标：
- 从当前 `data_segment/` 的大文件中，截取前 131072 个 complex IQ 点；
- 生成一套更适合实时/性能验证的小尺寸输入；
- 默认输出到 `data_segment_131072/`；
- 目录中若缺失标准 13 窗口的某个中心频率，则按显式补位策略生成，并记录到 manifest。

当前仓库的已知偏差：
- 标准窗口中心应为 13 个：130, 330, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400 MHz；
- 但现有 `data_segment/` 仅有 12 个源文件，缺少 2400MHz 源；
- 默认补位策略：使用 2200MHz 的截取数据复制为 `2400MHz.bin`，仅用于链路联调，不代表真实 2400MHz 采集。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data_segment"
DEFAULT_OUTPUT_DIR = ROOT / "data_segment_131072"
DEFAULT_COMPLEX_POINTS = 131072
STANDARD_CENTERS_MHZ = (
    130,
    330,
    400,
    600,
    800,
    1000,
    1200,
    1400,
    1600,
    1800,
    2000,
    2200,
    2400,
)
FILENAME_CENTER_RE = re.compile(r"(?P<center>\d+)MHz", re.IGNORECASE)


def _parse_center_mhz(path: Path) -> Optional[int]:
    match = FILENAME_CENTER_RE.search(path.name)
    if match is None:
        return None
    return int(match.group("center"))


def _index_source_files(source_dir: Path) -> Dict[int, Path]:
    files = sorted(source_dir.glob("*.bin"))
    if not files:
        raise FileNotFoundError(f"源目录中没有 .bin 文件：{source_dir}")

    by_center: Dict[int, Path] = {}
    for path in files:
        center = _parse_center_mhz(path)
        if center is None:
            continue
        by_center[center] = path
    return by_center


def _copy_prefix_bytes(src: Path, dst: Path, byte_count: int) -> int:
    with src.open("rb") as src_f:
        data = src_f.read(byte_count)
    if len(data) != byte_count:
        raise ValueError(
            f"源文件 {src} 数据不足：需要 {byte_count} bytes，实际只读到 {len(data)} bytes"
        )
    with dst.open("wb") as dst_f:
        dst_f.write(data)
    return len(data)


def main() -> int:
    if sys.platform == "win32":
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name, None)
            if stream is None or getattr(stream, "closed", False):
                continue
            if not hasattr(stream, "reconfigure"):
                continue
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    parser = argparse.ArgumentParser(description="生成 13 个 131072 复数点的测试 bin 文件")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR, help="源 bin 目录")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument(
        "--complex-points",
        type=int,
        default=DEFAULT_COMPLEX_POINTS,
        help="每个输出文件保留的复数 IQ 点数（默认 131072）",
    )
    parser.add_argument(
        "--fill-missing-from",
        type=int,
        default=2200,
        help="缺失中心频率时，使用哪个中心的源文件补位（默认 2200）",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    complex_points = int(args.complex_points)
    fill_missing_from = int(args.fill_missing_from)
    bytes_per_complex_iq = 4  # int16 I + int16 Q
    target_bytes = complex_points * bytes_per_complex_iq

    source_map = _index_source_files(source_dir)
    if fill_missing_from not in source_map:
        raise FileNotFoundError(
            f"补位源中心 {fill_missing_from}MHz 不存在，当前可用中心：{sorted(source_map)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for existing in output_dir.glob("*.bin"):
        existing.unlink()

    manifest = {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "complex_points_per_file": complex_points,
        "bytes_per_file": target_bytes,
        "standard_centers_mhz": list(STANDARD_CENTERS_MHZ),
        "fill_missing_from_mhz": fill_missing_from,
        "files": [],
    }

    print("=" * 80)
    print("生成 131072 点测试 bin")
    print(f"源目录: {source_dir}")
    print(f"输出目录: {output_dir}")
    print(f"每文件复数点数: {complex_points}")
    print(f"每文件字节数: {target_bytes}")
    print("=" * 80)

    for center in STANDARD_CENTERS_MHZ:
        src = source_map.get(center)
        fallback_used = False
        if src is None:
            src = source_map[fill_missing_from]
            fallback_used = True

        dst = output_dir / f"{center}MHz.bin"
        written = _copy_prefix_bytes(src, dst, target_bytes)
        info = {
            "target_center_mhz": center,
            "output_name": dst.name,
            "source_name": src.name,
            "fallback_used": fallback_used,
            "written_bytes": written,
            "complex_points": complex_points,
        }
        manifest["files"].append(info)
        fallback_tag = " [fallback]" if fallback_used else ""
        print(
            f"{dst.name:<12} <- {src.name}{fallback_tag} | "
            f"bytes={written} | complex_points={complex_points}"
        )

    manifest_path = output_dir / "manifest_131072.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 80)
    print(f"manifest 已写入: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
