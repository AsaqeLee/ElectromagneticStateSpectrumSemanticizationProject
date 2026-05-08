#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试脚本 - 生成2组数据验证功能
"""
import sys

# 导入同目录批量生成脚本的函数
from batch_generate_spectrum import generate_one_simulation

def quick_test():
    """快速测试：生成2组数据"""
    print("\n" + "=" * 80)
    print("Quick Test - Generating 2 datasets")
    print("=" * 80)
    
    try:
        # 生成第1组
        print("\n[Test 1/2]")
        generate_one_simulation(sim_id=1, seed=1001)
        
        # 生成第2组
        print("\n[Test 2/2]")
        generate_one_simulation(sim_id=2, seed=1002)
        
        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)
        print("\nGenerated files:")
        print("  - output/01/composed_spectrum.npz")
        print("  - output/01/composed_spectrum.png")
        print("  - output/01/jammer_config.txt")
        print("  - output/01/README.md")
        print("  - output/02/... (same structure)")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    quick_test()
