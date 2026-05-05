from ..main import mgraph_suffix

def get_mgraph(segmentation_file_path):
    '''
    This function, from the name of the segmentation file, will be able to get the .tomostar microgaph file.
    It will also obtain which object the membrane is, and allow the star file to be written out per object

    :param segmentation: string of the file path
    :type segmentation: str
    :return: Name of the .tomostar file
    :rtype: str
    '''

    path_parts = segmentation_file_path.split('/')
    segmentation_file = path_parts[-1]
    mgraph_parts = segmentation_file.split('_')
    mgraph_Name = mgraph_parts[0]+'_'+mgraph_parts[1]+mgraph_suffix

    return mgraph_Name