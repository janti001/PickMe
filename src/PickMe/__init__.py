from importlib import import_module
from typing import TYPE_CHECKING

__all__ = [
    'utils',
    'angles',
    'filter',
    'plotting',
    'sampling',
    'filter_objects',
    'choose_object',
    'particle_extract',
    'decompress',
]

_SUBMODULES = {'utils', 'angles', 'filter', 'plotting', 'sampling'}
_PIPELINE_FUNCTIONS = {
    'filter_objects',
    'choose_object',
    'particle_extract',
    'decompress',
}

if TYPE_CHECKING:
    from . import angles, filter, plotting, sampling, utils
    from .main import choose_object, decompress, filter_objects, particle_extract #can just write this line and it would be fine


def __getattr__(name):
    if name in _SUBMODULES:
        module = import_module(f'{__name__}.{name}')
        globals()[name] = module
        return module

    if name in _PIPELINE_FUNCTIONS:
        from .main import choose_object, decompress, filter_objects, particle_extract

        exports = {
            'filter_objects': filter_objects,
            'choose_object': choose_object,
            'particle_extract': particle_extract,
            'decompress': decompress,
        }
        globals().update(exports)
        return exports[name]
    raise AttributeError(f"module 'PickMe' has no attribute {name!r}")
