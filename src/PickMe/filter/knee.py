import numpy as np

from ..plotting.knee_plot import plot_knee



def knee_detection(volume_array, objects_dictionary, micrograph, index=None):
    '''
    This function performs a volume based filtering of the objects in the segmentation. 


    :param objects_dictionary: Dictionary containing each object and associated data. This should be the dictionary of of a single tomogram and not a full dictionary.
    :param volume_array: array of the counts of each voxel value, sorted in ascending order.
    :param index: index of which iteration we are in when looping through the object data within a tomogram.
    :type objects_dictionary: dict
    :type volume_array: numpy.1darray

    :return objects_filtered: Dictionary of filtered objects
    :rtype objects_filtered: dict

    '''

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
        if index is not None:
            if index % 3 == 0: #print every third tomogram - this can be rmemoved
                plot_knee(max_normalised, index_threshold=threshold, micrograph=micrograph, norm_threshold=threshold_normalised_value)
        else:
            plot_knee(max_normalised, index_threshold=threshold, micrograph=micrograph, norm_threshold=threshold_normalised_value)

        return objects_filtered

    except Exception as e:
        print('There was an error')
        print(f'Error: {e}')
        raise(e)

