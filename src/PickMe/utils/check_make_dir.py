from pathlib import Path


def get_output_root(directory=None):
    """Return the root directory used for PickMe pipeline outputs."""
    if directory is None:
        return Path.cwd() / 'outputs'
    return Path(directory).expanduser().resolve()


def check_make_dir(job_name, directory=None):
    '''
    When this function is called, it will check if there is an output directory for the current pipeline segment. 
    For example, if this is ran in extract_and_store, it will check if there is an extract directory in output.

    This is done so we can store any results we may want to write into an output directory.

    By default outputs are written under ./outputs from the directory where PickMe is run.
    If directory is provided, it is treated as the pipeline output root.

    :param directory: Path of the directory for which we want to check.
    :param job_name: name of the type of job that is being run
    :type directory: str, pathlike
    :type jobe_name: str

    :return output_directory: file path of the output directory that was made
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
    
