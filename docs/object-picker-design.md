# Click-to-select object picker for `choose_objects` — design

Status: agreed 2026-10-13, implemented on branch `interactive_object_selection_pyqt5`.

## Problem

`choose_objects` used to make users run the napari-skimage **Regionprops** plugin,
click *Analyze*, then click rows in its results table one by one to pick objects.
PickMe read those rows by reaching into the plugin's private Qt widget tree
(~400 lines in `gui/napari_compat.py`), which any upstream release could break.
It also loaded every tomogram in the input directory into one viewer at once.

Separately, the deployment cluster is old and its administrator requires **PyQt5**,
while laptops/WSL use PyQt6.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Qt binding | Binding-agnostic code (`qtpy` only); PyQt6 by default, PyQt5 via `[gui-pyqt5]` / `PickMe-pyqt5.yml` | Cluster admin requires Qt5; napari 0.7.0 still declares a `pyqt5` extra. The binding becomes an install choice, not a code choice |
| Where users click | 2D slice view primarily, 3D view also | 3D needs working OpenGL, which old clusters on software rendering may lack |
| Multiple tomograms | One at a time, switched from a dock panel (dropdown + Previous/Next) | Clicks can never land in the wrong tomogram; peak memory ~one tomogram regardless of count |
| Click behaviour | Plain click toggles; press→release moving > 4 px is a drag (pan/rotate) and selects nothing | Fast, and does not fight napari's own camera controls |
| Selection list | Dock list of `label N — V voxels` with *Remove selected* and *Clear all* | A readable record of what will be written, fixable without re-finding the object |
| Regionprops plugin | Removed; `napari-skimage` dropped as a dependency | Removes the fragile private-API code and one cluster dependency |
| Highlight | **Recolour** the existing labels layer (`DirectLabelColormap`): selected green, others magenta (60% opacity), background transparent | Zero extra memory. Trade-off accepted: a fill, not a 1-pixel outline. Unselected objects were first drawn grey at 25% opacity, which vanished against grey tomograms; green/magenta is the colour-blind-safe pair |

Rejected highlight options: per-object cropped outline layers (`contour=1`) —
cheap-ish but adds layers and `contour` is 2D-only; a full-size overlay layer —
~1.4 GB per tomogram at int8.

## Components

```
gui/selection.py      ObjectSelection state, is_click, voxel_counts, selection_colormap_dict
                      — numpy only, no napari/Qt, unit-tested headless
gui/picker_widget.py  PickerWidget(QWidget) dock panel — qtpy only, emits signals, holds no data
gui/picker.py         ObjectPicker — owns the current tomogram's layers, the mouse
                      callback, and wires selection <-> widget <-> viewer
main.py               choose_object builds an ObjectPicker, runs napari, then reads
                      picker.selections() into the UNCHANGED write-out loop
gui/napari_compat.py  Regionprops/table helpers removed; version, display,
                      render-backend checks and release_viewer kept
```

The interface between the GUI and the write-out code is `dict[str, set[int]]`
(tomogram id → selected labels), the same shape as before, so file output is unchanged.

## Data flow for one click

1. Press on the labels layer → remember screen position (left button only).
2. Release → `is_click` (≤ 4 px)? If not, it was a pan/rotate; stop.
3. `labels_layer.get_value(position, view_direction=..., dims_displayed=..., world=True)`
   returns the label under the cursor (in 3D, the first object along the view ray).
4. 0/None → status "Clicked background". Otherwise `ObjectSelection.toggle`.
5. Rebuild the colour dict → `DirectLabelColormap` on the layer; refresh the dock list.

## Memory rules this respects

- Tomograms stay memory-mapped, with explicit `contrast_limits` (see CLAUDE.md Key Decisions).
- On switching tomogram, the old layers are removed from the viewer **before** the
  memory-map handle is closed.
- `voxel_counts` uses z-slab `np.bincount`; a whole-array `bincount` would cast an
  int8 tomogram to int64 (~11 GB).

## Not in this change

- Documentation updates (`README.md`, `docs/gui-setup.md`, `docs/cli-reference.md`,
  `docs/pipeline.md`, `docs/known-issues.md` still describe Regionprops) — pending
  the user's go-ahead per the "ask first" doc rule.
- Container definitions for a PyQt5 image.
