import os

def check_make_dir(directory, job_name):
    '''
    When this function is called, it will check if there is an output directory for the current pipeline segment. 
    For example, if this is ran in extract_and_store, it will check if there is an extract directory in output.

    This is done so we can store any results we may want to write into an output directory.

    This function, for now, assumes a certain file structure - as determined by the project structure - we use relative paths to coordinate this.

    :param directory: Path of the directory for which we want to check.
    :param job_name: name of the type of job that is being run
    :type directory: str, pathlike
    '''

    if directory is not None:
        outputs_directories = os.listdir('../outputs/')
        if directory not in outputs_directories:
            os.mkdir(f'../outputs/{directory}')
    elif directory is None:
        directory = job_name
        outputs_directories = os.listdir('../outputs/')
        if directory not in outputs_directories:
            os.mkdir(f'../outputs/{directory}')
    
    return None