"""GUI-only helpers for PickMe.

Everything in this subpackage exists to support the napari step of
`choose_objects`. Nothing here is imported when PickMe starts: `napari`,
`qtpy` and Qt itself are only imported inside the functions that need them,
so the headless pipeline stages (`filter_objects`, `particle_extraction`)
never pay for - or fail on - a GUI import.

Import the module you need directly and lazily, from inside the GUI code
path:

    from ..gui import napari_compat

Deliberately empty otherwise: adding a re-export here would pull Qt in at
package import time and defeat the point.
"""
