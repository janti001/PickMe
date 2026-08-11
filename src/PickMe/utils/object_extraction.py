
#imports
from skimage.measure import regionprops
from numpy import ndarray, sort, int32, int64


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


def object_coords_by_label(segmentation, labels=None):
    """Extract just the voxel coordinates of each labeled object.

    This is the low-memory alternative to `object_extraction` for code that
    only needs to know *where* each object's voxels are. The difference
    matters more than it looks:

    A `skimage` `RegionProperties` object holds a reference to the whole label
    image it was measured from. Keeping even one of them alive therefore keeps
    the entire segmentation array alive too, so storing them across a loop
    over many tomograms pins every segmentation in RAM at once. Returning
    plain coordinate arrays instead means the segmentation can be garbage
    collected as soon as the caller drops its own reference to it.

    Coordinates are returned as `int32` rather than the `int64` skimage
    produces. Tomogram dimensions are far below the `int32` limit, so nothing
    is lost, and the arrays take half the memory.

    Args:
        segmentation (numpy.ndarray): 3D labeled segmentation array in
            **zyx** axis order, where each distinct positive integer marks the
            voxels belonging to one object (0 is background).
        labels (collections.abc.Iterable[int], optional): Only return these
            label IDs. Coordinates are never materialised for the objects left
            out, which is where most of the saving comes from when only a
            handful of objects were selected. Defaults to None, meaning every
            object in the segmentation.

    Returns:
        dict[int, numpy.ndarray]: Maps each label ID to its `(N, 3)` array of
            voxel coordinates in **zyx** order, matching the input array.
            Labels asked for but not present in the segmentation are simply
            absent from the result.

    Raises:
        TypeError: If `segmentation` is not a `numpy.ndarray`.
    """

    #checking for valid data type
    if not isinstance(segmentation, ndarray):
        raise TypeError('Segmentation needs to be a numpy ndarray!')

    #Normalise to a set of plain ints up front: label IDs coming back from a
    #GUI table may be numpy integers, which compare equal but hash the same,
    #so this is about being explicit rather than about correctness.
    wanted = None if labels is None else {int(label) for label in labels}

    coords_by_label = {}
    #`regionprops` is lazy — `.coords` is only computed when it is read — so
    #skipping unwanted labels here really does avoid the work and the memory.
    for props in regionprops(segmentation):
        label = int(props.label)
        if wanted is not None and label not in wanted:
            continue
        coords_by_label[label] = props.coords.astype(int32, copy=False)

    #The RegionProperties objects (and their references to `segmentation`) go
    #out of scope here; only the coordinate arrays survive the return.
    return coords_by_label