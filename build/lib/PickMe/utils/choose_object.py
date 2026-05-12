
def choose_object(data):
    '''
    This function takes a user's choice of tomogram's segmentation files, and can specify the specific objects witin these tomograms in which they wish to keep.
    The user can only choose from objects which have passed the volume-based filter which aims to filter out noise.

    The output of this function can be used to extract particle coordinates and output a star file.

    :param data: Dictionary containing the data. Key: tomogram, value: tomogram segmentation object dictionary (also dictionary)
    :type data: dict

    :return data_final: original dictionary modified with the appropriate choices from the user
    :rtype data_final: dict
    '''
    ask_user = input('Before processing, are there any objects of interest you would like to select from the filtered set during processing?')
    while ask_user.lower() not in ['y', 'yes', 'n', 'no']:
        print('Answer must be yes or no!')
        ask_user = input('Before processing, are there any objects of interest you would like to select from the filtered set during processing?')
    if ask_user.lower() in ['y', 'yes']:
        ask_user = True
    elif ask_user.lower() in ['n', 'no']:
        ask_user = False

    return None


        ## ---- NAPARI plugin would be here
        # Go through each tomogram, get the shape, put th