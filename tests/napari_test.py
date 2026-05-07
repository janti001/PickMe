import numpy as np
import pandas as pd
import starfile
import mrcfile
import napari


import glob
import os
import sys

#probable inputs
# tomogram_reconstruction input directory 
# directory with the filtered segmentation volumes as another input
# napari option - do they want to open the napari plugin


#Create a napari viewer object
viewer = napari.Viewer() 

#Get the list of files
tomogram_list = glob.glob('/Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/data/tomo_reconstruction/*10.00*')
filtered_seg_list = glob.glob('/Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/PickMe/outputs/extract/*mrc.gz')
# I want to zip up the two lists and create a dict that would map a tomogram file name to the segmentation - this would make the assigning of tomogram and segmentation layers to napari much easier
data_dict = {}
selected_data={}
for tomogram in tomogram_list:
    tomo_id_parts = tomogram.split('/')[-1].split('_')[:2]
    tomo_id = f'{tomo_id_parts[0]}_{tomo_id_parts[1]}'
    data_dict[tomo_id] = {'tomogram': tomogram}
    data_dict[tomo_id].update({'segmentation': seg for seg in filtered_seg_list if tomo_id in seg})
# --- Go through dictionary, make image layeer and open up segmentations and get their data - add labels layer with name label
for tomogram_id, data in data_dict.items():
    tomogram_path = data['tomogram']
    segmentation_path = data['segmentation']
    #Open up the tomogram and extract the data from it
    with mrcfile.open(tomogram_path, mode='r') as tomogram:
        tomogram_data = tomogram.data.copy()
    #Open up the segmentation and extract the data from it
    with mrcfile.open(segmentation_path, mode='r') as segmentation:
        segmentation_data = segmentation.data.copy()
    print(np.zeros_like(segmentation_data.shape))
    #add image and label layers to napari viewer
    image = viewer.add_image(tomogram_data, name=tomogram_id)
    segmentation = viewer.add_labels(segmentation_data, name=f'{tomogram_id}_segmentation')
    #selection = viewer.add_labels(data=np.zeros_like(segmentation_data.shape), name = f'{tomogram_id}_selected')
#add skimage window
viewer.window.add_plugin_dock_widget(plugin_name='napari-skimage', widget_name='Regionprops (labels)')

#open up the napari viewer
napari.run()


# I want to incorporate a user's decision from the gui



