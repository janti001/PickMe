# The PickMe Pipeline

This guide explains the **workflow**: how a membrane segmentation becomes a
`particles.star` file you can hand to Warp, M or RELION, and how PickMe decides
which files feed into which stage. For install instructions see
[`../README.md`](../README.md); for exact flags and defaults see
[`cli-reference.md`](cli-reference.md).

PickMe is a chain of stages. Each stage writes into a numbered job directory,
and the next stage, unless you tell it otherwise, picks up the *latest* job of
the stage before it.

## 1. Overview

```
 tomograms (*.mrc)                 segmentations (*segment*, e.g. MemBrain-seg)
        |                                        |
        |                                        v
        |                              +-------------------+
        |                              |  filter_objects   |   keep real membranes,
        |                              +-------------------+   drop small debris
        |                                        |
        |                      outputs/filter/jobNNN/*_filtered.mrc.gz
        |                                        |
        |        (optional)                      v
        +------------------------>   +-------------------+
          tomograms are shown        |  choose_objects   |   click the membranes
          behind the segmentation    +-------------------+   you want (napari)
                                                 |
                              outputs/choose/jobNNN/<tomogram id>_chosen.mrc.gz
                                                 |
                                                 v
                                      +----------------------+
         --tomogram-dir (raw) ------> | particle_extraction  | --> STAR for
                                      +----------------------+     Warp / M / RELION
                                                 |
                          outputs/particle_extraction/jobNNN/{*.star, particles.star}

 Side utilities (not part of the chain):
   decompress : .mrc.gz / .mrc.bz2 -> .mrc   (to look at results in Chimera/ChimeraX)
   convert    : tomogram -> float32 .mrc     (for software that needs a given data type)
```

**Which stages can be skipped?**

- `choose_objects` is optional. Skip it if every filtered object is a
  membrane you want.
- `filter_objects` is optional too. `particle_extraction` accepts any
  segmentation files through `--input-dir`, or a PickMe job through
  `--input-job`.
- `particle_extraction` can run directly on a **filter job**
  (`--input-job N`) or on a folder of files (`--input-dir`). For raw
  segmentations (not produced by PickMe), also pass `--tomogram-dir` so
  `rlnMicrographName` gets the right tomogram name (see section 3).
- With no `--input-dir` and no `--input-job`, `particle_extraction` uses the
  latest `choose_objects` job. If no choose job exists yet, it stops with an
  error rather than guessing.

## 2. Worked example

Starting point: one dataset with tomograms in `./tomograms/` and MemBrain-seg
output in `./segmentations/`:

```
tomograms/
    TS_1166_10.00Apx.mrc
    TS_1167_10.00Apx.mrc
segmentations/
    TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc
    TS_1167_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc
```

### Step 1: filter_objects

```bash
PickMe filter_objects --input-dir ./segmentations
```

PickMe finds every file whose name contains `segment`, asks whether you want
specific segmentations (`n` = all), and labels the objects in each one. It
keeps the large ones past the volume "knee" (section 4). Files written:

```
outputs/filter/job001/
    TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented_filtered.mrc.gz
    TS_1167_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented_filtered.mrc.gz
    plots/
        TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented_knee.png
        TS_1167_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented_knee.png
```

It also prints one line per segmentation, e.g. "For segmentation <id>, N
objects were selected. Objects: [...]".

### Step 2: choose_objects (optional, needs a display)

```bash
PickMe choose_objects --input-dir ./tomograms
```

With no `--segmentation-dir` or `--input-job`, this uses the latest filter job
(`job001`). Answer `y` to "Are there any objects which you would like to
select", and napari opens, one tomogram at a time (section 4). Close the
window when you are done. Files written:

```
outputs/choose/job002/
    TS_1166_10.00Apx_chosen.mrc.gz
    TS_1167_10.00Apx_chosen.mrc.gz
```

Note the name: `<tomogram id>_chosen.mrc.gz`. The long MemBrain suffix is gone,
because after picking, each file is tied to its tomogram. Objects keep their
label values. Tomograms where you selected nothing get no file.

Adding `--write-selections` writes one uncompressed binary mask per object
instead (voxels = 1):

```
outputs/choose/job002/
    TS_1166_10.00Apx_membranes/
        TS_1166_10.00Apx_obj4.mrc
        TS_1166_10.00Apx_obj12.mrc
```

### Step 3: particle_extraction

```bash
PickMe particle_extraction --sample-rate 15 --cmm
```

With no input flags it uses the latest choose job (`job002`). `--sample-rate`
is the minimum spacing, in pixels, between sampled points. Files written:

```
outputs/particle_extraction/job003/
    TS_1166_10.00Apx.star
    TS_1167_10.00Apx.star
    particles.star                  # all tomograms combined
    AnglePlots/
        TS_1166_10.00Apx.png
        TS_1167_10.00Apx.png
    TS_1166_10.00Apx.cmm            # only because --cmm was given
    TS_1167_10.00Apx.cmm
```

In `particles.star`, `rlnMicrographName` is `TS_1166.tomostar` and
`TS_1167.tomostar`: the Warp/M convention (section 3). PickMe prints the
particle count per `rlnMicrographName` and the total at the end.

### Shortcut: skip the picking

Run straight from the filter job (job001 in this example):

```bash
PickMe particle_extraction --input-job 1 --sample-rate 15 \
    --tomogram-dir ./tomograms
```

`--tomogram-dir` is what lets PickMe turn the long MemBrain name back into
`TS_1166_10.00Apx` and then `TS_1166.tomostar`.

### The same pipeline with unrelated names

Nothing above depends on the `TS_` prefix. Take:

```
lamella_A.mrc
lamella_A_membrain_segmented.mrc
```

```bash
PickMe filter_objects --input-dir ./seg
#  -> outputs/filter/job001/lamella_A_membrain_segmented_filtered.mrc.gz
PickMe choose_objects --input-dir ./tomo
#  -> outputs/choose/job002/lamella_A_chosen.mrc.gz
PickMe particle_extraction --sample-rate 15
#  -> outputs/particle_extraction/job003/lamella_A.star, particles.star
#     rlnMicrographName = lamella_A.tomostar
```

`lamella_A` has no trailing `_<number>Apx`, so the name is kept whole and only
`.tomostar` is added.

## 3. How data and names flow between stages

### Ids

A file's **id** is its file name minus `.mrc`, `.mrc.gz` or `.mrc.bz2`.
`TS_1166_10.00Apx.mrc` has the id `TS_1166_10.00Apx`. PickMe never parses
digits or underscores out of ids, so any naming scheme works.

Where PickMe asks you to pick files, it shows a numbered list
(`  1. name`, in natural order, so 2 comes before 10). Type indices, never
names: `1 3 5-8`, `1,3`, or `all`. Invalid input (0, out of range, text, a
reversed range) is explained and asked again.

### Pairing a segmentation with its tomogram

A segmentation belongs to the tomogram whose id is the **longest prefix** of
the segmentation's file name, and the id must end at a separator (`_`, `.`,
`-`), not in the middle of a word.

Why: segmentation tools such as MemBrain-seg *append* to the tomogram name.

```
TS_1166_10.00Apx.mrc
TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc
```

The longest-prefix and separator rules also avoid wrong matches:
`lamella_B10_seg` pairs with `lamella_B10`, never with `lamella_B1`, even if
`lamella_B10` is missing.

If a segmentation matches no tomogram, or two segmentations match one
tomogram, `choose_objects` prompts you: type a tomogram index for each
segmentation (blank = skip; each tomogram can be used once). Under
`--non-interactive` such segmentations are skipped with a warning.
`choose_objects` prints "Paired N tomogram(s) with a segmentation; M
segmentation(s) skipped." If nothing pairs, it exits without opening napari.
A tomogram is never treated as its own segmentation, even if both sit in the
same folder.

### How particle_extraction recovers the tomogram id

- **PickMe outputs** (filter or choose jobs): PickMe strips its own markers
  (`_filtered`, `_chosen`, `_decompressed`) and any `_obj<N>` from the input id.
  A `_chosen` file is already named after its tomogram, so this is exact.
- **Raw segmentations**: the name still carries the tool's suffix, so give
  `--tomogram-dir`. PickMe pairs by the rule above. Without it, a warning says
  `rlnMicrographName` will be derived from a segmentation name.

Then `rlnMicrographName` follows the Warp/M convention: the tomogram id with a
trailing `_<number>Apx` removed, plus `.tomostar`.

| Tomogram id | rlnMicrographName |
|---|---|
| `TS_1166_10.00Apx` | `TS_1166.tomostar` |
| `lamella3_rec` | `lamella3_rec.tomostar` |

### Per-object inputs (`_obj<N>`)

With `--write-selections`, each object is its own file
(`<id>_membranes/<id>_obj12.mrc`). `particle_extraction` finds these
automatically in the latest choose job. The output `.star` keeps the
`_obj<N>` (`TS_1166_10.00Apx_obj12.star`) so objects do not overwrite each
other, while `rlnMicrographName` still uses the plain tomogram id.
`particles.star` combines everything.

### Duplicate output names

If two inputs would write the same output name (for example `a.mrc` and
`a.mrc.gz` in one folder), `filter_objects`, `particle_extraction`,
`decompress` and `convert` print:

```
WARNING: a.mrc, a.mrc.gz all produce output named 'a'; the one processed last will overwrite the others.
```

and carry on. Check the warning, and remove one input if it is a mistake.

### Older outputs

Filter outputs written before the filename-agnostic change (for example
`TS_1166_filtered.mrc.gz`) do not start with the full tomogram id
(`TS_1166_10.00Apx`), so they cannot auto-pair. They go to the manual pairing
prompt. Re-running `filter_objects` gives the new names.

## 4. What each stage does

### filter_objects: knee filtering

A segmentation is one volume in which each connected membrane piece carries its
own integer label. PickMe measures the volume of every labelled object
(`skimage.measure.regionprops`), normalises by the largest, and sorts them.
Debris and fragments form a long tail of small objects, and real membranes sit
above a "knee" in that curve. PickMe finds the knee and keeps the objects past
it. The curve is saved in `plots/<id>_knee.png` so you can check the cut.
Output is gzip (`.mrc.gz`), `int8` labels.

### choose_objects: picking, one tomogram at a time

Opens napari with the tomogram and its filtered labels. Only one tomogram is
loaded at a time, so memory stays small.

- **Click** an object to select it; click again to deselect. This works in the
  2D slice view and the 3D view (left button, in the labels layer's normal
  navigation mode, not paint/fill/erase).
- **Drag** pans (2D) or rotates (3D) and never selects. A press-and-release
  that moves more than 4 pixels counts as a drag.
- **Colours:** selected = bright green; unselected = magenta (60% opaque);
  background is transparent. Objects are filled, not outlined.
- The viewer opens on the middle of the z-slices that contain objects.
- **Dock panel "PickMe objects"** (right side): a tomogram dropdown with
  Previous/Next buttons, a list of selected objects (`label 12 - 48,301
  voxels`), "Remove selected", "Clear all", and a status line.
- Selections are remembered per tomogram while you switch.
- A tomogram whose segmentation has a different shape, or a corrupt file, is
  refused with a warning and you return to the previous tomogram.
- **Close the napari window to finish**; the selection is then written.

If you answer `n` to "Are there any objects which you would like to select",
the job is **cancelled**: nothing is written and no job directory is made. To
export every filtered object, select them all or skip this stage.

### particle_extraction: from objects to particles

For each object:

1. **Smoothing:** a Gaussian (sigma 3) on a crop around the object, so the
   binary mask becomes a smooth density.
2. **Marching cubes** turns it into a triangle mesh of the membrane surface.
3. **Sampling:** points on the surface are kept at least `--sample-rate`
   pixels apart.
4. **Euler angles** come from the mesh normal at each point, so that each
   particle's z axis points out of the membrane. `rlnAngleRot` (rotation about
   the normal) has no meaningful reference, so it is drawn at random.

`rlnAngleRot` uses an unseeded random generator, so it differs from run to run
(a `--seed` option is planned, not yet implemented). Arrays are processed in
**zyx** order internally and written as X/Y/Z. Angles are in degrees, in
RELION's convention. Each STAR row has `rlnCoordinateX/Y/Z`, `rlnOriginX/Y/Z`
(zero), `rlnAngleRot/Tilt/Psi`, `rlnMicrographName`, `rlnObject`,
`rlnNormalX/Y/Z` and `rlnImagePixelSize`.

### decompress and convert

- `decompress` turns `.mrc.gz`/`.mrc.bz2` (from `--input-dir` or
  `--input-job`) into `<id>_decompressed.mrc` for Chimera/ChimeraX. The voxel
  size is copied. Example: `PickMe decompress --input-job 2`.
- `convert` writes `<id>_f32.mrc` from a tomogram file or folder. The output is
  always float32: `--data-type` is accepted but ignored. The voxel size is
  copied from the input.

## 5. Output root and job numbers

Everything is written below an **output root**, `./outputs` by default
(relative to where you run PickMe). `--output-dir` *replaces* this root for
the run; it does not add a subfolder.

| Subcommand | Job directory |
|---|---|
| `filter_objects` | `outputs/filter/jobNNN` |
| `choose_objects` | `outputs/choose/jobNNN` |
| `particle_extraction` | `outputs/particle_extraction/jobNNN` |
| `decompress` | `outputs/decompress/jobNNN` |
| `convert` | `outputs/convert/jobNNN` |

Job numbers are zero-padded to three digits and come from **one global
counter across the whole output root**, not per stage. PickMe takes the
highest existing `jobNNN` anywhere under the root and adds 1, so `filter/job003`
is followed by `choose/job004`. `--input-job 4` (or `004`) always means "the
folder named `job004`, wherever it is".

Which input to use:

- **`--input-job N`** pins a specific earlier run, e.g. re-running
  `particle_extraction` at a different `--sample-rate` on the same choose job
  even after newer jobs exist. It wins over `--input-dir` if both are given.
- **`--input-dir`** is for files that did not come from a PickMe job.
- **Neither**: the latest job of the previous stage. Convenient, but the most
  likely to pick up the wrong data if you have been experimenting.

## 6. Running on HPC

Four subcommands prompt: `filter_objects`, `choose_objects`, `decompress` and
`convert`. Add `--non-interactive` to take the default answer to every prompt
(`particle_extraction` never prompts). Defaults are: process every
segmentation or file found; skip unpaired segmentations with a warning.

`choose_objects` is special: picking objects needs a display, so under
`--non-interactive` it **cancels** and writes nothing. The pattern is:

1. Run `filter_objects` anywhere (workstation or cluster).
2. Run `choose_objects` on a **workstation** with a display, and copy the
   `outputs/choose/jobNNN` folder to the cluster.
3. Run the rest in batch:

```bash
PickMe filter_objects --input-dir /data/seg --output-dir /scratch/me/pickme --non-interactive
PickMe particle_extraction --input-job 2 --sample-rate 15 \
    --output-dir /scratch/me/pickme
```

Use the same `--output-dir` for every stage so they share one root (and one
job counter), and give `--input-job` explicitly in batch scripts instead of
relying on "latest". The headless install (`pip install PickMe-EM`) has no
napari; see [`gui-setup.md`](gui-setup.md) for the GUI.

## 7. Memory

Peak memory is roughly flat in the number of tomograms, because each tomogram
is processed, written and released before the next:

| Stage | Peak (large tomogram) |
|---|---|
| `filter_objects` | about 4.2 GB |
| `choose_objects` | about 2.8 GB (tomograms are memory-mapped for display; only one is loaded at a time) |

`particle_extraction` smooths only a crop around each object, not a whole
tomogram-sized array.

## Next steps

- Exact flags: [`cli-reference.md`](cli-reference.md)
- Window will not open: [`gui-setup.md`](gui-setup.md)
- Known problems: [`known-issues.md`](known-issues.md)
