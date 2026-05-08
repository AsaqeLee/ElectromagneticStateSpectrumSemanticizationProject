"""Test JSON and TXT format support for semantic parameter files."""

import json
from pathlib import Path
import sys
import numpy as np

SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

def _ensure_console_utf8() -> None:
    """Windows 控制台 UTF-8 兜底（避免 import 阶段修改全局 stdout/stderr）。"""
    if sys.platform != "win32":
        return

    def _try_reconfigure(stream) -> None:
        if stream is None:
            return
        if getattr(stream, "closed", False):
            return
        if not hasattr(stream, "reconfigure"):
            return
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            return

    _try_reconfigure(sys.stdout)
    _try_reconfigure(sys.stderr)

from electromagnetic_state.semantics.decode_v2 import (
    load_semantic_v2_file,
    decode_semantic_v2,
)
from electromagnetic_state.core.schemas import SemanticEncodingV2


def create_test_files():
    """创建测试用的 JSON 和 TXT 文件。"""
    
    # 确保目录存在
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # JSON 文件内容
    json_data = {
        "freq_min_mhz": 30.0,
        "freq_max_mhz": 2500.0,
        "num_bins": 2471,
        "noise_floor_db": -80.0,
        "jammer_regions": [
            {"start_bin": 100, "end_bin": 200, "jnr_db": 20.5},
            {"start_bin": 500, "end_bin": 600, "jnr_db": 15.3},
            {"start_bin": 1000, "end_bin": 1200, "jnr_db": 25.0},
        ]
    }
    
    # 创建 JSON 文件
    json_file = test_dir / "test_semantic.json"
    json_file.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # TXT 文件内容
    txt_content = """# 语义参数配置文件（测试用）
# 频率范围（MHz）
freq_min_mhz=30.0
freq_max_mhz=2500.0

# 频谱离散点数
num_bins=2471

# 底噪功率（dB）
noise_floor_db=-80.0

# 干扰区域列表
[jammer_regions]
100,200,20.5
500,600,15.3
1000,1200,25.0
"""
    
    # 创建 TXT 文件
    txt_file = test_dir / "test_semantic.txt"
    txt_file.write_text(txt_content, encoding='utf-8')
    
    return json_file, txt_file


def compare_params(params1: SemanticEncodingV2, params2: SemanticEncodingV2) -> bool:
    """比较两个语义参数是否相同。"""
    
    if params1.freq_min_mhz != params2.freq_min_mhz:
        print(f"freq_min_mhz 不同: {params1.freq_min_mhz} vs {params2.freq_min_mhz}")
        return False
    
    if params1.freq_max_mhz != params2.freq_max_mhz:
        print(f"freq_max_mhz 不同: {params1.freq_max_mhz} vs {params2.freq_max_mhz}")
        return False
    
    if params1.num_bins != params2.num_bins:
        print(f"num_bins 不同: {params1.num_bins} vs {params2.num_bins}")
        return False
    
    if params1.noise_floor_db != params2.noise_floor_db:
        print(f"noise_floor_db 不同: {params1.noise_floor_db} vs {params2.noise_floor_db}")
        return False
    
    if len(params1.jammer_regions) != len(params2.jammer_regions):
        print(f"干扰区域数量不同: {len(params1.jammer_regions)} vs {len(params2.jammer_regions)}")
        return False
    
    for i, (r1, r2) in enumerate(zip(params1.jammer_regions, params2.jammer_regions)):
        if r1.start_bin != r2.start_bin:
            print(f"区域 {i} start_bin 不同: {r1.start_bin} vs {r2.start_bin}")
            return False
        if r1.end_bin != r2.end_bin:
            print(f"区域 {i} end_bin 不同: {r1.end_bin} vs {r2.end_bin}")
            return False
        if r1.jnr_db != r2.jnr_db:
            print(f"区域 {i} jnr_db 不同: {r1.jnr_db} vs {r2.jnr_db}")
            return False
    
    return True


def compare_spectrums(spec1: np.ndarray, spec2: np.ndarray) -> bool:
    """比较两个频谱是否相同。"""
    
    if spec1.shape != spec2.shape:
        print(f"频谱形状不同: {spec1.shape} vs {spec2.shape}")
        return False
    
    if not np.allclose(spec1, spec2):
        diff = np.abs(spec1 - spec2)
        max_diff = np.max(diff)
        print(f"频谱数值不同，最大差异: {max_diff}")
        return False
    
    return True


def main():
    """主测试函数。"""
    
    print("=" * 60)
    print("语义参数格式支持测试")
    print("=" * 60)
    
    # 创建测试文件
    print("\n[1/4] 创建测试文件...")
    json_file, txt_file = create_test_files()
    print(f"  ✓ JSON 文件: {json_file}")
    print(f"  ✓ TXT 文件: {txt_file}")
    
    # 加载 JSON 格式
    print("\n[2/4] 加载 JSON 格式...")
    try:
        json_params = load_semantic_v2_file(json_file)
        print(f"  ✓ 成功加载 JSON 文件")
        print(f"    - 频率范围: {json_params.freq_min_mhz} - {json_params.freq_max_mhz} MHz")
        print(f"    - 频点数: {json_params.num_bins}")
        print(f"    - 底噪: {json_params.noise_floor_db} dB")
        print(f"    - 干扰区域数: {len(json_params.jammer_regions)}")
    except Exception as e:
        print(f"  ✗ 加载 JSON 失败: {e}")
        return False
    
    # 加载 TXT 格式
    print("\n[3/4] 加载 TXT 格式...")
    try:
        txt_params = load_semantic_v2_file(txt_file)
        print(f"  ✓ 成功加载 TXT 文件")
        print(f"    - 频率范围: {txt_params.freq_min_mhz} - {txt_params.freq_max_mhz} MHz")
        print(f"    - 频点数: {txt_params.num_bins}")
        print(f"    - 底噪: {txt_params.noise_floor_db} dB")
        print(f"    - 干扰区域数: {len(txt_params.jammer_regions)}")
    except Exception as e:
        print(f"  ✗ 加载 TXT 失败: {e}")
        return False
    
    # 比较参数
    print("\n[4/4] 比较两种格式加载的参数...")
    if compare_params(json_params, txt_params):
        print("  ✓ 参数完全一致")
    else:
        print("  ✗ 参数不一致")
        return False
    
    # 恢复频谱并比较
    print("\n[5/5] 恢复频谱并比较...")
    json_spectrum = decode_semantic_v2(json_params)
    txt_spectrum = decode_semantic_v2(txt_params)
    
    if compare_spectrums(json_spectrum, txt_spectrum):
        print("  ✓ 恢复的频谱完全一致")
        print(f"    - 频谱长度: {len(json_spectrum)}")
        print(f"    - 底噪值: {json_spectrum[0]:.2f} dB")
        print(f"    - 最大功率: {np.max(json_spectrum):.2f} dB")
    else:
        print("  ✗ 恢复的频谱不一致")
        return False
    
    # 测试通过
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    print("\n总结：")
    print("  - JSON 格式：加载成功 ✓")
    print("  - TXT 格式：加载成功 ✓")
    print("  - 参数一致性：通过 ✓")
    print("  - 频谱一致性：通过 ✓")
    print("\n两种格式完全等效，可以根据使用习惯选择！")
    
    return True


if __name__ == "__main__":
    _ensure_console_utf8()
    success = main()
    raise SystemExit(0 if success else 1)
