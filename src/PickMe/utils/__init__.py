"""Shared helper utilities for the PickMe pipeline.

Re-exports file-handling, path-resolution, and Chimera/ChimeraX-output
helpers used across the `filter_objects`, `choose_objects`,
`particle_extraction`, `decompress` and `convert` CLI subcommands: job
output-directory management (`check_make_dir`, `get_output_root`),
filename-agnostic identifiers and segmentation/tomogram pairing (`file_id`,
`match_segmentations`, `tomostar_name`, `strip_pickme_suffix`,
`tomogram_id_from_name`, ...), index-based file selection (`choose_tomograms`,
`choose_files`, `pair_unmatched`), labeled-object extraction
(`object_extraction`), interactive object selection (`choose_object`), and
Chimera/ChimeraX file writers (`chimera_star`, `cmm_write`).
"""

from .naming import (
    MRC_EXTENSIONS,
    PICKME_SUFFIXES,
    file_id,
    natural_sort_key,
    match_segmentations,
    tomostar_name,
    strip_pickme_suffix,
    tomogram_id_from_name,
    parse_index_selection,
)
from .object_extraction import object_extraction
from .choose_object import choose_object
from .choose_tomograms import (
    SEGMENTATION_PATTERN,
    format_indexed_choices,
    choose_files,
    choose_tomograms,
    pair_unmatched,
)
from .chimera_star import chimera_star
from .check_make_dir import check_make_dir, get_output_root
from .chimera_cmm import cmm_write
