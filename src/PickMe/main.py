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


# --- Setting up parameters and data structures ---

#will make a particle row dictionary in a for loop within the segmentation mesh - loop over vertices
full_data_dict = {} #dictionary associating tomogram, with objects, and the objects data

# This file will contain the pipeline
#Each function will be called by a subcommand in the CLI

#this function just ensures that if job number of 1 is provided, 001 is parsed
def _format_job_number(job_number):
    return f'{int(job_number):03d}'

# --- Object extraction and filtering ---
def extract_and_store(input_dir: str, filter_choice=None, output_dir=None):
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
    '''
    This function takes a user's choice of tomogram's segmentation files, and can specify the specific objects witin these tomograms in which they wish to keep.
    The user can only choose from objects which have passed the volume-based filter which aims to filter out noise.

    This will open a napari window to allow users to visualise the objects in a particular tomogram.

    The output of this function can be used to extract particle coordinates and output a star file.

    :param input_dir: Directory containing the tomograms, these should be the tomograms from which segmentations where performed.
    :param segmentation_dir: If users have a segmentation that they want to pick specific objects, they can supply the directory of these. Here, we assume that the segmetation files are in mrc format.
    :param output_dir: user can select a desired directory to output this job - NOT RECOMMENDED
    :type input_dir: str, pathlike
    :type segmentation_dir: str, pathlike

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
        filtered_seg_list = glob.glob(f'{segmentation_dir}/*.mrc') #This o
    
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

        print(f'\n\nAll object data has been written to gzipped mrc files in {output_directory}!')
        return None
    else:
        #if write_selections is true
        #go through each segmentation file in the list
        #get the objects, and write out each object as a separate mrc file in the output directory - this is for the purpose of doing membrane sampling, where we want to sample across each object separately
        if write_selections == True:
            for tomo_id, data in data_dict.items():
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
        else:
            print(f'\n\nThe files have remained unchanged and are located in {os.path.dirname(filtered_seg_list[0])}!')
        return None




# --- Meshing of objects, particle extraction and  angle assignments ----
def particle_extract(sample_rate: int, cmm: bool, input_dir=None, input_job=None, output_dir=None):
    '''
    This function will take the objects that have been filtered and selected and particle extraction begins.

    Particle extraction involves:
    - Gaussian smoothing the segmentation to get a smoother marching cubes output
    - creating a triangular mesh across all of the desired objects
    - sample these points at a set pixel distance
    - calculate euler angles and make data entries to be stored in a dataframe
    - write out dataframe to a star file
    - Optionally, users can write out the particles to a .cmm file

    :params input_dir: Directory containing the filtered and chosen segmentation objects. Users can provide their own segmentations, or be a part of the pipeline.
    :params sample_rate: The minimum radius distance enforced between particle points
    :params cmm: boolean, Option to enable the output of particle picks to a .cmm
    :type sample_rate: int
    :type cmm: bool

    :return: None
    '''
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
        files = list(path_to_outputs.glob(f'**/job{input_job}/*.mrc*'))
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
    '''
    In this package, we write out all the segmentations in a compressed mrc format. 
    Users may want to view these files in Chimera/ChimeraX therefore these files must be decompressed prior to use.

    Users can call this command to decompress any selected tomogram from any part of the pipeline - not stricly in a linear fashion.

    :param input_dir: directory containing the desired mrc.gz or mrc.bz2
    :param job: Alternatively users can supply a job number if the file is from PickMe pipeline. Must be the exact string - 001 not 1
    :type input_dir: str, pathlike
    
    :return: None
    '''
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

def convert(input, output_dir=None, data_type = None):
    '''
    This function will take a tomogram reconstruction and convert the data type to a user-defined data type.

    If no data_type is provided, function defaults to Float32

    :param input: directory or file path to the tomogram(s) to be converted
    :param output_dir: directory to which the converted files will be written
    :param data_type: desired data type to convert the tomogram(s) to. Must be a valid numpy data type (i.e., np.float32, np.int16)
    :type input: str, pathlike
    :type output_dir: str, pathlike
    :type data_type: np.dtype

    '''
    #For now, we default to float32 as this is what I need for the moment
    
    # checking if input is a file or directory and creating list of files to convert
    if os.path.isfile(input):
        file_list = [input]
    elif os.path.isdir(input):
        file_list = utils.choose_tomograms(input)
        file_list = [file for file in file_list if file.endswith('.mrc')] #this assumes that the tomograms are in mrc format - we can change this to be more flexible if needed

    else:
        raise RuntimeError('Input must be a file or directory')
    
    for file in file_list:
        #getting the tomogram identifier
        tomo_file = os.path.basename(file)
        tomo_file_parts =  tomo_file.split('_')
        output_file = f'{tomo_file_parts[0]}_{tomo_file_parts[1]}_f32.mrc'

        with mrcfile.open(file, mode='r') as f:
            data = f.data.copy()

        #convert to float 32
        data_32 = data.astype(np.float32)

        #write output
        with mrcfile.new(os.path.join(output_dir, output_file)) as mrc:
            mrc.set_data(data_32)
            mrc.voxel_size = 10


    return None
