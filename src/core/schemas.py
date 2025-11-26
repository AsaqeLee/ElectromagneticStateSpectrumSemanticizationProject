"""核心数据结构定义，避免模块间传递裸数组导致的歧义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np


# 语义频谱默认配置（按最新需求约定）
# 说明：
# - 这些默认值在“语义恢复频谱”场景下视为固定配置；
# - 之所以集中在此处，是为了在需要调整频段 / 点数 / 底噪时只改一处；
# - 上层如需覆盖，可显式传入 freq_min_mhz/freq_max_mhz/num_bins/noise_floor_db。
DEFAULT_SEMANTIC_FREQ_MIN_MHZ = 30.0
DEFAULT_SEMANTIC_FREQ_MAX_MHZ = 2500.0
DEFAULT_SEMANTIC_NUM_BINS = 2471
DEFAULT_SEMANTIC_NOISE_FLOOR_DB = -80.0


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
        """验证语义参数的完整性和一致性。

        约束规则（按优先级由高到低）：
        1. 基本数值范围合法（fenbianlv、频率区间）
        2. start/end 在有效索引范围内且形成闭区间 [start, end]
        3. pos_edge/neg_edge 索引均在 [0, fenbianlv) 且长度相等
        4. sinr 非空，且长度为 1 或 end-start+1
        """

        # 1. 基本范围检查
        if self.fenbianlv <= 0:
            raise ValueError("fenbianlv 必须为正整数")
        if self.freq_max_mhz <= self.freq_min_mhz:
            raise ValueError(
                f"freq_max_mhz ({self.freq_max_mhz}) 必须大于 "
                f"freq_min_mhz ({self.freq_min_mhz})"
            )

        # 2. start/end 索引范围检查（闭区间 [start, end]）
        if self.start < 0 or self.end < 0:
            raise ValueError("start/end 不能为负数")
        if self.start > self.end:
            raise ValueError(f"start ({self.start}) 必须 <= end ({self.end})")
        if self.end >= self.fenbianlv:
            raise ValueError(
                f"end ({self.end}) 必须 < fenbianlv ({self.fenbianlv})，"
                "索引范围应为 [0, fenbianlv-1]"
            )

        # 3. 边缘索引验证：所有边缘索引必须落在 [0, fenbianlv) 内
        for i, idx in enumerate(self.pos_edge):
            if not (0 <= idx < self.fenbianlv):
                raise ValueError(
                    f"pos_edge[{i}] = {idx} 越界，有效范围 [0, {self.fenbianlv - 1}]"
                )

        for i, idx in enumerate(self.neg_edge):
            if not (0 <= idx < self.fenbianlv):
                raise ValueError(
                    f"neg_edge[{i}] = {idx} 越界，有效范围 [0, {self.fenbianlv - 1}]"
                )

        # 4. 边缘长度一致性检查
        if len(self.pos_edge) != len(self.neg_edge):
            raise ValueError(
                "pos_edge 和 neg_edge 长度必须相等，"
                f"当前分别为 {len(self.pos_edge)} 和 {len(self.neg_edge)}"
            )

        # 5. sinr 检查：不能为空，且长度必须匹配区间长度或为统一 JNR
        if self.sinr.size == 0:
            raise ValueError("sinr 不能为空")

        expected = self.end - self.start + 1
        if self.sinr.size not in (1, expected):
            raise ValueError(
                f"sinr 长度需为 1（统一 JNR）或 {expected}（逐点 JNR），"
                f"当前 {self.sinr.size}"
            )

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticParams":
        """从字典构造 SemanticParams，并立即执行合法性校验。"""
        sinr = np.asarray(data.get("sinr", []), dtype=float)
        obj = cls(
            yonghu=int(data["yonghu"]),
            youwu=int(data["youwu"]),
            menxian=float(data["menxian"]),
            pos_edge=list(map(int, data.get("pos_edge", []))),
            neg_edge=list(map(int, data.get("neg_edge", []))),
            start=int(data["start"]),
            end=int(data["end"]),
            fenbianlv=int(data["fenbianlv"]),
            sinr=sinr,
            freq_min_mhz=float(
                data.get("freq_min_mhz", DEFAULT_SEMANTIC_FREQ_MIN_MHZ)
            ),
            freq_max_mhz=float(
                data.get("freq_max_mhz", DEFAULT_SEMANTIC_FREQ_MAX_MHZ)
            ),
        )
        obj.validate()
        return obj

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
class JammerRegionV2:
    """v2 语义编码中的单个干扰区域（参见 `semantic_encoding_requirements.md`）。

    - start_bin/end_bin: 以 0 为起点的闭区间索引；
    - jnr_db: 相对底噪的干扰功率（dB）。
    """

    start_bin: int
    end_bin: int
    jnr_db: float


@dataclass
class SemanticEncodingV2:
    """v2 版本的语义编码结构，直接对应 docs/semantic_encoding_requirements.md 中的 JSON Schema。

    字段说明：
    - freq_min_mhz/freq_max_mhz: 频率范围 [MHz]；
    - num_bins: 频谱离散点数；
    - noise_floor_db: 底噪功率（dB）；
    - jammer_regions: 多个不重叠干扰区域，每个区域用 start_bin/end_bin/jnr_db 描述。
    """

    freq_min_mhz: float = DEFAULT_SEMANTIC_FREQ_MIN_MHZ
    freq_max_mhz: float = DEFAULT_SEMANTIC_FREQ_MAX_MHZ
    num_bins: int = DEFAULT_SEMANTIC_NUM_BINS
    noise_floor_db: float = DEFAULT_SEMANTIC_NOISE_FLOOR_DB
    jammer_regions: List[JammerRegionV2] = field(default_factory=list)

    def validate(self) -> None:
        """按 v2 规范校验参数合法性。"""

        if self.freq_max_mhz <= self.freq_min_mhz:
            raise ValueError("freq_max_mhz 必须大于 freq_min_mhz")
        if self.num_bins < 2:
            raise ValueError("num_bins 必须 >= 2")
        if not (-120.0 <= self.noise_floor_db <= -10.0):
            # 不强制，但给出合理区间限制
            raise ValueError(f"noise_floor_db 数值异常: {self.noise_floor_db}")

        regions = self.jammer_regions
        for i, r in enumerate(regions):
            if r.start_bin < 0 or r.end_bin < 0:
                raise ValueError(f"第 {i} 个区域索引不能为负: {r.start_bin}, {r.end_bin}")
            if not (0 <= r.start_bin < r.end_bin < self.num_bins):
                raise ValueError(
                    f"第 {i} 个区域越界: start={r.start_bin}, end={r.end_bin}, "
                    f"合法范围 [0, {self.num_bins - 1}]"
                )
            if r.jnr_db <= 0.0:
                raise ValueError(f"第 {i} 个区域 jnr_db 必须 > 0, 当前 {r.jnr_db}")

        # 区域按照 start_bin 排序且不重叠
        for i in range(len(regions) - 1):
            if regions[i].end_bin >= regions[i + 1].start_bin:
                raise ValueError(
                    f"区域 {i} 与 {i+1} 发生重叠: "
                    f"[{regions[i].start_bin}, {regions[i].end_bin}] vs "
                    f"[{regions[i+1].start_bin}, {regions[i+1].end_bin}]"
                )

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticEncodingV2":
        """从 v2 JSON 字典构造实例。"""

        regions_data = data.get("jammer_regions", [])
        regions: List[JammerRegionV2] = []
        for entry in regions_data:
            # 允许存在额外字段（如 comment），这里只关心必须字段
            regions.append(
                JammerRegionV2(
                    start_bin=int(entry["start_bin"]),
                    end_bin=int(entry["end_bin"]),
                    jnr_db=float(entry["jnr_db"]),
                )
            )
        obj = cls(
            freq_min_mhz=float(
                data.get("freq_min_mhz", DEFAULT_SEMANTIC_FREQ_MIN_MHZ)
            ),
            freq_max_mhz=float(
                data.get("freq_max_mhz", DEFAULT_SEMANTIC_FREQ_MAX_MHZ)
            ),
            num_bins=int(
                data.get("num_bins", DEFAULT_SEMANTIC_NUM_BINS)
            ),
            noise_floor_db=float(
                data.get("noise_floor_db", DEFAULT_SEMANTIC_NOISE_FLOOR_DB)
            ),
            jammer_regions=regions,
        )
        obj.validate()
        return obj

    def to_dict(self) -> dict:
        """转回 JSON 友好的 dict 结构。"""

        return {
            "freq_min_mhz": float(self.freq_min_mhz),
            "freq_max_mhz": float(self.freq_max_mhz),
            "num_bins": int(self.num_bins),
            "noise_floor_db": float(self.noise_floor_db),
            "jammer_regions": [
                {
                    "start_bin": int(r.start_bin),
                    "end_bin": int(r.end_bin),
                    "jnr_db": float(r.jnr_db),
                }
                for r in self.jammer_regions
            ],
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
