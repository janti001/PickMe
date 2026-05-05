import glob

import re
import os

def choose_tomograms(segmentation_directory):

    #not sure which one of the two of these to use
    #first one assumes that the segmentation software that users use will leave a segment in the file name
    files = glob.glob(os.path.join(segmentation_directory, '*segment*'))
    files = glob.glob(segmentation_directory)

    user_decision = input(f'Are there specific tomograms you want to process?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Are there specific tomograms you want to process?')
    if user_decision.lower in ['y', 'yes']:
        print(f'Tomograms available to select from:\n\n{[file.split("/")[-1] for file in files]}\n')
        tomo_choices = re.findall(r'\d+', input('What specific tomograms would you like to process?'))
        files_choice = []
        for tomo_id in tomo_choices:
            for file in files:
                if tomo_id in file:
                    files_choice.append(file)
        return files_choice
    if user_decision.lower() in ['n', 'no']:
        return files
    


