"""Simple import test without stdout manipulation"""

if __name__ == "__main__":
    import sys
    
    # Test compose module
    from src.pipeline.compose import compose_spectrum
    from src.pipeline.compose import generate_jammers
    
    # Test stitch module
    from src.pipeline.stitch import stitch_multi
    from src.pipeline.stitch import stitch_real_data
    
    # Test semantic module
    from src.pipeline.semantic import semantic_generate
    from src.pipeline.semantic import semantic_eval
    from src.pipeline.semantic import semantic_eval_v2
    
    # Test utils module
    from src.pipeline.utils import analyze_comb
    from src.pipeline.utils import simulate_iq
    
    # Write to file instead of stdout (avoid encoding issues)
    with open('import_test_result.txt', 'w', encoding='utf-8') as f:
        f.write('SUCCESS: All core modules imported successfully!\n')
        f.write(f'Python version: {sys.version}\n')
    
    sys.exit(0)
