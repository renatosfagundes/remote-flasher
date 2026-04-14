"""Plots tab — dynamic plot panels with per-channel visibility, add/remove.

Follows the same dynamic panel pattern as SerialTab: the user can add up to
4 independent plot panels, each showing any combination of channels overlaid.
"""

import json
import os
import sys
from collections import deque

from PySide6.QtCore import Qt, Signal, QTimer, QPointF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFileDialog, QSplitter, QCheckBox, QFrame, QSpinBox, QGridLayout,
    QScrollArea,
)

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from dashboard_backend import DashboardBackend


# Channel colors (cycling palette)
CHANNEL_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#ecf0f1",
    "#e84393", "#00cec9", "#fdcb6e", "#6c5ce7",
    "#ff7675", "#74b9ff", "#55efc4", "#ffeaa7",
]

MAX_PANELS = 4


# ---------------------------------------------------------------------------
# PlotPanel — a single chart with channel checkboxes
# ---------------------------------------------------------------------------

class PlotPanel(QFrame):
    """One plot pane: a QChartView + channel toggle checkboxes."""

    close_requested = Signal(object)

    def __init__(self, backend: DashboardBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "PlotPanel { border: 1px solid #444; border-radius: 3px; background: #1e1e2e; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Header row: channel checkboxes + window + close ---
        header = QHBoxLayout()
        header.setSpacing(6)

        header.addWidget(QLabel("Channels:"))

        # Channel checkboxes container
        self._ch_container = QWidget()
        self._ch_layout = QHBoxLayout(self._ch_container)
        self._ch_layout.setContentsMargins(0, 0, 0, 0)
        self._ch_layout.setSpacing(6)
        header.addWidget(self._ch_container, stretch=1)

        self._checkboxes: list[QCheckBox] = []

        # Window size spinner
        header.addWidget(QLabel("Window:"))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(50, 5000)
        self.window_spin.setValue(500)
        self.window_spin.setSingleStep(100)
        self.window_spin.setSuffix(" pts")
        self.window_spin.setFixedWidth(100)
        header.addWidget(self.window_spin)

        # Close button — matches Serial tab style
        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setToolTip("Close this plot panel")
        self.close_btn.setStyleSheet(
            "QPushButton { background: #8b0000; color: white; font-weight: bold; "
            "border-radius: 3px; padding: 0; } QPushButton:hover { background: #b22222; }"
        )
        self.close_btn.clicked.connect(lambda: self.close_requested.emit(self))
        header.addWidget(self.close_btn)

        layout.addLayout(header)

        # --- Chart ---
        self._chart = QChart()
        self._chart.setBackgroundBrush(QColor("#16162a"))
        self._chart.setPlotAreaBackgroundBrush(QColor("#16162a"))
        self._chart.setPlotAreaBackgroundVisible(True)
        self._chart.legend().setVisible(True)
        self._chart.legend().setLabelColor(QColor("#ccc"))
        from PySide6.QtCore import QMargins
        self._chart.setMargins(QMargins(4, 4, 4, 4))
        self._chart.setTitle("")

        self._x_axis = QValueAxis()
        self._x_axis.setLabelsColor(QColor("#999"))
        self._x_axis.setGridLineColor(QColor("#333"))
        self._x_axis.setLinePenColor(QColor("#555"))
        self._x_axis.setRange(0, 500)
        self._x_axis.setTickCount(6)
        self._chart.addAxis(self._x_axis, Qt.AlignBottom)

        self._y_axis = QValueAxis()
        self._y_axis.setLabelsColor(QColor("#999"))
        self._y_axis.setGridLineColor(QColor("#333"))
        self._y_axis.setLinePenColor(QColor("#555"))
        self._y_axis.setRange(0, 100)
        self._y_axis.setTickCount(6)
        self._chart.addAxis(self._y_axis, Qt.AlignLeft)

        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(self._chart_view.renderHints())
        self._chart_view.setStyleSheet("background: #16162a; border: none;")
        layout.addWidget(self._chart_view, stretch=1)

        # Channel → series mapping
        self._series: dict[int, QLineSeries] = {}

        # Listen for channel count changes to rebuild checkboxes
        self._backend.channelCountChanged.connect(self._rebuild_checkboxes)
        self._rebuild_checkboxes(self._backend.channelCount)

    def _rebuild_checkboxes(self, count: int):
        """Create/remove channel checkboxes to match the detected channel count."""
        # Remove excess
        while len(self._checkboxes) > count:
            cb = self._checkboxes.pop()
            self._ch_layout.removeWidget(cb)
            cb.deleteLater()

        # Add missing
        for i in range(len(self._checkboxes), count):
            cb = QCheckBox(f"CH{i}")
            color = CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            cb.setStyleSheet(
                f"QCheckBox {{ color: {color}; font-weight: bold; font-size: 11px; }}"
                f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
            )
            cb.setChecked(False)
            cb.toggled.connect(lambda checked, ch=i: self._on_channel_toggled(ch, checked))
            self._ch_layout.addWidget(cb)
            self._checkboxes.append(cb)

    def _on_channel_toggled(self, channel: int, checked: bool):
        if checked:
            self._add_series(channel)
        else:
            self._remove_series(channel)

    def _add_series(self, channel: int):
        if channel in self._series:
            return
        s = QLineSeries()
        s.setName(f"CH{channel}")
        color = QColor(CHANNEL_COLORS[channel % len(CHANNEL_COLORS)])
        pen = QPen(color)
        pen.setWidth(2)
        s.setPen(pen)
        self._chart.addSeries(s)
        s.attachAxis(self._x_axis)
        s.attachAxis(self._y_axis)
        self._series[channel] = s

    def _remove_series(self, channel: int):
        s = self._series.pop(channel, None)
        if s is not None:
            self._chart.removeSeries(s)

    def refresh(self):
        """Pull latest data from backend and update all active series."""
        if not self._series:
            return

        window = self.window_spin.value()
        global_min_y = float("inf")
        global_max_y = float("-inf")
        max_x = 0.0
        min_x = 0.0

        for channel, series in self._series.items():
            buf = self._backend._series_buffers[channel]
            n = len(buf)
            if n == 0:
                continue

            start = self._backend._sample_index - n
            points = [QPointF(float(start + i), v) for i, v in enumerate(buf)]
            series.replace(points)

            buf_min = min(buf)
            buf_max = max(buf)
            if buf_min < global_min_y:
                global_min_y = buf_min
            if buf_max > global_max_y:
                global_max_y = buf_max

            last_x = float(start + n)
            if last_x > max_x:
                max_x = last_x
            min_x = float(start)

        # Update axes
        if global_min_y != float("inf"):
            rng = global_max_y - global_min_y
            if rng < 1:
                rng = 1
            margin = rng * 0.1
            self._y_axis.setRange(global_min_y - margin, global_max_y + margin)

        x_start = max(min_x, max_x - window)
        self._x_axis.setRange(x_start, max(max_x, x_start + window))

    def set_channels(self, channels: list[int]):
        """Programmatically enable specific channels (used for default config)."""
        for ch in channels:
            if ch < len(self._checkboxes):
                self._checkboxes[ch].setChecked(True)

    def cleanup(self):
        """Called before removal."""
        self._backend.channelCountChanged.disconnect(self._rebuild_checkboxes)


# ---------------------------------------------------------------------------
# PlotsTab — dynamic panel container
# ---------------------------------------------------------------------------

class PlotsTab(QWidget):
    """Tab with dynamically add/removable plot panels."""

    source_changed = Signal(int)

    def __init__(self, backend: DashboardBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self.panels: list[PlotPanel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- Control bar ---
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Serial source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("(none)", userData=-1)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.source_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        ctrl.addWidget(self.source_combo)

        ctrl.addStretch()

        self.log_btn = QPushButton("Start Log")
        self.log_btn.setCheckable(True)
        self.log_btn.toggled.connect(self._on_log_toggled)
        ctrl.addWidget(self.log_btn)

        self.add_btn = QPushButton("+ Add Plot")
        self.add_btn.clicked.connect(self._add_panel)
        self.add_btn.setStyleSheet(
            "QPushButton { background: #27ae60; }"
            "QPushButton:hover { background: #2ecc71; }"
        )
        ctrl.addWidget(self.add_btn)

        layout.addLayout(ctrl)

        # --- Panel container ---
        self._grid_container = QWidget()
        layout.addWidget(self._grid_container, stretch=1)

        # Start with one panel
        self._add_panel()

        # Refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(33)  # ~30 fps
        self._refresh_timer.timeout.connect(self._refresh_all)
        self._refresh_timer.start()

        self._backend.loggingChanged.connect(self._sync_log_button)

    # ------------------------------------------------------------------
    # Panel management (mirrors SerialTab pattern)
    # ------------------------------------------------------------------

    def _add_panel(self):
        if len(self.panels) >= MAX_PANELS:
            return
        panel = PlotPanel(self._backend)
        panel.close_requested.connect(self._remove_panel)
        self.panels.append(panel)
        self._rebuild_layout()
        self._update_add_btn()

    def _remove_panel(self, panel):
        if panel in self.panels:
            panel.cleanup()
            self.panels.remove(panel)
            panel.setParent(None)
            panel.deleteLater()
        self._rebuild_layout()
        self._update_add_btn()
        if not self.panels:
            self._add_panel()

    def _update_add_btn(self):
        self.add_btn.setEnabled(len(self.panels) < MAX_PANELS)
        self.add_btn.setText(
            f"+ Add Plot ({len(self.panels)}/{MAX_PANELS})"
        )

    def _rebuild_layout(self):
        """Rebuild the splitter layout based on current panel count."""
        # Clear old layout
        old_layout = self._grid_container.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w and w not in self.panels:
                    w.deleteLater()
            from PySide6.QtWidgets import QWidget as _QW
            _QW().setLayout(old_layout)  # discard

        n = len(self.panels)
        if n == 0:
            layout = QVBoxLayout(self._grid_container)
            return

        # Show/hide close buttons
        for p in self.panels:
            p.close_btn.setVisible(n > 1)

        EQUAL = 10000

        if n == 1:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.panels[0])

        elif n == 2:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            splitter = QSplitter(Qt.Vertical)
            splitter.addWidget(self.panels[0])
            splitter.addWidget(self.panels[1])
            splitter.setSizes([EQUAL, EQUAL])
            layout.addWidget(splitter)

        elif n == 3:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            v_split = QSplitter(Qt.Vertical)
            top_split = QSplitter(Qt.Horizontal)
            top_split.addWidget(self.panels[0])
            top_split.addWidget(self.panels[1])
            top_split.setSizes([EQUAL, EQUAL])
            v_split.addWidget(top_split)
            v_split.addWidget(self.panels[2])
            v_split.setSizes([EQUAL, EQUAL])
            layout.addWidget(v_split)

        else:  # 4
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            v_split = QSplitter(Qt.Vertical)
            top_split = QSplitter(Qt.Horizontal)
            top_split.addWidget(self.panels[0])
            top_split.addWidget(self.panels[1])
            top_split.setSizes([EQUAL, EQUAL])
            bot_split = QSplitter(Qt.Horizontal)
            bot_split.addWidget(self.panels[2])
            bot_split.addWidget(self.panels[3])
            bot_split.setSizes([EQUAL, EQUAL])
            v_split.addWidget(top_split)
            v_split.addWidget(bot_split)
            v_split.setSizes([EQUAL, EQUAL])
            layout.addWidget(v_split)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self):
        for panel in self.panels:
            panel.refresh()

    # ------------------------------------------------------------------
    # Source & logging controls
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
