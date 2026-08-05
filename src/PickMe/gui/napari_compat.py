"""Compatibility layer for the napari / napari-skimage GUI integration.

`choose_objects` does not talk to napari-skimage through a documented API -
there isn't one. It reaches into the plugin's Qt widget tree to find the
regionprops results table and the "Run" button, and it reads napari's private
`viewer.window._dock_widgets` mapping. None of that is public, so any napari
or napari-skimage release can change it without notice. That is the most
likely explanation for "the same code behaves differently on a different
machine".

Every one of those fragile accesses lives in this module, for two reasons:

1. There is one place to fix when an upstream release moves something.
2. A version mismatch fails *loudly*, naming the versions PickMe was pinned
   against, instead of silently selecting nothing and writing empty output.

Nothing here is imported at package import time. `napari` and `qtpy` are
imported inside the functions that use them, so the headless pipeline stages
never touch Qt.

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
    'napari-skimage': ((0, 6, 0), (0, 7, 0)),
}

# Name of the napari-skimage widget PickMe drives. If upstream renames this,
# `add_regionprops_widget` is where you will find out.
REGIONPROPS_PLUGIN = 'napari-skimage'
REGIONPROPS_WIDGET = 'Regionprops (labels)'

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
        package_name (str): Distribution name, e.g. ``'napari-skimage'``.

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
    surfacing later as an empty selection.

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


def add_regionprops_widget(viewer):
    """Dock the napari-skimage Regionprops widget into a viewer.

    Args:
        viewer (napari.Viewer): The viewer to dock the widget into.

    Returns:
        tuple: ``(dock_widget, plugin_widget)`` as returned by napari's
        `add_plugin_dock_widget`.

    Raises:
        NapariCompatError: If the plugin or the named widget could not be
            loaded - usually a version mismatch or a missing install.
    """
    try:
        return viewer.window.add_plugin_dock_widget(
            plugin_name=REGIONPROPS_PLUGIN,
            widget_name=REGIONPROPS_WIDGET,
        )
    except Exception as error:
        found = installed_version(REGIONPROPS_PLUGIN) or 'not installed'
        minimum, maximum = SUPPORTED_VERSIONS[REGIONPROPS_PLUGIN]
        raise NapariCompatError(
            f"could not load the '{REGIONPROPS_WIDGET}' widget from "
            f'{REGIONPROPS_PLUGIN} (found {found}, PickMe expects '
            f'>={_join(minimum)},<{_join(maximum)}). Object selection cannot '
            f'run without it. {DOCS_HINT}\nUnderlying error: {error}'
        ) from error


def iter_dock_widgets(viewer):
    """Yield napari's dock widgets, tolerating the public/private rename.

    napari has exposed this mapping as both `window.dock_widgets` and
    `window._dock_widgets` across releases. Trying the public name first
    means PickMe keeps working if and when the private one disappears.

    Args:
        viewer (napari.Viewer): The viewer to inspect.

    Yields:
        tuple[str, object]: ``(dock_widget_name, dock_widget)`` pairs. Yields
        nothing if neither attribute exists.
    """
    dock_widgets = getattr(viewer.window, 'dock_widgets', None)
    if dock_widgets is None:
        dock_widgets = getattr(viewer.window, '_dock_widgets', None)
    if dock_widgets is None:
        print(
            '[PickMe] WARNING: this napari build exposes neither '
            '`dock_widgets` nor `_dock_widgets`; falling back to searching '
            f'the plugin widget only. {DOCS_HINT}'
        )
        return

    yield from dock_widgets.items()


def dock_widget_names(viewer):
    """List the names of the viewer's dock widgets, for debug output.

    Args:
        viewer (napari.Viewer): The viewer to inspect.

    Returns:
        list[str]: Dock widget names, or an empty list if napari does not
        expose them.
    """
    return [name for name, _ in iter_dock_widgets(viewer)]


def find_regionprops_table(viewer, plugin_widget):
    """Locate the regionprops results table in the Qt widget tree.

    Searches the plugin's own widget first, then every dock widget napari has
    registered. Both are `findChild` scans rather than a supported lookup, so
    this is exactly the kind of access that breaks on upgrade - which is why
    it is isolated here.

    Args:
        viewer (napari.Viewer): The viewer, used for the dock-widget fallback
            search.
        plugin_widget: The widget returned by `add_regionprops_widget`.

    Returns:
        QTableView or QTableWidget or None: The table if found, otherwise
        None. The caller decides whether that is fatal.
    """
    from qtpy.QtWidgets import QTableView, QTableWidget

    table_classes = (QTableView, QTableWidget)

    for table_class in table_classes:
        table = plugin_widget.native.findChild(table_class)
        if table is not None:
            print(f'[PickMe] Found table in plugin widget: {table_class.__name__}')
            return table

    for dock_name, dock_widget in iter_dock_widgets(viewer):
        native = getattr(dock_widget, 'native', dock_widget)
        for table_class in table_classes:
            table = native.findChild(table_class)
            if table is not None:
                print(
                    f"[PickMe] Found table in dock widget: '{dock_name}' "
                    f'({table_class.__name__})'
                )
                return table

    return table


def find_run_button(plugin_widget):
    """Locate the plugin's "Run"/"Analyse" button.

    Takes the first `QPushButton` in the widget tree, which is how the button
    has been positioned in the supported napari-skimage versions. If upstream
    adds another button ahead of it, this picks up the wrong one - hence the
    isolation, and hence the tight pin on napari-skimage.

    Args:
        plugin_widget: The widget returned by `add_regionprops_widget`.

    Returns:
        QPushButton or None: The button if one was found, otherwise None.
    """
    from qtpy.QtWidgets import QPushButton

    return plugin_widget.native.findChild(QPushButton)

def _find_table(viewer, plugin_widget):
    """Search the plugin widget first, then all viewer dock widgets."""
    # Search inside the plugin widget's native Qt widget
    from qtpy.QtWidgets import QTableView, QTableWidget
    for cls in (QTableView, QTableWidget):
        table = plugin_widget.native.findChild(cls)
        if table is not None:
            print(f"[PickMe] Found table in plugin widget: {cls.__name__}")
            return table

    # Fallback: search every dock widget napari has registered
    for dock_name, dw in viewer.window._dock_widgets.items(): #changed from _dock_widgets to dock_widgets  
        native = dw.native if hasattr(dw, 'native') else dw
        for cls in (QTableView, QTableWidget):
            table = native.findChild(cls)
            if table is not None:
                print(f"[PickMe] Found table in dock widget: '{dock_name}' ({cls.__name__})")
                return table

    return None