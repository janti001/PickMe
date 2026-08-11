# Known Issues

Bugs and rough edges found during the documentation and docstring cleanup pass.
The original pass was documentation-only by design, so this file records what
was found for you to decide on.

**Status as of branch `gui_3d`** — some have since been fixed; each heading
below says which. Line numbers in entries predating the `gui_3d` memory work
have shifted; locate by pattern, not by number.

| # | Issue | Status |
|---|---|---|
| 1 | `TS_filtered` micrograph names | **OPEN — blocks distribution** |
| 2 | Per-tomogram STAR files overwrite | Partly fixed (`removesuffix` done; the collapse persists via #1) |
| 3 | `filter_objects` reuses last shape/voxel size | **Fixed** |
| 4 | `convert` hardcodes voxel size to 10 | **Fixed** |
| 5 | `convert --data-type` ignored | OPEN |
| 6 | `convert` fails on re-run | OPEN |
| 7–12 | Dead code, typos, API awkwardness | OPEN |

Line numbers refer to the state of the code after the docstring pass.

Each entry is marked with how it was established:

- **Verified** — reproduced or traced through the code directly during the pass.
- **Reported** — found by inspection and looks right, but was not executed or
  independently confirmed.

---

## 1. `particle_extraction` labels every tomogram `TS_filtered` — Verified

**Where:** `src/PickMe/utils/get_mgraph.py:71`

**What happens:** `choose_objects` writes files named `<id>_filtered_chosen.mrc.gz`
(for example `1007_filtered_chosen.mrc.gz`) — note there is no `TS_` prefix.
`particle_extraction` passes those filenames to `get_mgraph(caller='particle_extract')`,
which does:

```python
mgraph_parts = segmentation_file.split('_')
mgraph_name = f'TS_{mgraph_parts[1]}{mgraph_suffix}'
```

Splitting `1007_filtered_chosen.mrc.gz` on `_` gives
`['1007', 'filtered', 'chosen.mrc.gz']`, so index `[1]` is the literal string
`"filtered"`. The function returns `TS_filtered.tomostar` for **every** tomogram.

**Why it matters:** this value is written to `rlnMicrographName` for every
particle in `particles.star`, so downstream tools (RELION, Warp/M) cannot tell
which tomogram a particle came from. It also collapses the per-tomogram STAR
filenames — see issue 2 — so each tomogram overwrites the previous one.

**Likely fix:** index `[0]` rather than `[1]` in this branch. The default branch
at line 77 is correct for its own inputs (`TS_<id>_...`), which is why the two
branches disagree; the `particle_extract` branch appears to be a copy-paste of the
default that was never adjusted for the different filename shape.

**Note:** the default and `decompress` branches are fine. Only the
`caller='particle_extract'` path is affected.

---

## 2. Per-tomogram STAR files overwrite each other — PARTLY FIXED

> **Status:** the `str.strip` half is fixed — `main.py` now uses
> `tomo_name.removesuffix(".tomostar")`. The overwriting itself persists,
> because it is caused by issue 1 below handing every tomogram the same name.
> Fixing issue 1 resolves the remainder.


**Where:** `src/PickMe/main.py:629`

```python
starfile.write(tomogram_star_df, f'{output_directory}/{tomo_name.strip(".tomostar")}.star')
```

Two separate problems:

**`str.strip` does not remove a suffix.** It removes any leading or trailing
characters that appear in the set `{'.', 't', 'o', 'm', 's', 'a', 'r'}`. For a
name like `TS_1007.tomostar` it happens to give `TS_1007`, but the behaviour is
accidental — an ID ending in one of those characters would be silently truncated.
`str.removesuffix('.tomostar')` (Python 3.9+) does what was intended.

**Combined with issue 1**, `tomo_name` is always `TS_filtered.tomostar`, so every
tomogram writes to the same `TS_filtered.star` file and each run overwrites the
last. Only the final tomogram's particles survive as a per-tomogram file.
The aggregate `particles.star` still contains all rows, but with the wrong
micrograph names.

Fixing issue 1 restores distinct filenames; fixing the `strip` call makes them
robust.

---

## 3. `filter_objects` reuses the last tomogram's shape and voxel size — FIXED

> **Status:** fixed on `gui_3d`. The two-loop structure that caused it was
> merged into one during the memory work, so shape and voxel size are now
> re-derived per tomogram inside the loop that writes the output.


**Where:** `src/PickMe/main.py:117` (and the surrounding writing loop)

`extract_and_store` runs two sequential loops. The first iterates over every
segmentation and sets `shape_zyx` and `pix_size` from each file in turn. The
second loop writes the filtered output — but it never re-derives those two
values, so it uses whatever was left in scope from the **final iteration** of the
first loop.

**Why it matters:** if every tomogram in a run has identical dimensions and voxel
size this is harmless, which is probably why it has gone unnoticed. As soon as a
dataset mixes shapes or pixel sizes, the written arrays get the wrong dimensions
(or fail outright) and the voxel size in the header is wrong for every file but
the last.

**Likely fix:** re-read shape and voxel size per tomogram inside the writing
loop, or carry them alongside the objects in `full_data`.

---

## 4. `convert` hardcodes the output voxel size to 10 — FIXED

> **Status:** fixed. `convert` now reads `voxel_size` from the source file and
> carries it through to the output.


**Where:** `src/PickMe/main.py:816`

```python
mrc.voxel_size = 10
```

Every converted tomogram is written with a voxel size of 10, regardless of the
source file's actual calibration. This silently corrupts the pixel-size metadata
on the output, which matters for anything downstream that reads it.

**Likely fix:** read `voxel_size` from the source file and carry it through, as
the other write paths in `main.py` already do.

---

## 5. `convert --data-type` is accepted but ignored — Verified

**Where:** `src/PickMe/main.py:751` (signature), `:811` (the cast)

The `data_type` parameter is parsed by the CLI and passed into `convert()`, but
the body always does `data.astype(np.float32)`. Requesting `--data-type int16`
silently produces float32.

**Options:** honour the parameter, or remove the flag from `cli.py` until it is
implemented. Documented as a known limitation in the meantime.

---

## 6. `convert` fails on re-run — Reported

**Where:** `src/PickMe/main.py:814`

```python
with mrcfile.new(os.path.join(output_directory, output_file)) as mrc:
```

`mrcfile.new()` defaults to `overwrite=False`, so a second run that lands on an
existing output filename raises rather than overwriting. Every other write path
in `main.py` passes `overwrite=True`.

---

## 7. `filter_objects --filter` is dead — Verified

**Where:** `src/PickMe/cli.py:117` → `src/PickMe/main.py:47`

The flag is parsed and passed through as `filter_choice`, but
`extract_and_store` never reads the parameter. `filter.knee_detection` always
runs. The flag's help text advertises a choice that does not exist.

**Options:** as with issue 5 — implement it, or hide it until it does something.

---

## 8. `knee.py` type check passes `np.array` as a type — Verified

**Where:** `src/PickMe/filter/knee.py:50`

```python
if not isinstance(volume_array, (np.ndarray, np.array)):
```

`np.array` is a function, not a type. This does not currently raise, but only by
luck: `isinstance` short-circuits on the first matching tuple element, so a real
`ndarray` matches `np.ndarray` and `np.array` is never examined. Pass anything
that is *not* an ndarray and you get
`TypeError: isinstance() arg 2 must be a type...` instead of the clear error the
check was written to give.

**Likely fix:** drop `np.array` from the tuple.

---

## 9. Dead code that would not run if called — Verified (as uncalled)

None of the following are referenced anywhere in the package. `main.py` imports
`marching_cubes` from `skimage.measure` directly and calls
`sampling.non_random_membrane_sampling`, bypassing all of them. Their bugs are
therefore latent, not live — but they will bite whoever wires them up.

| Location | Problem |
|---|---|
| `src/PickMe/meshing/safe_marching_cubes.py:2` | Only `from numpy import max, min` is imported, but the body uses `np.*` and `m.e` — raises `NameError` immediately. |
| `src/PickMe/meshing/safe_marching_cubes.py:36` | `if initial_level or step_size is not None:` — operator precedence means this never checks `initial_level is not None`. |
| `src/PickMe/meshing/safe_marching_cubes.py:5` | `step_size` is validated but never used in the retry loop. |
| `src/PickMe/sampling/sampling.py:208` | `tree.qury_ball_point` — typo for `query_ball_point`, raises `AttributeError`. |
| `src/PickMe/sampling/sampling.py:208` | Indexes `coords_normals_shuffled[i[:3]]` where `i` is an integer from `argsort` — `TypeError`. |
| `src/PickMe/utils/choose_object.py:44` | The whole function is a stub; the selection logic is an unreachable comment after `return`, and the parsed yes/no answer is discarded. |

---

## 10. `meshing/__init_.py` is misspelled — Verified

**Where:** `src/PickMe/meshing/__init_.py`

One underscore before `.py` instead of two. Python does not treat this as a
package initialiser, so the `from .safe_marching_cubes import ...` line inside it
never executes and `meshing` is not a regular package.

Renaming it to `__init__.py` would activate that import — which, given issue 9,
would immediately surface the `NameError` in `safe_marching_cubes`. Fix them
together.

---

## 11. `sampling.shuffle_sampling` parameter is misspelled — Verified

**Where:** `src/PickMe/sampling/sampling.py:7`

The parameter is named `grid_samping` (missing the `l`). The function works, but
any caller using a keyword argument has to reproduce the typo. Renaming it is a
breaking change for existing callers, so it is worth doing deliberately rather
than incidentally.

---

## 12. `object_extraction` keys cannot be matched to volumes — Reported

**Where:** `src/PickMe/utils/object_extraction.py`

The returned dictionary is keyed `"Object1"`, `"Object2"`, … following the order
`regionprops` returns objects, which is not the same as the object's `label`.
The companion `volume_array` is positional. As a result there is no reliable way
to map an entry in the dict back to its volume by index or by key.

This was found by inspection and not executed — worth confirming before acting
on it.

---

## Not bugs, but worth a decision

- **`pyproject.toml` has no upper Python bound.** It declares
  `requires-python = ">=3.12"`, while `PickMe.yml` pins `python=3.12` and the
  project notes elsewhere say `>=3.12, <3.14`. If 3.14 is genuinely unsupported,
  the bound belongs in `pyproject.toml`.
- **Four of the five subcommands block on `input()`.** `filter_objects`,
  `choose_objects`, `convert` and `decompress` all prompt; only
  `particle_extraction` can run unattended. A `--yes` / `--non-interactive` flag
  would make the tool scriptable.
- **Job numbering is global across the output root.** `check_make_dir` takes
  `max()` over every `job###` directory anywhere under the root, so stages share
  one counter (`filter/job003` is followed by `choose/job004`). This is
  deliberate enough to rely on — `--input-job N` works precisely because numbers
  are unique across stages — but it surprises people, so it is documented in
  `docs/pipeline.md`.
