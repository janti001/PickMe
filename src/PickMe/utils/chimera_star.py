import starfile

def chimera_star(star_file, output_dir):
    '''Convert a particle STAR file into a ChimeraX-readable STAR file.

    Reads `star_file`, drops the columns ChimeraX cannot interpret
    (`rlnMicrographName`, `rlnNormalX`, `rlnNormalY`, `rlnNormalZ`), and
    writes the result as a new STAR file.

    Args:
        star_file (str): Path to the particle STAR file to convert. The
            output filename is derived from this path's basename (text
            before the first ``.``), with ``_chimera`` appended.
        output_dir (str or pathlib.Path): Directory the ChimeraX-readable
            STAR file is written into.

    Returns:
        None: Writes ``<output_dir>/<tomo_name>_chimera.star`` as a side
        effect; nothing is returned.

    Note:
        The original reST docstring named this parameter `star_dir`; the
        actual parameter is `output_dir`. Corrected here.
    '''
    tomo_name = star_file.split('/')[-1].split('.')[0]
    df = starfile.read(star_file)
    chimera_readable = df.drop(labels=['rlnMicrographName', 'rlnNormalX', 'rlnNormalY', 'rlnNormalZ'], axis=1)
    starfile.write(chimera_readable, f'{output_dir}/{tomo_name}_chimera.star')