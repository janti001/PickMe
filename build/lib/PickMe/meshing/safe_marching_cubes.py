#imports
from numpy import max, min
from skimage.measure import marching_cubes

def safe_marching_cubes(map, initial_level, step_size):
    '''
    This function creates a mesh from a segmentation as a Numpy array. 

    :param map: Numpy ndarray of the membrane segmentation
    :param initial_level: The initial contour level to use on the segmentation
    :param step_size: If initial contour does not work, then step size determines how far to search
    :rtype map: Numpy ndarray
    :rtype initial_level: (float, int)
    :rtype step_size: (float, int)

    :return: return the coordinates of the triangular mesh vertices, their normals relative to the density at that position, faces and values

    '''

    #ensure that initial level and step size are either floats or integers
    if initial_level or step_size is not None:
        if not isinstance(initial_level, (float, int)):
            raise TypeError('Initial contour level must be float or integer')

        if not isinstance(step_size, (int, float)) or step_size > 1 or step_size<0:
            raise TypeError('Step size must be an integer or float and be between 0 and 1')
        
    
    max_attempts = 10

    #getting the max and min contour levels
    cmax = np.max(map.copy())
    cmin = np.min(map.copy())


    for attempt in range(max_attempts):
        if initial_level < cmin:
            initial_level += 2* (cmin - initial_level) #multiple 2 to get one up the other way
        elif initial_level > cmax:
            initial_level -= 2*(initial_level - cmax)
        else:

            try:
                verts, faces, normals, values = marching_cubes(map.copy(),level=initial_level)
                return verts, faces, normals, values
            except RuntimeError:
                print(f"\nmarching_cubes failed at level={initial_level}, trying different contour...")

                # adjust level downward
                initial_level += (m.e**(0.25*initial_level)-0.7)
        
    raise RuntimeError("Marching cubes failed after multiple attempts")