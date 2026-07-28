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

## Where PickMe fits in a cryo-ET pipeline

```
Collect tilt-series
  -> pre-process tilt-series
  -> get tomogram reconstructions
  -> run your favourite segmentation software
  -> PickMe
  -> your favourite downstream particle processing pipeline
     (Warp/M/RELION, Dynamo, IMOD, etc.)
```

PickMe is meant to be a highly modular tool used in conjunction with other tools at your disposal.

**Example 1 — round-trip with MemBrain-seg.** Take a segmentation from MemBrain-seg, filter it and pick specific membranes with PickMe, then feed those individual membranes back to MemBrain-seg to re-train. The `choose_objects --write-selections` flag exists exactly for this: it writes each object out as its own uncompressed `.mrc`, which is the format MemBrain-seg wants.

**Example 2 — feeding a subtomogram averaging pipeline.** PickMe can take a segmentation file, oversample the membrane surface to generate particle picks with Euler angles already calculated, and hand the resulting STAR file to the Warp/M/RELION pipeline.

This is where the power of PickMe comes from: being used in conjunction with other tools.

---

## Installation

[**Link to PyPI**](https://pypi.org/project/PickMe-EM/)

- OS-independent
- Requires Python >= 3.12

### Recommended: conda environment file

The repository ships a `PickMe.yml` conda environment file, and **this is the supported install route**. It deliberately installs the Qt/GUI stack (`pyqt6`, `qt6-main`, the `xcb-util*` libraries, `libxkbcommon`) through conda-forge, because installing those through pip tends to mix incompatible Qt libraries and break napari — which is the part of PickMe you need for `choose_objects`.

```bash
git clone https://github.com/janti001/PickMe.git
cd PickMe
conda env create -f PickMe.yml
conda activate pickme
```

The environment is called **`pickme`** (lowercase). The last step of `PickMe.yml` runs `pip install --no-deps -e .`, so **creating the environment already installs PickMe in editable mode** — you do *not* need to run `pip install -e .` separately.

Editable mode matters here: PickMe is being worked on regularly, so `git pull` is enough to pick up new features and bug fixes. You do not need to reinstall.

Check it worked:

```bash
PickMe -h
```

### Alternative: pip

If you would rather manage the environment yourself, PickMe-EM is on PyPI:

```bash
conda create -n pickme python=3.12
conda activate pickme
pip install PickMe-EM
```

Be aware that this route installs napari's Qt dependencies through pip, which is the setup that most often goes wrong. If napari fails to launch, use the conda route above.

### Dependencies

Runtime dependencies are: `numpy`, `pandas`, `matplotlib`, `starfile`, `mrcfile`, `napari`, `napari-skimage`, `scikit-image`, `seaborn`, `plotly`, `tqdm`, `scipy`.

Version requirements are deliberately not listed here so this file cannot go stale — `pyproject.toml` and `PickMe.yml` are the source of truth.

---

## Core concepts

### The command is `PickMe`

The console script installed by the package is `PickMe` (capital P, capital M). Every subcommand also has its own help:

```bash
PickMe -h
PickMe extract_objects -h
PickMe choose_objects -h
PickMe particle_extraction -h
PickMe decompress -h
PickMe convert -h
```

### Output roots and job directories

PickMe writes everything under an **output root**, which defaults to `./outputs` — created relative to *wherever you run the command from*. So it is worth making a project directory and running all your PickMe jobs from inside it:

```bash
mkdir my_pickme_project
cd my_pickme_project
```

`--output-dir` sets the output root for **the entire pipeline**, not just one result folder. If you pass it to one subcommand you generally want to pass the same value to all of them, otherwise later jobs will not find earlier ones.

Every job gets its own numbered directory:

```
<output_root>/<job_name>/jobNNN
```

`NNN` is zero-padded to three digits (`job001`, `job002`, …).

**The job directory name does not always match the subcommand name.** This trips people up, so here it is explicitly:

| Subcommand | Writes to |
|---|---|
| `extract_objects` | `outputs/filter/jobNNN` |
| `choose_objects` | `outputs/choose/jobNNN` |
| `particle_extraction` | `outputs/particle_extraction/jobNNN` |
| `decompress` | `outputs/decompress/jobNNN` |
| `convert` | `outputs/convert/jobNNN` |

Job numbers are allocated across the **whole output root**, not per job type. If `outputs/filter/job001` exists, the next job you run is `job002` whatever kind of job it is — it might land in `outputs/choose/job002`. That is why `--input-job` can find a job by number alone without you telling it which type of job it was.

### How jobs chain together

Most subcommands can work out their own input from previous jobs. The resolution order is worth knowing, because it is what makes the pipeline runnable with almost no arguments.

**`choose_objects`** picks its segmentation input by:

1. `--segmentation-dir` if given → uses `<dir>/*.mrc`
2. otherwise `--input-job N` → looks in `<output_root>/**/job<NNN>/*.mrc*`
3. otherwise the **latest** `outputs/filter/jobNNN`, taking files matching `*filtered*`

**`particle_extraction`** picks its input by:

1. `--input-job N` → `<output_root>/**/job<NNN>/**/*.mrc*`
2. otherwise, if no `--input-dir` was given and at least one `choose` job exists → the **latest** `outputs/choose/jobNNN`, taking files matching `*chosen*`
3. otherwise, if no `--input-dir` was given and no `choose` job exists → raises a `RuntimeError` telling you to run `choose_objects` first
4. otherwise `--input-dir` → `*.mrc`, `*.mrc.gz` and `*.mrc.bz2` in that directory

**`decompress`** picks its input by:

1. `--input-job N` → `<output_root>/**/job<NNN>/*.mrc*`
2. otherwise `<--input-dir>/*.mrc*`

`--input-job` takes a plain integer and zero-pads it for you: `--input-job 1` means `job001`.

### These commands ask you questions

Several subcommands prompt on stdin before they do anything. **None of these are safe to drop into a non-interactive batch script or a cluster submission** — they will hang waiting for input.

| Subcommand | Prompt |
|---|---|
| `extract_objects` | `Are there specific tomograms you want to process (y/n)?` — answer `y` to pick a subset by number ID |
| `choose_objects` | `Are there any objects which you would like to select (y/n)?` — see below |
| `decompress` | `Are there any specific tomograms you want to decompress? (y/n)` |
| `convert` | `Are there specific tomograms you want to process (y/n)?` (when given a directory) |

The `choose_objects` prompt deserves a note, because what happens next depends on both your answer and on `--write-selections`:

- **`y`** → opens napari so you can select objects by hand.
- **`n`** with `--write-selections` → skips napari and writes **every** filtered object out as its own file.
- **`n`** without `--write-selections` → does nothing to your files; it just tells you where they already are.

### File naming assumptions

- `extract_objects` looks for files whose name contains **`segment`** in `--input-dir`. If your segmentation software does not put that in the filename, rename the files or PickMe will find nothing.
- Tomogram IDs are parsed from filenames by splitting on underscores, in the style `TS_<id>_...`. `choose_objects` matches a tomogram to its segmentation using that ID, so the tomogram `.mrc` and the segmentation need to share it.
- Segmentation arrays are handled in `zyx` order; STAR coordinates are written as `X`/`Y`/`Z`.

---

## Usage

### 1. Extract and filter objects

First, filter the segmentations to remove suspected noise that has been segmented. PickMe identifies each labelled object with `regionprops` and applies a volume-normalised knee-detection filter.

```bash
PickMe extract_objects \
  --input-dir path/to/directory/containing/segmentations
```

| Flag | Required | Meaning |
|---|---|---|
| `--input-dir` | yes | Directory containing the segmentation files (filenames must contain `segment`) |
| `--output-dir` | no | Pipeline output root (default `./outputs`) |
| `--filter` | no | Filter method — see [Known limitations](#known-limitations) |

Writes gzipped `.mrc.gz` files containing the objects that passed the filter, plus knee-detection diagnostic plots showing how the threshold was chosen.

### 2. Choose objects

Second, you can visually choose objects using the wrapper built around napari.

```bash
PickMe choose_objects \
  --input-dir path/to/tomogram/reconstruction/mrc/files
```

| Flag | Required | Meaning |
|---|---|---|
| `--input-dir` | yes | Directory of the reconstructed tomograms (`.mrc`) |
| `--segmentation-dir` | no | Use your own segmentations instead of a previous job |
| `--output-dir` | no | Pipeline output root |
| `--input-job` | no | Use a specific job number as input, e.g. `--input-job 1` |
| `--write-selections` | no | Write each selected object to its own `.mrc` file |

Note that `--input-dir` here is the **tomogram** directory, not the segmentation directory. With no other flags PickMe will find the latest `extract_objects` job and use those segmentations.

#### Working in the napari window

Answer `y` at the prompt and a napari window opens with a Regionprops table on the right-hand side.

1. You will see the tomogram and segmentation layers in the napari layer list. You can show and hide any pairs of tomograms and segmentations you like — selections for a specific tomogram are only applied while that segmentation layer is highlighted in blue.
2. With a tomogram/segmentation pair open, use the dropdowns at the top right to point Regionprops at the segmentation (labels) layer and the tomogram (image) layer.
3. In the right-hand feature table, click **labels** and then **analyse**. A feature table of object labels appears at the bottom, and some output is printed to the command line confirming PickMe can see the label table.
4. Tick **show selected** in the segmentation layer options, and scroll through each object by clicking its label in the table.
5. To select an object, **hold cmd/ctrl + left-mouse click** on it. It should highlight, and the command line should print that the selection was registered. Hold cmd/ctrl and click again to select multiple objects.
6. To move on to another tomogram/segmentation pair, select that segmentation layer until it is highlighted blue, show/hide the appropriate layers, and repeat.

When you are done, close the napari window. PickMe registers the selections and writes them to `outputs/choose/jobNNN/`.

Optionally, supply your own segmentations or an explicit job number:

```bash
PickMe choose_objects \
  --input-dir path/to/tomogram/reconstruction/mrc/files \
  --segmentation-dir path/to/segmentations \
  --input-job 23
```

### 3. Particle extraction

Now extract particles from the surface of the objects you have filtered and selected. PickMe Gaussian-smooths each object, runs marching cubes to build a triangular surface mesh, samples that surface at your chosen spacing, and computes Euler angles that orient each particle normal to the membrane.

```bash
PickMe particle_extraction \
  --sample-rate 5 \
  --cmm
```

| Flag | Required | Meaning |
|---|---|---|
| `--sample-rate` | yes | Minimum spacing between sampled particles, in pixels |
| `--input-dir` | no | Use your own segmentations instead of a previous job |
| `--input-job` | no | Use a specific job number as input |
| `--output-dir` | no | Pipeline output root |
| `--cmm` | no | Also write Chimera `.cmm` marker files |

With no input flags, PickMe uses the latest `choose_objects` job.

### 4. Decompress

PickMe writes segmentations compressed. If you want to open them in Chimera/ChimeraX, decompress them first. This can be run against any part of the pipeline, not just the last step.

```bash
PickMe decompress --input-job 2
# or
PickMe decompress --input-dir path/to/compressed/files
```

| Flag | Required | Meaning |
|---|---|---|
| `--input-dir` | see note | Directory containing `.mrc.gz` / `.mrc.bz2` files |
| `--input-job` | see note | A job number from the PickMe pipeline |
| `--output-dir` | no | Pipeline output root |

Neither flag is individually required, but you must supply **one of them** — with neither, the command raises a `RuntimeError`.

### 5. Convert

Converts tomogram data types, which is useful when a downstream package insists on a particular type.

```bash
PickMe convert --input-dir path/to/tomograms
```

| Flag | Required | Meaning |
|---|---|---|
| `--input-dir` | yes | Directory (or single file) containing the tomograms to convert |
| `--output-dir` | no | Pipeline output root |
| `--data-type` | no | Target data type — see [Known limitations](#known-limitations) |

---

## Worked example: segmentations to a STAR file

Assuming you have a directory of segmentations you want to take through the entire PickMe pipeline, and the matching tomogram reconstructions:

```bash
# Work from a dedicated project directory so all outputs land together
mkdir my_pickme_project
cd my_pickme_project
conda activate pickme

# 1. Filter noise out of the segmentations   -> outputs/filter/job001
#    Answer 'n' at the prompt to process every tomogram found.
PickMe extract_objects --input-dir /data/segmentations

# 2. Pick the membranes you actually want    -> outputs/choose/job002
#    Answer 'y' to open napari; picks up outputs/filter/job001 automatically.
PickMe choose_objects --input-dir /data/tomograms

# 3. Oversample the chosen membranes         -> outputs/particle_extraction/job003
#    Uses the latest choose job automatically. 5 px spacing, plus .cmm for Chimera.
PickMe particle_extraction --sample-rate 5 --cmm

# 4. (Optional) decompress a job's mrc.gz    -> outputs/decompress/job004
PickMe decompress --input-job 2
```

After step 3 your particles are in `outputs/particle_extraction/job003/particles.star`, ready to hand to Warp/M/RELION.

To feed individual membranes back to MemBrain-seg instead, run step 2 with `--write-selections`:

```bash
PickMe choose_objects --input-dir /data/tomograms --write-selections
```

---

## Outputs reference

| Subcommand | Output |
|---|---|
| `extract_objects` | `<tomo>_filtered.mrc.gz` (gzip) per tomogram, plus knee-detection plots in a `plots/` subdirectory |
| `choose_objects` (default) | `<tomo_id>_filtered_chosen.mrc.gz` per tomogram |
| `choose_objects --write-selections` | A `TS_<id>_membranes/` subdirectory per tomogram, containing one **uncompressed** `TS_<id>_obj<label>.mrc` per object, with the object's voxels set to 1 |
| `particle_extraction` | One `.star` per tomogram, an aggregate `particles.star` across all tomograms, Euler angle distribution plots in an `AnglePlots/` subdirectory, and `.cmm` marker files if `--cmm` was passed |
| `decompress` | `TS_<id>_decompressed.mrc` |
| `convert` | `<prefix>_<id>_f32.mrc` |

Particle STAR files contain `rlnCoordinateX/Y/Z`, `rlnOriginX/Y/Z`, `rlnAngleRot`, `rlnAngleTilt`, `rlnAnglePsi`, `rlnMicrographName` (the `.tomostar` name), `rlnObject` (the object label the particle came from), `rlnNormalX/Y/Z` and `rlnImagePixelSize`.

---

## Known limitations

Being upfront about the rough edges, so you do not lose an afternoon to them:

- **`convert --data-type` is accepted but not yet honoured.** Whatever you pass, output is always float32. The converted file's voxel size is also currently hardcoded to 10 rather than being read from the input. Check your header before using converted files downstream.
- **`extract_objects --filter` is accepted but not yet honoured.** There is currently one filter — the volume-normalised knee detection — and that is what runs regardless of what you pass. The flag is there for the alternative filters on the roadmap below.
- **Four of the five subcommands prompt on stdin** (see [above](#these-commands-ask-you-questions)), so the pipeline cannot currently be run unattended in a batch script.
- **`choose_objects` needs a graphical session** if you answer `y`, since it launches napari and Qt.
- Filename conventions are assumed rather than configurable: `*segment*` for segmentation inputs, and `TS_<id>` underscore-separated tomogram IDs.

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
