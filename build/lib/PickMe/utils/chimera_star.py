import starfile

def chimera_star(star_file, output_dir):
    '''
    Function takes in a star file, and modifies the data in which allows chimerax to read. 
    The output chimera-readable file is written to the desired directory which the final output file is written to.

    :param star_dir: The directory in which the chimer-readable file will be written to
    :param star_file: path of the star file which is to be edited 
    '''   
    tomo_name = star_file.split('/')[-1].split('.')[0]
    df = starfile.read(star_file)
    chimera_readable = df.drop(labels=['rlnMicrographName', 'rlnNormalX', 'rlnNormalY', 'rlnNormalZ'], axis=1)
    starfile.write(chimera_readable, f'{output_dir}/{tomo_name}_chimera.star')