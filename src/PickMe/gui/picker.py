"""Controller for click-to-select of segmented objects in napari.

`ObjectPicker` ties three things together for `choose_objects`:

- the napari viewer, where the user clicks on objects,
- `ObjectSelection` (``selection.py``), which remembers what was clicked, and
- `PickerWidget` (``picker_widget.py``), the dock panel listing the picks and
  switching between tomograms.

Only ONE tomogram (plus its segmentation) is loaded at a time. Switching
tomogram removes the old layers and loads the new pair, so memory stays at
roughly one tomogram however many are in the input directory.

Selected objects are highlighted by recolouring the existing labels layer
(selected -> green, others dimmed, background transparent). No extra arrays
or overlay layers are created, which again keeps memory flat.

This module imports napari and Qt (via ``picker_widget``) at import time, so
it must only be imported from inside the GUI branch of `choose_object`.
"""

import mrcfile
from napari.utils.colormaps import DirectLabelColormap

from .picker_widget import PickerWidget
from .selection import ObjectSelection, is_click, selection_colormap_dict, voxel_counts


class ObjectPicker:
    """Shows one tomogram at a time and lets the user click objects to keep.

    The tomogram loader and contrast-limit helper live in `main.py`. They are
    passed in as callables rather than imported, because `main.py` imports
    this module and importing back would be circular.

    Attributes:
        viewer (napari.Viewer): The viewer the picker draws into.
        widget (PickerWidget): The dock panel.
        current_id (str or None): Tomogram currently shown.
    """

    def __init__(self, viewer, data_dict, open_tomogram, contrast_limits):
        """Builds the picker, docks its panel and shows the first tomogram.

        Args:
            viewer (napari.Viewer): An open viewer to add layers and the dock
                panel to.
            data_dict (dict): ``{tomo_id: {"tomogram": path,
                "segmentation": path}}``, as built in `choose_object`.
            open_tomogram (callable): `main._open_tomogram_for_display`; takes
                a path and returns ``(handle_or_None, array)``.
            contrast_limits (callable): `main._sampled_contrast_limits`; takes
                an array and returns ``(low, high)``.
        """
        self.viewer = viewer
        self._data_dict = data_dict
        self._open_tomogram = open_tomogram
        self._contrast_limits = contrast_limits

        self._tomo_ids = sorted(data_dict)
        self._selection = ObjectSelection(self._tomo_ids)
        # {tomo_id: {label: voxel_count}} - a few numbers per object, so cheap
        # to keep for every tomogram visited, and saves re-counting on return.
        self._voxel_counts = {}

        self.current_id = None
        self._image_layer = None
        self._labels_layer = None
        self._tomogram_handle = None

        self.widget = PickerWidget(self._tomo_ids)
        viewer.window.add_dock_widget(self.widget, name="PickMe objects", area="right")
        self.widget.tomogram_requested.connect(self.show)
        self.widget.remove_requested.connect(self._on_remove_requested)
        self.widget.clear_requested.connect(self._on_clear_requested)

        if self._tomo_ids:
            self.show(self._tomo_ids[0])
        else:
            self.widget.set_status("No tomograms with a matching segmentation.")

    # ---- public API -------------------------------------------------------

    def show(self, tomo_id):
        """Replaces the displayed tomogram and segmentation with `tomo_id`'s.

        Args:
            tomo_id (str): One of the IDs in `data_dict`.
        """
        if tomo_id == self.current_id:
            return

        message = f"Loading {tomo_id}…"
        print(f"[PickMe] {message}")
        self.widget.set_status(message)

        self._unload_current()

        paths = self._data_dict[tomo_id]
        handle, tomogram = self._open_tomogram(paths["tomogram"])
        self._tomogram_handle = handle

        # Segmentations are gzip-compressed (.mrc.gz), and compressed data
        # cannot be memory-mapped, so it is decompressed into RAM. They are
        # int8 label arrays, roughly a quarter the size of the tomogram.
        with mrcfile.open(paths["segmentation"], mode="r") as mrc:
            segmentation = mrc.data.copy()

        if tomo_id not in self._voxel_counts:
            self._voxel_counts[tomo_id] = voxel_counts(segmentation)

        # Image first so the labels layer is drawn on top of it. The explicit
        # contrast limits are load-bearing: without them napari scans the
        # whole array for min/max, paging the entire memmap into RAM.
        self._image_layer = self.viewer.add_image(
            tomogram,
            name=tomo_id,
            contrast_limits=self._contrast_limits(tomogram),
        )
        self._labels_layer = self.viewer.add_labels(
            segmentation, name=f"{tomo_id}_segmentation"
        )
        self._labels_layer.mouse_drag_callbacks.append(self._on_mouse_drag)

        # napari only sends mouse events to the *active* layer, so the click
        # callback above does nothing unless the labels layer is the one
        # selected in the layer list.
        self.viewer.layers.selection.active = self._labels_layer

        self.current_id = tomo_id
        # Revisiting a tomogram must show the picks made there earlier.
        self._refresh()
        self.widget.set_current_tomogram(tomo_id)

        count = len(self._voxel_counts[tomo_id])
        message = f"{tomo_id}: {count} objects. Click one to select it."
        self.widget.set_status(message)

    def selections(self):
        """Returns every tomogram's selected labels.

        Returns:
            dict[str, set[int]]: A copy, including tomograms with nothing
            selected (as empty sets).
        """
        return self._selection.as_dict()

    def close(self):
        """Removes the picker's layers and closes the open tomogram file.

        Call before the viewer itself is released. Safe to call twice.
        """
        self._unload_current()

    # ---- internals --------------------------------------------------------

    def _unload_current(self):
        """Removes the current layers, then closes the tomogram's file handle.

        The order matters: a memory-mapped array is only valid while its file
        handle is open, so the handle is closed only once napari no longer
        holds a layer that could try to draw from it.
        """
        for layer in (self._labels_layer, self._image_layer):
            if layer is None:
                continue
            try:
                if layer in self.viewer.layers:
                    self.viewer.layers.remove(layer)
            except Exception as error:
                # The viewer may already be torn down on the way out; the
                # handle still needs closing below, so do not stop here.
                print(f"[PickMe] WARNING: could not remove layer {layer.name}: {error}")
        self._labels_layer = None
        self._image_layer = None
        self.current_id = None

        if self._tomogram_handle is not None:
            self._tomogram_handle.close()
            self._tomogram_handle = None

    def _on_mouse_drag(self, layer, event):
        """Toggles the clicked object, ignoring drags (pan/zoom/rotate).

        napari calls this generator on mouse press, then resumes it at each
        `yield` for every move and finally for the release. Only a press and
        release within a few screen pixels of each other counts as a click,
        so dragging to pan or rotate never changes the selection.

        Args:
            layer (napari.layers.Labels): The layer that received the event.
            event: napari's read-only mouse event.
        """
        if event.button != 1:  # left button only
            return
        # In paint/fill/erase mode a click edits the segmentation; toggling a
        # selection on top of that would do two things at once. Only select
        # while the layer is in its normal navigation ("pan_zoom") mode.
        if layer.mode != "pan_zoom":
            return
        press_pos = tuple(event.pos)
        yield
        while event.type == "mouse_move":
            yield
        if not is_click(press_pos, tuple(event.pos)):
            return

        # In 3D, view_direction makes napari cast a ray into the volume and
        # return the first non-background label it hits.
        value = layer.get_value(
            event.position,
            view_direction=event.view_direction,
            dims_displayed=event.dims_displayed,
            world=True,
        )
        self._toggle(value)

    def _toggle(self, value):
        """Toggles one label of the current tomogram and redraws.

        Args:
            value: Label under the cursor as returned by `get_value` (an int,
                a numpy int, or None outside the data).
        """
        tomo_id = self.current_id
        if tomo_id is None:
            return
        if value is None or int(value) <= 0:
            self.widget.set_status("Clicked background — no object there.")
            return

        label = int(value)  # get_value may return a numpy int
        now_selected = self._selection.toggle(tomo_id, label)
        self._refresh()
        verb = "Selected" if now_selected else "Deselected"
        self.widget.set_status(f"{verb} label {label}.")
        print(f"[PickMe] {tomo_id} → selected labels: {self._selection.labels(tomo_id)}")

    def _on_remove_requested(self, label):
        if self.current_id is None:
            return
        self._selection.remove(self.current_id, label)
        self._refresh()
        print(
            f"[PickMe] {self.current_id} → selected labels: "
            f"{self._selection.labels(self.current_id)}"
        )

    def _on_clear_requested(self):
        if self.current_id is None:
            return
        self._selection.clear(self.current_id)
        self._refresh()
        print(f"[PickMe] {self.current_id} → selection cleared")

    def _refresh(self):
        """Recolours the labels layer and updates the panel's list."""
        tomo_id = self.current_id
        if tomo_id is None or self._labels_layer is None:
            return
        selected = self._selection.labels(tomo_id)
        self._labels_layer.colormap = DirectLabelColormap(
            color_dict=selection_colormap_dict(selected)
        )
        counts = self._voxel_counts.get(tomo_id, {})
        self.widget.set_selected_objects([(label, counts.get(label)) for label in selected])
