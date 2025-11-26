#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze real IQ acquisition data."""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.io.reader import BinDataType, _load_bin, parse_bin_filename

# Load one real IQ file
bin_file = Path("data_segment/noise_130MHz_204.8MHz_11h11m11s.bin")

print("=" * 60)
print("Real IQ Data Analysis")
print("=" * 60)

# Parse filename
meta = parse_bin_filename(bin_file.name)
print(f"\nFile: {bin_file.name}")
print(f"  Center Freq:  {meta.get('center_freq_mhz', 0):.1f} MHz")
print(f"  Bandwidth:    {meta.get('bandwidth_mhz', 0):.1f} MHz")
print(f"  File Size:    {bin_file.stat().st_size / 1024**2:.1f} MB")

# Convert to Hz for loading
center_freq_hz = meta.get('center_freq_mhz', 130) * 1e6
sample_rate_hz = meta.get('bandwidth_mhz', 204.8) * 1e6

# Load IQ data
samples, meta_loaded = _load_bin(bin_file, dtype=BinDataType.INT16,
                                  sample_rate_hz=sample_rate_hz,
                                  center_freq_hz=center_freq_hz)

num_samples = len(samples)
duration_seconds = num_samples / sample_rate_hz

print(f"\nIQ Data:")
print(f"  Samples:      {num_samples:,}")
print(f"  Duration:     {duration_seconds:.3f} seconds")
print(f"  I range:      {samples.real.min():.3f} to {samples.real.max():.3f}")
print(f"  Q range:      {samples.imag.min():.3f} to {samples.imag.max():.3f}")
print(f"  Mean power:   {np.mean(np.abs(samples)**2):.6f}")

# Compute power spectrum (use first 32768 samples)
fft_size = 32768
iq_chunk = samples[:fft_size]

# Apply window
window = np.hanning(fft_size)
iq_windowed = iq_chunk * window

# FFT
fft_result = np.fft.fftshift(np.fft.fft(iq_windowed))
power = np.abs(fft_result) ** 2 / fft_size
power_db = 10.0 * np.log10(power + 1e-12)

# Frequency axis
freq_hz = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0/sample_rate_hz))
freq_mhz = (freq_hz + center_freq_hz) / 1e6

print(f"\nPower Spectrum:")
print(f"  Freq range:   {freq_mhz.min():.1f} to {freq_mhz.max():.1f} MHz")
print(f"  Power range:  {power_db.min():.1f} to {power_db.max():.1f} dB")
print(f"  Mean power:   {power_db.mean():.1f} dB")
print(f"  Median:       {np.median(power_db):.1f} dB")
print(f"  Std Dev:      {power_db.std():.1f} dB")

# Noise floor (10th percentile)
noise_floor = np.percentile(power_db, 10)
print(f"  Noise floor:  {noise_floor:.1f} dB (10th percentile)")

# Dynamic range
peak_power = power_db.max()
dynamic_range = peak_power - noise_floor
print(f"  Peak power:   {peak_power:.1f} dB")
print(f"  Dynamic range: {dynamic_range:.1f} dB")

# Analyze noise characteristics
noise_mask = power_db < (noise_floor + 3)
noise_samples = power_db[noise_mask]
print(f"\nNoise Characteristics (below noise_floor + 3dB):")
print(f"  Noise bins:   {len(noise_samples)} / {len(power_db)} ({100*len(noise_samples)/len(power_db):.1f}%)")
print(f"  Noise mean:   {noise_samples.mean():.2f} dB")
print(f"  Noise std:    {noise_samples.std():.2f} dB")

# Time domain analysis
print(f"\nTime Domain (first 1000 samples):")
i_vals = samples[:1000].real
q_vals = samples[:1000].imag
print(f"  I mean: {i_vals.mean():.6f}, std: {i_vals.std():.6f}")
print(f"  Q mean: {q_vals.mean():.6f}, std: {q_vals.std():.6f}")
print(f"  I/Q correlation: {np.corrcoef(i_vals, q_vals)[0,1]:.6f}")

# Plot
fig = plt.figure(figsize=(14, 10))

# Time domain I/Q
ax1 = plt.subplot(3, 2, 1)
t_ms = np.arange(1000) / (sample_rate_hz / 1000)
ax1.plot(t_ms, samples[:1000].real, 'b-', linewidth=0.5, label='I', alpha=0.7)
ax1.plot(t_ms, samples[:1000].imag, 'r-', linewidth=0.5, label='Q', alpha=0.7)
ax1.set_xlabel('Time (ms)')
ax1.set_ylabel('Amplitude')
ax1.set_title('Time Domain IQ')
ax1.legend()
ax1.grid(True, alpha=0.3)

# IQ constellation
ax2 = plt.subplot(3, 2, 2)
ax2.plot(samples[:10000].real, samples[:10000].imag,
         'b.', markersize=1, alpha=0.1)
ax2.set_xlabel('I')
ax2.set_ylabel('Q')
ax2.set_title('IQ Constellation (10k samples)')
ax2.grid(True, alpha=0.3)
ax2.axis('equal')

# Power spectrum
ax3 = plt.subplot(3, 2, 3)
ax3.plot(freq_mhz, power_db, linewidth=0.5, color='#00d4ff')
ax3.axhline(noise_floor, color='red', linestyle='--', linewidth=1,
            alpha=0.7, label=f'Noise Floor ({noise_floor:.1f} dB)')
ax3.set_xlabel('Frequency (MHz)')
ax3.set_ylabel('Power (dB)')
ax3.set_title('Power Spectrum (32k FFT)')
ax3.legend()
ax3.grid(True, alpha=0.3)

# Power histogram
ax4 = plt.subplot(3, 2, 4)
ax4.hist(power_db, bins=100, color='#4ecdc4', alpha=0.7, edgecolor='black')
ax4.axvline(noise_floor, color='red', linestyle='--', linewidth=2, label='Noise Floor')
ax4.axvline(power_db.mean(), color='green', linestyle='--', linewidth=2, label='Mean')
ax4.set_xlabel('Power (dB)')
ax4.set_ylabel('Count')
ax4.set_title('Power Distribution')
ax4.legend()
ax4.grid(True, alpha=0.3)

# Amplitude histogram
ax5 = plt.subplot(3, 2, 5)
amp = np.abs(samples[:100000])
ax5.hist(amp, bins=100, color='#ff6b6b', alpha=0.7, edgecolor='black')
ax5.set_xlabel('Amplitude')
ax5.set_ylabel('Count')
ax5.set_title('Amplitude Distribution')
ax5.grid(True, alpha=0.3)

# Spectrogram (first 0.1 seconds)
ax6 = plt.subplot(3, 2, 6)
nfft = 2048
noverlap = 1024
spec_samples = int(0.1 * sample_rate_hz)
spec_samples = min(spec_samples, len(samples))
Pxx, freqs, bins, im = ax6.specgram(
    samples[:spec_samples],
    NFFT=nfft,
    Fs=sample_rate_hz/1e6,
    noverlap=noverlap,
    cmap='viridis'
)
ax6.set_xlabel('Time (ms)')
ax6.set_ylabel('Frequency (MHz, relative)')
ax6.set_title('Spectrogram (first 0.1s)')
plt.colorbar(im, ax=ax6, label='Power (dB)')

fig.tight_layout()
plt.savefig('data/delivery/real_iq_analysis.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved to: data/delivery/real_iq_analysis.png")
