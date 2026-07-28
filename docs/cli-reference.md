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

**Batch-script warning.** Four of the five subcommands — `extract_objects`,
`choose_objects`, `decompress`, and `convert` (when given a directory) —
block on an interactive `y/n` prompt read from stdin, and `choose_objects`
can additionally open a napari GUI. **`particle_extraction` is the only
subcommand with no interactive prompt at all.** If you're scripting the full
pipeline unattended, you'll need to either pre-answer the other four
subcommands' prompts (e.g. by piping input) or restructure your script
around that constraint.

## Contents

- [`extract_objects`](#extract_objects)
- [`choose_objects`](#choose_objects)
- [`particle_extraction`](#particle_extraction)
- [`decompress`](#decompress)
- [`convert`](#convert)
- [Common errors](#common-errors)

---

## `extract_objects`

Finds segmentation files, identifies every labelled object in them with
`skimage.measure.regionprops`, discards the objects that look like noise using
a volume-based knee filter, and writes the surviving objects back out.

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--input-dir` | str (path) | Yes | — | Directory containing the segmentation files to process. |
| `--output-dir` | str (path) | No | `./outputs` | Overrides the pipeline output root (see [pipeline.md](pipeline.md#output-root-and-job-numbering)). |
| `--filter` | str | No | `None` | Accepted but currently has no effect — see [Known limitations](#known-limitations). |

**File selection.** Inside `--input-dir`, PickMe looks for files matching
`*segment*` (i.e. the word "segment" must appear somewhere in the filename).
Files that don't match are silently ignored.

**Interactive prompt.** Before doing anything else, PickMe asks:

```
Are there specific tomograms you want to process (y/n)?
```

- **n** — every matched `*segment*` file is processed.
- **y** — it prints the matched files and asks you to type the numeric
  tomogram IDs you want (e.g. `1007 1012`), then processes only those.

This prompt fires every time — there is currently no flag to skip it, so
`extract_objects` cannot be driven from a fully unattended batch script.

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
PickMe extract_objects --input-dir ./segmentations --output-dir ./outputs
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

**Interactive prompt.** Always asked first, regardless of any flag:

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
  - `--write-selections` set: every object that survived `extract_objects` is
    written out as its own file (see Outputs below) — useful for exporting
    membranes without hand-picking any of them.

This prompt makes `choose_objects` unsuitable for a non-interactive batch
script in the `y` path (it blocks on the napari GUI); the `n` path is safe to
script only if you also hard-code the answer via stdin.

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

**Input resolution:**

1. `--input-job N` is given → use every file matching
   `<output_root>/**/job<NNN>/*.mrc*`. This wins even if `--input-dir` is
   also supplied.
2. else `--input-dir <dir>` is given → use every `<dir>/*.mrc*` file.
3. neither is given → raises `RuntimeError` before anything else runs.

**Interactive prompt.** After resolving the file list, PickMe always asks:

```
Are there any specific tomograms you want to decompress? (y/n)
```

- **n** — every resolved file is decompressed.
- **y** — it lists the tomograms found and asks you to type the numeric IDs
  you want; only those are decompressed.

This makes `decompress` unsafe to call from a non-interactive script without
also scripting the stdin answer.

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

**File selection.** If `--input-dir` points at a single file, only that file
is converted. If it points at a directory, PickMe globs for tomograms inside
it (interactively — see below) and then keeps only the ones ending in
`.mrc`.

**Interactive prompt.** When `--input-dir` is a directory (not a single
file), the same tomogram-selection prompt used by `extract_objects` fires:

```
Are there specific tomograms you want to process (y/n)?
```

Answer `n` to convert everything found, or `y` to type specific numeric IDs.
This means `convert` is also not safe to drive from an unattended script
unless the input path is a single file.

**Known limitation.** `--data-type` is parsed but never used — `convert()`
always casts to `numpy.float32` and always sets the output voxel size to
`10`, no matter what `--data-type` or the tomogram's original voxel size
were. Pass it if you like for documentation purposes in your own command
history, but it currently changes nothing.

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
