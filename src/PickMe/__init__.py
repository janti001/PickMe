from importlib import import_module
from typing import TYPE_CHECKING

__all__ = [
    'utils',
    'angles',
    'filter',
    'plotting',
    'sampling',
    'extract_and_store',
    'choose_object',
    'particle_extract',
    'decompress',
]

_SUBMODULES = {'utils', 'angles', 'filter', 'plotting', 'sampling'}
_PIPELINE_FUNCTIONS = {
    'extract_and_store',
    'choose_object',
    'particle_extract',
    'decompress',
}

if TYPE_CHECKING:
    from . import angles, filter, plotting, sampling, utils
    from .main import choose_object, decompress, extract_and_store, particle_extract


def __getattr__(name):
    if name in _SUBMODULES:
        module = import_module(f'{__name__}.{name}')
        globals()[name] = module
        return module

    if name in _PIPELINE_FUNCTIONS:
        from .main import choose_object, decompress, extract_and_store, particle_extract

        exports = {
            'extract_and_store': extract_and_store,
            'choose_object': choose_object,
            'particle_extract': particle_extract,
            'decompress': decompress,
        }
        globals().update(exports)
        return exports[name]
    raise AttributeError(f"module 'PickMe' has no attribute {name!r}")
