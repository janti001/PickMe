# PickMe-EM 🎯

![PickMe logo](https://github.com/janti001/PickMe/blob/main/assets/pickme_logo2.png)

A tool to incorporate into membrane segmentation-based workflows. Typical workflows involving membranes involve:

1. Membrane segmentation
2. Oversample the segmentation of desired objects to get particle picks
3. Clean up particle picks
4. Assign angles to particle picks
5. Export particles
6. Additional processing to push resolution

This tool looks to address the issue of parts 2 and 3 and provide some level of standardisation in this part of the workflow. At the moment individual groups write custom scripts to address the needs of the individuals analysing the data — this leads to high levels of redundancy.

This project looks to reduce that redundancy and aid in membrane oversampling, particle picking and other analysis and clean-up by being an open-source, easy-to-use and customisable tool.

## Disclaimer

I am very open to contributions to this project by anyone interested. For additional tools/functionalities that you feel should be contributed, or want to contribute yourself, feel free to contact me (see `pyproject.toml` for contact info, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to get started).

### Additional disclaimer

This is intended as a CLI tool. However, there are some useful functions in this package which you could import and use in your own scripts.

---

## What PickMe does

PickMe takes a membrane segmentation (for example from MemBrain-seg) and turns it into particle picks with Euler angles already assigned. It removes small, noisy objects with a volume-normalised knee filter, lets you click the membranes you want in napari, then oversamples each chosen membrane surface at a spacing you set and writes RELION-style STAR files.

```
 segmentations  +  tomograms (.mrc)
        |                 |
        v                 |
  filter_objects          |     drop noisy objects (knee filter)
        |                 |
        v                 v
  choose_objects  <-------+     click membranes in napari
        |
        v
 particle_extraction            sample surface, compute Euler angles
        |
        v
  particles.star  ->  Warp / M / RELION, Dynamo, ...
```

PickMe is meant to be a highly modular tool used in conjunction with other tools. Where it fits in a cryo-ET pipeline:

```
Collect tilt-series
  -> pre-process tilt-series
  -> get tomogram reconstructions
  -> run your favourite segmentation software
  -> PickMe
  -> your favourite downstream particle processing pipeline
     (Warp/M/RELION, Dynamo, IMOD, etc.)
```

**Example 1 — round-trip with MemBrain-seg.** Take a segmentation from MemBrain-seg, filter it and pick specific membranes with PickMe, then feed those individual membranes back to MemBrain-seg to re-train. `choose_objects --write-selections` exists for this: it writes each object as its own uncompressed `.mrc`.

**Example 2 — feeding a subtomogram averaging pipeline.** Oversample the membrane surface to generate particle picks with Euler angles already calculated, and hand the resulting STAR file to the Warp/M/RELION pipeline.

---

## Installation

[**Link to PyPI**](https://pypi.org/project/PickMe-EM/)

- OS-independent
- Requires Python >= 3.12, < 3.14

### Recommended: conda (PyQt6)

The repository ships a `PickMe.yml` conda environment file. It installs the napari/Qt6 stack from conda-forge, because installing Qt through pip tends to mix incompatible Qt libraries and break napari, which `choose_objects` needs.

```bash
git clone https://github.com/janti001/PickMe.git
cd PickMe
conda env create -f PickMe.yml
conda activate PickMe
PickMe -h
```

The environment is called **`PickMe`** — capital P, capital M. Conda environment names are case-sensitive on Linux, so `conda activate pickme` fails with `EnvironmentNameNotFound`.

The last step of `PickMe.yml` runs `pip install --no-deps -e .`, so creating the environment already installs PickMe in editable mode. `git pull` is enough to pick up new versions.

### Clusters that require Qt5: conda (PyQt5)

Some older HPC clusters can only provide Qt5. Use the PyQt5 environment instead:

```bash
conda env create -f PickMe-pyqt5.yml
conda activate PickMe-pyqt5
```

It is named `PickMe-pyqt5`, so it can live alongside the default environment, and it sets `QT_API=pyqt5` on activation so napari uses the Qt5 binding. Everything else is identical to `PickMe.yml`. Prefer the default PyQt6 environment everywhere else.

### Alternative: pip

```bash
conda create -n pickme-pip python=3.12
conda activate pickme-pip

pip install PickMe-EM                  # headless: filter_objects, particle_extraction,
                                       # decompress, convert. No napari, no Qt
pip install "PickMe-EM[gui]"           # adds napari + PyQt6 for choose_objects
pip install "PickMe-EM[gui-pyqt5]"     # adds napari + PyQt5 (old Linux/HPC only)
```

> **Warning:** install **one** Qt binding, never both. `[gui]` and `[gui-pyqt5]` are alternatives; installing both puts two competing bindings in one environment.

The GUI stack is an optional extra so that a headless cluster install does not pull in an OpenGL/Qt stack it can never use. If napari fails to launch from a pip install, use one of the conda routes or the container.

### Development install

```bash
git clone https://github.com/janti001/PickMe.git
cd PickMe
pip install -e ".[gui]"     # or use the conda route above
```

### More install help

- **[docs/gui-setup.md](docs/gui-setup.md)** — getting a napari window to open on WSL and HPC, what is pinned and why. Start here if the GUI will not open.
- **[container/README.md](container/README.md)** — Apptainer/Docker image that ships the whole stack. Note the image has not yet been built successfully (see [Known limitations](#known-limitations)).

---

## Quick start

A worked example on MemBrain-seg output. Your tomograms are in `/data/tomograms` (e.g. `TS_1166_10.00Apx.mrc`) and the segmentations in `/data/segmentations` (e.g. `TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc`).

```bash
mkdir my_pickme_project && cd my_pickme_project   # outputs land in ./outputs
conda activate PickMe

# 1. Drop noisy objects              -> outputs/filter/job001/
PickMe filter_objects --input-dir /data/segmentations

# 2. Click the membranes you want    -> outputs/choose/job002/
PickMe choose_objects --input-dir /data/tomograms

# 3. Sample the surface              -> outputs/particle_extraction/job003/
PickMe particle_extraction --sample-rate 5 --cmm
```

Each stage finds the previous one automatically (the latest filter job, then the latest choose job). Your particles are in `outputs/particle_extraction/job003/particles.star`.

At the prompts, files are chosen by index (see [File naming](#file-naming)); answering `n` to "specific files?" takes all of them.

---

## Job types

PickMe writes everything under an output root (default `./outputs`, relative to where you run it; `--output-dir` moves the **whole** root). Each run gets `<root>/<job_name>/jobNNN`, numbered from one counter shared by all job types (`filter/job003` is followed by `choose/job004`). `--input-job 1` and `--input-job 001` both mean `job001`. Full option tables are in **[docs/cli-reference.md](docs/cli-reference.md)**; the stage-by-stage walkthrough is in **[docs/pipeline.md](docs/pipeline.md)**.

### `filter_objects`

Finds every `*segment*` file in `--input-dir`, labels the objects, and keeps those past a volume-normalised knee, removing small noise.

- Key options: `--input-dir` (required), `--output-dir`, `--non-interactive`. (`--filter` is accepted but only one filter exists.)
- Outputs: `outputs/filter/jobNNN/<segmentation id>_filtered.mrc.gz` and a knee diagnostic plot `plots/<segmentation id>_knee.png`.

### `choose_objects`

Opens napari so you can pick membranes by clicking them, one tomogram at a time.

- Key options: `--input-dir` (tomograms, required), `--segmentation-dir`, `--input-job`, `--write-selections`, `--non-interactive`.
- Segmentations come from `--segmentation-dir`, else `--input-job`, else the latest filter job.
- In napari, a "PickMe objects" panel on the right has a tomogram dropdown with Previous/Next and a list of your selections. **Click an object to select it, click again to deselect.** Selected objects are green, unselected magenta. Dragging pans or rotates and never selects. It works in both 2D and 3D views. Selections are remembered as you switch tomograms. Close the window to write the result.
- Answering `n` to "Are there any objects which you would like to select (y/n)?" **cancels the job**: nothing is written.
- Outputs: `outputs/choose/jobNNN/<tomogram id>_chosen.mrc.gz` per tomogram; with `--write-selections`, `<tomogram id>_membranes/<tomogram id>_obj<label>.mrc` per object (uncompressed, voxels set to 1).

### `particle_extraction`

Gaussian-smooths each object, runs marching cubes, samples the surface at your spacing and computes Euler angles from the surface normals. Never prompts.

- Key options: `--sample-rate` (required, pixels), `--input-dir`, `--input-job`, `--cmm`, `--tomogram-dir`.
- Input: `--input-job`, else `--input-dir`, else the latest choose job.
- For segmentations **not** produced by PickMe, pass `--tomogram-dir` so each is paired to its tomogram by name; otherwise `rlnMicrographName` is derived from the segmentation name and PickMe warns you.
- Outputs in `outputs/particle_extraction/jobNNN/`: one `<name>.star` per input, an aggregate `particles.star`, `AnglePlots/<name>.png`, and `<name>.cmm` Chimera markers with `--cmm`. STAR columns include `rlnCoordinateX/Y/Z`, `rlnAngleRot/Tilt/Psi`, `rlnMicrographName`, `rlnObject` and `rlnImagePixelSize`.

### `decompress`

Converts `.mrc.gz` / `.mrc.bz2` to plain `.mrc` for viewing in Chimera/ChimeraX.

- Key options: `--input-dir` or `--input-job` (give one), `--non-interactive`.
- Output: `outputs/decompress/jobNNN/<id>_decompressed.mrc` (voxel size copied).

### `convert`

Casts tomograms to another data type for software that is fussy about it.

- Key options: `--input-dir` (file or directory, required), `--non-interactive`. `--data-type` is accepted but ignored; output is always float32.
- Output: `outputs/convert/jobNNN/<id>_f32.mrc` (voxel size copied from the input).

---

## File naming

PickMe does not assume any naming scheme such as `TS_<id>`.

- **Tomogram** = any `*.mrc`. **Segmentation** = any `.mrc`, `.mrc.gz` or `.mrc.bz2` whose name contains `segment`.
- A file's **id** is its name minus `.mrc` / `.mrc.gz` / `.mrc.bz2`: `TS_1166_10.00Apx.mrc` has id `TS_1166_10.00Apx`.
- **Pairing by prefix.** A segmentation belongs to the tomogram whose id is the *longest* prefix of its file name, ending at a separator (`_`, `.`, `-`). So `TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc` pairs with `TS_1166_10.00Apx.mrc`, and `lamella_B10_seg` pairs with `lamella_B10`, never `lamella_B1`.
- **Unmatched or ambiguous** segmentations trigger a prompt asking which tomogram each belongs to (blank skips it). Under `--non-interactive` they are skipped with a warning.
- **Selecting files by index.** Lists are numbered (`  1. name`); type `1 3 5-8`, `1,3` or `all`. You never type names. Bad input is explained and asked again.
- **`rlnMicrographName`** follows the Warp/M convention: the tomogram id with a trailing `_<number>Apx` removed, plus `.tomostar`. `TS_1166_10.00Apx` becomes `TS_1166.tomostar`; `lamella3_rec` becomes `lamella3_rec.tomostar`.
- **Duplicate outputs.** If two inputs would write the same name (`a.mrc` and `a.mrc.gz` in one folder) PickMe prints a warning and carries on; the one processed last overwrites the others.
- Outputs from older PickMe versions (e.g. `TS_1166_filtered.mrc.gz`) do not start with the full tomogram id, so they go to the manual pairing prompt. Re-run `filter_objects` to get new names.
- Arrays are handled in `zyx` order; STAR coordinates are written as `X`/`Y`/`Z`.

---

## Running on a cluster

Four subcommands prompt (`filter_objects`, `choose_objects`, `decompress`, `convert`); `particle_extraction` never does. Add `--non-interactive` to take the default answer to every prompt so a batch job does not hang:

```bash
PickMe filter_objects --input-dir /scratch/$USER/segmentations --non-interactive
```

`choose_objects` needs a display, so **under `--non-interactive` it cancels and writes nothing**. Run `choose_objects` interactively on a machine with a graphical session first, then run `particle_extraction` on the cluster. See [docs/gui-setup.md](docs/gui-setup.md) for how to split the pipeline around this.

---

## Documentation map

| File | What it covers |
|---|---|
| [docs/cli-reference.md](docs/cli-reference.md) | Every subcommand and option |
| [docs/pipeline.md](docs/pipeline.md) | Stage-by-stage walkthrough of the pipeline |
| [docs/gui-setup.md](docs/gui-setup.md) | Getting napari to open on WSL/HPC; Qt5 vs Qt6; pinned versions |
| [docs/known-issues.md](docs/known-issues.md) | Catalogue of bugs and their status |
| [container/README.md](container/README.md) | Building and running the Apptainer/Docker image |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

## Known limitations

- **`convert --data-type` is ignored.** Output is always float32.
- **`filter_objects --filter` is accepted but only one filter exists** (volume-normalised knee detection).
- **Euler angles are not reproducible.** `rlnAngleRot` is drawn from an unseeded random number generator, so angles differ from run to run. A `--seed` option is planned.
- **`choose_objects` needs a graphical session**, and cannot run under `--non-interactive`.
- **The container image has never been built successfully.** Treat `container/` as untested.

---

## Potential new features coming

**Different filter algorithms/types**
- Implement an Otsu-threshold based filter on log-transformed volumes
- ML/DL classifier using a feature set of the objects

**Particle coordinate manipulation**
- Adding a particle coordinate offset so transmembrane proteins can be picked

**Alternate file type outputs for particle coordinates**
- Potentially writing wrappers which can handle the conversion of STAR files to file types other software uses, such as `.motl`

---

## Contributing

Contributions of any size are welcome — bug reports, feature ideas, documentation fixes and code. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow.

## Licence

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
