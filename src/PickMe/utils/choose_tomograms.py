import glob

import re
import os


def _format_tomogram_choices(files, max_visible=40):
    """Format a numbered, human-readable listing of tomogram filenames.

    Args:
        files (list[str]): Absolute or relative file paths to list.
        max_visible (int, optional): Maximum number of filenames to print
            before truncating with a "... and N more" line. Defaults to 40.

    Returns:
        str: Multi-line string, one numbered filename per line, suitable
        for printing directly in a CLI prompt.
    """
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


def choose_tomograms(segmentation_directory, caller=None, non_interactive=False):
    '''
    List tomogram files in a directory, with an optional interactive filter.

    Globs `segmentation_directory` for candidate files, then prompts the
    user to optionally narrow the list down to specific tomogram IDs.

    Args:
        segmentation_directory (str or pathlike): Directory containing the
            tomogram (or segmentation) files to choose from.
        caller (str, optional): Selects which glob pattern is used to find
            candidate files. Defaults to None.

            - None (or any value other than ``"convert"``): matches
              ``*segment*`` — i.e. files with "segment" in the name,
              assuming the segmentation software used leaves that marker
              in the filename.
            - ``"convert"``: matches ``*.mrc`` instead, for the
              `decompress` pipeline stage, which operates on raw `.mrc`
              tomogram files rather than segmentations.
        non_interactive (bool, optional): If True, skip the prompts
            entirely and return every matched file. This is what lets
            `filter_objects` and `convert` run under a batch scheduler
            (Slurm, SGE), where there is no terminal attached and
            `input()` would raise `EOFError`. Defaults to False.

    Returns:
        list[str]: File paths matching the glob pattern. If the user opts
        to filter (see Note below), only paths containing one of the
        chosen numeric tomogram IDs are returned; this may be an empty
        list if none match. Otherwise, all matched paths are returned
        unfiltered.

    Note:
        Unless `non_interactive` is set, prompts interactively via
        `input()`: first a yes/no question (re-asked until answered
        ``y``/``yes``/``n``/``no``), and if yes, a follow-up prompt asking
        for specific tomogram number IDs (parsed out of the response with
        a digit regex, e.g. ``"1007 1012"``). The available choices are
        printed to stdout via :func:`_format_tomogram_choices` before that
        second prompt.
    '''
    #not sure which one of the two of these to use
    #first one assumes that the segmentation software that users use will leave a segment in the file name
    files = glob.glob(os.path.join(segmentation_directory, '*segment*'))
    if caller == 'convert':
        files = glob.glob(os.path.join(segmentation_directory, '*.mrc'))
    #under --non-interactive there is nobody to narrow the list, so take all of them
    if non_interactive:
        print(f'Non-interactive mode: processing all {len(files)} matched tomogram(s).')
        return files
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
    

