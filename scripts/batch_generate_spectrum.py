#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch Spectrum Generation Script

Purpose:
- Generate 50 independent jammer spectrum datasets
- Each set contains 10-20 random jammer signals
- Frequency range: 30-2500 MHz
- Center frequencies do not overlap within each simulation
- Output to output/01/ ~ output/50/ directories

Each output directory contains:
- composed_spectrum.npz (spectrum data)
- jammer_config.txt (configuration file)
- composed_spectrum.png (power spectrum plot)
"""
from __future__ import annotations


import json
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
    print("WARNING: matplotlib not installed, PNG generation will be skipped")

# Add project root directory to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.signal.spectrum_composer import (
    SpectrumComposerConfig,
    JammerSpec,
    compose_spectrum,
)

# ============================================================================
# Global Configuration Parameters
# ============================================================================
FREQ_MIN = 30.0  # MHz
FREQ_MAX = 2500.0  # MHz
RESOLUTION = 0.1  # MHz
NOISE_FLOOR = -120.0  # dB
SAMPLE_RATE = 125e6  # Hz
IQ_LENGTH = 32768
NUM_SIMULATIONS = 50
OUTPUT_BASE = "output"

# Jammer types and their typical bandwidths (for overlap prevention algorithm)
JAMMER_TYPES = [
    ("noise_fm", "FM Noise", 20.0),
    ("single_tone", "Single Tone", 0.1),
    ("multi_tone", "Multi Tone", 10.0),
    ("comb", "Comb", 50.0),
    ("partial_band_noise", "Partial Band Noise", 30.0),
    ("sweep", "Sweep", 40.0),
]


# ============================================================================
# Core Algorithm: Overlap Prevention Jammer Generation
# ============================================================================
def estimate_bandwidth(jam_type: str) -> float:
    """Estimate typical bandwidth of jammer signal (for overlap detection)"""
    bandwidth_map = {t[0]: t[2] for t in JAMMER_TYPES}
    return bandwidth_map.get(jam_type, 10.0)


def check_overlap(
    center: float, bandwidth: float, allocated: List[Tuple[float, float]]
) -> bool:
    """
    Check if frequency range overlaps with allocated ranges
    
    Args:
        center: Jammer center frequency (MHz)
        bandwidth: Jammer bandwidth (MHz)
        allocated: List of allocated frequency ranges [(min1, max1), (min2, max2), ...]
    
    Returns:
        True: overlap exists, False: no overlap
    """
    range_min = center - bandwidth / 2
    range_max = center + bandwidth / 2

    for alloc_min, alloc_max in allocated:
        # Overlap check: two ranges don't overlap if one is completely left or right of the other
        if not (range_max <= alloc_min or range_min >= alloc_max):
            return True  # overlap exists
    return False  # no overlap


def generate_random_jammers(
    num_jammers: int, rng: np.random.Generator
) -> List[JammerSpec]:
    """
    Generate random jammer configurations with overlap prevention
    
    Args:
        num_jammers: Target number of jammers
        rng: NumPy random number generator
    
    Returns:
        List of jammer specifications
    """
    jammers = []
    allocated_ranges = []

    max_attempts = 1000  # prevent infinite loop
    attempts = 0

    while len(jammers) < num_jammers and attempts < max_attempts:
        attempts += 1

        # Randomly select jammer type
        jam_type, desc, typical_bw = JAMMER_TYPES[rng.integers(0, len(JAMMER_TYPES))]

        # Randomly generate center frequency (leave margin to avoid edge effects)
        center_freq = rng.uniform(FREQ_MIN + 50, FREQ_MAX - 50)

        # Estimate bandwidth
        bandwidth = estimate_bandwidth(jam_type)

        # Check if overlaps with existing jammers
        if not check_overlap(center_freq, bandwidth, allocated_ranges):
            # Randomly generate JNR (Jammer-to-Noise Ratio: 10-30 dB)
            jnr_db = rng.uniform(10.0, 30.0)

            # Create jammer specification
            jammers.append(
                JammerSpec(
                    jam_type=jam_type, center_freq_mhz=center_freq, jnr_db=jnr_db
                )
            )

            # Record allocated frequency range
            allocated_ranges.append(
                (center_freq - bandwidth / 2, center_freq + bandwidth / 2)
            )

    if len(jammers) < num_jammers:
        print(
            f"  WARNING: Only generated {len(jammers)}/{num_jammers} jammers (insufficient spectrum space)"
        )

    return jammers


# ============================================================================
# File Saving Functions
# ============================================================================
def save_spectrum_png(
    freq_mhz: np.ndarray, power_db: np.ndarray, output_path: Path, title: str = ""
):
    """Save spectrum plot as PNG format"""
    if plt is None:
        print(f"  SKIP PNG generation (matplotlib not installed)")
        return

    try:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(freq_mhz, power_db, linewidth=0.8, color="blue")
        ax.set_xlabel("Frequency (MHz)", fontsize=12)
        ax.set_ylabel("Power (dB)", fontsize=12)
        if title:
            ax.set_title(title, fontsize=14, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.set_xlim(freq_mhz.min(), freq_mhz.max())
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
    except Exception as e:
        print(f"  WARNING: PNG save failed: {e}")


def save_config_txt(config_data: dict, output_path: Path):
    """Save configuration as TXT format (human-readable)"""
    lines = []
    lines.append("=" * 80)
    lines.append("Jammer Spectrum Configuration File")
    lines.append("=" * 80)
    lines.append("")

    lines.append("[Spectrum Parameters]")
    lines.append(
        f"  Frequency Range: {config_data['freq_min_mhz']} - {config_data['freq_max_mhz']} MHz"
    )
    lines.append(f"  Frequency Resolution: {config_data['resolution_mhz']} MHz")
    lines.append(f"  Noise Floor: {config_data['noise_floor_db']} dB")
    lines.append(f"  Sample Rate: {config_data['sample_rate_hz']} Hz")
    lines.append(f"  IQ Length: {config_data['iq_length']}")
    lines.append(f"  Random Seed: {config_data['seed']}")
    lines.append("")

    lines.append("[Jammer Signal List]")
    lines.append(f"  Total: {len(config_data['jammers'])} jammers")
    lines.append("")

    for i, jammer in enumerate(config_data["jammers"], 1):
        jam_type_desc = next(
            (t[1] for t in JAMMER_TYPES if t[0] == jammer["type"]), jammer["type"]
        )
        lines.append(f"  [{i}] {jam_type_desc}")
        lines.append(f"      Type: {jammer['type']}")
        lines.append(f"      Center Frequency: {jammer['center_freq_mhz']:.2f} MHz")
        lines.append(f"      JNR (Jammer-to-Noise Ratio): {jammer['jnr_db']:.2f} dB")
        lines.append("")

    lines.append("=" * 80)

    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_readme_md(
    config_data: dict,
    freq_mhz: np.ndarray,
    power_db: np.ndarray,
    output_path: Path,
):
    """Save README.md documentation"""
    lines = []
    lines.append("# Jammer Spectrum Dataset Documentation")
    lines.append("")
    lines.append("## Data Overview")
    lines.append("")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append(
        f"| Frequency Range | {config_data['freq_min_mhz']} - {config_data['freq_max_mhz']} MHz |"
    )
    lines.append(f"| Frequency Resolution | {config_data['resolution_mhz']} MHz |")
    lines.append(f"| Number of Frequency Points | {freq_mhz.size} |")
    lines.append(f"| Noise Floor | {config_data['noise_floor_db']} dB |")
    lines.append(f"| Number of Jammers | {len(config_data['jammers'])} |")
    lines.append(f"| Random Seed | {config_data['seed']} |")
    lines.append("")

    lines.append("## Power Spectrum Statistics")
    lines.append("")
    lines.append(f"- **Minimum Power**: {power_db.min():.2f} dB")
    lines.append(f"- **Maximum Power**: {power_db.max():.2f} dB")
    lines.append(f"- **Mean Power**: {power_db.mean():.2f} dB")
    lines.append(f"- **Standard Deviation**: {power_db.std():.2f} dB")
    lines.append("")

    lines.append("## Jammer Signal Details")
    lines.append("")
    lines.append("| No. | Type | Center Freq (MHz) | JNR (dB) |")
    lines.append("|-----|------|-------------------|----------|")

    for i, jammer in enumerate(config_data["jammers"], 1):
        jam_type_desc = next(
            (t[1] for t in JAMMER_TYPES if t[0] == jammer["type"]), jammer["type"]
        )
        lines.append(
            f"| {i} | {jam_type_desc} | {jammer['center_freq_mhz']:.2f} | {jammer['jnr_db']:.2f} |"
        )

    lines.append("")
    lines.append("## File Descriptions")
    lines.append("")
    lines.append(
        "- `composed_spectrum.npz`: NumPy format spectrum data (freq_mhz, power_db)"
    )
    lines.append("- `jammer_config.txt`: Human-readable configuration file")
    lines.append("- `composed_spectrum.png`: Power spectrum visualization image")
    lines.append("- `README.md`: This documentation file")
    lines.append("")

    lines.append("## Usage Example")
    lines.append("")
    lines.append("```python")
    lines.append("import numpy as np")
    lines.append("")
    lines.append("# Load data")
    lines.append("data = np.load('composed_spectrum.npz')")
    lines.append("freq_mhz = data['freq_mhz']")
    lines.append("power_db = data['power_db']")
    lines.append("")
    lines.append("# Plot")
    lines.append("import matplotlib.pyplot as plt")
    lines.append("plt.plot(freq_mhz, power_db)")
    lines.append("plt.xlabel('Frequency (MHz)')")
    lines.append("plt.ylabel('Power (dB)')")
    lines.append("plt.show()")
    lines.append("```")

    output_path.write_text("\n".join(lines), encoding="utf-8")


# ============================================================================
# Single Simulation Generation
# ============================================================================
def generate_one_simulation(sim_id: int, seed: int):
    """
    Generate one simulation dataset
    
    Args:
        sim_id: Simulation number (1-50)
        seed: Random seed
    """
    print(f"\n{'='*80}")
    print(f"[Simulation {sim_id:02d}/50] seed={seed}")
    print(f"{'='*80}")

    # Create output directory
    output_dir = Path(OUTPUT_BASE) / f"{sim_id:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create random number generator
    rng = np.random.default_rng(seed)

    # Randomly determine number of jammers (20-50)
    num_jammers = rng.integers(20, 51)
    print(f"  -> Target jammers: {num_jammers}")

    # Generate random jammer configs (with overlap prevention)
    print(f"  -> Generating jammer configurations...")
    jammers = generate_random_jammers(num_jammers, rng)
    print(f"  OK Generated {len(jammers)} jammers")

    # Sort by center frequency (for readability)
    jammers = sorted(jammers, key=lambda j: j.center_freq_mhz)

    # Create configuration object
    cfg = SpectrumComposerConfig(
        freq_min_mhz=FREQ_MIN,
        freq_max_mhz=FREQ_MAX,
        resolution_mhz=RESOLUTION,
        noise_floor_db=NOISE_FLOOR,
        sample_rate_hz=SAMPLE_RATE,
        iq_length=IQ_LENGTH,
        jammers=jammers,
    )

    # Generate spectrum
    print(f"  -> Generating power spectrum...")
    freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
    print(f"  OK Generated: {freq_mhz.size} frequency points")

    # Save NPZ file
    npz_path = output_dir / "composed_spectrum.npz"
    np.savez(npz_path, freq_mhz=freq_mhz, power_db=power_db)
    print(f"  OK Saved NPZ: {npz_path}")

    # Prepare config data
    config_data = {
        "freq_min_mhz": FREQ_MIN,
        "freq_max_mhz": FREQ_MAX,
        "resolution_mhz": RESOLUTION,
        "noise_floor_db": NOISE_FLOOR,
        "sample_rate_hz": SAMPLE_RATE,
        "iq_length": IQ_LENGTH,
        "seed": seed,
        "jammers": [
            {
                "type": j.jam_type,
                "center_freq_mhz": j.center_freq_mhz,
                "jnr_db": j.jnr_db,
            }
            for j in jammers
        ],
    }

    # Save config TXT file
    txt_path = output_dir / "jammer_config.txt"
    save_config_txt(config_data, txt_path)
    print(f"  OK Saved TXT: {txt_path}")

    # Save spectrum PNG
    png_path = output_dir / "composed_spectrum.png"
    title = f"Simulation {sim_id:02d} - {len(jammers)} Jammers (seed={seed})"
    save_spectrum_png(freq_mhz, power_db, png_path, title=title)
    print(f"  OK Saved PNG: {png_path}")

    # README.md generation removed - not needed per user request

    print(f"  OK Simulation {sim_id:02d} completed")
    print(f"    - Frequency: {freq_mhz.min():.1f} - {freq_mhz.max():.1f} MHz")
    print(f"    - Power: {power_db.min():.1f} - {power_db.max():.1f} dB")


# ============================================================================
# Main Function: Batch Generation
# ============================================================================
def main():
    """Main function: Generate 50 simulation datasets"""
    print("\n" + "=" * 80)
    print("|" + " " * 78 + "|")
    print("|" + "  Batch Generation - Jammer Spectrum Dataset  ".center(76) + "|")
    print("|" + " " * 78 + "|")
    print("=" * 80)
    print(f"\nTask Configuration:")
    print(f"  - Simulations: {NUM_SIMULATIONS}")
    print(f"  - Jammers per simulation: 20-50 (random)")
    print(f"  - Frequency range: {FREQ_MIN} - {FREQ_MAX} MHz")
    print(f"  - Frequency resolution: {RESOLUTION} MHz")
    print(
        f"  - Output directory: {OUTPUT_BASE}/01/ ~ {OUTPUT_BASE}/{NUM_SIMULATIONS:02d}/"
    )
    print(f"  - Overlap prevention: Enabled")
    print(f"  - Jammer types: {len(JAMMER_TYPES)}")

    input("\nPress Enter to start generation...")

    # Batch generation
    success_count = 0
    for sim_id in range(1, NUM_SIMULATIONS + 1):
        seed = 1000 + sim_id  # Use different seeds to ensure diversity
        try:
            generate_one_simulation(sim_id, seed)
            success_count += 1
        except Exception as e:
            print(f"  FAILED Simulation {sim_id:02d}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("|" + " " * 78 + "|")
    print("|" + "  Generation Complete!  ".center(76) + "|")
    print("|" + " " * 78 + "|")
    print("=" * 80)
    print(f"\nGeneration Results:")
    print(f"  Success: {success_count}/{NUM_SIMULATIONS}")
    print(f"  Failed: {NUM_SIMULATIONS - success_count}/{NUM_SIMULATIONS}")
    print(f"\nAll data saved to: {OUTPUT_BASE}/ directory")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nUser interrupted, exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
