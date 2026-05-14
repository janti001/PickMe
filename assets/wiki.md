# PickMe-EM Wiki

**PickMe-EM** is an early-stage, open-source command-line tool for membrane and segmentation handling in cryo-electron tomography (cryo-ET). It bridges the gap between segmentation outputs and subtomogram averaging (STA) pipelines by automating particle picking from membranes, computing surface normals and Euler angles, and exporting RELION-compatible STAR files.

> ⚠️ **This project is in active early development.** APIs, CLI commands, and file formats may change between versions. Contributions and feedback are very welcome — see [Contributing](#contributing).

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [How It Fits Into a CryoET Pipeline](#how-it-fits-into-a-cryo-et-pipeline)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [CLI Reference](#cli-reference)
- [Napari Integration](#napari-integration)
- [Output Formats](#output-formats)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Citation](#citation)

---

## Overview

CryoET membrane particle picking is a technically demanding step: segmentation tools produce voxel masks, but STA pipelines like RELION need surface coordinates, orientations, and correctly formatted metadata. PickMe-EM handles that conversion layer.

It takes segmentation data (e.g. from MemBrain-seg or any binary mask), extracts surface points via marching cubes, computes surface normals, converts them to RELION ZYZ Euler angles, and writes particle STAR files ready for downstream processing.

A Napari integration provides visual QC so you can inspect picks and orientations directly on the tomogram before committing to a full STA run.

---

## Key Features

| Feature | Description |
|---|---|
| 🧫 **Membrane particle picking** | Extract surface coordinates from segmentation masks using marching cubes |
| 📐 **Normal vector → Euler angle conversion** | Compute ZYZ Euler angles (rot, tilt, psi) from surface normals in RELION convention |
| 📄 **STAR file export** | Write RELION-compatible particle STAR files ready for subtomogram averaging |
| 🔬 **Napari visualisation** | Inspect picks and orientations overlaid on tomogram data |
| 🖥️ **CLI interface** | Scriptable, pipeline-friendly command-line usage |

---

## How It Fits Into a CryoET Pipeline

```
Tomogram (.mrc)
      │
      ▼
Segmentation tool          e.g. MemBrain-seg → membrane mask (.mrc)
      │
      ▼
 PickMe-EM ◄─────────────────────────────────────────────────────┐
      │                                                           │
      ├── Surface extraction (marching cubes)                     │
      ├── Normal vector computation                               │  Visual QC
      ├── ZYZ Euler angle conversion (RELION convention)          │  via Napari
      └── STAR file export                                        │
      │                                                           │
      ▼                                                           │
particles.star ──────────────────────────────────────────────────┘
      │
      ▼
RELION / WarpTools subtomogram averaging
```

---

## Installation

### Option 1 — pip install (recommended)

```bash
pip install pickme-em
```

For the latest development version directly from GitHub:

```bash
pip install git+https://github.com/YOUR_ORG/pickme-em.git
```

### Option 2 — Clone and install manually

```bash
git clone https://github.com/YOUR_ORG/pickme-em.git
cd pickme-em
pip install -e .
```

The `-e` flag installs in editable mode, so any changes you make to the source are immediately reflected without reinstalling.

### Installing with dev dependencies

If you plan to contribute or run tests:

```bash
pip install -e ".[dev]"
```

### Requirements

- Python ≥ 3.10
- Napari (installed automatically as a dependency)
- See `pyproject.toml` or `PickMe.yml` for the full dependency list

> **Note:** It is strongly recommended to use a virtual environment or conda environment to avoid dependency conflicts with other cryo-ET tools.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pickme-em
```

---

## Quick Start

> 📝 The commands below are illustrative placeholders. Update with real command names as the CLI stabilises.

### 1. Pick particles from a membrane segmentation

```bash
pickme-em extract_objects \
  --input-dir membrane_mask.mrc \
```

### 2. Inspect picks in Napari

```bash
pickme-em choose_objects \
  --input-dir path/to/reconstructed/tomograms/which/segmentations/are/from/ \
  --input-job specify-job-number \
  --segmentation-dir path/to/other/segmentations/users/may/want/t/use/
```

### 3. Batch process a dataset

```bash
pickme-em particle_extraction \
  --input-dir /path/to/segmentations \
  --input-job job-number \
  --sample-rate pixel_number \
  --cmm
```

---

## Core Concepts

### Membrane segmentation input

PickMe-EM expects a **binary segmentation volume** in `.mrc` format where membrane voxels are labelled `1` and background is `0`. This is the standard output format of tools like [MemBrain-seg](https://github.com/CellArchLab/MemBrain-seg).

Before surface extraction, the segmentation is **Gaussian-smoothed** to avoid quantized axis-aligned normals that would otherwise arise from sharp binary boundaries. This is an important pre-processing step — without it, surface normals cluster artificially along the X, Y, and Z axes, producing a spherical artefact in the reconstruction.

### Surface extraction via marching cubes

PickMe-EM uses the **marching cubes** algorithm (`skimage.measure.marching_cubes`) to extract a triangle mesh from the segmentation volume. Particle coordinates are sampled from the mesh vertices.

### Surface normals and Euler angles

Each surface point has an associated **outward-facing normal vector** computed from the mesh geometry. These normals define the orientation of a particle sitting on the membrane surface.

PickMe-EM converts these normals into **RELION ZYZ Euler angles** (rot, tilt, psi):

| Angle | Meaning |
|---|---|
| `tilt` | Polar angle of the normal from the Z axis |
| `rot` | Azimuthal rotation around Z |
| `psi` | In-plane rotation (set to 0 by default for new picks) |

> **Convention note:** PickMe-EM follows the **inverted ZYZ convention** used by RELION, where the rotation matrix R is applied as R⁻¹ to go from particle frame to tomogram frame. Getting this wrong is a common source of spherical reconstruction artefacts.

### STAR file output

Output is written as a RELION-compatible `.star` file containing per-particle coordinates and Euler angles, ready to be used with `relion_subtomo` or passed to WarpTools `ts_export_particles`.

---

## CLI Reference

> 📝 Full command documentation will be added as the CLI stabilises. Run `pickme-em --help` or `pickme-em <command> --help` for up-to-date usage.

### Global options

```
pickme -h        Show all available commands
pip show PickMe-em     Show installed version
```

### `pickme-em particle_extraction`

Extract particles from a membrane segmentation.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | Input segmentation mask (.mrc) |
| `--input-job` | integer | job number that users may want to use insted of path |
| `--output` | path | Output STAR file path |
| `--sample-rate` | float | Target spacing between picks in pix (default: 5) |
| `--smooth-sigma` | float | Gaussian smoothing sigma before marching cubes (default: 3) | *NOT YET AN OPTION*
| `--cmm`   | bool | Whether user wants a cmm file written

### `pickme-em choose_objects`

Open a Napari viewer with particles overlaid on the tomogram.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | Tomogram to display (.mrc) |
| `--input-job` | integer | job number that users ma want to use instead of path |
| `--segmentation-dir` | path | Optional — use a segmentation that you may have that is not in the PickMe pipeline |
| `--output-dir`    | path | optional - desired output directory 

---

## Napari and ChimeraX Integration

PickMe-EM uses [Napari](https://napari.org) for visual quality control of particle picks and orientations.

### What you can inspect

- **Particle positions** overlaid as points on the tomogram volume [ChimeraX]
- **Orientation vectors** showing the computed surface normals at each pick [ChimeraX]
- **Segmentation mask** as a separate layer for context [Napari]

### Launching the viewer

```bash
pickme-em choose_objects  --input-dir tomo_001.mrc
```

Napari will open as an interactive GUI. You can:
- Toggle layers on/off
- Scroll through Z-slices
- Rotate and zoom the 3D view
- Visually assess whether normals are pointing in the correct direction

### Napari installation

Napari is installed automatically as a dependency of PickMe-EM. If you encounter display issues, refer to the [Napari installation guide](https://napari.org/stable/tutorials/fundamentals/installation.html) for platform-specific notes (particularly on headless Linux systems).

---

## Output Formats

### RELION STAR file

PickMe-EM outputs a RELION 3.1-compatible STAR file. Key columns:

| Column | Description |
|---|---|
| `rlnCoordinateX/Y/Z` | Particle position in tomogram voxels |
| `rlnAngleRot` | ZYZ Euler angle — rot (azimuthal) |
| `rlnAngleTilt` | ZYZ Euler angle — tilt (polar) |
| `rlnAnglePsi` | ZYZ Euler angle — psi (in-plane) |
| `rlnMicrographName` | Source tomogram name |

This file can be used directly with RELION's subtomogram averaging pipeline or passed to WarpTools `ts_export_particles`.

---

## Troubleshooting

### Templates not showing on GitHub

Ensure your issue templates are in `.github/ISSUE_TEMPLATE/` (uppercase, singular) on the default branch. See the [Issue Templates Guide](./GitHub-Issue-Templates-Guide) for the full checklist.

### Picks look uniform / spherical reconstruction artefact

This is almost always caused by one of:
- **Missing Gaussian smoothing** — binary masks produce quantized axis-aligned normals. Increase `--smooth-sigma`.
- **Inverted rotation convention** — check that the ZYZ rotation is applied in the RELION-expected sense (R⁻¹, not R).
- **Swapped rot/psi assignment** — `rot` encodes the azimuthal angle of the normal; `psi` should be 0 for fresh picks.

### Napari won't open on a headless server

Napari requires a display. On a headless Linux system, use a virtual display:

```bash
export DISPLAY=:0
Xvfb :0 -screen 0 1024x768x24 &
pickme-em view ...
```

Or use X forwarding over SSH: `ssh -X user@server`.

### Installation conflicts

Use a dedicated virtual environment. If you see conflicts with numpy or other scientific packages, try:

```bash
conda create -n pickme python=3.10
conda activate pickme
pip install pickme-em
```

---

## Contributing

Contributions of all kinds are welcome — bug reports, feature requests, documentation improvements, and code. PickMe-EM is a community-built research tool and every contribution counts.

Please read the [CONTRIBUTING.md](../blob/main/CONTRIBUTING.md) in the main repo before opening a PR.

**Good first areas to contribute:**
- Improving CLI help text and error messages
- Adding usage examples to this Wiki
- Testing on new datasets and reporting edge cases
- Improving Napari layer styling

---

## Roadmap

PickMe-EM is in early development. Planned directions include:

- [ ] Stable, documented CLI with full flag reference
- [ ] Support for multi-label segmentations (pick from specific membrane classes)
- [ ] Helical filament picking with symmetry expansion export
- [ ] WarpTools direct integration for coordinate export
- [ ] ChimeraX visualisation support
- [ ] Conda package
- [ ] Unit tests and CI

Have an idea not listed here? [Open a feature request](../../issues/new?template=feature_request.yml).

---

## Citation

If you use PickMe-EM in your research, please cite it. Citation details will be added here once a preprint or publication is available.

In the meantime, please mention the GitHub repository URL in your methods section.

---

*This wiki is a living document. If something is unclear or out of date, please open an issue or submit a PR to improve it.*
