import glob
import numpy as np
import mrcfile
import napari
from qtpy.QtWidgets import QAbstractItemView, QTableView, QTableWidget, QPushButton

# ── your existing data loading ──────────────────────────────────────────────
tomogram_list = glob.glob('/Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/data/tomo_reconstruction/*10.00*')
filtered_seg_list = glob.glob('/Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/PickMe/outputs/extract/*mrc.gz')

data_dict = {}
for tomogram in tomogram_list:
    tomo_id_parts = tomogram.split('/')[-1].split('_')[:2]
    tomo_id = f'{tomo_id_parts[0]}_{tomo_id_parts[1]}'
    data_dict[tomo_id] = {'tomogram': tomogram}
    data_dict[tomo_id].update({'segmentation': seg for seg in filtered_seg_list if tomo_id in seg})

viewer = napari.Viewer()

# ── load all tomograms/segmentations ────────────────────────────────────────
for tomogram_id, data in data_dict.items():
    with mrcfile.open(data['tomogram'], mode='r') as f:
        tomogram_data = f.data.copy()
    with mrcfile.open(data['segmentation'], mode='r') as f:
        segmentation_data = f.data.copy()

    viewer.add_image(tomogram_data, name=tomogram_id)
    viewer.add_labels(segmentation_data, name=f'{tomogram_id}_segmentation')

# ── selection state ──────────────────────────────────────────────────────────
# Maps  tomo_id -> set of selected label IDs
selected_objects: dict[str, set[int]] = {tomo_id: set() for tomo_id in data_dict}

def _active_tomo_id() -> str | None:
    """Return the tomo_id of whichever labels layer is currently active."""
    layer = viewer.layers.selection.active
    if layer is not None and hasattr(layer, 'data') and '_segmentation' in layer.name:
        return layer.name.replace('_segmentation', '')
    return None


# ── connect to the table after the user clicks Run ──────────────────────────
dock_widget, plugin_widget = viewer.window.add_plugin_dock_widget(
    plugin_name='napari-skimage',
    widget_name='Regionprops (labels)'
)
def _find_table():
    """Search the plugin widget first, then all viewer dock widgets."""
    # Search inside the plugin widget's native Qt widget
    for cls in (QTableView, QTableWidget):
        table = plugin_widget.native.findChild(cls)
        if table is not None:
            print(f"[PickMe] Found table in plugin widget: {cls.__name__}")
            return table

    # Fallback: search every dock widget napari has registered
    for dock_name, dw in viewer.window._dock_widgets.items():
        native = dw.native if hasattr(dw, 'native') else dw
        for cls in (QTableView, QTableWidget):
            table = native.findChild(cls)
            if table is not None:
                print(f"[PickMe] Found table in dock widget: '{dock_name}' ({cls.__name__})")
                return table

    return None

_connected_table = None   # hold a reference so we can reconnect on subsequent Runs

def _on_run_clicked():
    global _connected_table

    table = _find_table()   # no argument needed now
    if table is None:
        print("[PickMe] Could not find regionprops table — try clicking Run first, or inspect dock widgets.")
        # Debug helper: print what dock widgets exist
        print(f"[PickMe] Current dock widgets: {list(viewer.window._dock_widgets.keys())}")
        return

    if _connected_table is not None and _connected_table is not table:
        try:
            _connected_table.selectionModel().selectionChanged.disconnect(_on_selection_changed)
        except RuntimeError:
            pass

    _connected_table = table
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.selectionModel().selectionChanged.connect(_on_selection_changed)

    headers = [table.model().headerData(i, 1) for i in range(table.model().columnCount())]
    print(f"[PickMe] Table connected. Columns: {headers}")

def _on_selection_changed():
    """Fired whenever the user clicks or deselects rows in the table."""
    tomo_id = _active_tomo_id()
    if tomo_id is None or _connected_table is None:
        return

    selected_objects[tomo_id].clear()
    seen_rows = set()
    for index in _connected_table.selectedIndexes():
        row = index.row()
        if row in seen_rows:
            continue
        seen_rows.add(row)

        # Label ID is typically in column 0 — verify from the print above
        item = _connected_table.model().index(row, 0).data()
        try:
            selected_objects[tomo_id].add(int(item))
        except (TypeError, ValueError):
            pass

    print(f"[PickMe] {tomo_id} → selected labels: {selected_objects[tomo_id]}")

# Find the Run button and connect to it
run_button = plugin_widget.native.findChild(QPushButton)
if run_button is not None:
    run_button.clicked.connect(_on_run_clicked)
else:
    print("[PickMe] Warning: could not find Run button — call _on_run_clicked() manually after running regionprops.")

# ── launch ───────────────────────────────────────────────────────────────────
napari.run()   # blocks here

# ── post-GUI: filter out tomograms where nothing was selected ────────────────
final_selection = {tomo: labels for tomo, labels in selected_objects.items() if labels}
print("\n=== Final selections ===")
for tomo, labels in final_selection.items():
    print(f"  {tomo}: {sorted(labels)}")