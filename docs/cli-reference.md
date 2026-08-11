# CLI Reference

This is the flag-by-flag reference for every `PickMe` subcommand. For installation
and a narrative overview of the tool, see [`../README.md`](../README.md). For how
the five subcommands chain together into a pipeline, see
[`pipeline.md`](pipeline.md).

The console script is `PickMe` (not `pickme-em`, not `PickMe-EM`). Every flag is
written with hyphens on the command line (`--input-dir`) but argparse converts
these to underscores internally (`args.input_dir`) — you don't need to do
anything about this, it's just why you'll see underscores if you ever read the
source.

Run `PickMe -h` or `PickMe <subcommand> -h` at any time to see this same
information from argparse directly.

**Batch-script warning.** Four of the five subcommands — `filter_objects`,
`choose_objects`, `decompress`, and `convert` (when given a directory) —
block on an interactive `y/n` prompt read from stdin, and `choose_objects`
can additionally open a napari GUI. **`particle_extraction` is the only
subcommand with no interactive prompt at all.** If you're scripting the full
pipeline unattended, you'll need to either pre-answer the other four
subcommands' prompts (e.g. by piping input) or restructure your script
around that constraint. The clean way is `--non-interactive`, documented per
subcommand below.

## How much memory do I need?

Roughly **3–4x the size of one uncompressed tomogram**, and it does *not* grow
with the number of tomograms in your input directory — each is processed and
released before the next is read.

For a 700x1400x1400 float32 tomogram (5.5 GB on disk) with a matching `int8`
segmentation:

| Subcommand | Approximate peak RAM |
|---|---|
| `filter_objects` | ~4.2 GB |
| `choose_objects` (napari GUI) | ~2.8 GB, plus what napari needs to display |
| `choose_objects` (`--non-interactive`) | ~2.6 GB |
| `particle_extraction` | small — objects are processed as cropped sub-volumes |
| `decompress`, `convert` | ~2x the size of one file |

If you are on **WSL2**, note that it caps itself at 50% of your Windows RAM (a
flat 8 GB on older builds) regardless of what the machine has. Raise it in
`C:\Users\<you>\.wslconfig`:

```ini
[wsl2]
memory=24GB
swap=8GB
```

then `wsl --shutdown` and reopen. A process killed with no traceback, or the
whole WSL session dying, is what hitting that cap looks like.

> Earlier versions needed 12+ GB and grew with the number of tomograms, which
> made an 8 GB machine unusable. See `distribution.md` §2.2 if you are
> comparing against older behaviour.

## Contents

- [`filter_objects`](#filter_objects)
- [`choose_objects`](#choose_objects)
- [`particle_extraction`](#particle_extraction)
- [`decompress`](#decompress)
- [`convert`](#convert)
- [Common errors](#common-errors)

---

## `filter_objects`

Finds segmentation files, identifies every labelled object in them with
`skimage.measure.regionprops`, discards the objects that look like noise using
a volume-based knee filter, and writes the surviving objects back out.

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--input-dir` | str (path) | Yes | — | Directory containing the segmentation files to process. |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root (see [pipeline.md](pipeline.md#output-root-and-job-numbering)). |
| `--filter` | str | No | `None` | Accepted but currently has no effect — see [Known limitations](#known-limitations). |
| `--non-interactive` | flag | No | `False` | Skip the prompt below and process every matched file. Use this in batch scripts. |

**File selection.** Inside `--input-dir`, PickMe looks for files matching
`*segment*` (i.e. the word "segment" must appear somewhere in the filename).
Files that don't match are silently ignored.

**Interactive prompt.** Unless `--non-interactive` is set, PickMe asks before
doing anything else:

```
Are there specific tomograms you want to process (y/n)?
```

- **n** — every matched `*segment*` file is processed.
- **y** — it prints the matched files and asks you to type the numeric
  tomogram IDs you want (e.g. `1007 1012`), then processes only those.

With `--non-interactive` the prompt is skipped entirely and every matched file
is processed, so this subcommand can be driven from an unattended batch script.
See [gui-setup.md](gui-setup.md#3-running-the-non-gui-stages-unattended).

**Outputs**, written to `<output_root>/filter/jobNNN/`:
- `<tomo>_filtered.mrc.gz` — one gzip-compressed mrc per tomogram, containing
  only the objects that passed the filter (voxels carry their original object
  label, not just 1/0).
- `plots/<micrograph>_knee.png` — a diagnostic plot per tomogram showing the
  volume knee and where the cutoff was placed.

**Known limitations.** `--filter` is parsed and stored on `args.filter`, but
`extract_and_store()` never passes it on to the filtering function
(`filter.knee_detection`). Whatever value you supply, the only behaviour you
get is the default: max-volume normalisation with a perpendicular-distance
knee cutoff. Treat `--filter` as reserved for future use, not a working
option today.

**Example:**
```bash
PickMe filter_objects --input-dir ./segmentations --output-dir ./outputs
```

---

## `choose_objects`

Lets you narrow a tomogram's filtered objects down to the ones you actually
want, either by hand in napari or by keeping everything. This is the stage
that produces the input `particle_extraction` normally expects.

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--input-dir` | str (path) | Yes | — | Directory (or single file) of the **reconstructed tomograms** — the raw/reconstructed volumes, not the segmentations. |
| `--segmentation-dir` | str (path) | No | `None` | Directory of segmentation `.mrc` files to pick objects from. See input resolution below. |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root. |
| `--input-job` | int | No | `None` | Use a specific `filter` job number as the segmentation source, e.g. `1` selects `job001`. |
| `--write-selections` | flag | No | `False` | Write each kept object to its own uncompressed `.mrc` file instead of one combined file per tomogram. |
| `--non-interactive` | flag | No | `False` | Skip the prompt below and take the **n** path — napari is never opened. Picking objects visually needs a display, which batch nodes do not have. |

Note `--input-dir` here is **not** the segmentation directory — it's the
tomogram volumes that get shown side-by-side with the segmentation in napari.
The segmentation source is chosen separately, by the three-way rule below.

**Segmentation source resolution** (first match wins):

1. `--segmentation-dir <dir>` is given → use every `<dir>/*.mrc` file.
2. else `--input-job N` is given → use every file matching
   `<output_root>/**/job<NNN>/*.mrc*` (zero-padded automatically, so `1` → `job001`).
3. else → use the **latest** `outputs/filter/jobNNN` directory, filtered to
   files matching `*filtered*`.

`--segmentation-dir` wins over `--input-job` if you accidentally supply both.

Tomogram IDs are matched between `--input-dir` and the resolved segmentation
files by splitting each filename on `_` and comparing the second field (e.g.
`TS_1007...` → `1007`). Only tomograms present on both sides end up processed.

**Interactive prompt.** Asked first, unless `--non-interactive` is set:

```
Are there any objects which you would like to select (y/n)?
```

- **y** — opens a napari viewer with each tomogram and its segmentation
  loaded, plus the napari-skimage "Regionprops (labels)" plugin dock widget.
  Click **Run** in that widget, then select rows in the resulting table to
  choose objects (multi-select is enabled). Closing the napari window
  continues the pipeline with whatever was selected at that point.
- **n** — no object picking happens. What happens next depends on
  `--write-selections`:
  - `--write-selections` **not** set: the filtered files are left exactly as
    they are; nothing new is written.
  - `--write-selections` set: every object that survived `filter_objects` is
    written out as its own file (see Outputs below) — useful for exporting
    membranes without hand-picking any of them.

The **y** path can never run in a batch job: it blocks on a napari window, and
a compute node has no display to open one on. That is a workflow constraint,
not a bug — run `choose_objects` on a machine with a display (or an
`ssh -X` / interactive session) and the other stages on the cluster. See
[gui-setup.md](gui-setup.md#hpc-clusters).

`--non-interactive` forces the **n** path, so `choose_objects` can be scripted
when combined with `--write-selections` to export every filtered object without
hand-picking.

**Outputs**, written to `<output_root>/choose/jobNNN/`:
- Default (no `--write-selections`, objects were picked in napari):
  `<tomo_id>_filtered_chosen.mrc.gz` — one gzip mrc per tomogram, voxels
  carrying the original object label.
- With `--write-selections` (either after picking in napari, or after
  answering `n` to skip picking): `TS_<id>_membranes/TS_<id>_obj<label>.mrc`
  — one **uncompressed** file per object, voxels set to `1` rather than the
  label. This shape is intended for feeding individual membranes back into
  MemBrain-seg for retraining.

**Example:**
```bash
PickMe choose_objects --input-dir ./tomograms --input-job 2 --write-selections
```

---

## `particle_extraction`

Takes chosen/filtered segmentation objects, Gaussian-smooths them, runs
marching cubes to build a surface mesh, samples points across that surface at
a fixed spacing, assigns each point a RELION-convention Euler angle, and
writes STAR files (and optionally a Chimera `.cmm` file).

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--sample-rate` | int | Yes | — | Minimum spacing enforced between sampled particle points on the membrane surface, in **pixels/voxels — not Ångströms**. Convert manually if you're used to thinking in physical units. |
| `--input-dir` | str (path) | No | `None` | Directory of segmentation files to sample. If omitted, PickMe falls back to the latest `choose_objects` job. |
| `--input-job` | int | No | `None` | Use a specific job number as input (any stage's `jobNNN` — three-digit padding is applied automatically from the integer you pass). |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root. |
| `--cmm` | flag | No | `False` | Also write particle coordinates and normals to a `.cmm` file for viewing in Chimera/ChimeraX. |

**Input resolution** (first match wins):

1. `--input-job N` is given → use every file matching
   `<output_root>/**/job<NNN>/**/*.mrc*`. This takes priority even if
   `--input-dir` is also supplied.
2. else, no `--input-dir` and at least one `choose_objects` job exists → use
   the **latest** `outputs/choose/jobNNN` directory, filtered to files
   matching `*chosen*`.
3. else, no `--input-dir` and **no** `choose_objects` job exists yet → raises
   `RuntimeError` (see [Common errors](#common-errors)).
4. else, `--input-dir` is given → use every `*.mrc`, `*.mrc.gz`, and
   `*.mrc.bz2` file directly in that directory.

No interactive prompts — this subcommand can run unattended once its inputs
exist.

**Outputs**, written to `<output_root>/particle_extraction/jobNNN/`:
- `<tomo_name>.star` — one STAR file per tomogram.
- `particles.star` — the aggregate STAR file across every tomogram and
  object processed in this job. Columns: `rlnCoordinateX/Y/Z` (particle
  position, pixel units), `rlnOriginX/Y/Z` (always `0`), `rlnAngleRot`,
  `rlnAngleTilt`, `rlnAnglePsi` (ZYZ Euler angles in RELION convention, in
  **degrees**), `rlnMicrographName` (a `.tomostar` filename, e.g.
  `TS_1007.tomostar`), `rlnObject` (the source object's label number),
  `rlnNormalX/Y/Z` (the surface normal at that particle), and
  `rlnImagePixelSize` (Ångströms per pixel, taken from the segmentation's
  MRC header). `rlnAngleRot` is drawn uniformly at random per particle —
  there is no meaningful azimuthal reference around a membrane normal, so
  it isn't derived from the data the way tilt and psi are.
- `AnglePlots/<tomo_name>.png` — a diagnostic angle-distribution plot per
  tomogram.
- `<tomo_name>.cmm` (only with `--cmm`) — particle coordinates and normals,
  for loading into Chimera/ChimeraX.

**Example:**
```bash
PickMe particle_extraction --sample-rate 15 --cmm
```

---

## `decompress`

Converts `.mrc.gz` or `.mrc.bz2` files back to plain `.mrc`, since
Chimera/ChimeraX can't open the compressed forms directly. Works on the
output of any pipeline stage, not just the latest one.

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--input-dir` | str (path) | One of `--input-dir` / `--input-job` required | `None` | Directory containing the `.mrc.gz` / `.mrc.bz2` files to decompress. |
| `--input-job` | int | One of `--input-dir` / `--input-job` required | `None` | Job number to pull files from (any stage). Takes priority over `--input-dir` if both are given. |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root. |
| `--non-interactive` | flag | No | `False` | Skip the prompt below and decompress every resolved file. Use this in batch scripts. |

**Input resolution:**

1. `--input-job N` is given → use every file matching
   `<output_root>/**/job<NNN>/*.mrc*`. This wins even if `--input-dir` is
   also supplied.
2. else `--input-dir <dir>` is given → use every `<dir>/*.mrc*` file.
3. neither is given → raises `RuntimeError` before anything else runs.

**Interactive prompt.** After resolving the file list, and unless
`--non-interactive` is set, PickMe asks:

```
Are there any specific tomograms you want to decompress? (y/n)
```

- **n** — every resolved file is decompressed.
- **y** — it lists the tomograms found and asks you to type the numeric IDs
  you want; only those are decompressed.

With `--non-interactive` the prompt is skipped and every resolved file is
decompressed, making this subcommand safe to call from a batch script.

**Outputs**, written to `<output_root>/decompress/jobNNN/`:
- `TS_<id>_decompressed.mrc` — one uncompressed mrc per selected tomogram.

**Example:**
```bash
PickMe decompress --input-job 3
```

---

## `convert`

Converts tomogram data type — in the current implementation, always to
float32, regardless of what you ask for. Useful when a downstream tool is
picky about voxel dtype.

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--input-dir` | str (path) | Yes | — | Directory (or single file) of tomograms to convert. |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root. |
| `--data-type` | str | No | `None` (documented as defaulting to float32) | **Accepted but ignored** — see below. |
| `--non-interactive` | flag | No | `False` | Skip the prompt below and convert every `.mrc` file found. Use this in batch scripts. |

**File selection.** If `--input-dir` points at a single file, only that file
is converted. If it points at a directory, PickMe globs for tomograms inside
it (interactively — see below) and then keeps only the ones ending in
`.mrc`.

**Interactive prompt.** When `--input-dir` is a directory (not a single file),
and unless `--non-interactive` is set, the same tomogram-selection prompt used
by `filter_objects` fires:

```
Are there specific tomograms you want to process (y/n)?
```

Answer `n` to convert everything found, or `y` to type specific numeric IDs.
With `--non-interactive`, everything found is converted without asking — as is
already the case when `--input-dir` points at a single file.

**Known limitation.** `--data-type` is parsed but never used — `convert()`
always casts to `numpy.float32` regardless of what you pass. Pass it if you
like for documentation purposes in your own command history, but it currently
changes nothing.

*(The output voxel size used to be hardcoded to `10`; that is fixed — the
source file's voxel size is now carried through.)*

**Outputs**, written to `<output_root>/convert/jobNNN/`:
- `<prefix>_<id>_f32.mrc` — where `<prefix>` and `<id>` are the first two
  underscore-separated fields of the source filename (e.g.
  `TS_1007_something.mrc` → `TS_1007_f32.mrc`).

**Example:**
```bash
PickMe convert --input-dir ./raw_tomograms --data-type float32
```

---

## Common errors

**`particle_extraction`: `RuntimeError: choose_object job must be run if you are to provide no input directory`**
Raised when you call `particle_extraction` with no `--input-dir`, no
`--input-job`, and no `choose_objects` job has ever been run under the
current output root. Fix by either running `choose_objects` first, or
passing `--input-dir`/`--input-job` explicitly.

**`decompress`: `RuntimeError: A directory or Job number must be provided for this job`**
Raised immediately if neither `--input-dir` nor `--input-job` is supplied.
Fix by passing one of the two.

**`convert`: `RuntimeError: Input must be a file or directory`**
Raised if the path given to `--input-dir` doesn't exist as either a file or
a directory (e.g. a typo in the path).
