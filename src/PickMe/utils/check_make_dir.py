from pathlib import Path


def get_output_root(directory=None):
    """Resolve the pipeline output root directory.

    By default outputs are written under ``./outputs`` relative to the
    directory PickMe is run from. If a directory is supplied, it is treated
    as an explicit output root (expanded and resolved to an absolute path)
    instead.

    Args:
        directory (str or pathlib.Path, optional): Candidate output root.
            Defaults to None, which selects ``<cwd>/outputs``.

    Returns:
        pathlib.Path: The resolved output root directory. This is a
        directory path only — it is not created by this function.
    """
    if directory is None:
        return Path.cwd() / 'outputs'
    return Path(directory).expanduser().resolve()


def check_make_dir(job_name, directory=None):
    '''
    Create (and return) the next numbered job directory for a pipeline stage.

    Ensures the output root and a `job_name` subdirectory under it exist,
    then picks the next job number and creates
    ``<output_root>/<job_name>/job<NNN>`` (zero-padded to 3 digits), e.g. the
    `extract_and_store` stage would create an `extract` job directory such
    as ``outputs/extract/job001``.

    Job numbering is global across the whole output root, not per
    `job_name`: every call scans **all** `job###` directories anywhere
    under `output_root` (via a recursive glob) and picks
    ``max(existing job numbers) + 1``. So if `filter` already has
    `job001`..`job003` and this is the first call for `choose`, the new
    directory will be `choose/job004`, not `choose/job001`. Callers that
    rely on "latest job" logic depend on this shared, monotonically
    increasing counter.

    Args:
        job_name (str): Name of the pipeline stage/job type being run
            (e.g. ``"filter"``, ``"choose"``, ``"particle_extract"``). Used
            as the subdirectory name under the output root.
        directory (str or pathlib.Path, optional): Output root override,
            passed through to :func:`get_output_root`. Defaults to None,
            which resolves to ``<cwd>/outputs``.

    Returns:
        str: Absolute path of the newly created job directory, as a plain
        string (not a `pathlib.Path`) — e.g.
        ``"/home/user/outputs/filter/job004"``.

    Note:
        Prints the resolved output root to stdout before creating any
        directories.
    '''

    output_root = get_output_root(directory)
    print(f'This is output root: {output_root}')
    output_root.mkdir(parents=True, exist_ok=True)

    job_root = output_root / job_name
    job_root.mkdir(parents=True, exist_ok=True)

    job_numbers = []
    for path in output_root.glob('**/job[0-9][0-9][0-9]'):
        if path.is_dir():
            try:
                job_numbers.append(int(path.name.removeprefix('job')))
            except ValueError:
                continue

    next_job_number = max(job_numbers, default=0) + 1
    output_directory = job_root / f'job{next_job_number:03d}'
    output_directory.mkdir()

    return str(output_directory)
    
