from numpy import dot, degrees, array
from numpy.random import default_rng
from math import sqrt, acos, atan2


def euler_star(centre_of_mass, particles, label, micrograph, **details):
    """Convert sampled membrane particles into RELION STAR-file data rows.

    For each particle, keeps only the outer membrane leaflet (the point
    whose normal points away from the segmentation's centre of mass) and
    assigns it a ZYZ Euler triplet (rot, tilt, psi) in the RELION
    convention, all in **degrees**:

    * ``rot`` — a uniform random draw in [0, 360), negated. There is no
      meaningful azimuthal reference around the membrane normal, so this
      angle is not derived from the data.
    * ``tilt`` — ``degrees(acos(nz))``, the polar angle between the
      particle's normal vector and the z-axis.
    * ``psi`` — ``-degrees(atan2(ny, nx))``, the azimuthal angle of the
      normal in the xy-plane, negated to match RELION's rotation sense.

    Outer-leaflet selection is done via the dot product of the particle's
    displacement from the centre of mass, ``d = particle - centre_of_mass``
    (zyx order), with its normal vector ``n``: particles are kept only when
    ``dot(n, d) > 0``, i.e. the normal points outward.

    Args:
        centre_of_mass (tuple): Centre of mass of the segmented object, in
            zyx order (as produced by ``skimage.measure.regionprops``).
        particles (dict): Particle dictionary as returned by the sampling
            functions in `PickMe.sampling`, e.g.
            `PickMe.sampling.non_random_membrane_sampling` — each value is
            a dict with ``'coordinates'`` (zyx) and ``'normal'`` (zyx).
        label (int): Object number of this segmentation within its
            tomogram, written to the ``rlnObject`` column.
        micrograph (str): Name of the tomogram/segmentation being
            processed, written to the ``rlnMicrographName`` column.
        **details: Extra keyword values for the output rows. Must include
            ``psize`` (float), the pixel size in Ångströms (read from the
            MRC header's ``voxel_size.x``), written to the
            ``rlnImagePixelSize`` column. Other keys passed by the caller
            (e.g. ``tomo_dimensions``) are accepted but currently unused —
            see the discrepancy report.

    Returns:
        list: One dict per kept (outer-leaflet) particle, each with the
            STAR columns ``rlnCoordinateX/Y/Z`` (particle position, pixel
            units, from the zyx coordinates reordered to x/y/z),
            ``rlnOriginX/Y/Z`` (always 0), ``rlnAngleRot``,
            ``rlnAngleTilt``, ``rlnAnglePsi`` (all degrees),
            ``rlnMicrographName``, ``rlnObject``, ``rlnNormalX/Y/Z``
            (normal vector, x/y/z order), and ``rlnImagePixelSize``.

    Raises:
        KeyError: If ``details`` does not contain ``'psize'``.
    """

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
            rng = default_rng()
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
                'rlnNormalZ':nz,
                'rlnImagePixelSize': details['psize']}
            data_rows.append(row)
    return data_rows


