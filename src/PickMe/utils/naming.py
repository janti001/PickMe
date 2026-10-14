"""Filename-agnostic naming rules shared by every PickMe pipeline stage.

PickMe used to assume files were called ``TS_<id>_...`` and pulled the tomogram
ID out with ``split("_")[1]``. That breaks as soon as someone uses a different
naming scheme. These pure functions (no file I/O, stdlib only) replace that
assumption with simple, predictable rules:

* A file's *identifier* is its name minus an MRC extension.
* A segmentation belongs to the tomogram whose identifier is the longest prefix
  of the segmentation's file name. Segmentation tools append to the input name,
  e.g. MemBrain-seg turns ``TS_1166_10.00Apx.mrc`` into
  ``TS_1166_10.00Apx_MemBrain_seg_v10_beta.ckpt_segmented.mrc``.
* Warp/M ``.tomostar`` names drop the trailing ``_<pixel size>Apx``.
* Users pick files by 1-based index, never by typing names.
"""

import os
import re

# Longest first: ".mrc.gz" must be tried before ".mrc", otherwise "a.mrc.gz"
# would be left as "a.mrc" + ".gz" instead of being recognised as "a".
MRC_EXTENSIONS = (".mrc.gz", ".mrc.bz2", ".mrc")

# Suffixes PickMe itself appends to output names; see strip_pickme_suffix().
PICKME_SUFFIXES = ("_filtered", "_chosen", "_decompressed")

_APIX_RE = re.compile(r"_\d+(?:\.\d+)?Apx$")
_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")
_OBJ_RE = re.compile(r"_obj\d+$")


def _basename(path) -> str:
    """Returns the final path component of a str or PathLike."""
    return os.path.basename(os.fspath(path))


def file_id(path) -> str:
    """Returns a file's identifier: its basename minus a known MRC extension.

    The extension match is case-insensitive, but the returned stem keeps its
    original case. A name without a known extension is returned unchanged.

    Args:
        path: File path (str or os.PathLike).

    Returns:
        The basename without ``.mrc.gz``, ``.mrc.bz2`` or ``.mrc``.
    """
    name = _basename(path)
    lowered = name.lower()
    for ext in MRC_EXTENSIONS:  # longest first, see MRC_EXTENSIONS
        if lowered.endswith(ext):
            return name[: -len(ext)]
    return name


def natural_sort_key(text) -> list:
    """Returns a sort key that orders embedded numbers numerically.

    ``'TS_2'`` sorts before ``'TS_10'``, which plain string sorting gets wrong.

    Args:
        text: String (or path) to build a key for; ``str()`` is applied to it.

    Returns:
        Alternating str and int chunks, always starting with a str, so keys
        from different inputs compare without type errors.
    """
    # re.split with a capture group keeps the digits; even positions are text,
    # odd positions are numbers, so str/int always line up when comparing.
    parts = re.split(r"(\d+)", str(text))
    return [int(p) if i % 2 else p for i, p in enumerate(parts)]


def match_segmentations(tomograms, segmentations):
    """Pairs each segmentation with the tomogram whose id is its longest prefix.

    Longest prefix means ``tomo10_seg.mrc`` matches ``tomo10``, not ``tomo1``.
    If two or more segmentations match the same tomogram we cannot tell which
    is right, so all of them are reported as unmatched and that tomogram gets
    no pair; the user resolves it by hand.

    Args:
        tomograms: List of tomogram path strings.
        segmentations: List of segmentation path strings.

    Returns:
        A tuple ``(pairs, unmatched)``. ``pairs`` maps tomogram id to
        ``{"tomogram": path, "segmentation": path}``, ordered naturally by id.
        ``unmatched`` lists segmentation paths, naturally sorted by basename,
        that matched no tomogram or were ambiguous.

    Raises:
        ValueError: If two tomograms share the same file id.
    """
    by_id = {}
    for tomo in tomograms:
        tomo_id = file_id(tomo)
        if tomo_id in by_id:
            raise ValueError(
                f"Two tomograms have the same id '{tomo_id}': "
                f"{by_id[tomo_id]} and {tomo}"
            )
        by_id[tomo_id] = tomo

    matches = {}  # tomogram id -> list of segmentation paths
    unmatched = []
    for seg in segmentations:
        seg_name = _basename(seg)
        # An empty id would be a prefix of everything, so it must never match.
        candidates = [i for i in by_id if i and seg_name.startswith(i)]
        if candidates:
            matches.setdefault(max(candidates, key=len), []).append(seg)
        else:
            unmatched.append(seg)

    pairs = {}
    for tomo_id in sorted(matches, key=natural_sort_key):
        segs = matches[tomo_id]
        if len(segs) == 1:
            pairs[tomo_id] = {"tomogram": by_id[tomo_id], "segmentation": segs[0]}
        else:
            unmatched.extend(segs)  # ambiguous: hand all of them to the user

    unmatched.sort(key=lambda p: natural_sort_key(_basename(p)))
    return pairs, unmatched


def tomostar_name(tomogram_id: str) -> str:
    """Returns the Warp/M ``.tomostar`` name for a tomogram id.

    One trailing ``_<number>Apx`` (integer or decimal) is removed; ``Apx``
    anywhere else in the name is left alone.

    Args:
        tomogram_id: Tomogram identifier without extension.

    Returns:
        E.g. ``'TS_1166_10.00Apx'`` -> ``'TS_1166.tomostar'``.
    """
    return _APIX_RE.sub("", tomogram_id) + ".tomostar"


def strip_pickme_suffix(name: str) -> str:
    """Removes PickMe's own trailing suffixes from an id.

    Repeats until none remain, because stages stack them
    (``X_filtered_chosen``). Suffixes in the middle of a name are untouched.

    Args:
        name: Identifier without extension.

    Returns:
        The name without trailing ``_filtered``/``_chosen``/``_decompressed``.
    """
    changed = True
    while changed:
        changed = False
        for suffix in PICKME_SUFFIXES:
            # Require something to remain so we never return an empty id.
            if name.endswith(suffix) and len(name) > len(suffix):
                name = name[: -len(suffix)]
                changed = True
    return name


def tomogram_id_from_name(name: str) -> str:
    """Recovers the tomogram id from a PickMe output id (no extension).

    Like strip_pickme_suffix(), but also removes the per-object marker
    ``_obj<digits>`` written by ``choose_objects --write-selections``. It is
    kept separate so strip_pickme_suffix() never touches ``_obj<digits>``.

    Args:
        name: Output identifier without extension, e.g. ``'TS_1_10Apx_obj4'``.

    Returns:
        The name with trailing PickMe suffixes and ``_obj<digits>`` removed,
        e.g. ``'TS_1_10Apx'``. ``'X_object'`` is unchanged (needs digits).
    """
    while True:
        stripped = strip_pickme_suffix(name)
        match = _OBJ_RE.search(stripped)
        # Require something to remain so we never return an empty id.
        if match and match.start() > 0:
            stripped = stripped[: match.start()]
        if stripped == name:
            return name
        name = stripped


def parse_index_selection(text: str, count: int) -> list[int]:
    """Parses a user's 1-based selection into sorted 0-based indices.

    Accepts single numbers (``3``), inclusive ranges (``5-8`` or ``5 - 8``) and
    ``all``, separated by spaces and/or commas.

    Args:
        text: The user's input, e.g. ``'1 3 5-8'``.
        count: Number of items available (valid choices are 1..count).

    Returns:
        Sorted, de-duplicated list of 0-based indices.

    Raises:
        ValueError: If count is 0, the input is empty, a token is not a
            number/range/'all', a number is 0 or above count, or a range is
            reversed. The message names the offending token.
    """
    if count <= 0:
        raise ValueError("There is nothing to select (count is 0).")
    # Close up spaces around '-' so "5 - 8" becomes the single token "5-8".
    cleaned = re.sub(r"\s*-\s*", "-", text.strip())
    tokens = [t for t in re.split(r"[\s,]+", cleaned) if t]
    if not tokens:
        raise ValueError("Empty selection: type numbers, ranges like 5-8, or 'all'.")

    if len(tokens) == 1 and tokens[0].lower() == "all":
        return list(range(count))

    chosen = set()
    for token in tokens:
        range_match = _RANGE_RE.match(token)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start > end:
                raise ValueError(f"Reversed range '{token}': use {end}-{start}.")
            numbers = range(start, end + 1)
        elif token.isdigit():
            numbers = [int(token)]
        else:
            raise ValueError(f"Cannot understand '{token}'.")
        for number in numbers:
            if number < 1 or number > count:
                raise ValueError(
                    f"'{token}' is out of range: choose between 1 and {count}."
                )
            chosen.add(number - 1)
    return sorted(chosen)
