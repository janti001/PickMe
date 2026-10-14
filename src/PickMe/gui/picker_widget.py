"""Dock panel for the click-to-select workflow in ``choose_objects``.

This widget is deliberately "dumb": it holds no data, knows nothing about
napari or files, and only (a) displays what it is told and (b) emits signals
when the user asks for something. A separate controller (``picker.py``)
connects those signals to the real work. Keeping the two apart means the
panel can be tested without a viewer.

All Qt imports go through ``qtpy`` so the same code runs on PyQt5 (HPC) and
PyQt6 (laptop). Enum names are written in the fully-scoped PyQt6 style, which
qtpy >= 2.4 also accepts on PyQt5.
"""

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PickerWidget(QWidget):
    """Side panel to switch tomogram and review/fix the current selection.

    Signals (the widget never acts on them itself; the controller does):
        tomogram_requested: ``tomo_id`` the user wants shown.
        remove_requested: one label to deselect (emitted once per list row).
        clear_requested: the user pressed "Clear all".
    """

    tomogram_requested = Signal(str)
    remove_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, tomo_ids, parent=None):
        """Builds the panel.

        Args:
            tomo_ids (list[str]): Tomogram IDs, in the order they are offered.
            parent (QWidget | None): Optional Qt parent.
        """
        super().__init__(parent)
        self._tomo_ids = list(tomo_ids)

        help_label = QLabel(
            "Click an object to select/deselect it.\nDrag to pan/rotate."
        )
        help_label.setWordWrap(True)

        self._combo = QComboBox()
        self._combo.addItems(self._tomo_ids)
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        tomo_row = QHBoxLayout()
        tomo_row.addWidget(self._combo, stretch=1)
        tomo_row.addWidget(self._prev_button)
        tomo_row.addWidget(self._next_button)

        self._header = QLabel("Selected: 0")
        self._list = QListWidget()
        self._list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self._remove_button = QPushButton("Remove selected")
        self._remove_button.setEnabled(False)
        self._clear_button = QPushButton("Clear all")
        button_row = QHBoxLayout()
        button_row.addWidget(self._remove_button)
        button_row.addWidget(self._clear_button)

        self._status = QLabel("")
        self._status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(help_label)
        layout.addLayout(tomo_row)
        layout.addWidget(self._header)
        layout.addWidget(self._list, stretch=1)
        layout.addLayout(button_row)
        layout.addWidget(self._status)

        # User-driven events only. set_current_tomogram() blocks the combo's
        # signals, so programmatic changes never reach _on_combo_changed.
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        self._prev_button.clicked.connect(lambda: self._step(-1))
        self._next_button.clicked.connect(lambda: self._step(1))
        self._list.itemSelectionChanged.connect(self._update_remove_enabled)
        self._remove_button.clicked.connect(self._on_remove_clicked)
        self._clear_button.clicked.connect(self.clear_requested.emit)

        self._update_nav_buttons()

    # ---- public API (called by the controller) ----

    def set_current_tomogram(self, tomo_id):
        """Shows ``tomo_id`` as current without emitting ``tomogram_requested``.

        Args:
            tomo_id (str): Must be one of the IDs given at construction.
        """
        index = self._tomo_ids.index(tomo_id)
        # blockSignals: otherwise changing the combo would look like a user
        # request and the controller would reload the tomogram it just loaded.
        was_blocked = self._combo.blockSignals(True)
        self._combo.setCurrentIndex(index)
        self._combo.blockSignals(was_blocked)
        self._update_nav_buttons()

    def set_selected_objects(self, rows):
        """Replaces the list contents.

        Args:
            rows (list[tuple[int, int | None]]): ``(label, voxel_count)``
                pairs; ``voxel_count`` may be None when unknown.
        """
        self._list.clear()
        for label, voxel_count in rows:
            if voxel_count is None:
                text = f"label {label}"
            else:
                text = f"label {label} — {voxel_count:,} voxels"
            item = QListWidgetItem(text)
            # Store the int on the item so we never have to parse the text.
            item.setData(Qt.ItemDataRole.UserRole, int(label))
            self._list.addItem(item)
        self._header.setText(f"Selected: {len(rows)}")
        self._update_remove_enabled()

    def set_status(self, text):
        """Shows a one-line status message.

        Args:
            text (str): Message to display.
        """
        self._status.setText(text)

    # ---- internal slots ----

    def _on_combo_changed(self, index):
        self._update_nav_buttons()
        if 0 <= index < len(self._tomo_ids):
            self.tomogram_requested.emit(self._tomo_ids[index])

    def _step(self, offset):
        """Requests the neighbouring tomogram (no wrap-around)."""
        new_index = self._combo.currentIndex() + offset
        if 0 <= new_index < len(self._tomo_ids):
            self.tomogram_requested.emit(self._tomo_ids[new_index])

    def _on_remove_clicked(self):
        for item in self._list.selectedItems():
            self.remove_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _update_remove_enabled(self):
        self._remove_button.setEnabled(bool(self._list.selectedItems()))

    def _update_nav_buttons(self):
        index = self._combo.currentIndex()
        self._prev_button.setEnabled(index > 0)
        self._next_button.setEnabled(index < len(self._tomo_ids) - 1)
