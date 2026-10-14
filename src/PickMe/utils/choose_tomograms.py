"""Interactive selection and manual pairing of tomogram / segmentation files.

Users narrow down which files to process by typing **index numbers** from a
printed list (``1 3 5-8``, ``1,3`` or ``all``), never file names or digits
found inside names. Indices work for any naming scheme and cannot
accidentally match several files the way substring matching did.

This module also provides the fallback prompt that lets a user pair
segmentations with tomograms by hand when automatic prefix matching fails.
"""
import glob
import os

from .naming import natural_sort_key, parse_index_selection, file_id

SEGMENTATION_PATTERN = "*segment*"


def format_indexed_choices(files):
    """Format a 1-based, human-readable listing of file names.

    Every file is shown (no truncation): with index selection the user can
    only pick what they can see.

    Args:
        files (list[str]): File paths, already in the order to display. The
            caller sorts; this function does not reorder.

    Returns:
        str: One ``'  {i:>3}. {basename}'`` line per file, joined by newlines.
    """
    return '\n'.join(
        f'  {index:>3}. {os.path.basename(path)}'
        for index, path in enumerate(files, start=1)
    )


def _ask_yes_no(question):
    """Ask a yes/no question, re-asking until the answer is valid.

    Args:
        question (str): Prompt text shown to the user.

    Returns:
        bool: True for y/yes, False for n/no.
    """
    answer = input(question).strip().lower()
    # Loop instead of failing: a typo should not abort a long pipeline run.
    while answer not in ('y', 'yes', 'n', 'no'):
        print('Answer must be yes or no!')
        answer = input(question).strip().lower()
    return answer in ('y', 'yes')


def choose_files(files, kind="tomogram", non_interactive=False):
    """Let the user pick a subset of files by index.

    Args:
        files (list[str]): Candidate file paths (any order).
        kind (str, optional): Word used in prompts, e.g. ``"tomogram"`` or
            ``"segmentation"``. Defaults to ``"tomogram"``.
        non_interactive (bool, optional): If True, skip all prompts and
            return every file (needed for batch jobs with no terminal, where
            ``input()`` would raise ``EOFError``). Defaults to False.

    Returns:
        list[str]: Chosen paths in natural sort order (``TS_2`` before
        ``TS_10``). Empty if ``files`` is empty.
    """
    if not files:
        print(f'No {kind} files found.')
        return []

    # Natural sort so the numbering the user sees is the order they expect.
    files = sorted(files, key=lambda path: natural_sort_key(os.path.basename(path)))

    if non_interactive:
        print(f'Non-interactive mode: processing all {len(files)} {kind}(s).')
        return files

    if not _ask_yes_no(f'Are there specific {kind}s you want to process (y/n)?'):
        return files

    print(f'\n{kind.capitalize()}s available ({len(files)} found):')
    print(format_indexed_choices(files))
    print()
    print('Type index numbers, e.g. 1 3 5-8, or all.')

    # Re-ask on bad input: the user has already seen the list, so a typo
    # should cost one retry, not a restart of the whole command.
    while True:
        text = input(f'Which {kind}s would you like to process? ')
        try:
            indices = parse_index_selection(text, len(files))
        except ValueError as error:
            print(error)
            continue
        break

    chosen = [files[i] for i in indices]
    print(f'Selected {len(chosen)} {kind}(s):')
    for path in chosen:
        print(f'  {os.path.basename(path)}')
    return chosen


def choose_tomograms(segmentation_directory, caller=None, non_interactive=False):
    """Find candidate files in a directory and let the user pick some.

    Args:
        segmentation_directory (str or pathlike): Directory to search.
        caller (str, optional): ``"convert"`` matches ``*.mrc`` tomograms;
            anything else matches ``SEGMENTATION_PATTERN`` (``*segment*``),
            assuming the segmentation software leaves "segment" in the file
            name. Defaults to None.
        non_interactive (bool, optional): Take every file without prompting.
            Defaults to False.

    Returns:
        list[str]: Chosen file paths; see :func:`choose_files`.
    """
    if caller == 'convert':
        pattern, kind = '*.mrc', 'tomogram'
    else:
        pattern, kind = SEGMENTATION_PATTERN, 'segmentation'
    files = glob.glob(os.path.join(segmentation_directory, pattern))
    return choose_files(files, kind=kind, non_interactive=non_interactive)


def pair_unmatched(unmatched_segmentations, unpaired_tomograms, non_interactive=False):
    """Manually pair segmentations with tomograms when name matching failed.

    Args:
        unmatched_segmentations (list[str]): Segmentation paths that
            automatic prefix matching could not assign to a tomogram.
        unpaired_tomograms (list[str]): Tomogram paths still without a
            segmentation.
        non_interactive (bool, optional): If True, warn and skip instead of
            prompting. Defaults to False.

    Returns:
        dict[str, dict[str, str]]: ``{tomogram_id: {"tomogram": path,
        "segmentation": path}}`` for each pair made, where ``tomogram_id`` is
        ``file_id(tomogram_path)``. Empty if nothing was paired.
    """
    if not unmatched_segmentations or not unpaired_tomograms:
        return {}

    segmentations = sorted(
        unmatched_segmentations, key=lambda p: natural_sort_key(os.path.basename(p))
    )
    tomograms = sorted(
        unpaired_tomograms, key=lambda p: natural_sort_key(os.path.basename(p))
    )

    if non_interactive:
        print('Warning: some segmentations were skipped: could not match to a '
              'tomogram by name; run interactively to pair it by index:')
        for path in segmentations:
            print(f'  skipped: {os.path.basename(path)}')
        return {}

    print('\nSome segmentations could not be matched to a tomogram by name.')
    print('Automatic matching pairs a segmentation with the tomogram whose '
          'file name it starts with.')
    print(f'\nUnmatched segmentations ({len(segmentations)}):')
    print(format_indexed_choices(segmentations))
    print(f'\nTomograms without a segmentation ({len(tomograms)}):')
    print(format_indexed_choices(tomograms))
    print()

    pairs = {}
    used = set()  # 0-based tomogram indices already taken
    for seg_path in segmentations:
        seg_name = os.path.basename(seg_path)
        # Re-ask until the answer is usable, so one typo does not lose the
        # pairs already made.
        while True:
            text = input(f'Tomogram index for {seg_name} (blank to skip): ').strip()
            if not text:
                print(f'  Skipping {seg_name}.')
                break
            try:
                index = int(text)
            except ValueError:
                print(f"'{text}' is not a single whole number.")
                continue
            if not 1 <= index <= len(tomograms):
                print(f'{index} is out of range (1-{len(tomograms)}).')
                continue
            if (index - 1) in used:
                print(f'Tomogram {index} is already paired; each tomogram can be used once.')
                continue
            used.add(index - 1)
            tomo_path = tomograms[index - 1]
            pairs[file_id(tomo_path)] = {
                'tomogram': tomo_path,
                'segmentation': seg_path,
            }
            print(f'  {seg_name} -> {os.path.basename(tomo_path)}')
            break
    return pairs
