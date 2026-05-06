from numpy import dot, degrees, array
from numpy.random import default_rng
from math import sqrt, acos, atan2


def euler_star(centre_of_mass, particles, label, micrograph, **details):
    '''
    This function will take the coordinates of the centre of mass of the segmentation and particle x,y,z coordinates to calculate two euler angles.
    In a spherical coordinate system, to euler angles help determine their position, thus only two are needed.

    :param centre_of_mass: tuple coordinates of the centre of mass of the segmentation, zyx format
    :param particles: particle dictionary containing their coordinates and normal vectors
    :param label: object number within a particular tomogram
    :param micrograph: Name of the tomogram segmentation being processed 
    :param **details: any other details which may be useful to add to the star file, such as micrograph name, or other data which may be useful for downstream processing. This is a flexible argument which can be used to add any other data which may be useful for downstream processing, such as micrograph name, or other data which may be useful for downstream processing.
    :type label: int
    :type centre_of_mass: tuple
    :type particles: dict

    :return: a list of dictionaries wth the entry fields
    :rtype: list

    '''

    # -- Type checking before doing any processing
    # haven't put anything here for now - can come back to this

    data_rows = []
    SEED = 123451
    
    centz, centy, centx = centre_of_mass[0], centre_of_mass[1], centre_of_mass[2]

    #loop through particles

    for particle in particles.values():
        z_coord, y_coord, x_coord = particle['coordinates'][0], particle['coordinates'][1], particle['coordinates'][2]

        # --- Enforcing directionality of normals
        # --- only want the outer membrane leaflet
        dz, dy, dx = ((z_coord - centz), (y_coord-centy), (x_coord-centx))
        d = array([dz,dy,dx])
        #getting normals
        n = particle['normal']

        # --- Calculate dot product to get just outer leaflet
        if dot(n, d) > 0:
            #instantiate random number generator
            rng = default_rng(seed=SEED)
            #Getting each normal component
            nz, ny, nx = n[0], n[1], n[2]
            
            # -- ROT
            rot = -(rng.uniform(0, 360))

            # -- TILT
            tilt = degrees(acos(nz))
            #-- PSI
            psi = -(degrees(atan2(ny, nx)))
            # -- Make data row
            row = {'rlnCoordinateX':x_coord,
                'rlnCoordinateY':y_coord,
                'rlnCoordinateZ':z_coord,
                'rlnOriginX':0,
                'rlnOriginY':0,
                'rlnOriginZ':0,
                'rlnAngleRot':rot,
                'rlnAngleTilt':tilt,
                'rlnAnglePsi':psi,
                'rlnMicrographName':micrograph,
                'rlnObject':label,
                'rlnNormalX':nx,
                'rlnNormalY':ny,
                'rlnNormalZ':nz}
            data_rows.append(row)
    return data_rows



    