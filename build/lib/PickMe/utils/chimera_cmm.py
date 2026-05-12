from pathlib import Path
from xml.sax.saxutils import quoteattr

import pandas as pd


def cmm_write(data: pd.DataFrame, tomogram_name: str, output_directory, **kwargs):
    '''
    The particle coordinates and their normals will be written to a .cmm file which can be viewed in chimera

    :param data: Dataframe containing all the data entries you wish to process. This must contain x,y,z coordinates and normals in a relion-like naming convention. I.e,. rlnCordinateX, and rlnNormalX
    :param tomogram_name: The tomogram file identifier which is to-be processed. 
    :param output_directory: Directory where cmm files should be written to. Ideally the same output directory in which the job is being run should be applied here. 

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
            cmm.write(f'<marker id="{i}" x="{x*pixel_size}" y="{y*pixel_size}" z="{z*pixel_size}" radius="1"/>\n')
            cmm.write(f'<marker id="{normal_id}" x="{(x*pixel_size)+(pixel_size*nx)}" y="{(y*pixel_size)+(pixel_size*ny)}" z="{(z*pixel_size)+(pixel_size*nz)}" r="1" g="0" b="0" radius="1"/>\n')
            cmm.write(f'<link id1="{i}" id2="{normal_id}" r="3" g="238" b="255" radius="0.5"/>\n')
        cmm.write('</marker_set>\n')
    
    return None


