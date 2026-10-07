# Electromagnetic State Spectrum Semanticization

Python toolkit for electromagnetic spectrum analysis over roughly **30–2500 MHz**: jammer power-spectrum composition, segmented spectrum stitching, and semantic encoding / recovery for sensing workflows.

## Overview

The project implements an engineering stack around spectrum semantic representation and recovery. It is organized as a layered package under `src/electromagnetic_state/` with CLI scripts for interactive and batch use.

## Features / scope

### 1. Jammer power-spectrum composition

- Configurable frequency range (default 30–2500 MHz)
- Default 1.0 MHz resolution (2471 bins at the default span)
- Six jammer types: noise FM, single-tone, multi-tone, comb, partial-band noise, sweep
- Outputs: NPZ power spectra and optional PNG plots

### 2. Segmented spectrum stitching

- Thirteen 200 MHz windows (±100 MHz half-bandwidth)
- Window centers: 130, 330, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400 MHz
- Modes: MAX / MEAN / FIRST
- Inputs: IQ `.bin` (int16/float32) or NPZ spectra

### 3. Semantic parameter recovery

- v1: `SemanticParams` (single- or multi-region)
- v2: `SemanticEncodingV2` (standardized multi-region encoding)
- Documented typical in-band recovery error on the order of a few dB; validate on your data before citing figures

## Architecture

Four layers with one-way dependencies (CLI → pipeline → algorithms/IO → core types):

```text
src/electromagnetic_state/
├── core/            # Layer 0: data structures and config
├── io/              # Layer 1: readers/writers
├── signal/          # Layer 1: signal / spectrum algorithms
├── semantics/       # Layer 1: encode / decode
├── pipeline/        # Layer 2: workflows
├── visualization/   # plotting helpers
└── viz/             # lightweight plot utilities
scripts/             # Layer 3: CLI entry points
tests/
docs/
```

## Requirements

- Python 3.11+
- Dependencies in `requirements.txt` (NumPy stack and project packages)
- Optional: `requirements-dev.txt` for lint/test tooling

## Getting started

```bash
conda create -n electromagnetic-state python=3.11
conda activate electromagnetic-state
pip install -r requirements.txt
# optional
pip install -r requirements-dev.txt

pytest -q
```

### Interactive CLI

```bash
python scripts/spectrum_cli.py
```

### Batch CLI examples

```bash
python scripts/spectrum_batch.py compose \
  --jammer single_tone:500:25 \
  --jammer sweep:1500:20 \
  -o data/composed.npz \
  --plot data/composed.png

python scripts/spectrum_batch.py stitch \
  --input-dir data_segment \
  --pattern "*.bin" \
  --dtype int16 \
  --mode max \
  -o data/stitched.npz \
  --plot data/stitched.png

python scripts/spectrum_batch.py decode-v2 \
  --input data_semantic/semantic_case01.json \
  -o data/recovered.npz
```

### Library usage (sketch)

```python
from electromagnetic_state.signal.spectrum_composer import (
    SpectrumComposerConfig, add_jammer, compose_spectrum,
)
import numpy as np

cfg = SpectrumComposerConfig(
    freq_min_mhz=30.0,
    freq_max_mhz=2500.0,
    resolution_mhz=1.0,
    noise_floor_db=-100.0,
)
add_jammer(cfg, "single_tone", 500.0, 25.0)
add_jammer(cfg, "sweep", 1500.0, 20.0)
rng = np.random.default_rng(42)
freq_mhz, power_db = compose_spectrum(cfg, rng=rng)
np.savez("data/my_spectrum.npz", freq_mhz=freq_mhz, power_db=power_db)
```

Ensure `src/` is on `PYTHONPATH` or install the package via `pyproject.toml` as documented in `docs/`.

## Status / limitations

Research / coursework-oriented engineering code. Accuracy claims depend on configuration and input quality. Large IQ corpora are not necessarily shipped with the repository; prepare local data directories as needed. No LICENSE file is present in the repository root at the time of this README rewrite.
