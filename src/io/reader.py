"""IQ 数据读取与切分工具。"""
from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable, Tuple

import h5py
import numpy as np

from ..core.schemas import IQData

SUPPORTED_EXTS = {".npy", ".npz", ".h5", ".hdf5"}


def _load_npy(path: Path) -> Tuple[np.ndarray, dict]:
    samples = np.load(path)
    return samples, {}


def _load_npz(path: Path) -> Tuple[np.ndarray, dict]:
    with np.load(path) as data:
        if "iq" not in data:
            raise ValueError("npz 文件需包含键 `iq`")
        samples = data["iq"]
        meta = {k: data[k].item() if data[k].size == 1 else data[k] for k in data.files if k != "iq"}
    return samples, meta


def _load_h5(path: Path) -> Tuple[np.ndarray, dict]:
    with h5py.File(path, "r") as h5:
        if "iq" not in h5:
            raise ValueError("HDF5 文件需包含数据集 `iq`")
        samples = h5["iq"][()]
        meta = {k: v[()] for k, v in h5.items() if k != "iq"}
    return samples, meta


def load_iq_file(path: str | Path, sample_rate_hz: float | None = None, center_freq_hz: float | None = None) -> IQData:
    """读取 IQ 文件，补全必要的元数据。

    - 支持 `.npy/.npz/.h5`，其中 `.npz/.h5` 可携带 `sample_rate_hz` / `center_freq_hz` 键；
    - 若文件中缺失这些字段，则必须通过参数显式传入。
    """

    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTS:
        raise ValueError(f"不支持的文件格式: {path.suffix}")

    if path.suffix.lower() == ".npy":
        samples, meta = _load_npy(path)
    elif path.suffix.lower() == ".npz":
        samples, meta = _load_npz(path)
    else:
        samples, meta = _load_h5(path)

    sr = sample_rate_hz or meta.get("sample_rate_hz")
    cf = center_freq_hz or meta.get("center_freq_hz", 0.0)
    if sr is None:
        raise ValueError("样本缺失 sample_rate_hz，请在参数中提供")
    return IQData(samples=np.asarray(samples, dtype=np.complex128), sample_rate_hz=float(sr), center_freq_hz=float(cf), meta=meta)


def chunk_iq(iq: IQData, chunk_size: int) -> Generator[IQData, None, None]:
    """将 IQ 切分为固定长度片段，供任务 2 拼接使用。"""

    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正")
    num_samples = iq.num_samples
    for start in range(0, num_samples, chunk_size):
        end = min(start + chunk_size, num_samples)
        chunk = IQData(
            samples=iq.samples[start:end],
            sample_rate_hz=iq.sample_rate_hz,
            center_freq_hz=iq.center_freq_hz,
            meta={**iq.meta, "offset": start},
        )
        yield chunk
