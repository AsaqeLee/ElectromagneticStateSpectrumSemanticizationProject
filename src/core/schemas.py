"""核心数据结构定义，避免模块间传递裸数组导致的歧义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np


# 语义频谱默认覆盖范围与分辨率（可通过 SemanticParams 覆盖）
DEFAULT_SEMANTIC_FREQ_MIN_MHZ = 30.0
DEFAULT_SEMANTIC_FREQ_MAX_MHZ = 2500.0


@dataclass
class SamplingConfig:
    """采样与 FFT 相关配置。"""

    sample_rate_hz: float
    center_freq_hz: float
    fft_size: int = 4096

    @property
    def resolution_hz(self) -> float:
        return self.sample_rate_hz / float(self.fft_size)


@dataclass
class BandConfig:
    """频段配置，单位 MHz。"""

    name: str
    start_freq_mhz: float
    end_freq_mhz: float

    def contains(self, freq_mhz: float) -> bool:
        return self.start_freq_mhz <= freq_mhz <= self.end_freq_mhz


@dataclass
class SemanticParams:
    """语义参数，根据 `频谱语义化表征及频谱恢复.md` 的字段约定，并结合 30–2500 MHz 场景进行约束。

    字段说明（保持原有拼音命名以兼容现有数据）：
    - yonghu: 用户ID (user_id)
    - youwu: 是否有干扰 0/1 (has_jammer)
    - menxian: 底噪功率 dB (noise_floor_db)
    - fenbianlv: 频谱离散点个数 (num_bins)
    - start/end: 干扰区域索引范围
    - sinr: 干扰相对底噪的能量（dB）
    - pos_edge/neg_edge: 正/负边缘索引列表
    - freq_min_mhz/freq_max_mhz: 频谱覆盖范围
    """

    yonghu: int
    youwu: int
    menxian: float
    pos_edge: List[int]
    neg_edge: List[int]
    start: int
    end: int
    fenbianlv: int
    sinr: np.ndarray = field(repr=False)
    freq_min_mhz: float = DEFAULT_SEMANTIC_FREQ_MIN_MHZ
    freq_max_mhz: float = DEFAULT_SEMANTIC_FREQ_MAX_MHZ

    # 英文别名属性（推荐使用）
    @property
    def user_id(self) -> int:
        return self.yonghu

    @property
    def has_jammer(self) -> bool:
        return self.youwu == 1

    @property
    def noise_floor_db(self) -> float:
        return self.menxian

    @property
    def num_bins(self) -> int:
        return self.fenbianlv

    @property
    def resolution_mhz(self) -> float:
        """语义频谱的频率分辨率（MHz）。"""

        if self.fenbianlv <= 1:
            return self.freq_max_mhz - self.freq_min_mhz
        return (self.freq_max_mhz - self.freq_min_mhz) / float(self.fenbianlv - 1)

    def validate(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("start/end 不能为负数")
        if self.start > self.end:
            raise ValueError("start 必须小于等于 end")
        if self.fenbianlv <= self.end:
            raise ValueError("fenbianlv 必须大于 end，确保索引不越界")
        if self.fenbianlv <= 0:
            raise ValueError("fenbianlv 必须为正")
        if self.freq_max_mhz <= self.freq_min_mhz:
            raise ValueError("freq_max_mhz 必须大于 freq_min_mhz")
        if self.sinr.size == 0:
            raise ValueError("sinr 不能为空")
        expected = self.end - self.start + 1
        if self.sinr.size not in (1, expected):
            raise ValueError(f"sinr 长度需为 1 或 {expected}，当前 {self.sinr.size}")

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticParams":
        sinr = np.asarray(data.get("sinr", []), dtype=float)
        return cls(
            yonghu=int(data["yonghu"]),
            youwu=int(data["youwu"]),
            menxian=float(data["menxian"]),
            pos_edge=list(map(int, data.get("pos_edge", []))),
            neg_edge=list(map(int, data.get("neg_edge", []))),
            start=int(data["start"]),
            end=int(data["end"]),
            fenbianlv=int(data["fenbianlv"]),
            sinr=sinr,
            freq_min_mhz=float(data.get("freq_min_mhz", DEFAULT_SEMANTIC_FREQ_MIN_MHZ)),
            freq_max_mhz=float(data.get("freq_max_mhz", DEFAULT_SEMANTIC_FREQ_MAX_MHZ)),
        )

    def to_dict(self) -> dict:
        return {
            "yonghu": self.yonghu,
            "youwu": self.youwu,
            "menxian": self.menxian,
            "pos_edge": list(self.pos_edge),
            "neg_edge": list(self.neg_edge),
            "start": self.start,
            "end": self.end,
            "fenbianlv": self.fenbianlv,
            "sinr": self.sinr.tolist(),
            "freq_min_mhz": self.freq_min_mhz,
            "freq_max_mhz": self.freq_max_mhz,
        }


@dataclass
class IQData:
    """IQ 数据包装结构，包含元数据便于频谱计算。"""

    samples: np.ndarray
    sample_rate_hz: float
    center_freq_hz: float
    meta: Optional[dict] = None

    def __post_init__(self) -> None:
        if not np.iscomplexobj(self.samples):
            raise ValueError("IQ 样本必须是复数数组")
        if self.samples.ndim != 1:
            raise ValueError("仅支持一维 IQ 向量，若存在多通道请预先合并")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz 必须为正")
        if self.meta is None:
            self.meta = {}

    @property
    def num_samples(self) -> int:
        return self.samples.size

    @property
    def duration_seconds(self) -> float:
        return self.samples.size / float(self.sample_rate_hz)
