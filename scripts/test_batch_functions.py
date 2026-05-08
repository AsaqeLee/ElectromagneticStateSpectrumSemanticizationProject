#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick Test Script - Verify batch_generate_spectrum.py functionality
Tests: imports, jammer generation, overlap prevention
"""
import sys

try:
    # Test imports
    print("Testing imports...")
    from batch_generate_spectrum import (
        estimate_bandwidth,
        check_overlap,
        generate_random_jammers,
        JAMMER_TYPES,
        FREQ_MIN,
        FREQ_MAX
    )
    print("  OK Imports successful")
    
    # Test bandwidth estimation
    print("\nTesting bandwidth estimation...")
    for jam_type, desc, expected_bw in JAMMER_TYPES:
        bw = estimate_bandwidth(jam_type)
        assert bw == expected_bw, f"Bandwidth mismatch for {jam_type}"
        print(f"  OK {jam_type}: {bw} MHz")
    
    # Test overlap detection
    print("\nTesting overlap detection...")
    allocated = [(100.0, 150.0), (200.0, 250.0)]
    
    # Should NOT overlap
    assert not check_overlap(75.0, 20.0, allocated), "False positive: overlap detected when shouldn't"
    assert not check_overlap(175.0, 20.0, allocated), "False positive: overlap in gap"
    assert not check_overlap(275.0, 20.0, allocated), "False positive: overlap after range"
    print("  OK No overlap cases passed")
    
    # Should overlap
    assert check_overlap(125.0, 20.0, allocated), "False negative: overlap not detected"
    assert check_overlap(95.0, 20.0, allocated), "False negative: edge overlap not detected"
    assert check_overlap(225.0, 60.0, allocated), "False negative: large bandwidth overlap"
    print("  OK Overlap cases passed")
    
    # Test jammer generation
    print("\nTesting jammer generation...")
    import numpy as np
    rng = np.random.default_rng(42)
    jammers = generate_random_jammers(5, rng)
    assert len(jammers) > 0, "No jammers generated"
    assert len(jammers) <= 5, "Too many jammers generated"
    print(f"  OK Generated {len(jammers)} jammers")
    
    # Verify no overlaps
    allocated_ranges = []
    for jammer in jammers:
        bw = estimate_bandwidth(jammer.jam_type)
        new_range = (jammer.center_freq_mhz - bw/2, jammer.center_freq_mhz + bw/2)
        for existing_range in allocated_ranges:
            assert not check_overlap(jammer.center_freq_mhz, bw, [existing_range]), \
                f"Overlap detected: {jammer.center_freq_mhz} overlaps with {existing_range}"
        allocated_ranges.append(new_range)
        print(f"    - {jammer.jam_type}: {jammer.center_freq_mhz:.2f} MHz (JNR: {jammer.jnr_db:.1f} dB)")
    print("  OK No overlaps verified")
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED - Script is ready to use!")
    print("="*60)
    
except ImportError as e:
    print(f"ERROR: Import failed - {e}")
    sys.exit(1)
except AssertionError as e:
    print(f"ERROR: Test failed - {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Unexpected error - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
