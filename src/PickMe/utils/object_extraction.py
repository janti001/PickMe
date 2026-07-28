
#imports
from skimage.measure import regionprops
from numpy import ndarray, sort, int64


def object_extraction(segmentation):
    """Extract labeled objects from a 3D segmentation array.

    Runs `skimage.measure.regionprops` on the segmentation to identify each
    labeled object, then collects their voxel-count volumes for downstream
    volume-based filtering.

    Args:
        segmentation (numpy.ndarray): 3D labeled segmentation array in
            **zyx** axis order, where each distinct positive integer marks
            the voxels belonging to one object (0 is background).

    Returns:
        tuple[dict, numpy.ndarray]: A 2-tuple of:

            - objects_dict (dict[str, skimage.measure._regionprops.RegionProperties]):
              Maps generated keys ``"Object1"``, ``"Object2"``, ... (in the
              order `regionprops` returned them — not necessarily label
              order) to each object's `RegionProperties`. Note that
              `.coords` on each `RegionProperties` is in **zyx** order,
              matching the input array.
            - volume_array (numpy.ndarray): Object volumes in voxel counts
              (`int64`), **sorted ascending**. This array is positional
              only — it is not keyed by object ID, so it cannot be
              matched back to a specific entry in `objects_dict` by index.

    Raises:
        TypeError: If `segmentation` is not a `numpy.ndarray`.
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