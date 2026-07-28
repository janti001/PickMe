
#imports
from numpy import random, concatenate, array, argsort, ndarray
from scipy.spatial import cKDTree

#There are three membrane sampling functions that could be used
def shuffle_sampling(coords, normal_vectors, grid_samping):
    """Randomly thin a mesh's surface points into evenly-spaced particles.

    Takes vertex coordinates and normals produced by marching cubes on a
    membrane segmentation and reduces them to a sparser set of particle
    positions. Points are visited in a random (seeded) order; for each point
    kept, every neighbour within ``grid_samping`` pixels is marked as used
    and skipped, via a `scipy.spatial.cKDTree` radius query. This gives an
    unbiased, non-deterministic order of point removal (compare to
    :func:`non_random_membrane_sampling`, which walks the points in their
    original mesh order).

    Args:
        coords (numpy.ndarray): Vertex coordinates from the mesh, one row
            per point, in zyx order. These become particle coordinates.
        normal_vectors (numpy.ndarray): Surface normal for each vertex in
            ``coords``, same row order and zyx axis order.
        grid_samping (int): Minimum enforced radius, in pixels, between two
            kept particles. Note the parameter name is misspelled (missing
            the "l" in "sampling"); this is a call-site detail, not a typo
            to silently document around.

    Returns:
        dict: Keys are the shuffled-array index of each kept particle.
            Each value is a dict with ``'coordinates'`` (the zyx point,
            numpy array of length 3) and ``'normal'`` (the corresponding
            zyx normal vector, numpy array of length 3).

    Raises:
        TypeError: If ``coords`` or ``normal_vectors`` is not a numpy
            array, or if ``grid_samping`` is not an int.
    """
    # --- Checking data types are correct before processin
    if not isinstance(coords, ndarray):
        raise TypeError('Coordinates must be a numpy array or numpy ndarray')

    if not isinstance(normal_vectors, ndarray):
        raise TypeError('Normal vectors must be a numpy array or numpy ndarray')
    
    if not isinstance(grid_samping, int):
        raise TypeError('Grid sampling rate must be an integer value')



    particles={}
    used=set()
    coords_shuffle= []
    #instantiate random generator
    #seed used for reproducible randomisation
    SEED = 12345
    rng = random.default_rng(seed = SEED)

    #concatenate the coordinates and normals and permute all together
    coords_normals = concatenate((coords, normal_vectors), axis=1)
    coords_normals_shuffled = rng.permutation(coords_normals)
    #retrieve all coordinates
    for particle in coords_normals_shuffled:
        coords_shuffle.append(particle[:3])
    #create array and create tree
    coords_shuffle_array = array(coords_shuffle)
    tree = cKDTree(coords_shuffle_array)

    for index, particle in enumerate(coords_normals_shuffled):
        if index in used:
            continue
        particles[index]={'coordinates': particle[:3],
                          'normal': particle[3:]}
        #find all neighbours within a given sampling distance
        neighbours = tree.query_ball_point(x=particle[:3], r=grid_samping)
        used.update(neighbours)

    return particles







def non_random_membrane_sampling(coords, normal_vectors, grid_sampling):
    """Thin a mesh's surface points into particles, in their original order.

    This is the sampling function used by the ``particle_extraction`` CLI
    pipeline (called with ``grid_sampling`` set from the CLI's
    ``--sample-rate`` option). It walks ``coords`` in the order marching
    cubes produced them (no shuffling) and, for each point not yet used,
    keeps it as a particle and marks every neighbour within
    ``grid_sampling`` pixels as used via a `scipy.spatial.cKDTree` radius
    query. This is a simple greedy rejection scheme: once an area is
    covered by a kept particle's radius, no further particle can be placed
    there, which enforces a minimum spacing between particles.

    Args:
        coords (numpy.ndarray): Vertex coordinates from the mesh, one row
            per point, in zyx order. These become particle coordinates.
        normal_vectors (numpy.ndarray): Surface normal for each vertex in
            ``coords``, same row order and zyx axis order.
        grid_sampling (int): Minimum enforced radius, in pixels, between
            two kept particles. This is the CLI's ``--sample-rate`` value.

    Returns:
        dict: Keys are the index of each kept particle within ``coords``.
            Each value is a dict with ``'coordinates'`` (the zyx point,
            numpy array of length 3) and ``'normal'`` (the corresponding
            zyx normal vector, numpy array of length 3).

    Raises:
        TypeError: If ``coords`` or ``normal_vectors`` is not a numpy
            array, or if ``grid_sampling`` is not an int.
    """
    # --- Checking data types are correct before processin
    if not isinstance(coords, ndarray):
        raise TypeError('Coordinates must be a numpy array or numpy ndarray')

    if not isinstance(normal_vectors, ndarray):
        raise TypeError('Normal vectors must be a numpy array or numpy ndarray')
    
    if not isinstance(grid_sampling, int):
        raise TypeError('Grid sampling rate must be an integer value')
    particles = {}
    used=set()
    tree = cKDTree(coords)

    for index, particle in enumerate(coords):
        if index in used:
            continue
        
        particles[index] = {'coordinates':particle,
                            'normal':normal_vectors[index]}
        #find all neighbours within a given sampling distance
        neighbours = tree.query_ball_point(x=particle, r=grid_sampling)
        used.update(neighbours)
    
    return particles







def density_based_sampling(coords, normal_vectors, grid_sampling):
    """Thin a mesh's surface points, visiting sparse regions first.

    A density-aware alternative to `non_random_membrane_sampling`. Because
    the cKDTree radius-rejection approach is greedy, sampling points in a
    dense cluster first tends to wipe out neighbours that belonged to
    sparser areas of the mesh. To reduce that bias, every point's local
    neighbour count (within ``grid_sampling`` pixels) is computed first,
    and points are then visited in ascending order of that count — the
    point in the least crowded neighbourhood is kept first, and its
    neighbours are marked used, before moving on to progressively denser
    areas.

    Args:
        coords (numpy.ndarray): Vertex coordinates from the mesh, one row
            per point, in zyx order. These become particle coordinates.
        normal_vectors (numpy.ndarray): Surface normal for each vertex in
            ``coords``, same row order and zyx axis order.
        grid_sampling (int): Minimum enforced radius, in pixels, between
            two kept particles, and the radius used to compute each
            point's local neighbour density.

    Returns:
        dict: Keys are the index of each kept particle. Each value is
            intended to be a dict with ``'coordinates'`` and ``'normal'``
            entries, matching the other sampling functions in this module.

    Raises:
        TypeError: If ``coords`` or ``normal_vectors`` is not a numpy
            array, or if ``grid_sampling`` is not an int.

    Note:
        This function currently raises at runtime before returning
        anything useful — see the discrepancy report for details.
    """
    # --- Checking data types are correct before processin
    if not isinstance(coords, ndarray):
        raise TypeError('Coordinates must be a numpy array or numpy ndarray')

    if not isinstance(normal_vectors, ndarray):
        raise TypeError('Normal vectors must be a numpy array or numpy ndarray')
    
    if not isinstance(grid_sampling, int):
        raise TypeError('Grid sampling rate must be an integer value')
    
    particles = {}
    used=set()
    coords_shuffled=[]

    SEED = 12345
    rng = random.default_rng(seed = SEED)
    #concatenate the coordinates and normals and permute all together
    coords_normals = concatenate((coords, normal_vectors), axis=1)
    coords_normals_shuffled = rng.permutation(coords_normals)
    #retrieve coordinates, make array and tree
    for particle in coords_normals_shuffled:
        coords_shuffled.append(particle[:3])
    coords_shuffled_array = array(coords_shuffled)
    tree = cKDTree(coords_shuffled_array)
    #create a list of how many neighbours are encountered by each point
    neighbour_density = [len(tree.qury_ball_point(x=particle[:3], r=grid_sampling)) for particle in coords_normals_shuffled]
    #sort this list and get the indices 
    order = argsort(neighbour_density)
    #go through indices 
    for i in order:
        if i in used:
            continue
        particles[i]={'coordinates':coords_normals_shuffled[i[:3]],
                      'normal': coords_normals_shuffled[i[3:]]}
        neighbours = tree.query_ball_point(x=coords_shuffled[i], r=grid_sampling)
        used.update(neighbours)
    return particles




