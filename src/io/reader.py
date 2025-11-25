"""IQ 数据读取与切分工具。

支持多种IQ数据格式：
- .npy: NumPy数组
- .npz: NumPy压缩包（需包含'iq'键）
- .h5/.hdf5: HDF5文件（需包含'iq'数据集）
- .bin: 二进制文件（支持多种数据类型）

.bin文件支持的数据格式：
- int16: 交织格式 [I0, Q0, I1, Q1, ...]
- int8: 交织格式
- float32: 交织格式
- complex64: 连续复数格式
- complex128: 连续复数格式
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Generator, Tuple

import h5py
import numpy as np

from ..core.schemas import IQData

SUPPORTED_EXTS = {".npy", ".npz", ".h5", ".hdf5", ".bin"}


class BinDataType(str, Enum):
    """二进制文件数据类型"""
    INT16 = "int16"  # 交织 I/Q int16
    INT8 = "int8"    # 交织 I/Q int8
    FLOAT32 = "float32"  # 交织 I/Q float32
    COMPLEX64 = "complex64"  # 复数 float32
    COMPLEX128 = "complex128"  # 复数 float64


def parse_bin_filename(filename: str, strict: bool = False) -> dict:
    """从文件名解析元数据。

    支持格式: {type}_{center_freq}MHz_{bandwidth}MHz_{timestamp}.bin
    例如: single_130MHz_204.8MHz_11h14m22s.bin

    返回:
    - jam_type: 干扰类型
    - center_freq_mhz: 中心频率 MHz
    - bandwidth_mhz: 带宽 MHz

    参数:
    - strict: 为 True 时，解析失败将抛出 ValueError；为 False 时返回空 dict。
    """
    # 匹配模式: type_freqMHz_bwMHz_timestamp.bin
    pattern = r"^(\w+)_(\d+(?:\.\d+)?)MHz_(\d+(?:\.\d+)?)MHz_.*\.bin$"
    match = re.match(pattern, filename)

    if not match:
        if strict:
            raise ValueError(f"无法从文件名解析元数据（strict 模式）：{filename}")
        return {}

    return {
        "jam_type": match.group(1),
        "center_freq_mhz": float(match.group(2)),
        "bandwidth_mhz": float(match.group(3)),
    }


def _load_bin(
    path: Path,
    dtype: BinDataType = BinDataType.INT16,
    sample_rate_hz: float | None = None,
    center_freq_hz: float | None = None,
) -> Tuple[np.ndarray, dict]:
    """加载二进制IQ文件，并对常见错误场景做健壮性处理。

    参数:
    - path: 文件路径
    - dtype: 数据类型
    - sample_rate_hz: 采样率（如果为 None，尝试从文件名推断）
    - center_freq_hz: 中心频率（如果为 None，尝试从文件名推断）

    返回:
    - samples: 复数IQ数组
    - meta: 元数据字典
    """
    # 1. 基本文件检查
    if not path.exists():
        raise FileNotFoundError(f"二进制 IQ 文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"路径不是普通文件: {path}")

    file_size = path.stat().st_size
    if file_size == 0:
        raise ValueError(f"二进制 IQ 文件为空: {path}")

    # 2. 从文件名解析元数据（宽松模式，失败时返回空 dict）
    meta = parse_bin_filename(path.name, strict=False)

    # 3. 读取二进制数据并转换为复数 IQ
    try:
        if dtype == BinDataType.INT16:
            raw = np.fromfile(path, dtype=np.int16)
            if raw.size % 2 != 0:
                raise ValueError(f"INT16 IQ 数据长度必须为偶数，当前 {raw.size}，文件: {path}")
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
            samples = samples / 32768.0  # 归一化到 [-1, 1]

        elif dtype == BinDataType.INT8:
            raw = np.fromfile(path, dtype=np.int8)
            if raw.size % 2 != 0:
                raise ValueError(f"INT8 IQ 数据长度必须为偶数，当前 {raw.size}，文件: {path}")
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)
            samples = samples / 128.0

        elif dtype == BinDataType.FLOAT32:
            raw = np.fromfile(path, dtype=np.float32)
            if raw.size % 2 != 0:
                raise ValueError(
                    f"FLOAT32 IQ 数据长度必须为偶数（实部/虚部交织），当前 {raw.size}，文件: {path}"
                )
            samples = raw[0::2].astype(np.float64) + 1j * raw[1::2].astype(np.float64)

        elif dtype == BinDataType.COMPLEX64:
            samples = np.fromfile(path, dtype=np.complex64).astype(np.complex128)

        elif dtype == BinDataType.COMPLEX128:
            samples = np.fromfile(path, dtype=np.complex128)

        else:
            raise ValueError(f"不支持的数据类型: {dtype}")

    except (IOError, OSError) as e:
        # 显式包装底层 IO 异常，便于调用方区分
        raise IOError(f"读取二进制 IQ 文件失败 {path}: {e}") from e

    # 4. 从文件名推断采样率和中心频率
    if "bandwidth_mhz" in meta:
        meta["sample_rate_hz"] = meta["bandwidth_mhz"] * 1e6
    if "center_freq_mhz" in meta:
        meta["center_freq_hz"] = meta["center_freq_mhz"] * 1e6

    # 5. 覆盖用户指定的参数
    if sample_rate_hz is not None:
        meta["sample_rate_hz"] = sample_rate_hz
    if center_freq_hz is not None:
        meta["center_freq_hz"] = center_freq_hz

    return samples, meta


def _load_npy(path: Path) -> Tuple[np.ndarray, dict]:
    """加载简单的 .npy 数组，不携带额外元数据。"""

    samples = np.load(path)
    return samples, {}


def _load_npz(path: Path) -> Tuple[np.ndarray, dict]:
    """加载 .npz 文件，将除 `iq` 以外的键都视为元数据返回。

    对元数据数组的处理策略：
    - size == 0: 原样返回空数组；
    - size == 1: 尝试 .item() 提取标量，失败则保留为数组；
    - size > 1: 保留为 numpy 数组，避免误用 .item() 触发异常。
    """
    try:
        with np.load(path) as data:
            if "iq" not in data:
                raise ValueError("npz 文件需包含键 `iq`")
            samples = data["iq"]

            meta: dict[str, object] = {}
            for k in data.files:
                if k == "iq":
                    continue
                v = data[k]
                if v.size == 0:
                    meta[k] = v
                elif v.size == 1:
                    try:
                        meta[k] = v.item()
                    except ValueError:
                        # 复数或结构化数组时，保持为数组
                        meta[k] = v
                else:
                    meta[k] = v

        return samples, meta
    except (IOError, OSError) as e:
        raise IOError(f"读取 npz 文件失败 {path}: {e}") from e


def _load_h5(path: Path) -> Tuple[np.ndarray, dict]:
    """加载 HDF5 文件，将除 `iq` 以外的顶层数据集视为元数据。"""
    with h5py.File(path, "r") as h5:
        if "iq" not in h5:
            raise ValueError("HDF5 文件需包含数据集 `iq`")
        samples = h5["iq"][()]
        meta = {k: v[()] for k, v in h5.items() if k != "iq"}
    return samples, meta


def load_iq_file(
    path: str | Path,
    sample_rate_hz: float | None = None,
    center_freq_hz: float | None = None,
    bin_dtype: BinDataType = BinDataType.INT16,
) -> IQData:
    """读取 IQ 文件，补全必要的元数据。

    支持格式:
    - `.npy/.npz/.h5`: 携带 `sample_rate_hz` / `center_freq_hz` 键
    - `.bin`: 从文件名解析元数据，或通过参数显式传入

    参数:
    - path: 文件路径
    - sample_rate_hz: 采样率 Hz（可选）
    - center_freq_hz: 中心频率 Hz（可选）
    - bin_dtype: .bin文件的数据类型（默认int16交织）

    返回:
    - IQData: 包含IQ样本和元数据的结构
    """

    path = Path(path)
    if path.suffix.lower() not in SUPPORTED_EXTS:
        raise ValueError(f"不支持的文件格式: {path.suffix}，支持: {SUPPORTED_EXTS}")

    if path.suffix.lower() == ".npy":
        samples, meta = _load_npy(path)
    elif path.suffix.lower() == ".npz":
        samples, meta = _load_npz(path)
    elif path.suffix.lower() == ".bin":
        samples, meta = _load_bin(path, bin_dtype, sample_rate_hz, center_freq_hz)
    else:  # .h5 / .hdf5
        samples, meta = _load_h5(path)

    sr = sample_rate_hz or meta.get("sample_rate_hz")
    cf = center_freq_hz or meta.get("center_freq_hz", 0.0)
    if sr is None:
        raise ValueError("样本缺失 sample_rate_hz，请在参数中提供或使用规范文件名")

    return IQData(
        samples=np.asarray(samples, dtype=np.complex128),
        sample_rate_hz=float(sr),
        center_freq_hz=float(cf),
        meta=meta,
    )


def load_bin_segments(
    directory: str | Path,
    pattern: str = "*.bin",
    bin_dtype: BinDataType = BinDataType.INT16,
) -> list[IQData]:
    """批量加载目录下的.bin文件。

    参数:
    - directory: 目录路径
    - pattern: 文件匹配模式
    - bin_dtype: 数据类型

    返回:
    - IQData列表，按中心频率排序
    """
    from glob import glob

    directory = Path(directory)
    files = sorted(directory.glob(pattern))

    if not files:
        raise FileNotFoundError(f"目录 {directory} 中未找到匹配 {pattern} 的文件")

    segments = []
    for f in files:
        try:
            iq = load_iq_file(f, bin_dtype=bin_dtype)
            segments.append(iq)
        except Exception as e:
            print(f"警告: 加载 {f} 失败: {e}")

    # 按中心频率排序
    segments.sort(key=lambda x: x.center_freq_hz)

    return segments


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
