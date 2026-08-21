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
    `release_viewer`'s docstring above - it is not; this is the second,
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

    napari-skimage builds the table as a `magicgui.widgets.Table` and docks it
    in its *own* dock widget named "Results Table" - it is not a child of the
    plugin's widget. Three lookups are tried, cheapest and most robust first:

    1. `plugin_widget.results_table`, the attribute napari-skimage sets on its
       own widget. This is the one that actually works today.
    2. A `findChild` scan of the plugin widget, in case a future release nests
       the table inside it again.
    3. A scan of every dock widget napari has registered.

    Step 3 has a trap worth naming, because it is what previously broke this
    function: `viewer.window.dock_widgets` returns the *inner* widget of each
    dock, so for "Results Table" the inner widget **is** the table. Qt's
    `findChild` only searches descendants, so it returns None for a widget
    that is itself the thing you are looking for. Each candidate is therefore
    isinstance-checked before its children are searched.

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

    # 1. The plugin's own attribute - a magicgui Table wrapping the Qt table.
    results_table = getattr(plugin_widget, 'results_table', None)
    native = getattr(results_table, 'native', None)
    if isinstance(native, table_classes):
        print(
            '[PickMe] Found table via the plugin\'s results_table attribute '
            f'({type(native).__name__}).'
        )
        return native

    # 2. Nested somewhere inside the plugin widget.
    for table_class in table_classes:
        table = plugin_widget.native.findChild(table_class)
        if table is not None:
            print(f'[PickMe] Found table in plugin widget: {table_class.__name__}')
            return table

    # 3. Any dock widget - checking each candidate itself before its children.
    for dock_name, dock_widget in iter_dock_widgets(viewer):
        native = getattr(dock_widget, 'native', dock_widget)
        if isinstance(native, table_classes):
            print(
                f"[PickMe] Found table as dock widget: '{dock_name}' "
                f'({type(native).__name__})'
            )
            return native
        for table_class in table_classes:
            table = native.findChild(table_class)
            if table is not None:
                print(
                    f"[PickMe] Found table inside dock widget: '{dock_name}' "
                    f'({table_class.__name__})'
                )
                return table

    return None


def table_headers(table):
    """Read the table's column headers.

    Args:
        table (QTableView or QTableWidget): The results table.

    Returns:
        list[str]: One header per column. Columns with no header text become
        empty strings.
    """
    from qtpy.QtCore import Qt

    model = table.model()
    if model is None:
        return []
    headers = []
    for column in range(model.columnCount()):
        value = model.headerData(column, Qt.Horizontal)
        headers.append('' if value is None else str(value))
    return headers


def find_label_column(table):
    """Find which column of the results table holds the object label.

    `skimage.measure.regionprops_table` returns its columns in alphabetical
    order, so "label" is almost never column 0 - it lands wherever the sort
    puts it among the properties the user ticked. Assuming column 0 reads the
    wrong property entirely (usually `area`), which is why this lookup is by
    header name.

    Args:
        table (QTableView or QTableWidget): The results table.

    Returns:
        int or None: The zero-based column index of the "label" column, or
        None if the user did not tick "label" in the plugin's property list.
    """
    for index, header in enumerate(table_headers(table)):
        if header.strip().lower() == 'label':
            return index
    return None


def read_label_cell(table, row, column):
    """Read one label value out of the results table.

    The table stores its values as *strings* ("7.0", not 7), because magicgui
    renders the dataframe for display. `int('7.0')` raises `ValueError`, so
    the value goes through `float` first.

    Args:
        table (QTableView or QTableWidget): The results table.
        row (int): Zero-based row index.
        column (int): Zero-based column index of the label column.

    Returns:
        int or None: The label, or None if the cell could not be read as a
        number.
    """
    value = table.model().index(row, column).data()
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def configure_table_selection(table):
    """Make the results table select whole rows, several at a time.

    Without this the table selects individual cells, so a click registers one
    property rather than one object. Qt's enums are addressed defensively
    because PyQt6/PySide6 scope them one level deeper than PyQt5 does.

    Args:
        table (QTableView or QTableWidget): The results table.
    """
    from qtpy.QtWidgets import QAbstractItemView

    selection_mode = getattr(
        QAbstractItemView,
        'ExtendedSelection',
        getattr(QAbstractItemView, 'SelectionMode', None),
    )
    if hasattr(selection_mode, 'ExtendedSelection'):
        selection_mode = selection_mode.ExtendedSelection

    selection_behavior = getattr(
        QAbstractItemView,
        'SelectRows',
        getattr(QAbstractItemView, 'SelectionBehavior', None),
    )
    if hasattr(selection_behavior, 'SelectRows'):
        selection_behavior = selection_behavior.SelectRows

    if selection_mode is not None:
        table.setSelectionMode(selection_mode)
    if selection_behavior is not None:
        table.setSelectionBehavior(selection_behavior)


def defer(callback):
    """Run `callback` on the next turn of the Qt event loop.

    Used to tell a real "deselect everything" apart from the empty selection
    Qt emits just *before* it repopulates or destroys a table. Both look
    identical at the moment they fire - the row count has not changed yet -
    but by the next tick the repopulation or teardown has finished and the
    two are easy to distinguish.

    Args:
        callback (callable): Called with no arguments on the next event-loop
            iteration.
    """
    from qtpy.QtCore import QTimer

    QTimer.singleShot(0, callback)


def table_is_alive(table):
    """Report whether the table's underlying Qt object still exists.

    Qt objects are destroyed when the viewer window closes, but the Python
    wrapper lingers; touching it then raises `RuntimeError`. Selections made
    before the close are still valid, so callers use this to bail out quietly
    rather than treating teardown as user input.

    Args:
        table (QTableView or QTableWidget): The results table.

    Returns:
        bool: True if the table can still be queried.
    """
    try:
        table.model()
    except RuntimeError:
        return False
    return True


def analysed_labels_layer(plugin_widget):
    """Return the labels layer the plugin last ran regionprops on.

    This is the layer the table's rows actually describe. It is a more
    reliable answer to "which tomogram is this selection for?" than the
    viewer's active layer, which follows whatever the user last clicked in the
    layer list and is not tied to the table's contents at all.

    Args:
        plugin_widget: The widget returned by `add_regionprops_widget`.

    Returns:
        napari.layers.Labels or None: The analysed layer, or None if the
        plugin does not expose it.
    """
    labels_layer = getattr(plugin_widget, 'labels_layer', None)
    return getattr(labels_layer, 'value', None)


def find_run_button(plugin_widget):
    """Locate the plugin's "Analyze" button.

    Prefers magicgui's own `call_button`, which is the documented handle for
    the button that runs the function. The `findChild` scans are fallbacks:
    the plugin also has a "Save Results" button, so taking the first button in
    the tree unconditionally can bind to the wrong one.

    Args:
        plugin_widget: The widget returned by `add_regionprops_widget`.

    Returns:
        QPushButton or None: The button if one was found, otherwise None.
    """
    from qtpy.QtWidgets import QPushButton

    call_button = getattr(plugin_widget, 'call_button', None)
    native = getattr(call_button, 'native', None)
    if isinstance(native, QPushButton):
        return native

    for button in plugin_widget.native.findChildren(QPushButton):
        if button.text().strip().lower() in ('analyze', 'analyse', 'run'):
            return button

    return plugin_widget.native.findChild(QPushButton)


def connect_analysis_finished(plugin_widget, callback):
    """Call `callback` every time the plugin finishes an analysis run.

    magicgui emits `called` after the widget's function returns, which is
    exactly when the results table has been filled. That is a supported API,
    so it is tried first; wiring the button's `clicked` signal is the fallback
    for builds that do not emit it.

    Args:
        plugin_widget: The widget returned by `add_regionprops_widget`.
        callback (callable): Called with no arguments after each run.

    Returns:
        str or None: A short description of what was connected, for printing,
        or None if neither route was available.
    """
    called = getattr(plugin_widget, 'called', None)
    if called is not None and hasattr(called, 'connect'):
        # magicgui passes the function's return value through; swallow it.
        called.connect(lambda *_: callback())
        return "magicgui 'called' signal"

    run_button = find_run_button(plugin_widget)
    if run_button is not None:
        run_button.clicked.connect(lambda *_: callback())
        return f"'{run_button.text()}' button"

    return None