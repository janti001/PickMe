
def choose_object(data):
    '''Ask the user whether they want to hand-pick objects from filtered data.

    Intended to let the user choose specific objects to keep, per
    tomogram, from the volume-filtered candidate set — restricting which
    objects go on to particle extraction. As currently implemented, this
    function only asks the yes/no question and does not yet perform any
    selection; see Note.

    Args:
        data (dict): Dictionary keyed by tomogram, with each value itself
            a dictionary of that tomogram's (already volume-filtered)
            segmentation objects.

    Returns:
        None: Currently always returns `None`, regardless of the user's
        answer. See Note — the intended per-object selection (docstring
        title notwithstanding) is not implemented.

    Note:
        Prompts interactively via `input()` for a yes/no answer (re-asked
        until answered ``y``/``yes``/``n``/``no``). **Likely bug /
        incomplete implementation**: the answer is parsed into a local
        boolean (`ask_user`) but that value is never used — the function
        falls straight through to ``return None``. The commented-out code
        below the `return` ("NAPARI plugin would be here...") indicates
        the actual object-selection logic was never written. Reported
        here per the "document, don't fix" constraint; not implemented in
        this pass.
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