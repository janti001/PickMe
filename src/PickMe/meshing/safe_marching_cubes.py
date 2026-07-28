#imports
from numpy import max, min
from skimage.measure import marching_cubes

def safe_marching_cubes(map, initial_level, step_size):
    """Run marching cubes on a segmentation, retrying at adjusted levels.

    Wraps `skimage.measure.marching_cubes` with a retry loop: if the
    requested contour level lies outside the data's value range, or if
    marching cubes fails to find a surface at that level, the level is
    nudged and the attempt is repeated (up to ``max_attempts`` times)
    before giving up.

    Args:
        map (numpy.ndarray): Segmentation volume to mesh, in zyx order.
        initial_level (float or int): Contour level to attempt first.
        step_size (float or int): Intended to control how far the contour
            level is adjusted between retries; must be between 0 and 1.
            See the discrepancy report — this value is validated but not
            actually used in the retry logic.

    Returns:
        tuple: ``(verts, faces, normals, values)`` as returned by
            `skimage.measure.marching_cubes` — mesh vertex coordinates
            (zyx order, matching ``map``), triangular faces, per-vertex
            normals, and the sampled density value at each vertex.

    Raises:
        TypeError: If ``initial_level`` is not a float or int, or if
            ``step_size`` is not a float or int in [0, 1].
        RuntimeError: If no valid contour is found after ``max_attempts``
            retries.
    """

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