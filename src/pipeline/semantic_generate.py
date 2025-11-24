#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语义参数随机生成脚本

根据 docs/semantic_encoding_requirements.md（v2.0）中定义的语义编码形式，
随机生成若干组语义数据（JSON），用于覆盖正常情况与边界条件测试。

生成的 JSON 结构示例::

    {
      "freq_min_mhz": 30.0,
      "freq_max_mhz": 2500.0,
      "num_bins": 2471,
      "noise_floor_db": -80.0,
      "jammer_regions": [
        {"start_bin": 50, "end_bin": 90, "jnr_db": 25.0},
        ...
      ]
    }

默认生成 10 组数据，保存到 data_semantic 目录下:

    semantic_case01.json, semantic_case02.json, ...
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np


if sys.platform == "win32":  # pragma: no cover - 仅在 Windows 控制台下生效
    import io

    if hasattr(sys.stdout, "buffer") and not sys.stdout.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and not sys.stderr.closed:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


@dataclass
class JammerRegion:
    """单个干扰区间定义。"""

    start_bin: int
    end_bin: int
    jnr_db: float

    def to_dict(self) -> dict:
        return {
            "start_bin": int(self.start_bin),
            "end_bin": int(self.end_bin),
            "jnr_db": float(self.jnr_db),
        }


@dataclass
class SemanticEncodingSample:
    """一组语义编码参数，直接对应 semantic_encoding_requirements.md 的 JSON Schema。"""

    freq_min_mhz: float
    freq_max_mhz: float
    num_bins: int
    noise_floor_db: float
    jammer_regions: List[JammerRegion]

    def to_dict(self) -> dict:
        return {
            "freq_min_mhz": float(self.freq_min_mhz),
            "freq_max_mhz": float(self.freq_max_mhz),
            "num_bins": int(self.num_bins),
            "noise_floor_db": float(self.noise_floor_db),
            "jammer_regions": [r.to_dict() for r in self.jammer_regions],
        }


def _validate_sample(sample: SemanticEncodingSample) -> None:
    """按 semantic_encoding_requirements.md 的约束做快速校验。

    若不满足约束，抛出 ValueError 便于调试。
    """

    if sample.freq_max_mhz <= sample.freq_min_mhz:
        raise ValueError("freq_max_mhz 必须大于 freq_min_mhz")
    if sample.num_bins < 2:
        raise ValueError("num_bins 必须 >= 2")
    # 噪声底推荐范围 [-100, -20]，这里不强制，但明显越界时提示
    if not (-120.0 <= sample.noise_floor_db <= -10.0):
        raise ValueError(f"noise_floor_db 数值异常: {sample.noise_floor_db}")

    regions = sample.jammer_regions
    for idx, r in enumerate(regions):
        if not (0 <= r.start_bin < r.end_bin < sample.num_bins):
            raise ValueError(f"第 {idx} 个 region 的 start_bin/end_bin 越界: {r.start_bin}, {r.end_bin}")
        if r.jnr_db <= 0.0:
            raise ValueError(f"第 {idx} 个 region 的 jnr_db 必须 > 0, 当前: {r.jnr_db}")
    for i in range(len(regions) - 1):
        if regions[i].end_bin >= regions[i + 1].start_bin:
            raise ValueError(f"第 {i} 与 {i+1} 个 region 发生重叠: [{regions[i].start_bin}, {regions[i].end_bin}] vs "
                             f"[{regions[i+1].start_bin}, {regions[i+1].end_bin}]")


def _make_empty_sample(num_bins: int, noise_floor_db: float) -> SemanticEncodingSample:
    """全噪声场景，jammer_regions 为空。"""

    return SemanticEncodingSample(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        num_bins=num_bins,
        noise_floor_db=noise_floor_db,
        jammer_regions=[],
    )


def _make_full_band_sample(num_bins: int, noise_floor_db: float, jnr_db: float) -> SemanticEncodingSample:
    """全频段都有干扰的场景，覆盖 0..num_bins-1。"""

    region = JammerRegion(start_bin=0, end_bin=num_bins - 1, jnr_db=jnr_db)
    sample = SemanticEncodingSample(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        num_bins=num_bins,
        noise_floor_db=noise_floor_db,
        jammer_regions=[region],
    )
    _validate_sample(sample)
    return sample


def _make_boundary_samples(num_bins: int, noise_floor_db: float) -> List[SemanticEncodingSample]:
    """构造若干边界条件样本。

    覆盖场景：
    - 干扰从 bin0 开始；
    - 干扰到达 num_bins-1 的尾部；
    - 极短干扰段（长度=1 或 2）；
    - 紧贴边界但不越界。
    """

    samples: List[SemanticEncodingSample] = []

    # 1) 干扰从最开头开始，长度适中
    r1 = JammerRegion(start_bin=0, end_bin=min(50, num_bins - 1), jnr_db=20.0)
    s1 = SemanticEncodingSample(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        num_bins=num_bins,
        noise_floor_db=noise_floor_db,
        jammer_regions=[r1],
    )
    _validate_sample(s1)
    samples.append(s1)

    # 2) 干扰覆盖到最后一个 bin
    end_len = min(60, num_bins // 4)
    r2 = JammerRegion(start_bin=num_bins - end_len, end_bin=num_bins - 1, jnr_db=18.0)
    s2 = SemanticEncodingSample(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        num_bins=num_bins,
        noise_floor_db=noise_floor_db,
        jammer_regions=[r2],
    )
    _validate_sample(s2)
    samples.append(s2)

    # 3) 极短区间（长度=2），置于中间附近
    mid = num_bins // 2
    if mid + 1 < num_bins:
        r3 = JammerRegion(start_bin=mid, end_bin=mid + 1, jnr_db=25.0)
        s3 = SemanticEncodingSample(
            freq_min_mhz=30.0,
            freq_max_mhz=2500.0,
            num_bins=num_bins,
            noise_floor_db=noise_floor_db,
            jammer_regions=[r3],
        )
        _validate_sample(s3)
        samples.append(s3)

    # 4) 两个相邻但不重叠的短干扰段，靠近起点
    if num_bins >= 12:
        r4a = JammerRegion(start_bin=2, end_bin=4, jnr_db=15.0)
        r4b = JammerRegion(start_bin=5, end_bin=7, jnr_db=12.0)
        s4 = SemanticEncodingSample(
            freq_min_mhz=30.0,
            freq_max_mhz=2500.0,
            num_bins=num_bins,
            noise_floor_db=noise_floor_db,
            jammer_regions=[r4a, r4b],
        )
        _validate_sample(s4)
        samples.append(s4)

    return samples


def _make_random_regions(
    rng: np.random.Generator,
    num_bins: int,
    max_regions: int,
    min_region_len: int = 5,
    max_region_len: int | None = None,
) -> List[JammerRegion]:
    """根据约束随机生成若干不重叠干扰区间。"""

    if max_region_len is None:
        max_region_len = max(num_bins // 8, min_region_len)

    regions: List[JammerRegion] = []
    current_start_min = 0
    for _ in range(max_regions):
        if current_start_min >= num_bins - 1:
            break
        # 随机选择 start_bin
        start_bin = int(rng.integers(current_start_min, num_bins - 1))
        # 可用的最大长度
        remaining = num_bins - start_bin
        if remaining < min_region_len:
            break
        length = int(rng.integers(min_region_len, min(max_region_len, remaining) + 1))
        end_bin = start_bin + length - 1
        # JNR 随机在 [5, 30] dB
        jnr_db = float(rng.uniform(5.0, 30.0))
        regions.append(JammerRegion(start_bin=start_bin, end_bin=end_bin, jnr_db=jnr_db))
        # 下一段起点至少在 end_bin+1 之后，保证不重叠
        current_start_min = end_bin + 1

    # 按 start_bin 排序，防止意外
    regions.sort(key=lambda r: r.start_bin)
    return regions


def generate_semantic_samples(num_samples: int, seed: int | None = None) -> List[SemanticEncodingSample]:
    """生成若干语义编码样本，包含多种情况和边界条件。

    设计策略：
    - 统一 freq_min/freq_max 为 30/2500 MHz；
    - num_bins 以 2471 为主（1 MHz 精度），同时也包含几个小分辨率 case；
    - noise_floor_db 在 [-90, -60] 内随机；
    - 部分样本 jammer_regions 为空（纯噪声）、覆盖全频段或构造短区间/边界区间；
    - 剩余样本使用随机不重叠区间。
    """

    rng = np.random.default_rng(seed)
    samples: List[SemanticEncodingSample] = []

    # 一些预设 num_bins 组合：标准 2471 + 小范围，用于边界测试
    candidate_bins = [2471, 128, 512]

    # 1) 纯噪声场景
    noise_floor = float(rng.uniform(-90.0, -70.0))
    s_empty = _make_empty_sample(num_bins=2471, noise_floor_db=noise_floor)
    _validate_sample(s_empty)
    samples.append(s_empty)

    # 2) 全频段干扰场景
    noise_floor2 = float(rng.uniform(-85.0, -65.0))
    s_full = _make_full_band_sample(num_bins=2471, noise_floor_db=noise_floor2, jnr_db=20.0)
    samples.append(s_full)

    # 3) 几个边界场景（不同 num_bins）
    for nb in (2471, 128):
        noise_floor_b = float(rng.uniform(-90.0, -60.0))
        boundary_samples = _make_boundary_samples(num_bins=nb, noise_floor_db=noise_floor_b)
        samples.extend(boundary_samples)
        if len(samples) >= num_samples:
            break

    # 4) 用随机不重叠区间补齐剩余样本数量
    while len(samples) < num_samples:
        nb = int(rng.choice(candidate_bins))
        noise_floor = float(rng.uniform(-85.0, -60.0))
        max_regions = int(rng.integers(1, 6))  # 1~5 段干扰
        regions = _make_random_regions(
            rng=rng,
            num_bins=nb,
            max_regions=max_regions,
            min_region_len=5,
        )
        sample = SemanticEncodingSample(
            freq_min_mhz=30.0,
            freq_max_mhz=2500.0,
            num_bins=nb,
            noise_floor_db=noise_floor,
            jammer_regions=regions,
        )
        _validate_sample(sample)
        samples.append(sample)

    # 若超过 num_samples（理论上不会超很多），裁剪到指定数量
    return samples[:num_samples]


def main() -> None:
    parser = argparse.ArgumentParser(description="随机生成语义编码 JSON 数据，用于测试与边界条件验证")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data_semantic"),
        help="输出目录，默认 data_semantic",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=10,
        help="生成样本数量，默认 10",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（可选），便于复现",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    num_samples: int = max(1, int(args.num_samples))
    seed = args.seed

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise SystemExit(f"创建输出目录失败: {output_dir}, 原因: {exc}") from exc

    samples = generate_semantic_samples(num_samples=num_samples, seed=seed)

    for idx, sample in enumerate(samples, start=1):
        filename = f"semantic_case{idx:02d}.json"
        path = output_dir / filename
        data = sample.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"生成语义样本 {idx:02d}: {path} "
              f"(num_bins={sample.num_bins}, regions={len(sample.jammer_regions)})")


if __name__ == "__main__":
    main()
