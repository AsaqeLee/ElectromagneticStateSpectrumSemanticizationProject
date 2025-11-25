"""Test new import paths"""
import sys
import io

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

print(f"Python version: {sys.version}")
print("Testing imports...")

try:
    # 测试 compose 模块
    from src.pipeline.compose import compose_spectrum
    print("✅ compose.compose_spectrum")
    
    from src.pipeline.compose import generate_jammers
    print("✅ compose.generate_jammers")
    
    # 测试 stitch 模块
    from src.pipeline.stitch import stitch_multi
    print("✅ stitch.stitch_multi")
    
    from src.pipeline.stitch import stitch_real_data
    print("✅ stitch.stitch_real_data")
    
    # 测试 semantic 模块
    from src.pipeline.semantic import semantic_generate
    print("✅ semantic.semantic_generate")
    
    from src.pipeline.semantic import semantic_eval
    print("✅ semantic.semantic_eval")
    
    from src.pipeline.semantic import semantic_eval_v2
    print("✅ semantic.semantic_eval_v2")
    
    # 测试 utils 模块
    from src.pipeline.utils import analyze_comb
    print("✅ utils.analyze_comb")
    
    from src.pipeline.utils import simulate_iq
    print("✅ utils.simulate_iq")
    
    print("\n[SUCCESS] All core modules imported successfully!")
    
except Exception as e:
    print(f"\n[ERROR] Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
