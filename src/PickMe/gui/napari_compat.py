"""Environment checks and viewer clean-up for the napari GUI step.

`choose_objects` drives napari through its public API (layers, mouse
callbacks, colormaps, a dock widget of PickMe's own - see `gui/picker.py`).
What is left here is everything around that which is environment-sensitive:

- `check_gui_versions` - compare the installed napari against the range
  PickMe pins, and warn loudly on a mismatch instead of failing obscurely.
- `check_display` - warn before Qt aborts on a machine with no display.
- `check_render_backend` - warn when OpenGL is a software rasterizer, which
  is known to crash napari's 3D view.
- `release_viewer` - deregister the viewer's vispy canvas on close, so a
  second viewer in the same Python session can render.

The last two touch napari's private `_qt_viewer.canvas._scene_canvas`
attribute, which is why they live in this one module: there is a single
place to fix if an upstream release moves it.

Nothing here is imported at package import time. `napari`, `vispy` and
`qtpy` are imported inside the functions that use them, so the headless
pipeline stages never touch Qt.

Note:
    `SUPPORTED_VERSIONS` below must be kept in step with the pins in
    `pyproject.toml` and `PickMe.yml`. If you widen a pin there, widen it
    here too, and vice versa.
"""

import importlib.metadata as importlib_metadata
import os
import sys

# Inclusive lower bound, exclusive upper bound - the same ranges as the pins
# in pyproject.toml and PickMe.yml, expressed as comparable tuples.
SUPPORTED_VERSIONS = {
    'napari': ((0, 7, 0), (0, 8, 0)),
}

DOCS_HINT = 'See docs/gui-setup.md for the supported install path.'


class NapariCompatError(RuntimeError):
    """Raised when the installed napari stack does not look like PickMe expects.

    Carries a message that names both the version PickMe was pinned against
    and the version actually installed, so the fix is obvious from the error
    alone.
    """


def _version_tuple(version_string):
    """Convert a version string to a tuple of ints for comparison.

    Only the leading numeric components are used, so pre-release and local
    suffixes (``0.7.0rc1``, ``0.7.0+local``) compare as their base release.

    Args:
        version_string (str): A version as reported by package metadata,
            e.g. ``'0.7.0'``.

    Returns:
        tuple[int, ...]: The numeric components, e.g. ``(0, 7, 0)``. Returns
        an empty tuple if nothing numeric could be parsed.
    """
    parts = []
    for chunk in version_string.split('.'):
        digits = ''
        for character in chunk:
            if not character.isdigit():
                break
            digits += character
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def installed_version(package_name):
    """Look up an installed package's version.

    Args:
        package_name (str): Distribution name, e.g. ``'napari'``.

    Returns:
        str or None: The version string, or None if the package is not
        installed.
    """
    try:
        return importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        return None


def check_gui_versions(strict=False):
    """Compare the installed napari stack against the versions PickMe pins.

    This is the loud-failure check described in the module docstring. It runs
    before the viewer opens so a mismatch is reported up front rather than
    surfacing later as a confusing error deep inside napari.

    Args:
        strict (bool, optional): If True, raise `NapariCompatError` on the
            first mismatch. If False (the default), print a warning per
            mismatched package and carry on - an out-of-range version often
            still works, and blocking the user's only way to pick objects is
            worse than warning them. Defaults to False.

    Returns:
        list[str]: One human-readable message per problem found. Empty when
        every pinned package is installed and inside its supported range.

    Raises:
        NapariCompatError: If `strict` is True and any package is missing or
            outside its supported range.
    """
    problems = []
    for package_name, (minimum, maximum) in SUPPORTED_VERSIONS.items():
        found = installed_version(package_name)
        expected = f'>={_join(minimum)},<{_join(maximum)}'

        if found is None:
            problems.append(
                f'expected {package_name} {expected}, but it is not installed '
                f'- GUI selection will not work. {DOCS_HINT}'
            )
            continue

        found_tuple = _version_tuple(found)
        if not found_tuple or minimum <= found_tuple < maximum:
            # An unparseable version is not worth failing over; treat it as OK.
            continue

        problems.append(
            f'expected {package_name} {expected}, found {found} - GUI '
            f'selection may not work. {DOCS_HINT}'
        )

    if problems and strict:
        raise NapariCompatError('\n'.join(problems))

    for problem in problems:
        print(f'[PickMe] WARNING: {problem}')

    return problems


def _join(version_tuple):
    """Render a version tuple back as a dotted string for messages."""
    return '.'.join(str(part) for part in version_tuple)


def check_display():
    """Warn early if this looks like a machine with no display to open onto.

    On Linux (including WSL and HPC compute nodes) Qt needs an X or Wayland
    display. Without one, napari aborts with a Qt platform-plugin error that
    gives the user no idea what to do. This turns that into a pointed message
    before the viewer is constructed.

    Only Linux is checked - macOS and Windows do not use `DISPLAY`.

    Returns:
        str or None: The warning message if no display was found, otherwise
        None. The message is also printed.
    """
    if not sys.platform.startswith('linux'):
        return None
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        return None

    message = (
        'no DISPLAY or WAYLAND_DISPLAY is set, so Qt has no window system to '
        'draw into. On HPC, connect with `ssh -X`/`-Y` or use an interactive '
        'job or VNC session - batch (sbatch) jobs cannot run choose_objects. '
        'On WSL, you need WSLg or an X server on the Windows side. '
        f'{DOCS_HINT}'
    )
    print(f'[PickMe] WARNING: {message}')
    return message


# Renderer name fragments that identify a software (CPU) OpenGL rasterizer
# rather than a real GPU. Lowercase, matched as a substring of GL_RENDERER.
_SOFTWARE_RENDERERS = ('llvmpipe', 'softpipe', 'swrast', 'software rasterizer')


def check_render_backend(viewer):
    """Warn if the viewer's OpenGL context is a software rasterizer.

    napari's 2D slice view and its 3D volume view are not equally demanding:
    3D pushes a large texture and an active ray-marching shader through
    OpenGL, where 2D only blits image slices. Software rasterizers (Mesa
    `llvmpipe`/`softpipe`, `swrast`) - the fallback this project's own
    `docs/gui-setup.md` recommends for WSL when GPU passthrough is missing -
    are known to handle the 2D path fine and then fail partway through
    building the 3D volume texture, leaving vispy's GLIR command queue
    referencing a buffer the driver never finished creating::

        RuntimeError: Cannot SIZE object 44 because it does not exist

    napari reports that as a napari/vispy version mismatch, which - per
    `release_viewer`'s docstring below - it is not; this is the second,
    unrelated cause of the same GLIR error. There is no reliable way to
    detect this before the user actually toggles to 3D (the failure is deep
    inside vispy's draw call), so this only warns up front, once, right
    after the viewer opens, rather than trying to intercept the crash.

    This is diagnostic only. It cannot make software rendering handle 3D
    volumes; it can only tell the user why it might not before they hit it.

    Args:
        viewer (napari.Viewer): The freshly-created viewer to inspect. Must
            already have an OpenGL context (i.e. called after
            `napari.Viewer()`, not before).

    Returns:
        str or None: The GL_RENDERER string if it looks like software
        rendering, otherwise None - including when the renderer could not be
        determined at all. Never raises; a failed check is not worth
        blocking a run over.
    """
    try:
        from vispy.gloo import gl

        scene_canvas = viewer.window._qt_viewer.canvas._scene_canvas
        scene_canvas.set_current()
        renderer = gl.glGetParameter(gl.GL_RENDERER)
    except Exception:
        return None

    if isinstance(renderer, bytes):
        renderer = renderer.decode('utf-8', 'replace')
    renderer = str(renderer)

    if not any(marker in renderer.lower() for marker in _SOFTWARE_RENDERERS):
        return None

    print(
        f"[PickMe] WARNING: napari's OpenGL renderer is '{renderer}', a "
        'software (CPU) rasterizer rather than a GPU. 2D slice viewing is '
        'fine, but toggling to 3D is known to crash software rasterizers '
        "with a vispy 'Cannot SIZE object ... because it does not exist' "
        'error - this looks like a napari/vispy version mismatch but is '
        f'not. {DOCS_HINT}'
    )
    return renderer


def release_viewer(viewer):
    """Shut a viewer down so its canvas stops being vispy's draw target.

    `viewer.close()` on its own is not enough. vispy keeps a module-level list
    of every canvas ever registered (`vispy.gloo.context.canvasses`) and routes
    each draw to the *most recently registered* one. napari's close tears down
    the Qt widget but never calls vispy's `forget_canvas`, so the entry stays.

    Open a second viewer later in the same session and there are then two
    canvases. Each OpenGL context has its own GLIR parser holding the objects
    it created, so draw commands can reach a parser that never saw the matching
    CREATE, and vispy raises::

        RuntimeError: Cannot SIZE object 44 because it does not exist

    napari reports that as a vispy/napari version mismatch, which it is not.
    Under the CLI the process exits between runs and none of this shows up; in
    one long IPython/Jupyter session it does.

    `_qt_viewer.canvas._scene_canvas` is private, hence living in this module.
    Cleanup must never be the thing that breaks a run, so a moved attribute is
    reported and skipped rather than raised.

    Args:
        viewer (napari.Viewer): The viewer to shut down. Safe to call on a
            viewer that is already closed.

    Returns:
        bool: True if the canvas was deregistered from vispy, False if the
        private path has moved (in which case the viewer is still closed).
    """
    from vispy.gloo.context import forget_canvas

    forgotten = False
    try:
        #Deregister before close() - once Qt has deleted the underlying C++
        #widget, touching the canvas raises instead of cleaning up.
        scene_canvas = viewer.window._qt_viewer.canvas._scene_canvas
    except AttributeError as exc:
        print(
            f'[PickMe] WARNING: could not reach the vispy canvas to release it '
            f'({exc}). Opening another viewer in this same session may fail to '
            f'render. Restart Python between runs. {DOCS_HINT}'
        )
    else:
        forget_canvas(scene_canvas)
        forgotten = True

    try:
        viewer.close()
    except Exception as exc:
        #Never let cleanup mask whatever the real error on the way out was.
        print(f'[PickMe] WARNING: could not close the napari viewer: {exc}')

    return forgotten

