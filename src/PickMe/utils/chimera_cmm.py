from pathlib import Path
from xml.sax.saxutils import quoteattr

import pandas as pd


def cmm_write(data: pd.DataFrame, tomogram_name: str, output_directory, **kwargs):
    '''Write particle coordinates and normals to a Chimera/ChimeraX .cmm file.

    For each row in `data`, writes one marker at the particle coordinate
    and a second marker offset along its normal (scaled by pixel size and
    the grid sampling distance), joined by a link — so opening the .cmm in
    Chimera/ChimeraX shows each particle as a short vector indicating its
    orientation.

    Args:
        data (pandas.DataFrame): Particle table with RELION-style STAR
            columns: `rlnCoordinateX`, `rlnCoordinateY`, `rlnCoordinateZ`,
            `rlnNormalX`, `rlnNormalY`, `rlnNormalZ`, and
            `rlnImagePixelSize`. One row per particle.
        tomogram_name (str): Tomogram identifier, used both in the output
            filename (``<tomogram_name>.cmm``) and as part of the marker
            set's display name.
        output_directory (str or pathlib.Path): Directory the `.cmm` file
            is written into.
        **kwargs: Must include `sampling` (the grid sampling distance used
            to generate `data`), which is embedded in the marker set name
            for reference. No other keyword arguments are used.

    Returns:
        None: Writes ``<output_directory>/<tomogram_name>.cmm`` as a side
        effect; nothing is returned.

    Raises:
        KeyError: If `sampling` is not present in `kwargs`.
    '''
    grid_sampling = kwargs['sampling']
    output_path = Path(output_directory) / f'{tomogram_name}.cmm'
    marker_set_name = f'{tomogram_name} @ {grid_sampling} sampling'
    normal_id_offset = data.shape[0]

    with open(output_path, 'w', encoding='utf-8') as cmm:
        cmm.write(f'<marker_set name={quoteattr(marker_set_name)}>\n')
        for i in range(data.shape[0]):
            entry = data.iloc[i]
            x, y, z = entry['rlnCoordinateX'], entry['rlnCoordinateY'], entry['rlnCoordinateZ']
            nx, ny, nz = entry['rlnNormalX'], entry['rlnNormalY'], entry ['rlnNormalZ']
            pixel_size = entry['rlnImagePixelSize']
            normal_id = i + normal_id_offset
            cmm.write(f'<marker id="{i}" x="{x*pixel_size}" y="{y*pixel_size}" z="{z*pixel_size}" radius="10"/>\n')
            cmm.write(f'<marker id="{normal_id}" x="{(x*pixel_size)+(pixel_size*nx)}" y="{(y*pixel_size)+(pixel_size*ny)}" z="{(z*pixel_size)+(pixel_size*nz)}" r="1" g="0" b="0" radius="10"/>\n')
            cmm.write(f'<link id1="{i}" id2="{normal_id}" r="3" g="238" b="255" radius="0.5"/>\n')
        cmm.write('</marker_set>\n')
    
    return None


