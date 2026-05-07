import numpy as np
import pandas as pd
import starfile
import mrcfile
from tqdm import tqdm
from scipy.ndimage import gaussian_filter, center_of_mass
import seaborn as sns

import glob
import os
import sys
import math as m

import sampling
import utils
import filter
import plotting


# --- Setting up parameters and data structures ---
mgraph_suffix = '.tomostar'
star_suffix = '.star'



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
def extract_and_store(input_dir, output_dir=None):
    '''
    Takes a list of tomogram segmentations, identifies all the objects, filter objects by NSR and provides a filtered object dataset, per tomogram.
    The user also has the option to, from the objects filtered set, choose objects of interest.

    :param input_dir: directory, pathlike, to the directory containing segmentation files
    :param output_dir: directory, pathlike, to  where outputs are to be put
    :type input_dir: string, pathlike
    :type output_dir:string, pathlike

    :return data.csv: CSV file containing the tomograms and their objects
    :rtype: dict

    '''
    full_data = {}

    #Get all objects 
    files = utils.choose_tomograms(segmentation_directory=input_dir)
    # --- Begin processing
    with tqdm(total=len(files), desc='Running Extraction', unit='Tomogram', leave=True) as pbar:
        for file in files:
            try:
                mgraph = utils.get_mgraph(file)
                with mrcfile.open(file, mode='r') as mrc:
                    segmentation = mrc.data.copy()
                shape_zyx = segmentation.shape
                pix_size = segmentation.voxel_size.x

                #add progress bar update
                pbar.set_postfix_str(f'Processing {mgraph}... | shape (zyx)={shape_zyx}')

                #getting out the objects of the tomograms and filtering out noise
                objects_dict, volumes = utils.object_extraction(segmentation)
                objects_filtered = filter.knee_detection(objects_dictionary=objects_dict, volume_array=volumes, micrograph=mgraph)
                #we now have filtered objects
                #add them to our full data dictionary
                full_data[f'{mgraph}'] = objects_filtered
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
    # --- Making output directories
    output_directory = utils.check_make_dir(directory=output_dir, job_name='extract')

    # --- Writing out the tomogram segmentations to mrc to the output directory
    print('Writing out tomogram segmentations to mrc.gz...')
    with tqdm(total=len(full_data.keys()), desc='Writing new objects to mrc.gz', unit='Tomogram', leave=True) as pbar:
        for tomogram, objects in full_data.items():
            tomo_name = tomogram.split('.')[0]
            filtered_array = np.zeros(shape=shape_zyx)
            filtered_array = filtered_array.astype(np.float32)
            #now go through all the objects, get their coordinates and labels and put them back in
            #update pbar
            pbar.set_postfix_str(f'Processing {mgraph}')
            for object in objects.values():
                coords = object.coords
                pix_label = object.label
                filtered_array[coords[:, 0], coords[:, 1], coords[:, 2]] = pix_label
            #now write a new mrc file
            with mrcfile.new(name=f'{os.path.join(output_directory, tomo_name)}_filtered.mrc.gz', compression='gzip') as mrc:
                mrc.set_data(filtered_array)
                mrc.voxel_size = pix_size
            pbar.update(1)
    #not sure to return full date or not
    return None


# --- Object choice with Napari plugin --- 

def choose_object(input_dir, napari, output_dir=None):
    '''
    This function takes a user's choice of tomogram's segmentation files, and can specify the specific objects witin these tomograms in which they wish to keep.
    The user can only choose from objects which have passed the volume-based filter which aims to filter out noise.

    This will open a napari window to allow users to visualise the objects in a particular tomogram.

    The output of this function can be used to extract particle coordinates and output a star file.

    :param data: CSV/mrc file containing the tomogram and its segmentation data, after filtering
    :type data: dict

    :return data_final: original dictionary modified with the appropriate choices from the user
    :rtype data_final: dict
    '''
    #ask user if they want specific objects
    ask_user = input('Which objects of interest would you like to select from the filtered set for processing?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Which objects of interest would you like to select from the filtered set for processing?')
    if ask_user.lower() in ['y', 'yes']:
        ask_user = True
    elif ask_user.lower() in ['n', 'no']:
        ask_user = False

    if ask_user == True:
        # --- convert csv back into dict
        ## ---- NAPARI plugin would be here
        #Go through each tomogram, get the shape, remake array
        #for each object that passed the filter, 'put them back in the array'
        #With this array - open up napari with the array and the binned tomogram

        #hopefully gui launches, then users can see and then submit choices in the CLI?
        
        return None

# --- Meshing of objects, particle extraction and  angle assignments ----
def particle_extract(input_dir, grid_sampling):
    return None