"""配置加载与默认频段定义。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

try:
    import yaml
except ImportError:  # pragma: no cover - 仅在未安装 PyYAML 时触发
    yaml = None  # type: ignore

from .schemas import BandConfig, SamplingConfig


DEFAULT_COARSE_BANDS = (
    BandConfig(name="low_band", start_freq_mhz=30.0, end_freq_mhz=225.0),
    BandConfig(name="mid_high_band", start_freq_mhz=225.0, end_freq_mhz=2500.0),
)

# 200 MHz 窗口中心，源自任务描述，围绕中心 +/-100 MHz。
# 覆盖 30–2500 MHz 的 13 个采集频段：
# 130(30~230)、330(230~430)、400(300~500)、600(500~700)、800(700~900)、
# 1000(900~1100)、1200(1100~1300)、1400(1300~1500)、1600(1500~1700)、
# 1800(1700~1900)、2000(1900~2100)、2200(2100~2300)、2400(2300~2500)。
DEFAULT_WINDOW_CENTERS_MHZ = (
    130.0,
    330.0,
    400.0,
    600.0,
    800.0,
    1000.0,
    1200.0,
    1400.0,
    1600.0,
    1800.0,
    2000.0,
    2200.0,
    2400.0,
)


@dataclass
class ProjectConfig:
    """工程级配置，供 pipeline/模块共享。"""

    sampling: SamplingConfig
    coarse_bands: Sequence[BandConfig] = field(default_factory=lambda: DEFAULT_COARSE_BANDS)
    window_centers_mhz: Sequence[float] = field(default_factory=lambda: DEFAULT_WINDOW_CENTERS_MHZ)
    output_root: Path = Path("data")

    def ensure_output_root(self) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)


def _band_from_dict(entry: dict) -> BandConfig:
    return BandConfig(
        name=str(entry["name"]),
        start_freq_mhz=float(entry["start_freq_mhz"]),
        end_freq_mhz=float(entry["end_freq_mhz"]),
    )


def _load_dict_from_file(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    raw = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("未安装 PyYAML，无法解析 YAML 配置")
        return yaml.safe_load(raw)
    if suffix == ".json":
        return json.loads(raw)
    raise ValueError(f"不支持的配置格式: {suffix}")


def load_config(path: str | None = None, overrides: dict | None = None) -> ProjectConfig:
    """加载工程配置，path 与 overrides 至少提供一个。

    - path: YAML/JSON 文件路径；
    - overrides: 直接传入的 dict，可覆盖文件中的字段。
    """

    data: dict = {}
    if path is not None:
        data.update(_load_dict_from_file(Path(path)))
    if overrides:
        data.update(overrides)

    if "sampling" not in data:
        raise ValueError("配置缺失 sampling 字段")
    sampling = SamplingConfig(
        sample_rate_hz=float(data["sampling"]["sample_rate_hz"]),
        center_freq_hz=float(data["sampling"]["center_freq_hz"]),
        fft_size=int(data["sampling"].get("fft_size", 4096)),
    )
    coarse_entries = data.get("coarse_bands")
    if coarse_entries:
        coarse_bands: List[BandConfig] = [_band_from_dict(entry) for entry in coarse_entries]
    else:
        coarse_bands = list(DEFAULT_COARSE_BANDS)

    centers = data.get("window_centers_mhz", DEFAULT_WINDOW_CENTERS_MHZ)
    if isinstance(centers, Iterable):
        centers_tuple = tuple(float(v) for v in centers)
    else:
        raise ValueError("window_centers_mhz 必须是可迭代对象")

    output_root = Path(data.get("output_root", "data"))
    cfg = ProjectConfig(
        sampling=sampling,
        coarse_bands=coarse_bands,
        window_centers_mhz=centers_tuple,
        output_root=output_root,
    )
    cfg.ensure_output_root()
    return cfg


def default_config() -> ProjectConfig:
    """提供便于单元测试与快速迭代的默认配置。"""

    return ProjectConfig(
        sampling=SamplingConfig(sample_rate_hz=200e6, center_freq_hz=0.0, fft_size=4096),
    )
