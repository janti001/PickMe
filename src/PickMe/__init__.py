__all__ = [
    'extract_and_store',
    'choose_object',
    'particle_extract',
    'decompress',
]


def __getattr__(name):
    if name in __all__:
        from .main import choose_object, decompress, extract_and_store, particle_extract

        exports = {
            'extract_and_store': extract_and_store,
            'choose_object': choose_object,
            'particle_extract': particle_extract,
            'decompress': decompress,
        }
        return exports[name]
    raise AttributeError(f"module 'PickMe' has no attribute {name!r}")
