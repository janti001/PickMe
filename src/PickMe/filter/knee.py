import numpy as np

from ..plotting import plot_knee



def knee_detection(volume_array, objects_dictionary, micrograph, output, index=None):
    """Drop small segmented objects using volume-normalised knee detection.

    Real membrane objects tend to be much larger than noise fragments, so
    when object volumes are sorted and normalised against the largest
    object, the curve typically has a sharp "knee": a flat run of small,
    noise-sized objects followed by a rise into real, larger objects. This
    function finds that knee (as the point of maximum perpendicular
    distance from the diagonal line joining the first and last points of
    the normalised curve) and discards everything before it, keeping only
    the larger, presumed-real objects.

    As a side effect, this also saves a diagnostic plot of the curve and
    the detected knee via `PickMe.plotting.plot_knee`.

    Args:
        volume_array (numpy.ndarray): 1D array of object volumes (voxel
            counts), one per object. Does not need to be pre-sorted — the
            function sorts it ascending internally.
        objects_dictionary (dict): Objects for a single tomogram, keyed by
            label, where each value is a `skimage.measure.RegionProperties`
            (or similar) object exposing an ``.area`` attribute. This must
            be the dictionary for one tomogram, not an aggregate over
            several.
        micrograph (str): Name of the tomogram being processed, used to
            name the saved diagnostic plot.
        output (str or pathlib.Path): Output directory passed through to
            `PickMe.plotting.plot_knee` for saving the plot.
        index (int, optional): Unused by this function's own logic;
            accepted for the caller's bookkeeping when iterating over
            multiple tomograms. Defaults to None.

    Returns:
        dict: The subset of ``objects_dictionary`` at and above the
            detected volume knee, i.e. the objects kept after filtering.

    Raises:
        TypeError: If ``volume_array`` is not a numpy array.
        Exception: Any error encountered during filtering is printed and
            re-raised.
    """

    # --- Type checking
    if not isinstance(volume_array, (np.ndarray, np.array)):
        raise TypeError('Volumes of objects must be supplied as a numpy array')

    try: 
        # --- Volume normalisation
        volume_array = np.sort(volume_array)
        max_volume = np.max(volume_array)
        max_normalised = []

        for volume in volume_array:
            vol_norm = volume/max_volume
            max_normalised.append(vol_norm)


        # --- Max-Volume normalised-based filtering
        #calculating the perpendicular distance from each point to a diagonal
        #seems a little funky, but the diagonal has a y=mx form
        #form of ax + by + c = 0
        slope = (1)/len(max_normalised)
        a = slope * -1
        b = 1
        #x = indices of data
        #y = max-normalised volume value
        dist_list =[]
        for x in range(len(volume_array)):
            y=max_normalised[x]
            distance = (np.abs((a*x)+(b*y)))/np.sqrt((a**2)+(b**2))
            dist_list.append(distance)
        dist_array=np.array(dist_list)
        #useful for plotting and visualising the readout
        threshold = np.argmax(dist_array) #this gives the index/position at which the filter occurs
        threshold_normalised_value = max_normalised[threshold]

        # --- Pulling out objects that have passed the filter
        objects_dictionary_copy = objects_dictionary.copy()
        objects_sorted_list = sorted(objects_dictionary.items(), key=lambda x: x[1].area, reverse=False) #sort the dictionary by area size
        objects_filtered = dict(objects_sorted_list[threshold:])


        # --- Visualising the filter
        plot_knee(max_normalised, index_threshold=threshold, micrograph=micrograph, norm_threshold=threshold_normalised_value, output_dir=output)

        return objects_filtered

    except Exception as e:
        print('There was an error')
        print(f'Error: {e}')
        raise(e)
