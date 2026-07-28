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

### Option 1 — conda environment (recommended)

This matches how the project itself is developed and correctly pulls in the Qt/napari GUI stack via conda-forge:

```bash
conda env create -f PickMe.yml
conda activate pickme
```

The `PickMe.yml` environment file already installs the package in editable mode (`pip -e .`), so no separate `pip install` step is needed.

### Option 2 — pip install

```bash
pip install pickme-em
```

For the latest development version directly from GitHub:

```bash
pip install git+https://github.com/janti001/PickMe.git
```

### Option 3 — Clone and install manually

```bash
git clone https://github.com/janti001/PickMe.git
cd PickMe
pip install -e .
```

The `-e` flag installs in editable mode, so any changes you make to the source are immediately reflected without reinstalling.

> **Note:** There is currently no `[dev]` extras group in `pyproject.toml` — `pip install -e .` (or the conda environment above) already installs everything needed to run and modify PickMe.

### Requirements

- Python ≥ 3.12 (see `pyproject.toml`'s `requires-python` for the exact constraint)
- Napari (installed automatically as a dependency)
- See `pyproject.toml` or `PickMe.yml` for the full dependency list — no versions are pinned

> **Note:** It is strongly recommended to use a virtual environment or conda environment to avoid dependency conflicts with other cryo-ET tools.

---

## Quick Start

> 📝 The command names below are real subcommands (`PickMe <subcommand>`); the paths and job numbers are still illustrative placeholders — swap in your own.

### 1. Extract labeled objects from a membrane segmentation

```bash
PickMe extract_objects \
  --input-dir path/to/directory/containing/segmentation/files
```

### 2. Inspect picks in Napari

```bash
PickMe choose_objects \
  --input-dir path/to/reconstructed/tomograms/which/segmentations/are/from/ \
  --input-job specify-job-number \
  --segmentation-dir path/to/other/segmentations/users/may/want/to/use/
```

### 3. Batch process a dataset

```bash
PickMe particle_extraction \
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

PickMe-EM converts these normals into **RELION ZYZ Euler angles** (rot, tilt, psi), all reported in **degrees**:

| Angle | Meaning |
|---|---|
| `rot` | Not derived from the normal — a uniform random draw in `[0, 360)`, negated. There is no meaningful azimuthal reference around the membrane normal, so this angle is randomized rather than computed from the data |
| `tilt` | Polar angle between the particle's normal vector and the Z axis (`degrees(acos(nz))`) |
| `psi` | Azimuthal angle of the normal in the XY-plane (`-degrees(atan2(ny, nx))`), negated to match RELION's rotation sense — **not** fixed at 0 |

> **Convention note:** PickMe-EM follows the **inverted ZYZ convention** used by RELION, where the rotation matrix R is applied as R⁻¹ to go from particle frame to tomogram frame. Getting this wrong is a common source of spherical reconstruction artefacts.

### STAR file output

Output is written as a RELION-compatible `.star` file containing per-particle coordinates and Euler angles, ready to be used with `relion_subtomo` or passed to WarpTools `ts_export_particles`.

---

## CLI Reference

> 📝 Full command documentation will be added as the CLI stabilises. Run `PickMe --help` or `PickMe <command> --help` for up-to-date usage.

There are five subcommands: `extract_objects`, `choose_objects`, `particle_extraction`, `decompress`, and `convert`.

> **Job numbering is global, not per stage.** Every job directory (`outputs/<job_name>/jobNNN`) is numbered from a single counter shared across the *entire* output root — `check_make_dir` globs for all `job###` directories anywhere under the output root and picks `max(existing) + 1`. So if `filter` already holds `job001`–`job003`, the first `choose_objects` run produces `choose/job004`, not `choose/job001`.
>
> **Interactive prompts:** `extract_objects`, `choose_objects`, `convert`, and `decompress` all prompt interactively via `input()` at some point during the run. Only `particle_extraction` is safe to call in a non-interactive batch script.

### Global options

```
PickMe -h               Show all available commands
pip show PickMe-em      Show installed version
```

### `PickMe extract_objects`

Find `*segment*` files, extract labeled objects, filter them by volume knee detection, and write filtered results.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | **Required.** Directory containing segmentation files of interest |
| `--output-dir` | path | Optional — pipeline output root. Defaults to `./outputs` in the working directory |
| `--filter` | str | Optional — accepted but currently ignored. Volume-normalized knee detection always runs regardless of what you pass here |

Output is written to `outputs/filter/jobNNN/` (job name is `filter`, not `extract_objects`), as gzip-compressed `_filtered.mrc.gz` files — never bz2.

> ⚠️ This command prompts interactively via `input()` (through `utils.choose_tomograms`) to ask which tomograms to process. It is **not safe to run in a non-interactive batch script.**

### `PickMe choose_objects`

Optionally open a Napari viewer to manually select objects from a filtered segmentation.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | **Required.** Directory containing the reconstructed tomograms |
| `--segmentation-dir` | path | Optional — use a segmentation that you may have that is not in the PickMe pipeline |
| `--output-dir` | path | Optional — desired output directory |
| `--input-job` | integer | Optional — use a specific filter job number as input instead of the latest one, e.g. `4` selects `job004`. Remember job numbers are assigned from a single counter shared across all stages (see note above), so they are not sequential per stage |
| `--write-selections` | flag | Optional — write selected objects to their own `.mrc` files in a subdirectory per tomogram ID, instead of one combined file |

Output is written to `outputs/choose/jobNNN/` (job name is `choose`, not `choose_objects`).

> ⚠️ This command always prompts interactively via `input()` to ask which objects to keep. It is **not safe to run in a non-interactive batch script.**

### `PickMe particle_extraction`

Gaussian-smooth objects, run marching cubes, sample surface points, compute Euler angles, and write STAR files (and optionally a `.cmm` file).

| Flag | Type | Description |
|---|---|---|
| `--sample-rate` | integer | **Required.** Minimum enforced radius, in pixels/voxels (not Ångströms), between two neighboring picks — no default is set by the CLI |
| `--input-dir` | path | Optional — directory containing segmentation files to sample. If not provided, the latest `choose` job is used |
| `--input-job` | integer | Optional — a specific job number to use instead of the latest `choose` job. Provide the three-digit identifier, e.g. `001` |
| `--output-dir` | path | Optional — pipeline output root. Defaults to `./outputs` |
| `--cmm` | flag | Optional — also write particle coordinates and normals to a `.cmm` file |

This is the only subcommand that does **not** prompt via `input()` — it is safe to call in a non-interactive batch script.

### `PickMe decompress`

Decompress `.mrc.gz` or `.mrc.bz2` files into `.mrc`, useful for viewing in Chimera/ChimeraX.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | Directory containing the `.mrc.gz`/`.mrc.bz2` files. You must supply either this or `--input-job` |
| `--input-job` | integer | A job number from the PickMe pipeline to decompress instead of a path. You must supply either this or `--input-dir` |
| `--output-dir` | path | Optional — pipeline output root. Defaults to `./outputs` |

Supplying neither `--input-dir` nor `--input-job` raises a `RuntimeError`.

> ⚠️ This command always prompts interactively via `input()` to ask which tomograms to decompress. It is **not safe to run in a non-interactive batch script.**

### `PickMe convert`

Convert tomogram data types — useful if downstream software requires a specific type.

| Flag | Type | Description |
|---|---|---|
| `--input-dir` | path | **Required.** Directory containing the tomograms you wish to convert |
| `--output-dir` | path | Optional — pipeline output root. Defaults to `./outputs` |
| `--data-type` | str | Intended target numpy dtype (e.g. `float32`, `int16`) |

> ⚠️ **Known limitation:** `--data-type` is currently accepted but ignored — output is always cast to `numpy.float32` regardless of what you pass.
>
> ⚠️ This command also prompts interactively via `input()` (through `utils.choose_tomograms`) to ask which tomograms to process. It is **not safe to run in a non-interactive batch script.**

---

## Napari and ChimeraX Integration

PickMe-EM uses [Napari](https://napari.org) for visual quality control of particle picks and orientations.

### What you can inspect

- **Particle positions** overlaid as points on the tomogram volume [ChimeraX]
- **Orientation vectors** showing the computed surface normals at each pick [ChimeraX]
- **Segmentation mask** as a separate layer for context [Napari]

### Launching the viewer

```bash
PickMe choose_objects --input-dir path/to/tomogram/directory
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
| `rlnOriginX/Y/Z` | Always `0` |
| `rlnAngleRot` | ZYZ Euler angle — rot, in degrees (randomized — see [Core Concepts](#surface-normals-and-euler-angles)) |
| `rlnAngleTilt` | ZYZ Euler angle — tilt, in degrees (polar angle from the normal) |
| `rlnAnglePsi` | ZYZ Euler angle — psi, in degrees (azimuthal angle of the normal, not fixed at 0) |
| `rlnMicrographName` | Source tomogram name |
| `rlnObject` | Object label within the tomogram |
| `rlnNormalX/Y/Z` | Surface normal vector at the particle |
| `rlnImagePixelSize` | Pixel size in Ångströms, read from the MRC header |

This file can be used directly with RELION's subtomogram averaging pipeline or passed to WarpTools `ts_export_particles`.

---

## Troubleshooting

### Templates not showing on GitHub

Ensure your issue templates are in `.github/ISSUE_TEMPLATE/` (uppercase, singular) on the default branch. See the [Issue Templates Guide](./GitHub-Issue-Templates-Guide) for the full checklist.

### Picks look uniform / spherical reconstruction artefact

This is almost always caused by one of:
- **Missing Gaussian smoothing** — binary masks produce quantized axis-aligned normals. `particle_extraction` applies this automatically (sigma is currently hardcoded, not yet an exposed CLI flag) — if you are calling the underlying functions directly, make sure smoothing runs before marching cubes.
- **Inverted rotation convention** — check that the ZYZ rotation is applied in the RELION-expected sense (R⁻¹, not R).
- **Swapped rot/psi assignment** — `rot` encodes the azimuthal angle of the normal; `psi` should be 0 for fresh picks.

### Napari won't open on a headless server

Napari requires a display. On a headless Linux system, use a virtual display:

```bash
export DISPLAY=:0
Xvfb :0 -screen 0 1024x768x24 &
PickMe choose_objects ...
```

Or use X forwarding over SSH: `ssh -X user@server`.

### Installation conflicts

Use a dedicated virtual environment. If you see conflicts with numpy or other scientific packages, try:

```bash
conda create -n pickme python=3.12
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
