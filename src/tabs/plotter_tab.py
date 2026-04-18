"""Plotter tab — real-time serial plotter with pyqtgraph.

Inspired by BetterSerialPlotter: scrolling time-series plot with per-signal
configuration (color, scale, offset, visibility). Uses pyqtgraph for GPU-
accelerated rendering at 30 fps.

Data source: check "Feed Dashboard" on any serial panel. Named signals
(key:value format) are auto-discovered and displayed. Signals matching
dashboard property names are automatically routed to the HMI gauges.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSplitter, QFileDialog,
)

from plotter.plotter_backend import PlotterBackend
from plotter.plotter_widget import PlotterWidget
from plotter.signal_list_widget import SignalListWidget


class PlotterTab(QWidget):
    """Top-level plotter tab with signal config and plot area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend = PlotterBackend(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("Window:"))
        self.window_combo = QComboBox()
        for label, secs in [("5s", 5), ("10s", 10), ("30s", 30), ("60s", 60), ("120s", 120)]:
            self.window_combo.addItem(label, userData=secs)
        self.window_combo.setCurrentIndex(1)  # 10s default
        self.window_combo.setToolTip("Visible time window on the X axis.")
        self.window_combo.currentIndexChanged.connect(self._on_window)
        toolbar.addWidget(self.window_combo)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setToolTip("Freeze the plot; incoming data is still buffered.")
        self.pause_btn.toggled.connect(self._on_pause)
        toolbar.addWidget(self.pause_btn)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setToolTip("Save the full buffered history to a CSV file.")
        self.export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self.export_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Discard all buffered samples and reset the signal list.")
        self.clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── Main area: signal list (left) + plot (right) ──────────
        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)

        self._signal_list = SignalListWidget()
        self._signal_list.setMinimumWidth(180)
        self._signal_list.setMaximumWidth(300)
        self._signal_list.config_changed.connect(self._on_config_changed)
        splitter.addWidget(self._signal_list)

        self._plot = PlotterWidget(self._backend)
        self._plot.signalVisibilityToggled.connect(self._signal_list.set_visibility)
        splitter.addWidget(self._plot)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 800])

        layout.addWidget(splitter, stretch=1)

        # React to channel count changes (auto-discovery)
        self._backend.channelCountChanged.connect(self._on_channels)

    @property
    def backend(self) -> PlotterBackend:
        return self._backend

    def _on_window(self, _index):
        secs = self.window_combo.currentData()
        if secs:
            self._plot.window_seconds = float(secs)

    def _on_pause(self, paused):
        self._backend.paused = paused
        self.pause_btn.setText("Resume" if paused else "Pause")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Data", "plot_data.csv", "CSV Files (*.csv)"
        )
        if path:
            self._backend.export_csv(path)

    def _on_clear(self):
        self._backend.reset()
        self._plot.clear_plot()
        self._signal_list.set_configs([])

    def _on_channels(self, count):
        """New channel count detected — rebuild signal list."""
        self._signal_list.set_configs(self._backend.configs[:count])

    def _on_config_changed(self, index, cfg):
        """User changed a signal's config — push to backend + update curve."""
        self._backend.update_config(index, cfg)
        self._plot.update_curve_style(index)
