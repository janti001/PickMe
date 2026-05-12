
#imports
from numpy import random, concatenate, array, argsort, ndarray
from scipy.spatial import cKDTree

#There are three membrane sampling functions that could be used
def shuffle_sampling(coords, normal_vectors, grid_samping):
    '''
    This function takes a set of points which have been curated by making a mesh around volumetric data, in mrc format.

    :param coords: A numpy array of coordinates which will act as particle coordinates
    :param normal_vectors: A numpy array of the vectors of the normal from a marching cubes output 
    :param grid_sampling: Integer value for the maximum distance between two particles, in pixels
    :type coords: Numpy n-dimentional array
    :type normal_vectors: Numpy n-dimensional array
    :type grid_sampling: int

    :return:
    :rtype: dictionary of particle coordinates and their normal vectors

    '''
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
    '''
    This function takes a set of points which have been curated by making a mesh around volumetric data, in mrc format.

    :param coords: A numpy array of coordinates which will act as particle coordinates
    :param normal_vectors: A numpy array of the vectors of the normal from a marching cubes output 
    :type coords: Numpy n-dimentional array
    :type normal_vectors: Numpy n-dimensional array

    :return:
    :rtype: dictionary of particle coordinates and their normal vectors

    '''
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
    '''
    This function samples a membrane but is density based. 
    As the cKDTree binary search is a greedy algorithm, samples which are more closer together wipe out more points, in which those points could have sparse neighbourhoods.
    
    Points which are in the least dense parts of the mesh are samples and queried first.

    We essentially want to remove as much bias as we can.

    :param coords: A numpy array of coordinates which will act as particle coordinates
    :param normal_vectors: A numpy array of the vectors of the normal from a marching cubes output 
    :type coords: Numpy n-dimentional array
    :type normal_vectors: Numpy n-dimensional array

    :return:
    :rtype: dictionary of particle coordinates and their normal vectors

    '''
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




