import numpy as np
import pandas as pd
import starfile
import mrcfile
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, center_of_mass
import seaborn as sns
from skimage.measure import regionprops, marching_cubes

import glob
import os
import sys
import math as m
from pathlib import Path
import re

from mrcfile.utils import data_shape_from_header

from . import sampling, utils, filter, plotting, angles
from .config import mgraph_suffix, star_suffix
from .utils.object_extraction import object_coords_by_label

"""Pipeline functions for the PickMe-EM CLI.

This module holds the high-level pipeline functions that ``cli.py`` dispatches
to for each subcommand: ``filter_objects`` (``filter_objects``),
``choose_object`` (``choose_objects``), ``particle_extract``
(``particle_extraction``), ``decompress``, and ``convert``. Each function sets
up its own job output directory under ``<output_root>/<job_name>/jobNNN`` (job
numbers zero-padded to 3 digits) and reports progress via ``print()`` and
``tqdm`` rather than a logging framework. Segmentation arrays are handled in
zyx axis order throughout; STAR file coordinate columns are written as X/Y/Z.
"""


# --- Setting up parameters and data structures ---

#will make a particle row dictionary in a for loop within the segmentation mesh - loop over vertices
full_data_dict = {} #dictionary associating tomogram, with objects, and the objects data

# This file will contain the pipeline
#Each function will be called by a subcommand in the CLI

#this function just ensures that if job number of 1 is provided, 001 is parsed
def _format_job_number(job_number):
    """Zero-pad a job number to 3 digits, e.g. ``1`` -> ``'001'``."""
    return f'{int(job_number):03d}'


def _tomogram_shape_and_voxel_size(path):
    """Read a tomogram's shape and voxel size without reading its voxels.

    Both of these live in the MRC header, which is the first 1024 bytes of the
    file. This matters more than it sounds: `mrcfile.open(path)` reads the
    *whole* file into RAM, so asking it for `mrc.data.shape` costs the full
    size of the tomogram — 5.5 GB for a 700x1400x1400 float32 volume — to
    learn three integers. That is what used to kill this pipeline on an 8 GB
    machine. `header_only=True` stops after the header, leaving `mrc.data` as
    None, and the numbers below come from the header instead.

    Args:
        path (str): Path to the tomogram, `.mrc` or a compressed `.mrc.gz` /
            `.mrc.bz2`.

    Returns:
        tuple: ``(shape_zyx, voxel_size)``. `shape_zyx` is a tuple of ints in
        **zyx** order, matching the array `mrcfile` would have produced had
        the data been read. `voxel_size` is the x voxel size in angstroms, as
        a float.
    """
    with mrcfile.open(path, mode='r', header_only=True) as mrc:
        #mrcfile's own header-to-shape helper, rather than reading nz/ny/nx
        #directly, so the shape is exactly the one mrcfile would have given
        #the data array — including its special cases for image stacks.
        shape_zyx = tuple(int(axis) for axis in data_shape_from_header(mrc.header))
        voxel_size = float(mrc.voxel_size.x)

    return shape_zyx, voxel_size


def _open_tomogram_for_display(path):
    """Open a tomogram for napari without reading it all into memory.

    A float32 tomogram at 1024x1440x500 is about 3 GB, and `choose_object`
    keeps every tomogram in the input directory open at once. Reading them in
    full exhausts RAM on a modest machine long before the viewer is shown.
    Memory-mapping instead leaves the voxels on disk and lets napari page in
    only the slices it actually draws.

    Only uncompressed `.mrc` files can be mapped, so a compressed file (or any
    other mapping failure) falls back to a normal in-memory read.

    Args:
        path (str): Path to the tomogram `.mrc` file.

    Returns:
        tuple: ``(handle, data)``. `data` is the voxel array, in zyx order.
        `handle` is the open mrcfile object the array is read through and must
        be kept alive for as long as the array is in use, then closed by the
        caller; it is None when the file was read into memory instead.
    """
    name = os.path.basename(path)
    try:
        handle = mrcfile.mmap(path, mode='r')
        return handle, handle.data
    except Exception as error:
        #Falling back to a full read is exactly what this function exists to
        #avoid, so always say so. A compressed file is an expected, benign
        #reason; anything else is reported with the underlying error, which for
        #a compressed file would otherwise read "not an MRC file, or file is
        #corrupt" and send the user hunting for a problem they do not have.
        if name.endswith(('.gz', '.bz2')):
            reason = 'it is compressed, and compressed data cannot be mapped'
        else:
            reason = str(error)
        print(
            f'[PickMe] WARNING: reading {name} fully into memory rather than '
            f'memory-mapping it — {reason}. This needs considerably more RAM; '
            'decompressing the tomogram first (PickMe decompress) avoids it.'
        )
        with mrcfile.open(path, mode='r') as mrc:
            return None, mrc.data.copy()


def _sampled_contrast_limits(array, max_sampled_voxels=5_000_000):
    """Estimate napari display contrast limits from a subsample of an array.

    napari needs a ``(min, max)`` pair to map voxel values onto screen
    intensity. Left to work it out itself it scans the array, which for a
    memory-mapped tomogram means paging the whole file in — undoing the point
    of mapping it. Striding over the array touches only a fraction of it.

    Args:
        array (numpy.ndarray): Image data in zyx order. May be a memmap.
        max_sampled_voxels (int, optional): Rough upper bound on how many
            voxels to read. Defaults to 5,000,000 (about 20 MB at float32).

    Returns:
        tuple: ``(low, high)`` floats. Falls back to a unit-width range when
        the sample is empty or flat, since napari rejects limits where the two
        values are equal.
    """
    #one stride shared across all axes, so an NxNxN array samples every
    #`step`-th voxel along each and reads roughly max_sampled_voxels in total
    step = max(1, int(round((array.size / max_sampled_voxels) ** (1 / array.ndim))))
    sample = array[(slice(None, None, step),) * array.ndim]

    if sample.size == 0:
        return (0.0, 1.0)

    low = float(np.min(sample))
    high = float(np.max(sample))
    if low == high:
        return (low, low + 1.0)
    return (low, high)

# --- Object extraction and filtering ---
def filter_objects(input_dir: str, filter_choice=None, output_dir=None, non_interactive=False):
    """Extract labeled objects from segmentation files and write filtered volumes.

    For each segmentation file found under `input_dir`, extracts labeled
    objects via `skimage.measure.regionprops`, applies volume-normalized
    knee-based filtering to drop small/noisy objects, and writes the filtered
    segmentation back out as a gzip-compressed MRC file
    (`<tomo_id>_filtered.mrc.gz`). Segmentation arrays are handled in zyx axis
    order throughout.

    Args:
        input_dir (str): Path, pathlike, to the directory containing all
            segmentation files to process.
        filter_choice: Currently unused — accepted but never read in this
            function's body. Reserved for a future filtering-mode option.
            Defaults to None.
        output_dir (str, optional): Root directory for pipeline outputs. Job
            output is written to `<output_dir>/filter/jobNNN`. Defaults to
            `./outputs` when None.
        non_interactive (bool, optional): If True, skip the "are there
            specific tomograms you want to process?" prompt and process
            every segmentation file found. Set this when running under a
            batch scheduler, where there is no terminal for `input()` to
            read from. Defaults to False.

    Returns:
        None: This function does not return a value. Filtered segmentations
            are written to disk as gzip-compressed `_filtered.mrc.gz` files
            under the job output directory; nothing is written to CSV.

    Note:
        Progress and a per-tomogram object count summary are printed via
        `print()` and `tqdm`, not a logging framework.
    """
    # --- Making output directories
    output_directory = utils.check_make_dir(directory=output_dir, job_name='filter')
    #Get all objects
    files = utils.choose_tomograms(segmentation_directory=input_dir, non_interactive=non_interactive)

    #Only the short per-tomogram summary lines are carried out of the loop.
    #Each tomogram's objects are written to disk inside the loop and then
    #dropped, because a skimage RegionProperties holds a reference to the whole
    #label image it was measured from — keeping one tomogram's objects alive
    #keeps that tomogram's entire segmentation array alive with it. Collecting
    #them all up first, as this used to, meant every segmentation in the input
    #directory was resident in RAM simultaneously.
    summary_lines = []

    # --- Begin processing
    print('Extracting objects and writing filtered segmentations to mrc.gz...')
    with tqdm(total=len(files), desc='Running Extraction', unit='Tomogram', leave=True) as pbar:
        for file in files:
            try:
                mgraph = utils.get_mgraph(file)
                with mrcfile.open(file, mode='r') as mrc:
                    segmentation = mrc.data.copy()
                    pix_size = mrc.voxel_size.x
                shape_zyx = segmentation.shape

                #add progress bar update
                pbar.set_postfix_str(f'Processing {mgraph}... | shape (zyx)={shape_zyx}')

                #getting out the objects of the tomograms and filtering out noise
                objects_dict, volumes = utils.object_extraction(segmentation)
                objects_filtered = filter.knee_detection(objects_dictionary=objects_dict, volume_array=volumes, micrograph=mgraph, output=output_directory)

                summary_lines.append(
                    f'\nFor tomogram {mgraph}, {len(objects_filtered)} objects were '
                    f'selected. Objects: {list(objects_filtered.keys())}'
                )

                # --- Write this tomogram's filtered segmentation straight out
                #`dtype=np.int8` is load-bearing. Without it np.zeros defaults
                #to float64, which for a 700x1400x1400 volume is 11 GB, and the
                #.astype(np.int8) that used to follow allocated the int8 array
                #on top of it rather than in place — so both were resident at
                #once. Labels are small integers and only ever need int8.
                #
                #The shape and voxel size come from *this* file. They used to be
                #read in this loop but used in a second loop after it, where
                #they still held whatever the last file processed had set, so
                #every output silently took the last tomogram's dimensions.
                filtered_array = np.zeros(shape_zyx, dtype=np.int8)
                #now go through all the objects, get their coordinates and labels and put them back in
                for object in objects_filtered.values():
                    coords = object.coords
                    pix_label = object.label
                    filtered_array[coords[:, 0], coords[:, 1], coords[:, 2]] = pix_label

                #now write a new mrc file
                tomo_name = mgraph.split('.')[0]
                out_path = f'{os.path.join(output_directory, tomo_name)}_filtered.mrc.gz'
                with mrcfile.new(name=out_path, compression='gzip', overwrite=True) as mrc:
                    mrc.set_data(filtered_array)
                    mrc.voxel_size = pix_size
            except Exception as e:
                print(f'There was an error with file:{file}')
                print(f'Error: {e}')
                raise(e)
            finally:
                #Drop this tomogram's arrays before the next one is read, so
                #peak memory is one segmentation rather than all of them.
                segmentation = None
                objects_dict = None
                objects_filtered = None
                filtered_array = None
                #update bar
                pbar.update(1)

    # --- Print out the results of the extraction
    for line in summary_lines:
        print(line)
    print('\n\nExtraction complete!')
    print(f'\n\nAll filtered segmentations have been written to gzipped mrc files in {output_directory}!')
    #not sure to return full date or not
    return None


# --- Object choice with Napari plugin --- 

def choose_object(input_dir:str, segmentation_dir = None, input_job=None, output_dir=None, write_selections=False, non_interactive=False):
    """Let a user pick which filtered objects to keep, per tomogram.

    Unless `non_interactive` is set, begins by prompting interactively via
    `input()`: "Are there any objects which you would like to select (y/n)?"
    The answer determines which path runs, and the user can only choose from
    objects that already passed the volume-based knee filter in
    `filter_objects`:

    - **yes**: Opens a napari viewer (with the napari-skimage Regionprops
      widget) loaded with each tomogram and its filtered segmentation, and
      blocks on `napari.run()` until the viewer window is closed. Labels
      selected in the Regionprops table are kept. After the viewer closes,
      the kept objects are written out — as a single gzip-compressed
      `<tomo_id>_filtered_chosen.mrc.gz` per tomogram (voxels set to each
      object's label value) if `write_selections` is False, or as individual
      uncompressed `TS_<tomo_id>_membranes/TS_<tomo_id>_obj<label>.mrc` files
      (voxels set to 1, not the label value) if `write_selections` is True.
    - **no** + `write_selections=True`: Writes every object already present in
      the filtered segmentation set (no further narrowing by selection) out
      as its own uncompressed
      `TS_<tomo_id>_membranes/TS_<tomo_id>_obj<label>.mrc` file (voxels set
      to 1).
    - **no** + `write_selections=False`: Leaves the filtered files untouched
      and only prints their location.

    The output of this function feeds into `particle_extract`. Segmentation
    arrays are handled in zyx axis order throughout.

    Args:
        input_dir (str): Path, pathlike, to a tomogram file or a directory of
            tomogram `.mrc` files — the reconstructions the segmentations were
            performed on.
        segmentation_dir (str, optional): Directory of segmentation `.mrc`
            files to choose objects from, for users supplying their own
            segmentations outside the pipeline. Defaults to None, which
            sources segmentations from `input_job` or the latest
            `filter_objects` job instead.
        input_job (str or int, optional): A specific `filter_objects` job
            number to source filtered segmentations from (e.g. `1` or
            `'001'`). Ignored if `segmentation_dir` is given. Defaults to
            None.
        output_dir (str, optional): Root directory for pipeline outputs. Job
            output is written to `<output_dir>/choose/jobNNN`. Changing this
            from the pipeline default is not recommended. Defaults to None
            (`./outputs`).
        write_selections (bool, optional): If True, write each kept object
            out as its own uncompressed `.mrc` file (voxels set to 1) instead
            of one combined gzip-compressed segmentation per tomogram.
            Defaults to False.
        non_interactive (bool, optional): If True, skip the prompt and take
            the "no" path — the napari viewer is never opened. This is the
            only sensible batch behaviour: picking objects visually needs a
            display, which batch nodes do not have (see docs/gui-setup.md).
            Defaults to False.

    Returns:
        None: This function does not return a value; results are written to
            disk (or left untouched) as described above.

    Note:
        Every tomogram found is loaded into the viewer at once and stays there
        until it closes. Tomograms are memory-mapped so their voxels stay on
        disk, but segmentations are gzip-compressed and must be decompressed
        into RAM, so peak memory still scales with the number of tomograms in
        the input directory.

    Note:
        Unless `non_interactive` is set, this function prompts via `input()`
        before doing anything else. When the user answers "yes", it also
        lazily imports `napari` and `qtpy` (only inside that branch, since
        they are optional GUI dependencies) and blocks until the napari
        window is closed.
    """
    #ask user if they want specific objects
    #under --non-interactive there is no display to open napari onto, so take the "no" path
    if non_interactive:
        print('Non-interactive mode: skipping napari object selection.')
        ask_user = False
    else:
        ask_user = input('Are there any objects which you would like to select (y/n)?')
        while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
            print('Answer must be yes or no!')
            ask_user = input('Which objects of interest would you like to select from the filtered set for processing?')
        if ask_user.lower() in ['y', 'yes']:
            ask_user = True
        elif ask_user.lower() in ['n', 'no']:
            ask_user = False

    #--- setting up directories and data structures
    #getting directories sorted so we can dispatch outputs
    output_directory = utils.check_make_dir(directory=output_dir, job_name='choose')
    if os.path.isfile(input_dir):
        tomogram_list = [input_dir]
    elif os.path.isdir(input_dir):
        tomogram_list = glob.glob(os.path.join(input_dir, '*.mrc')) #this assumes that the tomograms are in mrc format - we can change this to be more flexible if needed
    outputs_root = utils.get_output_root(output_dir)
    if segmentation_dir is None and input_job is None:
        extract_jobs = sorted(
            [job for job in (outputs_root / 'filter').glob('job[0-9][0-9][0-9]') if job.is_dir()]
        )
        if extract_jobs:
            filtered_seg_list = glob.glob(str(extract_jobs[-1] / '*filtered*'))
        else:
            filtered_seg_list = glob.glob(str(outputs_root / 'filter' / '*filtered*'))
    elif segmentation_dir is None and isinstance(input_job, (str, int)):
        input_job = _format_job_number(input_job)
        path_to_outputs = outputs_root
        filtered_seg_list = list(path_to_outputs.glob(f'**/job{input_job}/*.mrc*'))
        filtered_seg_list = [str(f) for f in filtered_seg_list]
    elif segmentation_dir is not None:
        if os.path.isdir(segmentation_dir):
            filtered_seg_list = glob.glob(f'{segmentation_dir}/*.mrc*') 
        elif os.path.isfile(segmentation_dir):
            filtered_seg_list = [segmentation_dir]
    
    #create a data dictionary to store the tomogram and segmentation file paths for a particular tomogram
    data_dict={} #this could be changed to a class
    valid_id = [seg.split('/')[-1].split('_')[1] for seg in filtered_seg_list] #we only want the tomograms that are in extract job
    for tomogram in tomogram_list:
        tomo_id = str(tomogram).split('/')[-1].split('_')[1]
        if tomo_id in valid_id:
            data_dict[tomo_id] = {'tomogram': tomogram}
            data_dict[tomo_id].update({'segmentation': seg for seg in filtered_seg_list if tomo_id in seg})

    if ask_user == True:
        #Imports - remove it from top level as these are only needed if user wants to select specific objects and we want to avoid unnecessary imports if they don't
        #(Qt itself is only touched inside gui/napari_compat.py.)
        #
        #The GUI stack is an optional extra: `pip install PickMe-EM` deliberately
        #leaves napari and Qt out so headless and cluster installs stay small, and
        #only `PickMe-EM[gui]` pulls them in. That makes a missing napari an
        #ordinary, expected situation rather than a broken install, so it is
        #caught here and explained. It has to be caught at the import itself —
        #napari_compat.check_gui_versions() below cannot help, because reaching
        #it already requires the import to have succeeded.
        #napari_compat itself imports nothing heavier than the standard library,
        #so it is safe to bring in first and gives us the shared docs pointer to
        #quote if napari turns out to be missing.
        from .gui import napari_compat

        try:
            import napari
        except ImportError as error:
            message = (
                'Object selection needs the optional GUI dependencies (napari, '
                'napari-skimage, qtpy, PyQt6, vispy), and they are not installed '
                f'in this environment — {error}.\n'
                '  Install them with:  pip install "PickMe-EM[gui]"\n'
                '  or recreate the conda environment from PickMe.yml, which '
                'installs them by default.\n'
                '  On a cluster, or any machine without a display, pass '
                '--non-interactive instead. That skips the napari step entirely '
                'and lets the rest of the pipeline run.\n'
                f'  {napari_compat.DOCS_HINT}'
            )
            print(f'[PickMe] ERROR: {message}')
            raise RuntimeError(message) from error

        #Check the GUI stack before opening a window. napari-skimage is driven
        #through private Qt internals (see gui/napari_compat.py), so a version
        #outside the pinned range is reported here rather than showing up later
        #as an empty selection.
        napari_compat.check_gui_versions()
        napari_compat.check_display()

        #instantiate the napari viewer
        viewer = napari.Viewer()

        #Load all tomograms and their segmentations into napari viewer.
        #
        #Every layer added here stays resident until the viewer closes, so this
        #loop holds the whole input directory in memory at once. Tomograms are
        #memory-mapped (see _open_tomogram_for_display) so their voxels stay on
        #disk; the mapping is only valid while its handle is open, so handles
        #are collected here and closed after napari.run() returns rather than
        #by a `with` block.
        open_tomogram_handles = []

        for tomogram_id, data in data_dict.items():
            handle, tomogram_data = _open_tomogram_for_display(data['tomogram'])
            if handle is not None:
                open_tomogram_handles.append(handle)

            #Segmentations are gzip-compressed (.mrc.gz), and compressed data
            #cannot be memory-mapped — it has to be decompressed into RAM.
            #They are int8 label arrays, so roughly a quarter the size of the
            #float32 tomogram they came from.
            with mrcfile.open(data['segmentation'], mode='r') as f:
                segmentation_data = f.data.copy()

            viewer.add_image(
                tomogram_data,
                name=tomogram_id,
                contrast_limits=_sampled_contrast_limits(tomogram_data),
            )
            viewer.add_labels(segmentation_data, name=f'{tomogram_id}_segmentation')
        
        # --- Interfacing with napari to select objects of interest directly from napari
        # Maps  tomo_id -> set of selected label IDs
        selections: dict[str, set[int]] = {tomo_id: set() for tomo_id in data_dict}

        def _analysed_tomo_id() -> str | None:
            """Return the tomo_id of the labels layer the table describes.

            Asks the plugin which layer it last analysed, rather than which
            layer the viewer has active — the table's rows belong to the
            analysed layer, and the active layer changes every time the user
            clicks something else in the layer list.
            """
            layer = napari_compat.analysed_labels_layer(plugin_widget)
            if layer is None:
                layer = viewer.layers.selection.active  # fallback
            if layer is not None and '_segmentation' in getattr(layer, 'name', ''):
                return layer.name.replace('_segmentation', '') #this just ensures that we have the tomogram id - TS_xyxy
            return None

        # ── connect to the table after the user clicks Analyze ──────────────────────────
        #Raises NapariCompatError, naming the expected version, if the widget has moved.
        dock_widget, plugin_widget = napari_compat.add_regionprops_widget(viewer)

        _connected_table = None   # hold a reference so we can reconnect on subsequent runs
        _label_column = None      # which column of the table holds the label ID

        def _on_analysis_finished():
            """Wire PickMe into the results table after each Analyze run."""
            nonlocal _connected_table, _label_column

            table = napari_compat.find_regionprops_table(viewer, plugin_widget)
            if table is None:
                print("[PickMe] Could not find the regionprops table — click Analyze first.")
                # Debug helper: print what dock widgets exist
                print(f"[PickMe] Current dock widgets: {napari_compat.dock_widget_names(viewer)}")
                return

            #The label column moves depending on which properties were ticked,
            #because regionprops_table sorts its columns alphabetically.
            _label_column = napari_compat.find_label_column(table)
            headers = napari_compat.table_headers(table)
            if _label_column is None:
                print(
                    "[PickMe] WARNING: no 'label' column in the results table "
                    f"(columns: {headers}). Tick 'label' in the plugin's "
                    'Properties list, then click Analyze again — selections '
                    'cannot be matched to objects without it.'
                )
                return

            #Reconnect only when the table object itself changed; connecting
            #twice to the same table would fire the handler twice per click.
            if _connected_table is not table:
                if _connected_table is not None:
                    try:
                        _connected_table.selectionModel().selectionChanged.disconnect(
                            _on_selection_changed
                        )
                    except (RuntimeError, TypeError):
                        pass
                _connected_table = table
                napari_compat.configure_table_selection(table)
                table.selectionModel().selectionChanged.connect(_on_selection_changed)

            print(
                f'[PickMe] Table connected for {_analysed_tomo_id()}. '
                f"Columns: {headers} (label in column {_label_column}). "
                'Click rows to choose objects; ctrl/cmd-click or shift-click '
                'for several.'
            )

        def _on_selection_changed(*_args):
            """Fired whenever the user clicks or deselects rows in the table."""
            tomo_id = _analysed_tomo_id()
            if tomo_id is None or tomo_id not in selections or _connected_table is None:
                return
            if _label_column is None:
                return

            if not napari_compat.table_is_alive(_connected_table):
                #The viewer is closing — whatever was selected before the
                #window went away is still the user's answer.
                return

            indexes = _connected_table.selectedIndexes()
            if not indexes:
                #Qt also fires an empty selection just before it repopulates or
                #destroys the table, and at this instant that is indistinguishable
                #from the user deselecting everything. Clearing now would throw
                #away a selection they had already made, so re-check on the next
                #event-loop tick, once the repopulation or teardown has finished.
                napari_compat.defer(_confirm_deselection)
                return

            labels = set()
            for row in {index.row() for index in indexes}:
                label = napari_compat.read_label_cell(_connected_table, row, _label_column)
                if label is not None:
                    labels.add(label)

            selections[tomo_id] = labels
            print(f"[PickMe] {tomo_id} → selected labels: {sorted(labels)}")

        def _confirm_deselection():
            """Clear a tomogram's selection, but only if the user really did."""
            tomo_id = _analysed_tomo_id()
            if tomo_id is None or tomo_id not in selections or _connected_table is None:
                return
            if not napari_compat.table_is_alive(_connected_table):
                return  # viewer closed — keep what was selected
            if _connected_table.selectedIndexes():
                return  # something is selected after all
            if _connected_table.model().rowCount() == 0:
                return  # the table was emptied, not deselected
            if not selections[tomo_id]:
                return  # nothing to clear, no need to say so
            selections[tomo_id] = set()
            print(f'[PickMe] {tomo_id} → selection cleared')

        connected_via = napari_compat.connect_analysis_finished(
            plugin_widget, _on_analysis_finished
        )
        if connected_via is None:
            print(
                '[PickMe] WARNING: could not connect to the plugin — no Analyze '
                'button or `called` signal was found, so selections cannot be '
                f'recorded. {napari_compat.DOCS_HINT}'
            )
        else:
            print(f'[PickMe] Listening for regionprops runs via the {connected_via}.')
            print(
                '[PickMe] In napari: pick the labels layer, tick at least '
                "'label' under Properties, click Analyze, then select rows in "
                'the Results Table. Close the viewer when you are done.'
            )

        # ── launch ───────────────────────────────────────────────────────────────────
        try:
            napari.run()   # blocks here
        finally:
            #Releasing the viewer is required for correctness, not tidiness: a
            #viewer left registered with vispy makes the *next* viewer in the
            #same session fail to render ("Cannot SIZE object N because it does
            #not exist"). See napari_compat.release_viewer for the mechanism.
            #In `finally` so a crash inside the GUI cannot leak the canvas.
            napari_compat.release_viewer(viewer)

            #napari read the tomograms straight off disk through these handles,
            #so they can only be released now the viewer is gone. The selection
            #is written out below by re-reading the segmentations from disk, so
            #nothing after this point depends on the mapped arrays.
            for handle in open_tomogram_handles:
                handle.close()
            open_tomogram_handles.clear()

        # ── post-GUI: filter out tomograms where nothing was selected ────────────────
        final_selection = {tomo: labels for tomo, labels in selections.items() if labels}
        print("\n=== Final selections ===")
        if not final_selection:
            print(
                '  nothing was selected — no files will be written.\n'
                "  To select objects: choose the labels layer, tick 'label' in "
                'the plugin Properties list, click Analyze, then click rows in '
                'the Results Table before closing the viewer.'
            )
        for tomo, labels in final_selection.items():
            print(f"  {tomo}: {sorted(labels)}")



        # --- Applying the selection and writing out files ---------------------
        #Extraction and writing are deliberately one loop. Doing all the
        #extraction first, as this used to, meant every tomogram's objects were
        #held until the last file had been read — and a skimage
        #RegionProperties keeps a reference to the whole label image it was
        #measured from, so that pinned every segmentation array in RAM at once.
        #Here each tomogram is read, written, and released before the next one
        #is touched, so peak memory is one tomogram's worth however many there
        #are.
        #
        #Tomograms nobody selected anything in are skipped outright; they used
        #to be read and fully analysed only for the result to be discarded.
        print('Extracting selected objects and writing them to disk...')

        with tqdm(total=len(final_selection), desc='Writing', unit='Tomogram', leave=True) as pbar:
            for tomo_id, chosen_labels in final_selection.items():
                try:
                    pbar.set_postfix_str(f'Processing tomogram: {tomo_id}...')

                    tomogram_path = data_dict.get(tomo_id)['tomogram']
                    if tomogram_path is None:
                        print(f'Warning: no matching tomogram found for {tomo_id}')
                        continue

                    segmentation_path = data_dict.get(tomo_id)['segmentation']
                    with mrcfile.open(segmentation_path, mode='r') as mrc:
                        segmentation = mrc.data.copy()

                    #Take the coordinates of the chosen objects only, then drop
                    #the segmentation array so it can be garbage collected
                    #before the (much larger) output array is allocated below.
                    chosen_coords = object_coords_by_label(segmentation, labels=chosen_labels)
                    segmentation = None
                    if not chosen_coords:
                        continue

                    #The output copies its shape and voxel size from the
                    #tomogram, and both of those live in the 1 KB MRC header.
                    #Opening the tomogram the normal way would read all 5.5 GB
                    #of its voxels just to reach them — that is what used to
                    #kill this loop at "Writing: 0%".
                    shape_zyx, pix_size = _tomogram_shape_and_voxel_size(tomogram_path)
                    pbar.set_postfix_str(f'Processing {tomo_id} | shape (zyx)={shape_zyx}')

                    if write_selections == False:
                        choice_array = np.zeros(shape_zyx, dtype=np.int8)
                        #One combined segmentation per tomogram, with each
                        #object painted in at its own label value.
                        for label, coords in chosen_coords.items():
                            zcoords, ycoords, xcoords = coords[:, 0], coords[:, 1], coords[:, 2]
                            choice_array[zcoords, ycoords, xcoords] = label

                        out_path = os.path.join(output_directory, f'TS_{tomo_id}_filtered_chosen.mrc.gz')
                        with mrcfile.new(out_path, compression = 'gzip', overwrite=True) as new_file:
                            new_file.set_data(choice_array)
                            new_file.voxel_size = pix_size
                    elif write_selections == True:
                        print(f'\n\nWriting out each selected object as a separate mrc file in {output_directory} for membrane sampling...')
                        out_dir = os.path.join(output_directory, f'TS_{tomo_id}_membranes')
                        os.makedirs(out_dir, exist_ok=True)
    
                        #One array reused across every object in this tomogram. It
                        #used to be reallocated per object, which meant two
                        #full-size arrays existed at once on every reset.
                        choice_array = np.zeros(shape_zyx, dtype=np.int8)
                        for coords in chosen_coords.values():
                            zcoords, ycoords, xcoords = coords[:, 0], coords[:, 1], coords[:, 2]
                            choice_array[zcoords, ycoords, xcoords] = 1
                            out_path = os.path.join(out_dir, f'TS_{tomo_id}_obj{label}.mrc') #could change this to mrc.gz -> for the purpsoe of doing membrain, will leave it as mrc - will change to give user an option
                            with mrcfile.new(out_path, overwrite=True) as new_file:
                                new_file.set_data(choice_array)
                                new_file.voxel_size = pix_size
                            choice_array.fill(0) #reset for next object

                except Exception as e:
                    print(f'Error with file: {tomo_id}\n{e}')
                    raise
                finally:
                    #Release the large arrays before the next tomogram is read.
                    #one tomogram done — this update used to sit inside the
                    #object loop, so the bar ran past its own total
                    segmentation = None
                    chosen_coords = None
                    choice_array = None
                    pbar.update(1)

        if write_selections == False:
            print(f'\n\nAll object data has been written to gzipped mrc files in {output_directory}!')
        elif write_selections == True:
            print(f'\n\nAll selected objects have been written to mrc files in {output_directory}!')

        return None
    

# --- Meshing of objects, particle extraction and  angle assignments ----
def particle_extract(sample_rate: int, cmm: bool, input_dir=None, input_job=None, output_dir=None):
    """Mesh filtered objects, sample surface points, and write particle STAR files.

    For each segmentation file (sourced from `input_dir`, `input_job`, or the
    latest `choose_objects` job), particle extraction:

    - Gaussian-smooths each labeled object so marching cubes produces a
      smoother surface mesh.
    - Runs marching cubes to build a triangular mesh across the object.
    - Samples mesh points at a minimum spacing of `sample_rate`.
    - Computes Euler angles from each sampled point's surface normal and
      assembles particle data entries.
    - Writes a per-tomogram `<name>.star` file, then folds those rows into an
      aggregate `particles.star` covering every tomogram processed.
    - Writes per-tomogram angle diagnostic plots.
    - Optionally writes particle coordinates and normals to a Chimera `.cmm`
      file per tomogram.

    STAR coordinate columns are written as X/Y/Z, even though the underlying
    segmentation arrays are handled in zyx axis order.

    Args:
        sample_rate (int): Minimum enforced distance, in pixels, between
            sampled particle points on an object's surface.
        cmm (bool): Whether to also write particle coordinates and normals to
            a Chimera `.cmm` file per tomogram.
        input_dir (str, optional): Directory of segmentation files to process
            (`.mrc`, `.mrc.gz`, or `.mrc.bz2`). Defaults to None, in which
            case `input_job` (if given) or the latest `choose_objects` job is
            used instead.
        input_job (str or int, optional): A specific `choose_objects` job
            number to source chosen segmentations from (e.g. `1` or `'001'`).
            Takes priority over `input_dir` when both would otherwise apply.
            Defaults to None.
        output_dir (str, optional): Root directory for pipeline outputs. Job
            output is written to `<output_dir>/particle_extraction/jobNNN`.
            Defaults to None (`./outputs`).

    Returns:
        None: This function does not return a value; results are written to
            disk as per-tomogram `.star` files, an aggregate `particles.star`,
            angle plots, and optional `.cmm` files.

    Raises:
        TypeError: If `cmm` is not a `bool`.
        RuntimeError: If `input_dir` is None, no usable `input_job` is given,
            and no prior `choose_objects` job exists to fall back on.

    Note:
        Progress and a per-tomogram particle count summary are printed via
        `print()` and `tqdm`, not a logging framework.
    """
    # --- Type checking
    if not isinstance(cmm, bool):
        print('If CMM argument is provided, it must be True or False')
        raise(TypeError)
    
    
    # --- Data structures
    #instantiate the data structure to be used to write the star file
    #other entries we could add LCCmax, CutOff, SearchStd, DetectorPixelSize - but these are more relevant for template matching and we don't have this data at this stage, so we will leave them blank for now
    star_dict = {'rlnCoordinateX':[],
                'rlnCoordinateY':[],
                'rlnCoordinateZ':[],
                'rlnOriginX':[],
                'rlnOriginY':[],
                'rlnOriginZ':[],
                'rlnAngleRot':[],
                'rlnAngleTilt':[],
                'rlnAnglePsi':[],
                'rlnMicrographName':[]} #This is .tomostar files -> TS_1234.tomostar

    total_star_df = pd.DataFrame.from_dict(star_dict)
    tomogram_star_df = total_star_df.copy()

    #set the output directory
    output_directory = utils.check_make_dir(job_name='particle_extraction', directory=output_dir)
    #check which job number we are on
    outputs_root = utils.get_output_root(output_dir)
    choose_jobs = sorted([job for job in (outputs_root / 'choose').glob("**/job[0-9][0-9][0-9]") if job.is_dir()])
    # ---- Getting files
    if isinstance(input_job, (str, int)):
        input_job = _format_job_number(input_job)
        path_to_outputs = outputs_root
        files = list(path_to_outputs.glob(f'**/job{input_job}/**/*.mrc*'))
        files = [str(f) for f in files]
    elif input_dir is None and choose_jobs: #choose obs has to return something - i.e., the choose job has to be run at least once prior if no input directory is provided
        #retrieve the files from the output/choose directory - latest job
        files = list(choose_jobs[-1].glob('*chosen*')) #we use glob method with Posix Path as it is a Path object, not a string
    elif input_dir is None and not choose_jobs:
        raise RuntimeError('choose_object job must be run if you are to provide no input directory')
    #possibility of having input dir
    else:
        print('WARNING: files must be in mrc, mrc.gz, mrc.bz2')
        files = glob.glob(f'{input_dir}/*mrc') + glob.glob(f'{input_dir}/*mrc.gz') + glob.glob(f'{input_dir}/*mrc.bz2')

    #cmm_ask = input('Do you want to ouptut the particle coordinates and normals into a .cmm file?')
    print(f'Processing {len(files)} files now....\n')

    # --- Begin processing
    with tqdm(total=len(files), desc='Extracting particles', unit='file', dynamic_ncols=True,
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [Elapsed(s):{elapsed}<>Remaining(s):{remaining}, {rate_fmt}] {postfix}') as pbar:
        try:
            for file in files:
                per_tomo_data = pd.DataFrame.from_dict({})
                # --- open up segmentation file and extract pixel size and data
                with mrcfile.open(file) as mrc:
                    #No .copy(): mrcfile has already read the file into its own
                    #array, so copying it only doubles the peak. The array stays
                    #valid after the handle closes (it owns its buffer); it is
                    #read-only, which regionprops is perfectly happy with.
                    mrc_data = mrc.data
                    shape_zyx = mrc_data.shape
                    pixel_size = mrc.voxel_size.x
                # Obtain objects from segmentations
                objects_dict, _ = utils.object_extraction(mrc_data)
                tomo_name = utils.get_mgraph(file, caller='particle_extract') #this is .tomostar file

                for object in objects_dict.values():
                    #Work on a crop around the object rather than a
                    #tomogram-sized array. The old version allocated a full
                    #volume per object and then smoothed `.astype(float)` —
                    #float64 — which is 11 GB for a 700x1400x1400 tomogram, for
                    #every object in turn.
                    #
                    #The crop is safe because a Gaussian has finite reach:
                    #scipy truncates the kernel at `truncate` (4.0 by default)
                    #standard deviations, so with sigma=3.0 no voxel influences
                    #another more than 12 away. Padding the bounding box by more
                    #than that means the smoothed values anywhere near the
                    #object — which is everywhere the surface can appear — are
                    #identical to smoothing the whole tomogram.
                    min_z, min_y, min_x, max_z, max_y, max_x = object.bbox
                    pad = 16
                    z0, y0, x0 = max(min_z - pad, 0), max(min_y - pad, 0), max(min_x - pad, 0)
                    z1 = min(max_z + pad, shape_zyx[0])
                    y1 = min(max_y + pad, shape_zyx[1])
                    x1 = min(max_x + pad, shape_zyx[2])

                    object_array = np.zeros((z1 - z0, y1 - y0, x1 - x0), dtype=np.int8)
                    #`object.image` is this object's mask within its own bounding
                    #box, so it drops straight in — same result as painting the
                    #object's coordinates one at a time, without building the
                    #coordinate array.
                    object_array[min_z - z0:max_z - z0,
                                 min_y - y0:max_y - y0,
                                 min_x - x0:max_x - x0] = object.image
                    #gaussian smooth all of the objects in the mrc files
                    smooth_object = gaussian_filter(object_array.astype(float), sigma=3.0)

                    # -- Perform marching cubes and particle extraction
                    #This creates a triangular mesh
                    verts, _, normals, _ = marching_cubes(volume=smooth_object)
                    #Marching cubes worked in the crop's own coordinates, so
                    #shift the vertices back into full-tomogram zyx coordinates.
                    #Normals are directions, so translation leaves them alone.
                    verts = verts + np.array([z0, y0, x0], dtype=verts.dtype)
                    # -- enforce grid sampling here
                    particle_dict = sampling.non_random_membrane_sampling(coords=verts, normal_vectors=normals, grid_sampling=sample_rate)
                    # -- calculate euler angles and other data needed for star file
                    data_entries = angles.euler_star(centre_of_mass=object.centroid, particles=particle_dict, label=int(object.label), micrograph=tomo_name, tomo_dimensions=shape_zyx, psize=pixel_size)
                    per_tomo_data = pd.concat([per_tomo_data, pd.DataFrame.from_dict(data_entries)], ignore_index=True)

                #Write out a star file, per tomogram
                tomogram_star_df = pd.DataFrame.from_dict(per_tomo_data)
                #Write out angles plots for each tomogram
                plotting.plot_angles(star_data=tomogram_star_df, output_dir=output_directory, tomogram_name=tomo_name)
                # --- Write out star files per tomogram
                starfile.write(tomogram_star_df, f'{output_directory}/{tomo_name.removesuffix(".tomostar")}.star')
                total_star_df = pd.concat([total_star_df, tomogram_star_df], ignore_index=True)
                # --- Write out .cmm files
                if cmm == True:
                    utils.cmm_write(data = tomogram_star_df, tomogram_name=tomo_name, output_directory=output_directory, sampling=sample_rate)
                #When we finish one tomogram, update progress bar
                pbar.update(1)
        except Exception as e:
            raise(e)
    # Write out a starfile with all objects and particles across all tomograms processed
    starfile.write(total_star_df, os.path.join(output_directory, 'particles.star'))
    print(f'\nAll particle data has been written to star files in {output_directory}!')

    # --- Print out the total number of particles sampled across all tomograms and objects
    particle_overview = dict(total_star_df['rlnMicrographName'].value_counts()) #counts how many particles retrieved in each micrograph
    print('\n')
    for tomogram, particle_count in particle_overview.items():
        print(f'Tomogram: {tomogram} | Particles samples: {particle_count}')
    print(f'\nTotal Particles sampled: {total_star_df.shape[0]}')

    return None

        

def decompress(input_dir=None, input_job=None, output_dir=None, non_interactive=False):
    """Decompress gzip/bzip2 MRC segmentations for viewing in Chimera/ChimeraX.

    This package writes segmentation outputs in compressed MRC formats (see
    `filter_object`, `choose_object`), which most viewers cannot open
    directly. This function decompresses a set of them back to plain `.mrc`.
    Users can call it to decompress any selected tomogram from any part of
    the pipeline, not strictly in a linear fashion. It always prompts
    interactively via `input()`, first printing the available tomograms, then
    asking whether to decompress all of them or only a user-specified subset
    of tomogram IDs.

    Args:
        input_dir (str, optional): Directory, pathlike, containing the
            `.mrc.gz` or `.mrc.bz2` files to decompress. Ignored if
            `input_job` is given. Defaults to None.
        input_job (str or int, optional): Alternatively, a specific pipeline
            job number to source compressed files from (e.g. `1` or `'001'`),
            searched across all job types under the output root. Defaults to
            None.
        output_dir (str, optional): Root directory for pipeline outputs. Job
            output is written to `<output_dir>/decompress/jobNNN`. Defaults
            to None (`./outputs`).
        non_interactive (bool, optional): If True, skip the prompt and
            decompress every file found. Set this when running under a batch
            scheduler, where there is no terminal for `input()` to read from.
            Defaults to False.

    Returns:
        None: This function does not return a value; decompressed files are
            written to disk as `TS_<tomo_id>_decompressed.mrc`.

    Raises:
        RuntimeError: If both `input_dir` and `input_job` are None.

    Note:
        Unless `non_interactive` is set, this function prompts via `input()`
        to ask which tomograms, if any, decompression should be restricted
        to.
    """
    if input_dir is None and input_job is None:
        raise RuntimeError('A directory or Job number must be provided for this job')
    
    output_directory = utils.check_make_dir(job_name='decompress', directory=output_dir)

    #create file list if user provides job
    if isinstance(input_job, (str, int)) and input_job is not None:
        input_job = _format_job_number(input_job)
        path_to_outputs = utils.get_output_root(output_dir)
        files = list(path_to_outputs.glob(f'**/job{input_job}/*.mrc*'))
        files = [str(f) for f in files]
    elif input_job is None:
        files = glob.glob(os.path.join(input_dir, '*.mrc*'))
    
    print(utils._format_tomogram_choices(files))
    #we have list of all files, but perhas user wants to only decompress a select few:
    #under --non-interactive there is nobody to narrow the list, so decompress all of them
    if non_interactive:
        print(f'Non-interactive mode: decompressing all {len(files)} file(s).')
        ask = 'n'
    else:
        ask = input('Are there any specific tomograms you want to decompress? (y/n)')

        while ask not in ['y', 'n']:
            print('Must be yes or no!')
            ask = input('Are there any specific tomograms you want to decompress? (y/n)')
    if ask == 'y':
        available_to_choose = [f"TS_{re.findall(r'\d+', file.split('/')[-1])}" for file in files]
        print(f'Available tomograms to choose:\n{available_to_choose}')
        choices = re.findall(r'\d+', input('Please list the tomograms you want to decompress. You only need to provide the number ID (i.e., TS_XXYY)/\n\nChoices:'))
        
        print(f'These are your choices {choices}')

        print('Decompressing your files for you now')

        for file in files:
            #get mgraph name
            mgraph = utils.get_mgraph(segmentation_file_path=file, caller='decompress')
            print(mgraph,type(mgraph ))
            out_path = os.path.join(output_directory, f'TS_{mgraph}_decompressed.mrc')
            #open up file and copy data
            if mgraph in choices:
                with mrcfile.open(file, mode='r') as mrc:
                    #No .copy(): mrcfile already decompressed the file into its
                    #own array, and that array stays valid after the handle
                    #closes. Copying it just doubled peak memory for no gain.
                    data = mrc.data
                    pix_size = mrc.voxel_size.x
                with mrcfile.new(out_path, overwrite=True) as newmrc:
                    newmrc.set_data(data)
                    newmrc.voxel_size = pix_size
            else:
                pass
        print(f'Decompresson complete!\nFiles written out to {output_directory}')
    else:
        print(f'Decompressing your files now...')
        for file in files:
            #get mgraph name
            mgraph = utils.get_mgraph(segmentation_file_path=file, caller='decompress')
            out_path = os.path.join(output_directory, f'TS_{mgraph}_decompressed.mrc')
            #open up file and read the data (see the note above on the .copy())
            with mrcfile.open(file, mode='r') as mrc:
                data = mrc.data
                pix_size = mrc.voxel_size.x
            with mrcfile.new(out_path, overwrite=True) as newmrc:
                newmrc.set_data(data)
                newmrc.voxel_size = pix_size
        print(f'Decompresson complete!\nFiles written out to {output_directory}')

    return None

def convert(input_dir, output_dir=None, data_type = None, non_interactive=False):
    """Convert tomogram reconstruction(s) to float32 MRC files.

    Reads each input tomogram and writes a converted copy named
    `<part0>_<part1>_f32.mrc`, where the name parts are taken from splitting
    the input filename on underscores. Output data is always cast to
    `numpy.float32`, and the output voxel size is currently hardcoded to 10
    rather than copied from the input file.

    Args:
        input_dir (str): Path, pathlike, to a single tomogram file or a
            directory of `.mrc` tomogram files to convert.
        output_dir (str, optional): Root directory for pipeline outputs. Job
            output is written to `<output_dir>/convert/jobNNN`. Defaults to
            None (`./outputs`).
        data_type: Intended to be the desired numpy data type to convert to
            (e.g. `np.float32`, `np.int16`), but this parameter is currently
            **not honoured** — regardless of what is passed, output is always
            cast to `numpy.float32`. Defaults to None.
        non_interactive (bool, optional): If True, skip the "are there
            specific tomograms you want to process?" prompt and convert every
            `.mrc` file found. Only has an effect when `input_dir` is a
            directory. Set this when running under a batch scheduler, where
            there is no terminal for `input()` to read from. Defaults to
            False.

    Returns:
        None: This function does not return a value; converted files are
            written to disk as `<tomo_id>_f32.mrc`.

    Raises:
        RuntimeError: If `input_dir` is neither an existing file nor an
            existing directory.

    Note:
        Progress is printed via `print()` and `tqdm`, not a logging
        framework.
    """
    #For now, we default to float32 as this is what I need for the moment
    
    # checking if input is a file or directory and creating list of files to convert
    if os.path.isfile(input_dir):
        file_list = [input_dir]
    elif os.path.isdir(input_dir):
        file_list = utils.choose_tomograms(input_dir, caller='convert', non_interactive=non_interactive)
        file_list = [file for file in file_list if file.endswith('.mrc')] #this assumes that the tomograms are in mrc format - we can change this to be more flexible if needed

    else:
        raise RuntimeError('Input must be a file or directory')
    
    output_directory = utils.check_make_dir(job_name='convert', directory=output_dir)
    
    print(f'Processing {len(file_list)} files now....\n')
    with tqdm(total=len(file_list), desc='Converting files', unit='file', dynamic_ncols=True,
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [Elapsed(s):{elapsed}<>Remaining(s):{remaining}, {rate_fmt}] {postfix}') as pbar:
        for file in file_list:
            pbar.set_postfix_str(f'Processing {os.path.basename(file)}...')
            #getting the tomogram identifier
            tomo_file = os.path.basename(file)
            tomo_file_parts =  tomo_file.split('_')
            output_file = f'{tomo_file_parts[0]}_{tomo_file_parts[1]}_f32.mrc'

            with mrcfile.open(file, mode='r') as f:
                #No .copy(): mrcfile's array already owns its buffer and stays
                #valid after the handle closes, so the copy was pure overhead.
                data = f.data
                pix_size = f.voxel_size.x

            #convert to float 32. copy=False means a tomogram that is *already*
            #float32 is passed straight through instead of being duplicated —
            #which for a 5.5 GB volume is the difference between 5.5 and 11 GB.
            data_32 = data.astype(np.float32, copy=False)

            #write output
            with mrcfile.new(os.path.join(output_directory, output_file)) as mrc:
                mrc.set_data(data_32)
                mrc.voxel_size = pix_size
                pbar.update(1)
        print(f'All files have been converted and written to {output_directory}!')


    return None
