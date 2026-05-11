from pathlib import PosixPath
from ..config import mgraph_suffix

def get_mgraph(segmentation_file_path):
    '''
    This function, from the name of the segmentation file, will be able to get the .tomostar microgaph file.
    It will also obtain which object the membrane is, and allow the star file to be written out per object

    :param segmentation: string of the file path
    :type segmentation: str
    :return: Name of the .tomostar file
    :rtype: str
    /Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/PickMe/outputs/choose/job009/1416_filtered_chosen.mrc.gz
    ''' 

    if isinstance(segmentation_file_path, PosixPath):
        file_path_string = str(segmentation_file_path)
        path_parts = file_path_string.split('/')
    else:
        path_parts = segmentation_file_path.split('/')
    segmentation_file = path_parts[-1]

    #check if it is from object choice job
    if "chosen" in segmentation_file:
        mgraph_name = segmentation_file.strip('.mrc.gz')
    else:
        mgraph_parts = segmentation_file.split('_')
        mgraph_name = mgraph_parts[0]+'_'+mgraph_parts[1]+mgraph_suffix
    return mgraph_name