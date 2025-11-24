#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze real spectrum data characteristics."""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

# Load real data
data = np.load('data/batch_test/test.npz')
freq = data['freq_mhz']
power = data['power_db']

print("=" * 60)
print("Real Spectrum Analysis")
print("=" * 60)

# Basic statistics
print(f"\nBasic Stats:")
print(f"  Mean:     {power.mean():.2f} dB")
print(f"  Median:   {np.median(power):.2f} dB")
print(f"  Std Dev:  {power.std():.2f} dB")
print(f"  Min:      {power.min():.2f} dB")
print(f"  Max:      {power.max():.2f} dB")

# Percentiles
print(f"\nPercentiles:")
for p in [10, 25, 50, 75, 90, 95, 99]:
    print(f"  {p:2d}%: {np.percentile(power, p):7.2f} dB")

# Noise floor estimation (10th percentile)
noise_floor = np.percentile(power, 10)
print(f"\nEstimated Noise Floor (10%): {noise_floor:.2f} dB")

# Signal regions (> noise + 6dB)
threshold = noise_floor + 6.0
signal_mask = power > threshold
signal_count = signal_mask.sum()
signal_percent = 100.0 * signal_count / len(power)

print(f"\nSignal Detection (threshold = {threshold:.1f} dB):")
print(f"  Signal bins: {signal_count} / {len(power)} ({signal_percent:.1f}%)")

# Find peak
peak_idx = np.argmax(power)
peak_freq = freq[peak_idx]
peak_power = power[peak_idx]
print(f"\nPeak Signal:")
print(f"  Frequency: {peak_freq:.1f} MHz")
print(f"  Power:     {peak_power:.2f} dB")
print(f"  SNR:       {peak_power - noise_floor:.2f} dB")

# Dynamic range
dynamic_range = peak_power - noise_floor
print(f"\nDynamic Range: {dynamic_range:.2f} dB")

# Frequency band characteristics
bands = [
    (30, 500, "VHF/Low"),
    (500, 1000, "UHF/Mid"),
    (1000, 1500, "L-band"),
    (1500, 2000, "S-band"),
    (2000, 2500, "High"),
]

print(f"\nBand Analysis:")
for start, end, name in bands:
    mask = (freq >= start) & (freq < end)
    band_power = power[mask]
    if len(band_power) > 0:
        print(f"  {name:12s} ({start:4.0f}-{end:4.0f} MHz): "
              f"mean={band_power.mean():.1f} dB, "
              f"std={band_power.std():.1f} dB, "
              f"max={band_power.max():.1f} dB")

# Plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))

# Spectrum
ax1.plot(freq, power, linewidth=0.5, color='#00d4ff')
ax1.axhline(noise_floor, color='red', linestyle='--', linewidth=1, alpha=0.7, label=f'Noise Floor (~{noise_floor:.1f} dB)')
ax1.axhline(threshold, color='orange', linestyle='--', linewidth=1, alpha=0.7, label=f'Threshold ({threshold:.1f} dB)')
ax1.set_xlabel('Frequency (MHz)')
ax1.set_ylabel('Power (dB)')
ax1.set_title('Real Spectrum Data')
ax1.grid(True, alpha=0.3)
ax1.legend()

# Histogram
ax2.hist(power, bins=100, color='#4ecdc4', alpha=0.7, edgecolor='black')
ax2.axvline(noise_floor, color='red', linestyle='--', linewidth=2, label='Noise Floor')
ax2.axvline(power.mean(), color='green', linestyle='--', linewidth=2, label='Mean')
ax2.set_xlabel('Power (dB)')
ax2.set_ylabel('Count')
ax2.set_title('Power Distribution')
ax2.legend()
ax2.grid(True, alpha=0.3)

fig.tight_layout()
plt.savefig('data/delivery/real_spectrum_analysis.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved to: data/delivery/real_spectrum_analysis.png")
