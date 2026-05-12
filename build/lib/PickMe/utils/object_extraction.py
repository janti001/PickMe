
#imports
from skimage.measure import regionprops
from numpy import ndarray, sort, int64


def object_extraction(segmentation):
    """
    Extract objects from a labeled 3D segmentation mrc file.

    :param segmentation: 3D labeled segmentation array where each integer corresponds to an object.
    :type segmentation: numpy.ndarray

    :return: 
        - objects_dict: Dictionary mapping object IDs to their region properties.
        - volume_array: Sorted array of object volumes (voxel counts) of each object.
    :rtype: tuple(dict[str, RegionProperties], numpy.ndarray)
    """

    #checking for valid data type
    if not isinstance(segmentation, ndarray):
        raise TypeError('Segmentation needs to be a numpy ndarray!')
    
    objects_dict = {}
    volume_list = [] #may get rid of this feature as I develop an ML classifier to get rid of noise
    # --- Getting the objects
    objects = regionprops(segmentation)

    #get the data into a dictionary
    for object in range(len(objects)):
        objects_dict[f'Object{object+1}'] = objects[object]
    
    # --- Calculate volumes that will be used to do volume-based filtering
    for label, data in objects_dict.items():
        volume = int64(data.area)
        volume_list.append(volume)
    volume_array = sort(volume_list)

    return objects_dict, volume_array