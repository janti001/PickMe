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

from . import sampling, utils, filter, plotting, angles
from .config import mgraph_suffix, star_suffix

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

# --- Object extraction and filtering ---
def filter_objects(input_dir: str, filter_choice=None, output_dir=None):
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

    Returns:
        None: This function does not return a value. Filtered segmentations
            are written to disk as gzip-compressed `_filtered.mrc.gz` files
            under the job output directory; nothing is written to CSV.

    Note:
        Progress and a per-tomogram object count summary are printed via
        `print()` and `tqdm`, not a logging framework.
    """
    full_data = {} #this could be a class for sure
    # --- Making output directories
    output_directory = utils.check_make_dir(directory=output_dir, job_name='filter')
    #Get all objects 
    files = utils.choose_tomograms(segmentation_directory=input_dir)
    # --- Begin processing
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
                #we now have filtered objects
                #add them to our full data dictionary
                full_data[f'{mgraph}'] = objects_filtered #this could be a class for sure
            except Exception as e:
                print(f'There was an error with file:{file}')
                print(f'Error: {e}')
                raise(e)
            #update bar
            pbar.update(1)
    
    # --- Print out the results of initial extraction
    for tomogram, data in full_data.items():
        print(f'\nFor tomogram {tomogram}, {len(list(data.values()))} objects were selected. Objects: {list(data.keys())}')
    print('\n\nExtraction complete!')

    # --- Writing out the tomogram segmentations to mrc to the output directory
    print('Writing out tomogram segmentations to mrc.gz...')
    with tqdm(total=len(full_data.keys()), desc='Writing new objects to mrc.gz', unit='Tomogram', leave=True) as pbar:
        for tomogram, objects in full_data.items():
            tomo_name = tomogram.split('.')[0]
            filtered_array = np.zeros(shape=shape_zyx)
            filtered_array = filtered_array.astype(np.int8)
            #now go through all the objects, get their coordinates and labels and put them back in
            #update pbar
            pbar.set_postfix_str(f'Processing {mgraph}')
            for object in objects.values():
                coords = object.coords
                pix_label = object.label
                filtered_array[coords[:, 0], coords[:, 1], coords[:, 2]] = pix_label
            #now write a new mrc file
            out_path = f'{os.path.join(output_directory, tomo_name)}_filtered.mrc.gz'
            with mrcfile.new(name=out_path, compression='gzip', overwrite=True) as mrc:
                mrc.set_data(filtered_array)
                mrc.voxel_size = pix_size
            pbar.update(1)
    print(f'\n\nAll filtered segmentations have been written to gzipped mrc files in {output_directory}!')
    #not sure to return full date or not
    return None


# --- Object choice with Napari plugin --- 

def choose_object(input_dir:str, segmentation_dir = None, input_job=None, output_dir=None, write_selections=False):
    """Let a user pick which filtered objects to keep, per tomogram.

    Always begins by prompting interactively via `input()`:
    "Are there any objects which you would like to select (y/n)?" The answer
    determines which path runs, and the user can only choose from objects that
    already passed the volume-based knee filter in `filter_objects`:

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

    Returns:
        None: This function does not return a value; results are written to
            disk (or left untouched) as described above.

    Note:
        This function always prompts via `input()` before doing anything
        else. When the user answers "yes", it also lazily imports `napari`
        and `qtpy` (only inside that branch, since they are optional GUI
        dependencies) and blocks until the napari window is closed.
    """
    #ask user if they want specific objects
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
    if os.path.isdir(input_dir):
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
        filtered_seg_list = glob.glob(f'{segmentation_dir}/*.mrc*') 
    
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
        from qtpy.QtWidgets import QAbstractItemView, QTableView, QTableWidget, QPushButton
        import napari

        #instantiate the napari viewer
        viewer = napari.Viewer()

        #Load all tomograms and their segmentations into napari viewer
        for tomogram_id, data in data_dict.items():
            with mrcfile.open(data['tomogram'], mode='r') as f:
                tomogram_data = f.data.copy()
            with mrcfile.open(data['segmentation'], mode='r') as f:
                segmentation_data = f.data.copy()
            viewer.add_image(tomogram_data, name=tomogram_id)
            viewer.add_labels(segmentation_data, name=f'{tomogram_id}_segmentation')
        
        # --- Interfacing with napari to select objects of interest directly from napari
        # Maps  tomo_id -> set of selected label IDs
        selected_objects: dict[str, set[int]] = {tomo_id: set() for tomo_id in data_dict}

        def _active_tomo_id() -> str | None:
            """Return the tomo_id of whichever labels layer is currently active."""
            layer = viewer.layers.selection.active
            if layer is not None and hasattr(layer, 'data') and '_segmentation' in layer.name:
                return layer.name.replace('_segmentation', '') #this just ensures that we have the tomogram id - TS_xyxy
            return None


        # ── connect to the table after the user clicks Analyse ──────────────────────────
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
            for dock_name, dw in viewer.window._dock_widgets.items(): #changed from _dock_widgets to dock_widgets  
                native = dw.native if hasattr(dw, 'native') else dw
                for cls in (QTableView, QTableWidget):
                    table = native.findChild(cls)
                    if table is not None:
                        print(f"[PickMe] Found table in dock widget: '{dock_name}' ({cls.__name__})")
                        return table

            return None

        _connected_table = None   # hold a reference so we can reconnect on subsequent Runs

        def _on_run_clicked(): #run button - "analyse" in the naari-skimage plugin
            nonlocal _connected_table

            table = _find_table()   # no argument needed now
            if table is None:
                print("[PickMe] Could not find regionprops table — try clicking Run first, or inspect dock widgets.")
                # Debug helper: print what dock widgets exist
                print(f"[PickMe] Current dock widgets: {list(viewer.window._dock_widgets.keys())}") #changed from _dock_widgets to dock_widgets
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
        


        # --- Applying the selection and writing out files ---------------------
        final_data = {}
        
        print('Extracting selected objects from tomograms...')
        with tqdm(total=len(filtered_seg_list), desc='Running Extraction', unit='Tomogram', leave=True) as pbar:
            for tomo_id, data in data_dict.items():
                try:
                    segmentation_path = data_dict.get(tomo_id)['segmentation']
                    with mrcfile.open(segmentation_path, mode='r') as mrc:
                        segmentation = mrc.data.copy()
                        shape_zyx = segmentation.shape
                        pix_size = mrc.voxel_size.x  # avoid re-opening for voxel size

                    pbar.set_postfix_str(f'Processing {tomo_id} | shape (zyx)={shape_zyx}')

                    # Extract and filter objects in one step
                    objects_dict, _ = utils.object_extraction(segmentation)

                    # Filter to selected labels immediately — no need to store full_data
                    selections = final_selection.get(tomo_id, set())
                    selected_objects = [obj for obj in objects_dict.values() if obj.label in selections]

                    if selected_objects:
                        final_data[tomo_id] = selected_objects

                except Exception as e:
                    print(f'Error with file: {tomo_id}\n{e}')
                    raise
                finally:
                    pbar.update(1)


        # Write filtered segmentation masks
        print('Writing new objects to disk now as mrc.gz files')


        if write_selections == False:
            with tqdm(total=len(final_data), desc='Writing', unit='Tomogram', leave=True) as pbar:
                for tomo_id, selected_objects in final_data.items():
                    tomogram_path = data_dict.get(tomo_id)['tomogram']
                    #print(f'tomogram path {tomogram_path}')
                    pbar.set_postfix_str(f'Processing tomogram: {tomo_id}...')
                    if tomogram_path is None:
                        print(f'Warning: no matching tomogram found for {tomo_id}')
                        continue

                    with mrcfile.open(tomogram_path, mode='r') as mrc:
                        shape_zyx = mrc.data.shape        # no .copy() needed for shape
                        pix_size = mrc.voxel_size.x

                    # Stack coords from all selected objects in one go
                    #all_coords = np.vstack([obj.coords for obj in selected_objects])
                    choice_array = np.zeros(shape_zyx, dtype=np.int8)
                    #go through each object, obtain coordinates, and set pixel value to the label value
                    for object in selected_objects:
                        zcoords, ycoords, xcoords = object.coords[:, 0], object.coords[:, 1], object.coords[:, 2]
                        choice_array[zcoords, ycoords, xcoords] = object.label

                    out_path = os.path.join(output_directory, f'{tomo_id}_filtered_chosen.mrc.gz')
                    with mrcfile.new(out_path, compression = 'gzip', overwrite=True) as new_file:
                        new_file.set_data(choice_array)
                        new_file.voxel_size = pix_size
                    pbar.update(1)
            print(f'\n\nAll object data has been written to gzipped mrc files in {output_directory}!')
        
        elif write_selections == True:
            with tqdm(total=len(final_data), desc='Writing', unit='Tomogram', leave=True) as pbar:
                for tomo_id, selected_objects in final_data.items():
                    tomogram_path = data_dict.get(tomo_id)['tomogram']
                    out_dir = os.path.join(output_directory, f'TS_{tomo_id}_membranes')
                    os.makedirs(out_dir, exist_ok=True)
                    pbar.set_postfix_str(f'Processing tomogram: {tomo_id}...')
                    if tomogram_path is None:
                        print(f'Warning: no matching tomogram found for {tomo_id}')
                        pass

                    with mrcfile.open(tomogram_path, mode='r') as mrc:
                        shape_zyx = mrc.data.shape        # no .copy() needed for shape
                        pix_size = mrc.voxel_size.x

                    choice_array = np.zeros(shape_zyx, dtype=np.int8)
                #go through each object, obtain coordinates, and set pixel value to the label value
                    for object in selected_objects:
                        zcoords, ycoords, xcoords = object.coords[:, 0], object.coords[:, 1], object.coords[:, 2]
                        choice_array[zcoords, ycoords, xcoords] = 1
                        #write the object into mrc.gz file then reset choice array to 0
                        out_path = os.path.join(out_dir, f'TS_{tomo_id}_obj{object.label}.mrc') #could change this to mrc.gz -> for the purpsoe of doing membrain, will leave it as mrc - will change to give user an option
                        with mrcfile.new(out_path, overwrite=True) as new_file:
                            new_file.set_data(choice_array)
                            new_file.voxel_size = pix_size
                        choice_array = np.zeros(shape_zyx, dtype=np.int8) #reset array for next object
                    pbar.update(1)
            print(f'\n\nAll selected objects have been written to mrc files in {output_directory}!')

        return None
    else:
        #if write_selections is true
        #go through each segmentation file in the list
        #get the objects, and write out each object as a separate mrc file in the output directory - this is for the purpose of doing membrane sampling, where we want to sample across each object separately
        if write_selections == True:
            print(f'\n\nWriting out each selected object as a separate mrc file in {output_directory} for membrane sampling...')
            with tqdm(total=len(data_dict.keys()), desc='Writing', unit='Tomogram', leave=True) as pbar:
                for tomo_id, data in data_dict.items():
                    pbar.set_postfix_str(f'Processing tomogram: {tomo_id}...')
                    segmentation_path = data_dict.get(tomo_id)['segmentation']
                    with mrcfile.open(segmentation_path, mode='r') as mrc:
                        segmentation = mrc.data.copy()
                        shape_zyx = segmentation.shape
                        pix_size = mrc.voxel_size.x  # avoid re-opening for voxel size
                    objects_dict, _ = utils.object_extraction(segmentation)
                    out_dir = os.path.join(output_directory, f'TS_{tomo_id}_membranes')
                    os.makedirs(out_dir, exist_ok=True)
                    for object in objects_dict.values():
                        choice_array = np.zeros(shape_zyx, dtype=np.int8)
                        zcoords, ycoords, xcoords = object.coords[:, 0], object.coords[:, 1], object.coords[:, 2]
                        choice_array[zcoords, ycoords, xcoords] = 1
                        out_path = os.path.join(out_dir, f'TS_{tomo_id}_obj{object.label}.mrc') #could change this to mrc.gz -> for the purpsoe of doing membrain, will leave it as mrc - will change to give user an option
                        with mrcfile.new(out_path, overwrite=True) as new_file:
                            new_file.set_data(choice_array)
                            new_file.voxel_size = pix_size
                        pbar.update(1)
            print(f'\n\nAll selected objects have been written to mrc files in {output_directory}!')
            
        else:
            print(f'\n\nThe files have remained unchanged and are located in {os.path.dirname(filtered_seg_list[0])}!')
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
                    mrc_data = mrc.data.copy()
                    shape_zyx = mrc_data.shape
                    pixel_size = mrc.voxel_size.x
                # Obtain objects from segmentations
                objects_dict, _ = utils.object_extraction(mrc_data)
                tomo_name = utils.get_mgraph(file, caller='particle_extract') #this is .tomostar file

                for object in objects_dict.values():
                    object_array = np.zeros(shape=shape_zyx, dtype=np.int8)
                    object_coords = object.coords #in zyx
                    zcoords, ycoords, xcoords = object.coords[:, 0], object.coords[:, 1], object.coords[:, 2]
                    object_array[zcoords, ycoords, xcoords] = 1
                    #gaussian smooth all of the objects in the mrc files
                    smooth_object = gaussian_filter(object_array.astype(float), sigma=3.0)

                    # -- Perform marching cubes and particle extraction
                    #This creates a triangular mesh
                    verts, _, normals, _ = marching_cubes(volume=smooth_object)
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
                starfile.write(tomogram_star_df, f'{output_directory}/{tomo_name.strip(".tomostar")}.star')
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

        

def decompress(input_dir=None, input_job=None, output_dir=None):
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

    Returns:
        None: This function does not return a value; decompressed files are
            written to disk as `TS_<tomo_id>_decompressed.mrc`.

    Raises:
        RuntimeError: If both `input_dir` and `input_job` are None.

    Note:
        This function always prompts via `input()` to ask which tomograms, if
        any, decompression should be restricted to.
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
                    data = mrc.data.copy()
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
            #open up file and copy data
            with mrcfile.open(file, mode='r') as mrc:
                data = mrc.data.copy()
                pix_size = mrc.voxel_size.x
            with mrcfile.new(out_path, overwrite=True) as newmrc:
                newmrc.set_data(data)
                newmrc.voxel_size = pix_size
        print(f'Decompresson complete!\nFiles written out to {output_directory}')

    return None

def convert(input_dir, output_dir=None, data_type = None):
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
        file_list = utils.choose_tomograms(input_dir, caller='convert')
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
                data = f.data.copy()

            #convert to float 32
            data_32 = data.astype(np.float32)

            #write output
            with mrcfile.new(os.path.join(output_directory, output_file)) as mrc:
                mrc.set_data(data_32)
                mrc.voxel_size = 10
                pbar.update(1)
        print(f'All files have been converted and written to {output_directory}!')


    return None
