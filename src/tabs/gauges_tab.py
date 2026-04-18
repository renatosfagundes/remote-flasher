"""Gauges tab — QPainter-based instrument cluster dashboard.

Uses AnalogGaugeWidget (ported from KhamisiKibet's PyQt5 widget) for polished
circular gauges with conical gradients, themed colors, and smooth rendering.
Info cards and status lights are simple QWidgets at the bottom.
"""

import json
import os
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QFileDialog, QFrame, QSizePolicy,
)

from analog_gauge_widget import AnalogGaugeWidget
from dashboard_backend import DashboardBackend


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "gauges": [
        {"channel": 0, "label": "RPM",   "min": 0, "max": 8000, "units": " x1000",
         "scalaCount": 8, "theme": 0},
        {"channel": 1, "label": "Speed", "min": 0, "max": 200,  "units": " km/h",
         "scalaCount": 10, "theme": 0},
    ],
    "infoCards": [
        {"channel": 1, "label": "MAX SPEED", "units": "km/h", "color": "#00e5ff", "format": 0},
        {"channel": 0, "label": "AVG RPM",   "units": "rpm",  "color": "#00e5ff", "format": 0},
        {"channel": 2, "label": "COOLANT",   "units": "\u00b0C",   "color": "#f39c12", "format": 1},
        {"channel": 3, "label": "FUEL",      "units": "%",    "color": "#2ecc71", "format": 0},
    ],
    "lights": [
        {"channel": 4, "label": "DTC",   "color": "#e74c3c", "threshold": 1},
        {"channel": 5, "label": "BAT",   "color": "#f39c12", "threshold": 1},
        {"channel": 6, "label": "OIL",   "color": "#e74c3c", "threshold": 1},
        {"channel": 7, "label": "BRAKE", "color": "#e74c3c", "threshold": 1},
    ],
}


def _load_config():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
    cfg_path = os.path.join(base, "dashboard_config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: data.get(k, _DEFAULTS[k]) for k in _DEFAULTS}
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULTS)


# ---------------------------------------------------------------------------
# Small helper widgets
# ---------------------------------------------------------------------------

class InfoCardWidget(QFrame):
    """Flat info card showing label + value + units."""

    def __init__(self, label="", units="", color="#00e5ff", tooltip="", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "InfoCardWidget { background: #0c0c20; border: 1px solid #1a3050; border-radius: 6px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: #667788; font-size: 10px; font-weight: bold; border: none;")
        layout.addWidget(self._label)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        self._value_lbl = QLabel("0")
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: bold; font-family: 'Orbitron'; border: none;"
        )
        row.addWidget(self._value_lbl)
        self._units_lbl = QLabel(units)
        self._units_lbl.setStyleSheet("color: #667788; font-size: 11px; border: none;")
        row.addWidget(self._units_lbl)
        layout.addLayout(row)

        self.setFixedHeight(55)

        # Propagate tooltip to all children — child QLabels cover the frame
        # entirely, so Qt's default tooltip bubbling doesn't reach the parent.
        if tooltip:
            self.setToolTip(tooltip)
            self._label.setToolTip(tooltip)
            self._value_lbl.setToolTip(tooltip)
            self._units_lbl.setToolTip(tooltip)

    def set_value(self, text: str):
        self._value_lbl.setText(text)


class StatusLightWidget(QFrame):
    """Small indicator light with label."""

    def __init__(self, label="", color="#2ecc71", tooltip="", parent=None):
        super().__init__(parent)
        self._on_color = color
        self.setStyleSheet("StatusLightWidget { border: none; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self._dot = QLabel()
        self._dot.setFixedSize(16, 16)
        self._dot.setAlignment(Qt.AlignCenter)
        self._set_active(False)
        layout.addWidget(self._dot, alignment=Qt.AlignCenter)

        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet("color: #556; font-size: 9px; font-weight: bold; border: none;")
        layout.addWidget(self._lbl)

        self.setFixedWidth(50)

        # Propagate tooltip to children so hovering over the dot or label
        # triggers it (child widgets cover the parent's hover area).
        if tooltip:
            self.setToolTip(tooltip)
            self._dot.setToolTip(tooltip)
            self._lbl.setToolTip(tooltip)

    def _set_active(self, active: bool):
        if active:
            self._dot.setStyleSheet(
                f"background: {self._on_color}; border-radius: 8px; "
                f"border: 2px solid {self._on_color};"
            )
        else:
            self._dot.setStyleSheet(
                "background: #222; border-radius: 8px; border: 1px solid #333;"
            )
        self._active = active

    def update_from_value(self, value: float, threshold: float):
        self._set_active(value >= threshold)


# ---------------------------------------------------------------------------
# GaugesTab
# ---------------------------------------------------------------------------

class GaugesTab(QWidget):
    """Tab with QPainter-based analog gauge dashboard."""

    source_changed = Signal(int)

    def __init__(self, backend: DashboardBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._cfg = _load_config()
        # Scoped selector — an unscoped rule cascades into every child and
        # can suppress tooltip events on some Qt themes.
        self.setStyleSheet("GaugesTab { background: #0a0a18; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Control bar ---
        ctrl = QHBoxLayout()
        lbl = QLabel("Serial source:")
        lbl.setStyleSheet("color: #ccc; border: none;")
        ctrl.addWidget(lbl)
        self.source_combo = QComboBox()
        self.source_combo.addItem("(none)", userData=-1)
        self.source_combo.setToolTip(
            "Pick a serial panel to feed this dashboard.\n"
            "Enable 'Feed Dashboard' on a panel in the Serial tab first."
        )
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.source_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        ctrl.addWidget(self.source_combo)
        ctrl.addStretch()
        self.log_btn = QPushButton("Start Log")
        self.log_btn.setCheckable(True)
        self.log_btn.setToolTip("Record the streaming channel values to a CSV file.")
        self.log_btn.toggled.connect(self._on_log_toggled)
        ctrl.addWidget(self.log_btn)
        layout.addLayout(ctrl)

        # --- Gauge cluster area ---
        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(0)

        self._gauges: list[AnalogGaugeWidget] = []
        gauge_cfgs = self._cfg.get("gauges", _DEFAULTS["gauges"])

        for i, gcfg in enumerate(gauge_cfgs):
            g = AnalogGaugeWidget()
            g.setMinValue(gcfg.get("min", 0))
            g.setMaxValue(gcfg.get("max", 100))
            g.units = gcfg.get("units", "")
            g.setScalaCount(gcfg.get("scalaCount", 10))
            # Leave mouse tracking enabled (the default) so tooltips fire reliably.
            # Disabling it suppresses QEvent::ToolTip on some themes.
            g.setToolTip(
                f"{gcfg.get('label', 'Gauge')}\n"
                f"Channel: {gcfg.get('channel', i)}\n"
                f"Range: {gcfg.get('min', 0)}–{gcfg.get('max', 100)}{gcfg.get('units', '')}"
            )

            # Dark theme — dark face, colored arc only at the value
            g.set_scale_polygon_colors([
                [0.0, QColor(0, 229, 255, 200)],
                [0.1, QColor(0, 180, 220, 160)],
                [0.15, QColor(0, 120, 160, 80)],
                [1.0, Qt.transparent],
            ])
            g.needle_center_bg = [
                [0, QColor(20, 25, 35, 255)],
                [0.16, QColor(15, 20, 30, 255)],
                [0.225, QColor(20, 26, 38, 255)],
                [0.42, QColor(10, 14, 22, 255)],
                [0.58, QColor(25, 32, 45, 255)],
                [0.79, QColor(30, 38, 52, 255)],
                [0.935, QColor(15, 20, 30, 255)],
                [1, QColor(20, 25, 35, 255)],
            ]
            g.outer_circle_bg = [
                [0.065, QColor(15, 20, 30, 255)],
                [0.378, QColor(30, 40, 55, 255)],
                [1, QColor(15, 20, 30, 255)],
            ]
            g.setNeedleColor(220, 235, 255, 255)
            g.setScaleValueColor(160, 190, 210, 255)
            g.setDisplayValueColor(220, 240, 255, 255)
            g.set_CenterPointColor(60, 80, 100, 255)
            g.setBigScaleColor("#5588aa")
            g.setFineScaleColor("#2a3a4a")
            g.setEnableBarGraph(True)
            g.setEnableCenterPoint(True)
            g.setEnableScaleText(True)
            g.setEnableValueText(True)

            # Make center gauge larger
            if i == len(gauge_cfgs) - 1 and len(gauge_cfgs) > 1:
                g.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                g.setMinimumSize(250, 250)
            else:
                g.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                g.setMinimumSize(180, 180)

            self._gauges.append(g)
            gauge_row.addWidget(g)

        layout.addLayout(gauge_row, stretch=1)

        # --- Status lights row ---
        lights_row = QHBoxLayout()
        lights_row.setAlignment(Qt.AlignCenter)
        lights_row.setSpacing(8)
        self._lights: list[tuple[StatusLightWidget, dict]] = []
        for lcfg in self._cfg.get("lights", []):
            light = StatusLightWidget(
                label=lcfg.get("label", ""),
                color=lcfg.get("color", "#2ecc71"),
                tooltip=(
                    f"{lcfg.get('label', 'Light')}\n"
                    f"Channel: {lcfg.get('channel', 0)}\n"
                    f"Lights up when value ≥ {lcfg.get('threshold', 1)}"
                ),
            )
            self._lights.append((light, lcfg))
            lights_row.addWidget(light)
        layout.addLayout(lights_row)

        # --- Info cards row ---
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        self._cards: list[tuple[InfoCardWidget, dict]] = []
        for ccfg in self._cfg.get("infoCards", []):
            units = ccfg.get("units", "")
            card = InfoCardWidget(
                label=ccfg.get("label", ""),
                units=units,
                color=ccfg.get("color", "#00e5ff"),
                tooltip=(
                    f"{ccfg.get('label', 'Card')}\n"
                    f"Channel: {ccfg.get('channel', 0)}"
                    + (f"\nUnits: {units}" if units else "")
                ),
            )
            self._cards.append((card, ccfg))
            cards_row.addWidget(card)
        layout.addLayout(cards_row)

        # --- Connect backend updates ---
        self._backend.channelsUpdated.connect(self._on_data_updated)
        self._backend.loggingChanged.connect(self._sync_log_button)

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _on_data_updated(self):
        vals = self._backend.channelValues
        gauge_cfgs = self._cfg.get("gauges", [])

        # Update gauges
        for i, g in enumerate(self._gauges):
            if i < len(gauge_cfgs):
                ch = gauge_cfgs[i].get("channel", i)
                if ch < len(vals):
                    g.updateValue(vals[ch])

        # Update info cards
        for card, ccfg in self._cards:
            ch = ccfg.get("channel", 0)
            if ch < len(vals):
                fmt = ccfg.get("format", 0)
                v = vals[ch]
                card.set_value(f"{v:.{fmt}f}" if fmt > 0 else str(int(v)))

        # Update status lights
        for light, lcfg in self._lights:
            ch = lcfg.get("channel", 0)
            thresh = lcfg.get("threshold", 1)
            v = vals[ch] if ch < len(vals) else 0
            light.update_from_value(v, thresh)

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _on_source_changed(self, idx):
        data = self.source_combo.itemData(idx)
        self.source_changed.emit(data if data is not None else -1)

    def _on_log_toggled(self, checked):
        if checked:
            default_name = DashboardBackend.default_log_path()
            path, _ = QFileDialog.getSaveFileName(
                self, "Save dashboard log", default_name, "CSV Files (*.csv)"
            )
            if path:
                self._backend.startLogging(path)
            else:
                self.log_btn.blockSignals(True)
                self.log_btn.setChecked(False)
                self.log_btn.blockSignals(False)
        else:
            self._backend.stopLogging()

    def _sync_log_button(self, logging):
        self.log_btn.blockSignals(True)
        self.log_btn.setChecked(logging)
        self.log_btn.setText("Stop Log" if logging else "Start Log")
        self.log_btn.blockSignals(False)
