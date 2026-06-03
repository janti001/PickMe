import glob

import re
import os


def _format_tomogram_choices(files, max_visible=40):
    """Return a readable list of available tomogram filenames for CLI prompts."""
    file_names = sorted(os.path.basename(file) for file in files)
    visible_names = file_names[:max_visible]

    lines = [
        f'  {index:>3}. {file_name}'
        for index, file_name in enumerate(visible_names, start=1)
    ]

    hidden_count = len(file_names) - len(visible_names)
    if hidden_count > 0:
        lines.append(f'  ... and {hidden_count} more tomogram(s).')
        lines.append('  Refine your input by typing the tomogram number IDs, e.g. 1007 1012.')

    return '\n'.join(lines)


def choose_tomograms(segmentation_directory, caller=None):
    '''
    Function creates a list of absolute file paths from a given directory. 

    :params segmentation_directory: Directory where the tomogram segmentation files are
    :type segmentation_directory: str, pathlike

    :return files: list of segmentation files
    :rtype: list
    
    '''
    #not sure which one of the two of these to use
    #first one assumes that the segmentation software that users use will leave a segment in the file name
    files = glob.glob(os.path.join(segmentation_directory, '*segment*'))
    if caller == 'convert':
        files = glob.glob(os.path.join(segmentation_directory, '*.mrc'))
    ask_user = input(f'Are there specific tomograms you want to process (y/n)?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Are there specific tomograms you want to process?')
    if ask_user.lower() in ['y', 'yes']:
        print(f'\nTomograms available to select from ({len(files)} found):')
        print(_format_tomogram_choices(files))
        print()
        tomo_choices = re.findall(r'\d+', input('What specific tomograms would you like to process?'))
        files_choice = []
        for tomo_id in tomo_choices:
            for file in files:
                if tomo_id in file:
                    files_choice.append(file)
        return files_choice
    if ask_user.lower() in ['n', 'no']:
        return files
    

