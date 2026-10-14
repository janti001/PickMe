# CLI Reference

This is the reference for every `PickMe` subcommand: what each job does, every
option, the questions it asks you, and the files it writes. For installation
see [`../README.md`](../README.md) and [`gui-setup.md`](gui-setup.md). For how
the jobs chain together see [`pipeline.md`](pipeline.md).

The console script is `PickMe`. Options are written with hyphens
(`--input-dir`). Run `PickMe -h` or `PickMe <subcommand> -h` at any time to
see the same information from the program itself.

## The workflow at a glance

```
tomograms (*.mrc)  +  segmentations (*segment*.mrc)
                         |
                  filter_objects      remove small/noisy objects (knee filter)
                         |
                  choose_objects      click the membranes you want (napari)
                         |
                particle_extraction   sample points, Euler angles -> STAR files
```

`decompress` and `convert` are side tools: `decompress` turns `.mrc.gz` /
`.mrc.bz2` into plain `.mrc` so you can look at them in Chimera/ChimeraX;
`convert` rewrites tomograms as float32.

You do not have to run every stage. `particle_extraction` can start from the
output of `choose_objects` (the default), or directly from any folder of
segmentations (see below).

## File naming and pairing rules

PickMe makes **no assumptions about how your files are named**. There is no
required `TS_` prefix or tomogram number.

| Term | Rule |
|---|---|
| Tomogram | Any `*.mrc` file. |
| Segmentation | Any file whose name contains `segment` (glob `*segment*`), as `.mrc`, `.mrc.gz` or `.mrc.bz2`. Files without `segment` in the name are ignored by `filter_objects`. |
| **id** | The file name with `.mrc`, `.mrc.gz` or `.mrc.bz2` removed. `TS_1166_10.00Apx.mrc` has id `TS_1166_10.00Apx`. |

**Pairing a segmentation with its tomogram.** A segmentation belongs to the
tomogram whose id is the **longest prefix** of the segmentation's file name,
where the id must end at a separator (`_`, `.`, `-`, ...) and not in the
middle of a word. This suits tools such as MemBrain-seg that append to the
tomogram name:

```
TS_1166_10.00Apx.mrc                                          <- tomogram
TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc     <- its segmentation
```

`lamella_B10_seg.mrc` pairs with `lamella_B10`, never with `lamella_B1`, even
if `lamella_B10` is missing. If a segmentation matches no tomogram, or two
segmentations match the same tomogram, PickMe asks you to pair them by hand
(see `choose_objects`). Each tomogram can be used once.

**Picking files by index.** Whenever PickMe lists files it numbers them
(`  1. name`, in natural order, so 2 comes before 10). You answer with numbers,
never with names:

| You type | Meaning |
|---|---|
| `1 3 5-8` | files 1, 3, 5, 6, 7, 8 |
| `1,3` | files 1 and 3 (commas also work) |
| `all` | every file in the list |

Bad input (0, a number past the end, text, a backwards range such as `8-5`)
prints why it was rejected and asks again.

**`rlnMicrographName` in STAR files** follows the Warp/M convention: the
tomogram id with a trailing `_<number>Apx` removed, plus `.tomostar`.

| Tomogram id | `rlnMicrographName` |
|---|---|
| `TS_1166_10.00Apx` | `TS_1166.tomostar` |
| `lamella3_rec` | `lamella3_rec.tomostar` |

**Duplicate-name warning.** If two inputs would write the same output name
(for example `a.mrc` and `a.mrc.gz` in one folder), `filter_objects`,
`particle_extraction`, `decompress` and `convert` continue but print:

```
WARNING: a.mrc, a.mrc.gz all produce output named 'a'; the one processed last will overwrite the others.
```

**Older outputs.** Files written before this naming scheme (for example
`TS_1166_filtered.mrc.gz`) do not start with the full tomogram id
(`TS_1166_10.00Apx`), so they cannot be paired automatically. You will be
taken to the manual pairing prompt, or you can re-run `filter_objects` to get
new names.

## Job directories and job numbers

Every run writes into a new numbered folder under the **output root**
(`./outputs` in the folder where you run PickMe; `--output-dir` moves the whole
root):

| Subcommand | Output folder |
|---|---|
| `filter_objects` | `<root>/filter/jobNNN` |
| `choose_objects` | `<root>/choose/jobNNN` |
| `particle_extraction` | `<root>/particle_extraction/jobNNN` |
| `decompress` | `<root>/decompress/jobNNN` |
| `convert` | `<root>/convert/jobNNN` |

Job numbers are zero-padded to three digits and come from **one global
counter** across the whole output root, not one per stage. If
`filter/job003` exists, the next `choose_objects` run is `choose/job004`.
Anywhere an option takes `--input-job`, `1` and `001` both mean `job001`.

## Unattended runs and `--non-interactive`

`filter_objects`, `choose_objects`, `decompress` and `convert` ask questions
and wait for your answer. Pass `--non-interactive` to take the default answer
to every question, which is what you need in a batch or HPC (Slurm) job. What
the default is differs per command and is listed below.
`particle_extraction` never asks anything.

PickMe reports progress with printed text and progress bars.

## How much memory do I need?

Roughly 3-4x the size of one uncompressed tomogram. It does not grow with the
number of tomograms, because each is processed and released before the next.
Figures for a 700x1400x1400 float32 tomogram (5.5 GB):

| Subcommand | Approximate peak RAM |
|---|---|
| `filter_objects` | ~4.2 GB |
| `choose_objects` | ~2.8 GB, plus what napari needs to display |
| `particle_extraction` | small (objects are processed as cropped sub-volumes) |
| `decompress`, `convert` | ~2x the size of one file |

On WSL2 the memory cap defaults to half your Windows RAM; raise it in
`C:\Users\<you>\.wslconfig` (`[wsl2]` then `memory=24GB`), then run
`wsl --shutdown`. A process killed with no message is what hitting the cap
looks like.

## Contents

- [`filter_objects`](#filter_objects)
- [`choose_objects`](#choose_objects)
- [`particle_extraction`](#particle_extraction)
- [`decompress`](#decompress)
- [`convert`](#convert)
- [Common errors](#common-errors)

---

## `filter_objects`

**What it does.** Reads each segmentation, finds every labelled object in it,
and removes the objects that look like noise using a volume-based **knee
detection**: objects are ranked by volume and those past the knee of the curve
are kept. This is the first stage of the workflow.

**Options**

| Option | Value | Required | Default | Meaning |
|---|---|---|---|---|
| `--input-dir` | path | Yes | - | Folder containing the segmentation files. |
| `--output-dir` | path | No | `./outputs` | Output root for the whole pipeline. |
| `--filter` | text | No | none | Method for filtering objects (default: max-volume normalisation). Currently accepted but has no effect; the max-volume knee method is always used. |
| `--non-interactive` | flag | No | off | Skip the question and process every segmentation found. |

**Inputs.** Files matching `*segment*` directly inside `--input-dir`
(`.mrc`, `.mrc.gz` or `.mrc.bz2`). Other files are ignored.

**Interactive prompts**

1. `Are there specific segmentations you want to process (y/n)?`
   - `n`: process every segmentation found.
   - `y`: the segmentations are listed with numbers; type indices such as
     `1 3 5-8` or `all`.

**`--non-interactive`:** answers `n`, so every segmentation is processed.

**Outputs**, in `<root>/filter/jobNNN/`:

| Path | Contents |
|---|---|
| `<segmentation id>_filtered.mrc.gz` | Gzip-compressed labels (int8) containing only the objects kept. Objects keep their original label numbers. |
| `plots/<segmentation id>_knee.png` | Diagnostic plot of the volume curve and where the cut-off fell. |

For each segmentation PickMe prints a summary line such as
`For segmentation <id>, N objects were selected. Objects: [...]`.

**Example**
```bash
PickMe filter_objects --input-dir ./segmentations
PickMe filter_objects --input-dir ./segmentations --non-interactive   # batch job
```

---

## `choose_objects`

**What it does.** Lets you pick, by clicking in napari, the membrane objects
you actually want, one tomogram at a time, with the tomogram shown beneath its
segmentation. It writes the chosen objects out for `particle_extraction`. This
is the second stage; it needs a screen.

**Options**

| Option | Value | Required | Default | Meaning |
|---|---|---|---|---|
| `--input-dir` | path | Yes | - | A tomogram `.mrc` file, or a folder of reconstructed tomograms (the volumes, not the segmentations). |
| `--segmentation-dir` | path | No | none | Folder of segmentation `.mrc` files to pick from. Assumed to be `.mrc`. |
| `--output-dir` | path | No | `./outputs` | Output root. Changing it is not recommended. |
| `--input-job` | integer | No | none | Use a specific filter job's output as the segmentations, e.g. `1` selects `job001`. |
| `--write-selections` | flag | No | off | Write each chosen object to its own `.mrc` file in a folder named by the tomogram id. Without it, all chosen objects of a tomogram go into one file. |
| `--non-interactive` | flag | No | off | Skip questions. The napari viewer is never opened (batch nodes have no display), so the job is cancelled (see below). |

**Inputs.** Tomograms from `--input-dir`. Segmentations come from the first of:

1. `--segmentation-dir`, if given;
2. `--input-job N`, if given;
3. the **latest** `filter` job.

A tomogram is never treated as its own segmentation when both sit in one
folder. Segmentations are paired with tomograms by the
[longest-prefix rule](#file-naming-and-pairing-rules).

**Interactive prompts**, in order:

1. `Are there any objects which you would like to select (y/n)?`
   - `y`: continue.
   - `n`: **cancels the job.** Nothing is written and no job folder is created.
2. *Manual pairing*, only for segmentations that matched no tomogram or
   matched ambiguously. For each such segmentation, type the number of the
   tomogram it belongs to; a blank answer skips it. Each tomogram can be used
   once.

   PickMe then prints `Paired N tomogram(s) with a segmentation; M
   segmentation(s) skipped.` If nothing is paired it says there is nothing to
   do and stops without opening napari.
3. `Are there specific tomograms you want to process (y/n)?` Asked only when
   more than one tomogram is paired. `n`: all paired tomograms; `y`: choose by
   index (`1 3 5-8` or `all`).

**`--non-interactive`:** answers the first question as "no", so the job is
cancelled and nothing is written. Object picking needs a display, so this
command cannot run unattended. Run it on a machine with a screen (or an
`ssh -X` session; see [gui-setup.md](gui-setup.md)) and use the other
stages in batch jobs.

### Using the object picker

napari opens showing **one tomogram at a time**, with its segmentation drawn
over it. The view starts at the middle of the slices that contain objects.

| Action | Result |
|---|---|
| Left-click an object | Selects it. |
| Click a selected object again | Deselects it. |
| Click-and-drag | Pans (2D view) or rotates (3D view). A drag never selects: any press-and-release that moves more than 4 pixels counts as a drag. |

Clicking works in both the 2D slice view and the 3D view, with the left mouse
button only, and only while the labels layer is in its normal navigation mode
(not paint, fill or erase).

Colours: **selected objects are bright green**, **unselected objects are
magenta** (60% opaque), and the background is transparent. Objects are filled,
not outlined.

The dock panel **PickMe objects** on the right contains:

- a tomogram drop-down with **Previous** / **Next** buttons;
- the list of selected objects, e.g. `label 12 - 48,301 voxels`, with
  **Remove selected** and **Clear all** buttons;
- a status line.

Your selection is remembered for each tomogram while you move between them.
Switching unloads the previous tomogram, so memory use stays at about one
tomogram. If a segmentation has a different shape from its tomogram, or is
corrupt, PickMe warns and returns to the previous tomogram.

**Close the napari window to finish.** Closing it writes your selection.

**Outputs**, in `<root>/choose/jobNNN/`. Tomograms with nothing selected are
skipped; if nothing at all was selected, no files are written.

| Mode | Path | Contents |
|---|---|---|
| Default | `<tomogram id>_chosen.mrc.gz` | One gzip file per tomogram; objects keep their label values. |
| `--write-selections` | `<tomogram id>_membranes/<tomogram id>_obj<label>.mrc` | One uncompressed file per object; voxels set to `1`. |

**Example**
```bash
PickMe choose_objects --input-dir ./tomograms
PickMe choose_objects --input-dir ./tomograms --input-job 2 --write-selections
PickMe choose_objects --input-dir ./tomograms --segmentation-dir ./segmentations
```

---

## `particle_extraction`

**What it does.** Smooths each chosen object, builds a surface with marching
cubes, samples points across that surface at a fixed spacing, computes an
Euler angle for each point from the surface normal, and writes STAR files
(optionally Chimera marker files). This is the final stage and runs unattended.

**Options**

| Option | Value | Required | Default | Meaning |
|---|---|---|---|---|
| `--sample-rate` | integer | Yes | - | Minimum spacing between sampled points on the membrane, in **pixels** (not Angstroms). |
| `--input-dir` | path | No | none | Folder of segmentation files to sample. If omitted, the latest `choose` job is used. |
| `--input-job` | integer | No | none | Use a specific job's output instead of the latest `choose` job. `1` and `001` both mean `job001`. |
| `--output-dir` | path | No | `./outputs` | Output root for the whole pipeline. |
| `--cmm` | flag | No | off | Also write particle coordinates to a `.cmm` file for Chimera/ChimeraX. |
| `--tomogram-dir` | path | No | none | Folder of the original tomograms. Only needed for segmentations **not** produced by PickMe: they are paired to tomograms by name so `rlnMicrographName` is correct. |

**Inputs** (first match wins):

1. `--input-job N`: every file under that job, including per-object files.
2. `--input-dir`: every `*.mrc`, `*.mrc.gz` and `*.mrc.bz2` in that folder.
3. Otherwise the **latest `choose` job** (both `<id>_chosen.mrc.gz` and
   `<id>_membranes/*.mrc`).

If no files are found, a warning is printed. For PickMe outputs the tomogram
id is the input id with `_filtered`, `_chosen`, `_decompressed` and `_obj<N>`
removed. For raw segmentations, pass `--tomogram-dir`; without it a warning
says `rlnMicrographName` will be derived from a segmentation name.

**Interactive prompts.** None. **`--non-interactive`** does not exist for this
command because it never asks anything.

**Outputs**, in `<root>/particle_extraction/jobNNN/`:

| Path | Contents |
|---|---|
| `<name>.star` | One STAR file per input file. `<name>` is the input id without the PickMe suffixes but keeping `_obj<N>`, so per-object inputs do not overwrite each other, e.g. `TS_1166_10.00Apx.star`, `TS_1166_10.00Apx_obj4.star`. |
| `particles.star` | All particles from every input in this job. |
| `AnglePlots/<name>.png` | Angle-distribution plot per input. |
| `<name>.cmm` | Chimera markers; only with `--cmm`. |

The job also prints particle counts per `rlnMicrographName` and the total.
Columns in the STAR files: `rlnCoordinateX/Y/Z` (pixels), `rlnOriginX/Y/Z`
(always 0), `rlnAngleRot`, `rlnAngleTilt`, `rlnAnglePsi` (degrees),
`rlnMicrographName`, `rlnObject` (source object label),
`rlnNormalX/Y/Z`, and `rlnImagePixelSize` (Angstroms per pixel, read from the
MRC header).

**Known limitation.** `rlnAngleRot` is drawn from an unseeded random number
generator (there is no natural azimuthal angle around a membrane normal), so
it differs from run to run. Tilt and psi come from the surface normal and are
reproducible.

**Example**
```bash
PickMe particle_extraction --sample-rate 15 --cmm
PickMe particle_extraction --input-job 4 --sample-rate 20
PickMe particle_extraction --input-dir ./segmentations --tomogram-dir ./tomograms --sample-rate 15
```

---

## `decompress`

**What it does.** Converts `.mrc.gz` / `.mrc.bz2` files to plain `.mrc`,
because Chimera/ChimeraX cannot open the compressed forms. It works on the
output of any stage. A side tool, usable at any point.

**Options**

| Option | Value | Required | Default | Meaning |
|---|---|---|---|---|
| `--input-dir` | path | One of `--input-dir` / `--input-job` | none | Folder containing the `.mrc.gz` / `.mrc.bz2` files. |
| `--input-job` | integer | One of `--input-dir` / `--input-job` | none | Take the files from a PickMe job number (any stage). |
| `--output-dir` | path | No | `./outputs` | Output root for the whole pipeline. |
| `--non-interactive` | flag | No | off | Skip the question and decompress every file found. |

**Inputs.** `*.mrc*` files in `--input-dir`, or in the given job. If both
options are given, the job takes priority. If neither is given, the command
stops with an error.

**Interactive prompts**

1. `Are there specific MRC files you want to process (y/n)?`
   - `n`: decompress every file found.
   - `y`: files are listed with numbers; type indices (`1 3 5-8` or `all`).

**`--non-interactive`:** answers `n`, so every file is decompressed.

**Outputs**, in `<root>/decompress/jobNNN/`: `<id>_decompressed.mrc`, one per
file. The voxel size is copied from the input.

**Example**
```bash
PickMe decompress --input-job 3
PickMe decompress --input-dir ./outputs/choose/job002 --non-interactive
```

---

## `convert`

**What it does.** Rewrites tomograms with a different data type, for
downstream software that is picky about it. At present the output is **always
float32**. A side tool, usable at any point.

**Options**

| Option | Value | Required | Default | Meaning |
|---|---|---|---|---|
| `--input-dir` | path | Yes | - | A single tomogram file, or a folder of tomograms. |
| `--output-dir` | path | No | `./outputs` | Output root for the whole pipeline. |
| `--data-type` | text | No | `float32` | The data type to convert to. **Accepted but ignored**: the output is always float32. |
| `--non-interactive` | flag | No | off | Skip the question and convert every `.mrc` file found. |

**Inputs.** The single file given, or the `.mrc` files in the folder.

**Interactive prompts.** Only when `--input-dir` is a folder:

1. `Are there specific tomograms you want to process (y/n)?`
   - `n`: convert every `.mrc` file found.
   - `y`: tomograms are listed with numbers; type indices (`1 3 5-8` or `all`).

A single file is converted without asking.

**`--non-interactive`:** answers `n`, so every `.mrc` file is converted.

**Outputs**, in `<root>/convert/jobNNN/`: `<id>_f32.mrc`, one per tomogram.
The voxel size is copied from the input.

**Example**
```bash
PickMe convert --input-dir ./raw_tomograms
PickMe convert --input-dir ./raw_tomograms/TS_1166_10.00Apx.mrc
```

---

## Common errors

**`particle_extraction`: `RuntimeError: choose_object job must be run if you are to provide no input directory`**
You gave no `--input-dir` and no `--input-job`, and no `choose_objects` job
exists under the output root. Run `choose_objects` first, or pass
`--input-dir` / `--input-job`.

**`decompress`: `RuntimeError: A directory or Job number must be provided for this job`**
Pass `--input-dir` or `--input-job`.

**`convert`: `RuntimeError: Input must be a file or directory`**
The path given to `--input-dir` does not exist (check for a typo).

**`choose_objects` finishes at once and writes nothing.**
You answered `n` to the first question, ran with `--non-interactive`, or
nothing could be paired or selected. Re-run and answer `y`.
