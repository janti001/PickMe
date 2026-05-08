import glob

import re
import os

def choose_tomograms(segmentation_directory):
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
    ask_user = input(f'Are there specific tomograms you want to process (y/n)?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Are there specific tomograms you want to process?')
    if ask_user.lower in ['y', 'yes']:
        print(f'Tomograms available to select from:\n\n{[file.split("/")[-1] for file in files]}\n')
        tomo_choices = re.findall(r'\d+', input('What specific tomograms would you like to process?'))
        files_choice = []
        for tomo_id in tomo_choices:
            for file in files:
                if tomo_id in file:
                    files_choice.append(file)
        return files_choice
    if ask_user.lower() in ['n', 'no']:
        return files
    


