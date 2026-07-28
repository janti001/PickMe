from pathlib import PosixPath
import re
from ..config import mgraph_suffix

def get_mgraph(segmentation_file_path, caller=None):
    '''
    Derive a tomogram/micrograph identifier from a segmentation file path.

    Parses the filename (the final path segment) by splitting on
    underscores. Which token is used, and what is returned, depends
    entirely on `caller`, because different pipeline stages hand this
    function differently-named files (see Args below).

    Args:
        segmentation_file_path (str or pathlib.PosixPath): Path to a
            segmentation (or related) file. Only the basename is used;
            any directory components are discarded.
        caller (str, optional): Selects the parsing behaviour. Defaults to
            None.

            - None (default) and any value other than ``"particle_extract"``
              or ``"decompress"``: assumes a filename of the form
              ``TS_<id>_...`` (as produced by the raw/`extract_objects`
              inputs). Splits on ``"_"`` and takes token index 1 as the
              tomogram ID, returning ``"TS_<id>.tomostar"``.
            - ``"particle_extract"``: intended for files coming out of the
              `choose_objects` stage, named ``<id>_filtered_chosen.mrc.gz``
              (no ``TS_`` prefix). It reuses the *same* index-1 split logic
              as the default branch, which for this filename shape
              actually picks up the literal token ``"filtered"`` rather
              than the tomogram ID — see Note below.
            - ``"decompress"``: extracts the first run of digits found
              anywhere in the filename via regex and returns it as-is.
              This is a bare numeric ID string, e.g. ``"1416"`` — not a
              ``.tomostar`` filename, and not prefixed with ``TS_`` or
              suffixed with the tomostar suffix.

    Returns:
        str: For the default branch, a ``.tomostar`` filename of the form
        ``"TS_<id>.tomostar"``. For ``caller="decompress"``, a bare numeric
        ID string instead. For ``caller="particle_extract"``, in practice
        currently a malformed value (see Note) rather than a usable
        ``.tomostar`` filename or ID.

    Note:
        **Likely bug** — the ``caller="particle_extract"`` branch is
        copy-pasted from the default branch and assumes the same
        ``TS_<id>_...`` filename layout. But its actual callers (see
        `main.py`, `particle_extraction`) pass filenames shaped
        ``<id>_filtered_chosen.mrc.gz`` (produced by `choose_objects`,
        which does not prepend ``TS_``). Splitting that filename on
        ``"_"`` gives ``[<id>, "filtered", "chosen.mrc.gz"]``, so index 1
        is the string ``"filtered"``, not the tomogram ID — this branch
        should almost certainly index token 0 instead. Reported here per
        the "document, don't fix" constraint; not corrected in this pass.
    '''

    if isinstance(segmentation_file_path, PosixPath):
        file_path_string = str(segmentation_file_path)
        path_parts = file_path_string.split('/')
    else:
        path_parts = segmentation_file_path.split('/')
    segmentation_file = path_parts[-1]

    #check if it is from object choice job
    if caller == 'particle_extract':
        #/Users/jantinoro/Documents/LIDo/Rotation_2/python_projects/PickMe/outputs/choose/job005/1007_filtered_chosen.mrc.gz
        mgraph_parts = segmentation_file.split('_')
        #print(f'Mgraph parts: {mgraph_parts}')
        #print(f'{mgraph_parts[0]}')
        mgraph_name = f'TS_{mgraph_parts[1]}{mgraph_suffix}'

    elif caller == 'decompress':
        mgraph_name = re.findall(r'\d+', segmentation_file)[0]
    else:
        mgraph_parts = segmentation_file.split('_')
        mgraph_name = f'TS_{mgraph_parts[1]}{mgraph_suffix}'


    return mgraph_name