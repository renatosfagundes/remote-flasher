"""Side panel for per-signal configuration (color, scale, offset, visibility)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QDoubleSpinBox, QLineEdit, QPushButton, QScrollArea, QFrame,
    QColorDialog,
)

from plotter.signal_config import SignalConfig


class SignalRow(QFrame):
    """One row in the signal list: visibility + color + name + scale + offset."""
    config_changed = Signal(int, SignalConfig)

    def __init__(self, cfg: SignalConfig, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "SignalRow { border: 1px solid #333; border-radius: 3px; "
            "background: #1e1e2e; padding: 2px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Top row: visibility + color swatch + name
        top = QHBoxLayout()
        top.setSpacing(4)

        self._vis_cb = QCheckBox()
        self._vis_cb.setChecked(cfg.visible)
        self._vis_cb.toggled.connect(self._on_vis)
        top.addWidget(self._vis_cb)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(20, 20)
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        top.addWidget(self._color_btn)

        self._name_edit = QLineEdit(cfg.name)
        self._name_edit.setMaximumWidth(100)
        self._name_edit.setStyleSheet("background: #252540; color: #ccc; padding: 1px 3px; font-size: 11px;")
        self._name_edit.editingFinished.connect(self._on_name)
        top.addWidget(self._name_edit)
        top.addStretch()
        layout.addLayout(top)

        # Bottom row: scale + offset spinners
        bottom = QHBoxLayout()
        bottom.setSpacing(4)

        bottom.addWidget(QLabel("S:"))
        self._scale_spin = QDoubleSpinBox()
        self._scale_spin.setRange(-1000, 1000)
        self._scale_spin.setDecimals(3)
        self._scale_spin.setSingleStep(0.1)
        self._scale_spin.setValue(cfg.scale)
        self._scale_spin.setMaximumWidth(70)
        self._scale_spin.setStyleSheet("font-size: 10px;")
        self._scale_spin.valueChanged.connect(self._on_scale)
        bottom.addWidget(self._scale_spin)

        bottom.addWidget(QLabel("O:"))
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(-100000, 100000)
        self._offset_spin.setDecimals(2)
        self._offset_spin.setSingleStep(1.0)
        self._offset_spin.setValue(cfg.offset)
        self._offset_spin.setMaximumWidth(70)
        self._offset_spin.setStyleSheet("font-size: 10px;")
        self._offset_spin.valueChanged.connect(self._on_offset)
        bottom.addWidget(self._offset_spin)
        bottom.addStretch()
        layout.addLayout(bottom)

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background: {self._cfg.color}; border: 1px solid #555; border-radius: 3px;"
        )

    def _emit(self):
        self.config_changed.emit(self._cfg.index, self._cfg)

    def _on_vis(self, checked):
        self._cfg.visible = checked
        self._emit()

    def _on_name(self):
        self._cfg.name = self._name_edit.text().strip() or f"CH{self._cfg.index}"
        self._emit()

    def _on_scale(self, v):
        self._cfg.scale = v
        self._emit()

    def _on_offset(self, v):
        self._cfg.offset = v
        self._emit()

    def _pick_color(self):
        color = QColorDialog.getColor(
            initial=self._cfg.color, parent=self, title=f"Color for {self._cfg.name}"
        )
        if color.isValid():
            self._cfg.color = color.name()
            self._update_color_btn()
            self._emit()


class SignalListWidget(QWidget):
    """Scrollable list of SignalRow widgets, one per detected channel."""
    config_changed = Signal(int, SignalConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[SignalRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Signals")
        header.setStyleSheet("font-weight: bold; font-size: 12px; color: #ccc; padding: 4px;")
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(2, 2, 2, 2)
        self._layout.setSpacing(4)
        self._layout.addStretch()

        scroll.setWidget(self._container)
        outer.addWidget(scroll)

    def set_configs(self, configs: list[SignalConfig]):
        """Rebuild the signal list to match the given configs."""
        # Remove excess rows
        while len(self._rows) > len(configs):
            row = self._rows.pop()
            self._layout.removeWidget(row)
            row.deleteLater()

        # Update existing rows
        for i, cfg in enumerate(configs):
            if i < len(self._rows):
                # Row already exists — just update visuals if needed
                pass
            else:
                # Create new row
                row = SignalRow(cfg)
                row.config_changed.connect(self._on_row_changed)
                self._rows.append(row)
                # Insert before the stretch
                self._layout.insertWidget(self._layout.count() - 1, row)

    def _on_row_changed(self, index: int, cfg: SignalConfig):
        self.config_changed.emit(index, cfg)
