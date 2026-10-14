"""Display-free logic for click-to-select of segmented objects.

This module deliberately imports only the standard library and numpy, so it
can be imported on a headless cluster (no napari, no Qt).
"""

import math

import numpy as np

# RGBA colours (0-1 floats), as napari's DirectLabelColormap expects.
GREEN = (0.0, 1.0, 0.0, 1.0)  # selected objects
# Every unselected object. Must stay clearly visible: an earlier grey at 25%
# opacity disappeared into the grey tomogram, so users saw no objects at all.
# Magenta/green is the standard colour-blind-safe pair, so selected (green)
# and unselected (magenta) cannot be confused.
UNSELECTED = (1.0, 0.0, 1.0, 0.6)
TRANSPARENT = (0.0, 0.0, 0.0, 0.0)  # background label 0


class ObjectSelection:
    """Tracks which object labels are selected, per tomogram.

    Labels are stored as plain Python ints (never numpy ints) so they are
    safe to use as dict keys and to serialise.
    """

    def __init__(self, tomo_ids):
        """Creates an empty selection for each tomogram.

        Args:
            tomo_ids: Iterable of tomogram ID strings.
        """
        self._selected = {str(tomo_id): set() for tomo_id in tomo_ids}

    def _get(self, tomo_id):
        """Returns the label set for a tomogram or raises a clear KeyError."""
        try:
            return self._selected[tomo_id]
        except KeyError:
            known = ", ".join(sorted(self._selected)) or "none"
            raise KeyError(
                f"Unknown tomogram id {tomo_id!r}. Known ids: {known}"
            ) from None

    def toggle(self, tomo_id, label):
        """Selects the label if unselected, otherwise deselects it.

        Args:
            tomo_id: Tomogram ID string.
            label: Integer object label (must be > 0).

        Returns:
            True if the label is now selected, False if now deselected.

        Raises:
            ValueError: If label is 0 or negative (background is not an
                object).
            KeyError: If tomo_id is unknown.
        """
        label = int(label)
        if label <= 0:
            raise ValueError(
                f"Label {label} is not an object (0 is background, "
                "negative labels are invalid)."
            )
        chosen = self._get(tomo_id)
        if label in chosen:
            chosen.discard(label)
            return False
        chosen.add(label)
        return True

    def remove(self, tomo_id, label):
        """Deselects a label; does nothing if it was not selected.

        Args:
            tomo_id: Tomogram ID string.
            label: Integer object label.

        Raises:
            KeyError: If tomo_id is unknown.
        """
        self._get(tomo_id).discard(int(label))

    def clear(self, tomo_id):
        """Deselects every label of one tomogram.

        Args:
            tomo_id: Tomogram ID string.

        Raises:
            KeyError: If tomo_id is unknown.
        """
        self._get(tomo_id).clear()

    def labels(self, tomo_id):
        """Returns the selected labels of one tomogram.

        Args:
            tomo_id: Tomogram ID string.

        Returns:
            Sorted list of ints.

        Raises:
            KeyError: If tomo_id is unknown.
        """
        return sorted(self._get(tomo_id))

    def as_dict(self):
        """Returns a copy of the whole selection.

        Returns:
            Dict mapping every tomogram ID (including those with nothing
            selected) to a new set of labels. Mutating it does not affect
            this object.
        """
        return {tomo_id: set(chosen) for tomo_id, chosen in self._selected.items()}


def is_click(press_xy, release_xy, tolerance_px=4.0):
    """Tells a click apart from a pan/rotate drag.

    Args:
        press_xy: (x, y) screen position of the mouse press.
        release_xy: (x, y) screen position of the mouse release.
        tolerance_px: Maximum movement, in screen pixels, still counted as a
            click.

    Returns:
        True if the pointer moved at most tolerance_px (Euclidean distance).
    """
    dx = release_xy[0] - press_xy[0]
    dy = release_xy[1] - press_xy[1]
    return math.hypot(dx, dy) <= tolerance_px


def voxel_counts(segmentation, slab_size=32):
    """Counts voxels per object label, without big temporary copies.

    ``np.bincount(seg.ravel())`` silently casts to int64, so a 1.4 GB int8
    tomogram would need ~11 GB. Instead we walk the array in slabs of
    ``slab_size`` planes along axis 0 (z), so the temporary copy is only one
    slab big.

    Args:
        segmentation: Integer label array (zyx order, or 2D). 0 is
            background; negative values are ignored.
        slab_size: Number of z-planes processed at a time.

    Returns:
        Dict {label: voxel count} for every label > 0 that occurs.

    Raises:
        ValueError: If slab_size is less than 1.
    """
    if slab_size < 1:
        raise ValueError(f"slab_size must be >= 1, got {slab_size}")

    seg = np.asarray(segmentation)
    if seg.ndim == 0 or seg.size == 0:
        return {}
    if seg.ndim == 2:
        seg = seg[np.newaxis]  # a view, not a copy: one slab of one plane

    counts = np.zeros(1, dtype=np.int64)
    for start in range(0, seg.shape[0], slab_size):
        slab = seg[start:start + slab_size]
        positive = slab[slab > 0]  # copy of this slab's object voxels only
        if positive.size == 0:
            continue
        # minlength keeps every slab's result at least as long as the running
        # total, so we only ever need to grow `counts`, never shrink it.
        slab_counts = np.bincount(positive, minlength=counts.size)
        if slab_counts.size > counts.size:
            grown = np.zeros(slab_counts.size, dtype=np.int64)
            grown[:counts.size] = counts
            counts = grown
        counts[:slab_counts.size] += slab_counts

    labels = np.nonzero(counts)[0]
    return {int(label): int(counts[label]) for label in labels}


def object_z_range(segmentation, slab_size=32):
    """Finds the first and last z-slice that contain any object.

    napari opens a volume at its middle slice, which can easily fall outside
    the objects - the user then sees an empty segmentation. The picker uses
    this range to open on a slice that actually shows objects. Works in
    z-slabs for the same memory reason as `voxel_counts`.

    Args:
        segmentation: Integer label array in zyx order. 0 is background;
            negative values are ignored.
        slab_size: Number of z-planes checked at a time.

    Returns:
        A ``(first_z, last_z)`` tuple of ints, or None if there are no
        objects.

    Raises:
        ValueError: If slab_size is less than 1.
    """
    if slab_size < 1:
        raise ValueError(f"slab_size must be >= 1, got {slab_size}")
    seg = np.asarray(segmentation)
    occupied = []
    for start in range(0, seg.shape[0], slab_size):
        slab = seg[start:start + slab_size]
        # One True/False per plane in this slab: does it hold any object?
        has_object = (slab > 0).reshape(slab.shape[0], -1).any(axis=1)
        occupied.extend(start + np.flatnonzero(has_object))
    if not occupied:
        return None
    return int(occupied[0]), int(occupied[-1])


def selection_colormap_dict(selected):
    """Builds the colour mapping for napari's DirectLabelColormap.

    Args:
        selected: Iterable of selected labels (ints or numpy ints).

    Returns:
        Dict {None: UNSELECTED, 0: TRANSPARENT, label: GREEN, ...}. The None key
        is napari's "default colour for any label not listed". Keys are
        plain Python ints.
    """
    colors = {None: UNSELECTED, 0: TRANSPARENT}
    for label in selected:
        label = int(label)
        if label > 0:  # never let a selected label override the background
            colors[label] = GREEN
    return colors
