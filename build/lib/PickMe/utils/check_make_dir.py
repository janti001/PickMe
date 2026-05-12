from pathlib import Path

def check_make_dir(job_name, directory=None):
    '''
    When this function is called, it will check if there is an output directory for the current pipeline segment. 
    For example, if this is ran in extract_and_store, it will check if there is an extract directory in output.

    This is done so we can store any results we may want to write into an output directory.

    This function, for now, assumes a certain file structure - as determined by the project structure - we use relative paths to coordinate this.

    :param directory: Path of the directory for which we want to check.
    :param job_name: name of the type of job that is being run
    :type directory: str, pathlike
    :type jobe_name: str

    :return output_directory: file path of the output directory that was made
    '''
    
    output_root = Path(__file__).resolve().parents[3] / 'outputs'
    output_root.mkdir(exist_ok=True)

    directory = directory if directory is not None else job_name
    job_root = output_root / directory
    job_root.mkdir(exist_ok=True)

    job_numbers = []
    for path in output_root.glob('*/job[0-9][0-9][0-9]'):
        if path.is_dir():
            try:
                job_numbers.append(int(path.name.removeprefix('job')))
            except ValueError:
                continue

    next_job_number = max(job_numbers, default=0) + 1
    output_directory = job_root / f'job{next_job_number:03d}'
    output_directory.mkdir()

    return str(output_directory)
    
