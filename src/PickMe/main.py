import numpy as np
import pandas as pd
import starfile
import mrcfile
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, center_of_mass
import seaborn as sns
from qtpy.QtWidgets import QAbstractItemView, QTableView, QTableWidget, QPushButton
import napari

import glob
import os
import sys
import math as m
from pathlib import Path

from PickMe import sampling, utils, filter, plotting
from .config import mgraph_suffix, star_suffix

# --- Setting up parameters and data structures ---

#instantiate the data structure to be used to write the star file
star_dict = {'rlnCoordinateX':[],
             'rlnCoordinateY':[],
             'rlnCoordinateZ':[],
             'rlnOriginX':[],
             'rlnOriginY':[],
             'rlnOriginZ':[],
             'rlnAngleRot':[],
             'rlnAngleTilt':[],
             'rlnAnglePsi':[],
             'rlnLCCmax':[],
             'rlnCutOff':[],
             'rlnSearchStd':[],
             'rlnDetectorPixelSize':[],
             'rlnMicrographName':[]} #This is .tomostar files -> TS_1234.tomostar

total_star_df = pd.DataFrame.from_dict(star_dict)
per_tomogram_star_df = total_star_df.copy()
#will make a particle row dictionary in a for loop within the segmentation mesh - loop over vertices
full_data_dict = {} #dictionary associating tomogram, with objects, and the objects data

# This file will contain the pipeline
#Each function will be called by a subcommand in the CLI

# --- Object extraction and filtering ---
def extract_and_store(input_dir: str, output_dir=None):
    '''
    Takes a list of tomogram segmentations, identifies all the objects, filter objects by NSR and provides a filtered object dataset, per tomogram.
    
    :param input_dir: directory, pathlike, to the directory containing ALL segmentation files
    :param output_dir: directory, pathlike, to  where outputs are to be put
    :type input_dir: string, pathlike
    :type output_dir:string, pathlike

    :return data.csv: CSV file containing the tomograms and their objects
    :rtype: dict

    '''
    full_data = {} #this could be a class for sure
    # --- Making output directories
    output_directory = utils.check_make_dir(directory=output_dir, job_name='extract')
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
    #not sure to return full date or not
    return None


# --- Object choice with Napari plugin --- 

def choose_object(input_dir:str, output_dir=None):
    '''
    This function takes a user's choice of tomogram's segmentation files, and can specify the specific objects witin these tomograms in which they wish to keep.
    The user can only choose from objects which have passed the volume-based filter which aims to filter out noise.

    This will open a napari window to allow users to visualise the objects in a particular tomogram.

    The output of this function can be used to extract particle coordinates and output a star file.

    :param input_dir: Directory containing the tomograms, these should be the tomograms from which segmentations where performed.
    :type input_dir: str, pathlike

    :return None: compressed mrc.gz files are written out.
    '''
    #ask user if they want specific objects
    ask_user = input('Are there any objects which you would like to select (y/n)?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Which objects of interest would you like to select from the filtered set for processing?')
    if ask_user.lower() in ['y', 'yes']:
        ask_user = True
    elif ask_user.lower() in ['n', 'no']:
        ask_user = False

    if ask_user == True:
        output_directory = utils.check_make_dir(directory=output_dir, job_name='choose')
        tomogram_list = glob.glob(f'{input_dir}/TS_*')
        outputs_root = Path(__file__).resolve().parents[2] / 'outputs'
        extract_jobs = sorted(
            [path for path in (outputs_root / 'extract').glob('job[0-9][0-9][0-9]') if path.is_dir()]
        )
        if extract_jobs:
            filtered_seg_list = glob.glob(str(extract_jobs[-1] / '*filtered*'))
        else:
            filtered_seg_list = glob.glob(str(outputs_root / 'extract' / '*filtered*'))
        
        #create a data dictionary to store the tomogram and segmentation file paths for a particular tomogram
        data_dict={} #this could be changed to a class
        valid_id = [seg.split('/')[-1].split('_')[1] for seg in filtered_seg_list]
        for tomogram in tomogram_list:
            tomo_id = tomogram.split('/')[-1].split('_')[1]
            if tomo_id in valid_id:
                data_dict[tomo_id] = {'tomogram': tomogram}
                data_dict[tomo_id].update({'segmentation': seg for seg in filtered_seg_list if tomo_id in seg})
    
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
        
        #tomogram
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
                    print(f'Error with file: {file}\n{e}')
                    raise
                finally:
                    pbar.update(1)


        # Write filtered segmentation masks
        print('Writing new objects to disk now as mrc.gz files')
        with tqdm(total=len(final_data), desc='Writing', unit='Tomogram', leave=True) as pbar:
            for tomo_id, selected_objects in final_data.items():
                print(tomo_id)
                tomogram_path = data_dict.get(tomo_id)['tomogram']
                print(f'tomogram path {tomogram_path}')
                pbar.set_postfix_str(f'Processing tomogram: {tomo_id}...')
                if tomogram_path is None:
                    print(f'Warning: no matching tomogram found for {tomo_id}')
                    continue

                with mrcfile.open(tomogram_path, mode='r') as mrc:
                    shape_zyx = mrc.data.shape        # no .copy() needed for shape
                    pix_size = mrc.voxel_size.x

                # Stack coords from all selected objects in one go
                all_coords = np.vstack([obj.coords for obj in selected_objects])

                choice_array = np.zeros(shape_zyx, dtype=np.int8)
                choice_array[all_coords[:, 0], all_coords[:, 1], all_coords[:, 2]] = 1

                out_path = os.path.join(output_directory, f'{tomo_id}_filtered_chosen.mrc.gz')
                with mrcfile.new(out_path, compression = 'gzip', overwrite=True) as new_file:
                    new_file.set_data(choice_array)
                    new_file.voxel_size = pix_size
                pbar.update(1)
        return None
    else:
        print('The files have remained unchanged and are located in outputs/extract')
        return None




# --- Meshing of objects, particle extraction and  angle assignments ----
def particle_extract(input_dir: str, grid_sampling: int):
    return None