# Filename-agnostic tomogram and segmentation handling — design

Status: agreed 2026-10-14. Branch `filename_agnostic_ids`, stacked on
`interactive_object_selection_pyqt5` (its PR targets that branch, not `main`).

## Problem

PickMe assumed every file was named `TS_<id>_...`, the convention of one dataset.
The tomogram ID was parsed as the second `_`-separated chunk and re-prefixed with
`TS_` (`utils/get_mgraph.py`, `main.py` `choose_object`, `decompress`, `convert`).
Consequences:

- Any other naming scheme breaks pairing, output names, and STAR files.
- `get_mgraph`'s `particle_extract` branch returned `TS_filtered.tomostar` for every
  tomogram (`docs/known-issues.md` #1), corrupting `rlnMicrographName`.
- Selecting tomograms meant typing digits that were substring-matched against file
  names, so typing `1` selected every file containing a 1.

## Rules

| Concept | Rule |
|---|---|
| Tomogram | any `*.mrc` in the tomogram directory |
| Segmentation | any file matching `*segment*` (`.mrc`, `.mrc.gz`, `.mrc.bz2`) |
| Identifier | file name minus its extension (`.mrc`, `.mrc.gz`, `.mrc.bz2`), e.g. `TS_1166_10.00Apx` |
| Pairing | a segmentation belongs to the tomogram whose identifier is the **longest prefix** of the segmentation's file name. Unmatched (or ambiguous: two segmentations for one tomogram) files are paired by the user by index; under `--non-interactive` they are skipped with a warning |
| `rlnMicrographName` | tomogram identifier, minus a trailing `_<number>Apx` if present, plus `.tomostar` (Warp/M convention): `TS_1166_10.00Apx` → `TS_1166.tomostar` |
| Selection | files are listed with 1-based indices; users type indices (`1 3 5-8`, `1,3`, `all`), never names |

Why the prefix rule: segmentation tools append to the input name. MemBrain-seg, which
users run, turns `TS_1166_10.00Apx.mrc` into
`TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc`. "Longest" makes
`tomo10_seg` match `tomo10`, not `tomo1`.

## Carrying the tomogram name through the pipeline

`particle_extraction` only sees segmentation files, yet must write the tomogram's
name. `choose_objects` is the first stage that knows both files, so from there on
PickMe names outputs after the **tomogram**, and later stages recover it by removing
PickMe's own fixed suffixes.

| Stage | Output name |
|---|---|
| `filter_objects` | `<segmentation id>_filtered.mrc.gz` (still starts with the tomogram id) |
| `choose_objects` | `<tomogram id>_chosen.mrc.gz`, or `<tomogram id>_membranes/<tomogram id>_obj<label>.mrc` |
| `particle_extraction` | `<tomogram id>.star` per tomogram; `rlnMicrographName` = `tomostar_name(tomogram id)` |
| `decompress` | `<id>_decompressed.mrc` |
| `convert` | `<id>_f32.mrc` |

With `--write-selections`, `choose_objects` writes one file per object
(`<tomogram id>_obj<label>.mrc`), so several `particle_extraction` inputs can belong to
one tomogram. Each input therefore gets its own STAR file, named
`strip_pickme_suffix(file id)` (keeps `_obj<label>`, so nothing overwrites), while
`rlnMicrographName` uses `tomogram_id_from_name`, which also strips `_obj<label>`.

`particle_extraction` recovers the tomogram id with `tomogram_id_from_name`. For raw
(non-PickMe) segmentations it takes an optional `--tomogram-dir` and pairs by prefix;
without it, a recovered id that still contains "segment" triggers a warning, since it
is a segmentation name rather than a tomogram name.

## Components

```
utils/naming.py            pure functions, unit-tested:
                             file_id, natural_sort_key, match_segmentations,
                             tomostar_name, strip_pickme_suffix, parse_index_selection
utils/choose_tomograms.py  index-based selection UI (list, prompt, re-ask on bad input)
                           and the manual pairing prompt for unmatched files
utils/get_mgraph.py        deleted — replaced by naming.py
main.py                    every stage switched to the above
cli.py                     --tomogram-dir on particle_extraction
```

## Compatibility

Outputs written before this change (e.g. `TS_1166_filtered.mrc.gz`) are shorter than
the tomogram id `TS_1166_10.00Apx`, so they cannot be prefix-matched; they fall through
to the index-pairing prompt. Re-running `filter_objects` produces the new names.

## Verification

- Unit tests for `naming.py`.
- Full smoke checks (`compileall`, all `-h`).
- End-to-end on the `TS_1166` data: `filter_objects` → `choose_objects --non-interactive`
  → `particle_extraction`; the STAR file must contain `rlnMicrographName` `TS_1166.tomostar`.
