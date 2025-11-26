#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交互式 CLI（实验/调试用）：统一入口运行任务一/二/三，并适配常见异常情况

用法（示例）::

    python -m src.pipeline.interactive_cli

功能说明：
- 任务一：在 30-2500 MHz 频段内，基于 jam.m 思想组合生成干扰功率谱；
- 任务二：从 200 MHz 频谱分段（int16 I/Q .bin 文件）拼接为宽带功率谱；
- 任务三：根据语义频域向量（JSON）恢复功率谱并对比参考谱。

本模块尽量复用现有 pipeline / signal / semantics 下的实现，仅提供：
- 菜单式交互输入；
- 针对路径不存在、格式错误、无数据等情况的中文错误提示。

注意：正式场景推荐使用仓库根目录下的 `spectrum_cli.py` /
`spectrum_batch.py` 作为官方 CLI 入口，本模块主要用于开发调试场景。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

import numpy as np

# Windows 控制台编码修复
if sys.platform == "win32":  # pragma: no cover - 仅在 Windows 下生效
    import io

    # 在某些非交互环境下 stdout/stderr 可能已经关闭，这里做保护性检查
    if hasattr(sys.stdout, "buffer") and not sys.stdout.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer") and not sys.stderr.closed:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:  # pragma: no cover - 作为模块导入时使用相对导入
    from ..signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
    from ..core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from ..core.schemas import IQData, SamplingConfig
    from ..signal.spectrum import compute_power_spectrum
    from ..signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from ..semantics.decode import decode_file
    from ..pipeline.semantic.semantic_eval import _load_reference, _build_semantic_axis, _validate_alignment
except ImportError:  # pragma: no cover - 直接 python 跑本文件时兜底
    from signal.spectrum_composer import SpectrumComposerConfig, add_jammer, compose_spectrum
    from core.config import DEFAULT_WINDOW_CENTERS_MHZ
    from core.schemas import IQData, SamplingConfig
    from signal.spectrum import compute_power_spectrum
    from signal.stitcher import SpectrumSegment, stitch_segments, StitchMode
    from semantics.decode import decode_file
    from pipeline.semantic.semantic_eval import _load_reference, _build_semantic_axis, _validate_alignment


# ===========================
# 通用交互辅助
# ===========================


def _input_with_default(prompt: str, default: str | None = None) -> str:
    """带默认值的输入函数。

    空输入时返回默认值；无默认值且空输入会反复提示。
    """

    while True:
        if default is None:
            raw = input(f"{prompt}: ").strip()
            if raw:
                return raw
            print("输入不能为空，请重试。")
        else:
            raw = input(f"{prompt} [默认: {default}]: ").strip()
            if not raw:
                return default
            return raw


def _ask_path(prompt: str, default: Path | None = None, must_exist: bool = True, is_dir: bool | None = None) -> Path:
    """询问路径，并根据需要检查是否存在/是否为目录。

    - must_exist=True 时，不存在会提示并重试；
    - is_dir=True/False 时，对类型进行检查。
    """

    default_str = str(default) if default is not None else None
    while True:
        raw = _input_with_default(prompt, default_str)
        path = Path(raw).expanduser()
        if must_exist:
            if not path.exists():
                print(f"路径不存在：{path}，请重试。")
                continue
            if is_dir is True and not path.is_dir():
                print(f"期待目录，但给出的路径不是目录：{path}")
                continue
            if is_dir is False and not path.is_file():
                print(f"期待文件，但给出的路径不是文件：{path}")
                continue
        return path


def _ask_float(prompt: str, default: float | None = None) -> float:
    """询问浮点数，带默认值与重试。"""

    default_str = f"{default}" if default is not None else None
    while True:
        raw = _input_with_default(prompt, default_str)
        try:
            return float(raw)
        except ValueError:
            print(f"无法解析为浮点数：{raw}，请重试。")


def _ask_int(prompt: str, default: int | None = None) -> int:
    """询问整数，带默认值与重试。"""

    default_str = f"{default}" if default is not None else None
    while True:
        raw = _input_with_default(prompt, default_str)
        try:
            return int(raw)
        except ValueError:
            print(f"无法解析为整数：{raw}，请重试。")


def _ensure_parent_dir(path: Path) -> None:
    """确保输出文件的父目录存在。"""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - 罕见文件系统错误
        raise RuntimeError(f"创建输出目录失败：{path.parent}，原因：{exc}") from exc


# ===========================
# 任务一：干扰功率谱生成（交互）
# ===========================


def _parse_jammer_spec_line(line: str) -> Tuple[str, float, float]:
    """解析一行 jammer 配置：格式为 TYPE:FREQ_MHZ:JNR_DB。"""

    parts = line.split(":")
    if len(parts) != 3:
        raise ValueError("格式应为 '类型:中心频率MHz:JNRdB'，例如 single_tone:500:20")
    jam_type = parts[0].strip()
    try:
        center_freq_mhz = float(parts[1])
        jnr_db = float(parts[2])
    except ValueError as exc:
        raise ValueError("中心频率和 JNR 必须是数字，例如 500:20") from exc
    return jam_type, center_freq_mhz, jnr_db


def run_task1_interactive() -> None:
    """任务一：交互式组合干扰功率谱。"""

    print("\n" + "=" * 80)
    print("任务一：30-2500 MHz 干扰功率谱合成")
    print("=" * 80)

    use_default = _input_with_default("是否使用默认示例配置? (y/n)", "y").lower()

    cfg = SpectrumComposerConfig(
        freq_min_mhz=30.0,
        freq_max_mhz=2500.0,
        resolution_mhz=1.0,
        noise_floor_db=-120.0,
        sample_rate_hz=125e6,
        iq_length=32768,
    )

    jammer_specs: List[Tuple[str, float, float]] = []
    if use_default.startswith("y"):
        # 使用 demo_all_tasks 中类似的默认配置
        jammer_specs = [
            ("single_tone", 500.0, 20.0),
            ("multi_tone", 1200.0, 18.0),
            ("sweep", 1800.0, 22.0),
            ("partial_band_noise", 800.0, 16.0),
        ]
    else:
        print("请输入干扰配置，每行一个，格式：类型:中心频率MHz:JNRdB")
        print("例如：single_tone:500:20")
        print("输入空行结束。")
        while True:
            line = input("jammer> ").strip()
            if not line:
                break
            try:
                spec = _parse_jammer_spec_line(line)
            except ValueError as exc:
                print(f"解析失败：{exc}")
                continue
            jammer_specs.append(spec)

    if not jammer_specs:
        print("未配置任何干扰源，任务一已取消。")
        return

    # 添加干扰
    for jam_type, center_freq_mhz, jnr_db in jammer_specs:
        if not (30.0 <= center_freq_mhz <= 2500.0):
            print(f"警告：中心频率 {center_freq_mhz} MHz 超出 [30, 2500] 范围，将仍然尝试生成。")
        try:
            add_jammer(cfg, jam_type, center_freq_mhz, jnr_db)
        except ValueError as exc:
            print(f"添加干扰失败：{exc}，已跳过该项。")

    if not cfg.jammers:
        print("所有干扰配置均无效，任务一已取消。")
        return

    output_npz = _ask_path("请输入输出 npz 路径", Path("data/interactive_task1.npz"), must_exist=False, is_dir=False)

    # 执行合成
    rng = np.random.default_rng(42)
    try:
        freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
    except Exception as exc:  # pragma: no cover - 算法内部异常
        print(f"生成干扰功率谱时出错：{exc}")
        return

    try:
        _ensure_parent_dir(output_npz)
        np.savez(output_npz, freq_mhz=freq_mhz, power_db=power_db)
    except Exception as exc:
        print(f"保存 npz 文件失败：{exc}")
        return

    print(f"任务一完成，频谱已保存到：{output_npz}")
    print(f"频率范围：{freq_mhz.min():.2f} - {freq_mhz.max():.2f} MHz，点数：{freq_mhz.size}")


# ===========================
# 任务二：200 MHz 频段拼接（交互）
# ===========================


def _load_int16_iq(path: Path) -> np.ndarray:
    """从 .bin 文件读取 int16 I/Q，返回 complex64 一维数组。"""

    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2 != 0:
        raw = raw[:-1]
    i = raw[0::2].astype(np.float64)
    q = raw[1::2].astype(np.float64)
    return i + 1j * q


def _build_global_axis(freq_list: List[np.ndarray]) -> Tuple[np.ndarray, float]:
    """根据多个频率轴构建全局频率轴（与 stitch_multi 一致）。"""

    if not freq_list:
        raise RuntimeError("没有可用的频率轴数据。")
    if any(arr.size < 2 for arr in freq_list):
        raise RuntimeError("存在频率轴长度小于 2 的片段，无法拼接。")
    step = float(freq_list[0][1] - freq_list[0][0])
    f_min = min(float(f[0]) for f in freq_list)
    f_max = max(float(f[-1]) for f in freq_list)
    axis = np.arange(f_min, f_max + step / 2.0, step, dtype=float)
    return axis, step


def run_task2_interactive() -> None:
    """任务二：交互式从 200MHz 片段拼接宽带频谱。

    这里采用简化版逻辑：
    - 要求目录下的文件数量与 DEFAULT_WINDOW_CENTERS_MHZ 相同；
    - 忽略文件名中的中心频率，用默认 13 个窗口中心；
    - 采样率由用户指定（默认 204.8e6 Hz）。
    """

    print("\n" + "=" * 80)
    print("任务二：200 MHz 频段拼接 30-2500 MHz 宽带频谱")
    print("=" * 80)

    input_dir = _ask_path("请输入包含 .bin 片段的目录", Path("data/test_segments"), must_exist=True, is_dir=True)
    pattern = _input_with_default("请输入文件通配符", "*.bin")
    fft_size = _ask_int("请输入 FFT 点数", 262144)
    sample_rate_hz = _ask_float("请输入采样率 (Hz)", 204.8e6)
    min_freq = _ask_float("请输入输出最小频率 MHz", 30.0)
    max_freq = _ask_float("请输入输出最大频率 MHz", 2500.0)
    output_npz = _ask_path("请输入输出 npz 路径", Path("data/interactive_task2.npz"), must_exist=False, is_dir=False)

    files = sorted(input_dir.glob(pattern))
    if not files:
        print(f"目录 {input_dir} 中未找到匹配 {pattern} 的文件。")
        return
    if len(files) != len(DEFAULT_WINDOW_CENTERS_MHZ):
        print(
            f"文件数量 {len(files)} 与预期的 13 个窗口不一致，请确认数据是否完整 "
            f"(DEFAULT_WINDOW_CENTERS_MHZ 长度为 {len(DEFAULT_WINDOW_CENTERS_MHZ)})。"
        )
        return

    segments_freq: List[np.ndarray] = []
    segments_power: List[np.ndarray] = []

    # 使用默认 13 个窗口中心，按排序后的文件顺序绑定
    for idx, path in enumerate(files):
        center_mhz = DEFAULT_WINDOW_CENTERS_MHZ[idx]
        center_hz = center_mhz * 1e6
        print(f"加载 {path.name}: 绑定中心频率 {center_mhz} MHz, 采样率 {sample_rate_hz/1e6:.1f} MHz")
        try:
            samples = _load_int16_iq(path)
        except Exception as exc:
            print(f"读取 {path} 失败：{exc}")
            return

        cfg = SamplingConfig(sample_rate_hz=sample_rate_hz, center_freq_hz=center_hz, fft_size=fft_size)
        try:
            iq = IQData(samples=samples, sample_rate_hz=cfg.sample_rate_hz, center_freq_hz=cfg.center_freq_hz)
            freq_mhz, power_db = compute_power_spectrum(iq, cfg)
        except Exception as exc:
            print(f"计算 {path} 的功率谱失败：{exc}")
            return
        segments_freq.append(freq_mhz)
        segments_power.append(power_db)

    # 构建全局频率轴并做 MAX 拼接（与 stitch_multi 主逻辑等价）
    try:
        global_axis, step = _build_global_axis(segments_freq)
    except Exception as exc:
        print(f"构建全局频率轴失败：{exc}")
        return

    global_power = np.full_like(global_axis, -180.0, dtype=float)
    for freq_mhz, power_db in zip(segments_freq, segments_power):
        idx = np.round((freq_mhz - global_axis[0]) / step).astype(int)
        valid = (idx >= 0) & (idx < global_power.size)
        idx_valid = idx[valid]
        seg = power_db[valid]
        current = global_power[idx_valid]
        global_power[idx_valid] = np.maximum(current, seg)

    mask = (global_axis >= min_freq) & (global_axis <= max_freq)
    if not np.any(mask):
        print("裁剪后的频率范围内没有任何数据，请检查 min/max 频率设置。")
        return
    freq_cropped = global_axis[mask]
    power_cropped = global_power[mask]

    try:
        _ensure_parent_dir(output_npz)
        np.savez(output_npz, freq_mhz=freq_cropped, power_db=power_cropped)
    except Exception as exc:
        print(f"保存拼接结果失败：{exc}")
        return

    print(f"任务二完成，拼接谱已保存到：{output_npz}")
    print(f"频率范围：{freq_cropped.min():.2f} - {freq_cropped.max():.2f} MHz，点数：{freq_cropped.size}")


# ===========================
# 任务三：语义向量恢复频谱（交互）
# ===========================


def run_task3_interactive() -> None:
    """任务三：交互式从语义 JSON 恢复功率谱，并评估相对参考谱。"""

    print("\n" + "=" * 80)
    print("任务三：语义频域向量恢复功率谱")
    print("=" * 80)

    reference_path = _ask_path("请输入参考频谱文件路径 (npy/npz)", Path("data/stitched_30_2500.npz"), must_exist=True, is_dir=False)
    semantic_path = _ask_path("请输入语义 JSON 文件路径", Path("data/demo_semantic.json"), must_exist=True, is_dir=False)
    output_report = _ask_path("请输入评估报告输出路径 (JSON)", Path("data/interactive_task3_report.json"), must_exist=False, is_dir=False)

    # 加载参考谱 & 语义参数
    try:
        freq_mhz, ref_power = _load_reference(reference_path)
    except Exception as exc:
        print(f"加载参考谱失败：{exc}")
        return

    try:
        params, recovered = decode_file(semantic_path)
    except Exception as exc:
        print(f"加载或解析语义 JSON 失败：{exc}")
        return

    freq_semantic = _build_semantic_axis(params)
    try:
        _validate_alignment(freq_mhz, freq_semantic)
    except SystemExit as exc:
        # semantic_eval 使用 SystemExit 报错，这里转换成友好提示
        print(f"参考谱与语义频点对齐校验失败：{exc}")
        return
    except Exception as exc:
        print(f"对齐校验时发生未知错误：{exc}")
        return

    if recovered.size != freq_semantic.size:
        print(
            f"恢复谱长度 {recovered.size} 与语义频点数量 {freq_semantic.size} 不一致，"
            "请检查 JSON 中的 fenbianlv/start/end/sinr 设置。"
        )
        return

    freq = freq_mhz
    ref = ref_power
    rec = recovered

    # 允许用户选择评估频段，可选
    band_min_raw = _input_with_default("是否限定评估最小频率 MHz(回车跳过)", "")
    band_max_raw = _input_with_default("是否限定评估最大频率 MHz(回车跳过)", "")
    band_min = None
    band_max = None
    try:
        if band_min_raw:
            band_min = float(band_min_raw)
        if band_max_raw:
            band_max = float(band_max_raw)
    except ValueError:
        print("评估频段输入无效，将使用全频段。")
        band_min = None
        band_max = None

    if band_min is not None or band_max is not None:
        mask = np.ones_like(freq, dtype=bool)
        if band_min is not None:
            mask &= freq >= band_min
        if band_max is not None:
            mask &= freq <= band_max
        if not np.any(mask):
            print("限定频段内没有任何数据，将使用全频段继续。")
        else:
            freq = freq[mask]
            ref = ref[mask]
            rec = rec[mask]

    diff = rec - ref
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    max_err = float(np.max(np.abs(diff)))

    report = {
        "yonghu": params.yonghu,
        "youwu": params.youwu,
        "mae_db": mae,
        "rmse_db": rmse,
        "max_err_db": max_err,
        "samples": int(freq.size),
        "band_min_mhz": band_min,
        "band_max_mhz": band_max,
        "semantic_freq_min_mhz": params.freq_min_mhz,
        "semantic_freq_max_mhz": params.freq_max_mhz,
        "semantic_resolution_mhz": params.resolution_mhz,
    }

    try:
        _ensure_parent_dir(output_report)
        output_report.write_text(
            __import__("json").dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"保存评估报告失败：{exc}")
        return

    print(f"任务三完成，评估报告已保存到：{output_report}")
    print(f"MAE={mae:.2f} dB, RMSE={rmse:.2f} dB, MAX={max_err:.2f} dB, 样本数={freq.size}")


# ===========================
# 顶层菜单
# ===========================

@dataclass
class MenuItem:
    key: str
    description: str
    handler: Callable[[], None]


def main() -> None:
    """交互式 CLI 主入口。"""

    menu: List[MenuItem] = [
        MenuItem(key="1", description="任务一：组合干扰功率谱 (30-2500 MHz)", handler=run_task1_interactive),
        MenuItem(key="2", description="任务二：从 200MHz 片段拼接宽带频谱", handler=run_task2_interactive),
        MenuItem(key="3", description="任务三：从语义 JSON 恢复并评估功率谱", handler=run_task3_interactive),
    ]

    print("\n" + "#" * 80)
    print("#" + "  电磁态频谱语义化 - 交互式 CLI 入口  ".center(78) + "#")
    print("#" * 80)

    while True:
        print("\n请选择要执行的任务：")
        for item in menu:
            print(f"  {item.key}) {item.description}")
        print("  q) 退出")

        choice = input("请输入选项: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("已退出。")
            break

        matched = [item for item in menu if item.key == choice]
        if not matched:
            print(f"无效选项：{choice}，请重试。")
            continue

        handler = matched[0].handler
        try:
            handler()
        except KeyboardInterrupt:
            print("\n操作被用户中断。")
        except Exception as exc:  # pragma: no cover - 顶层兜底
            print(f"执行任务过程中发生未预期错误：{exc}")


if __name__ == "__main__":
    main()
