"""Plotter tab — real-time serial plotter with pyqtgraph.

Inspired by BetterSerialPlotter: scrolling time-series plot with per-signal
configuration (color, scale, offset, visibility). Uses pyqtgraph for GPU-
accelerated rendering at 30 fps.

Data source: check "Feed Dashboard" on any serial panel. Named signals
(key:value format) are auto-discovered and displayed. Signals matching
dashboard property names are automatically routed to the HMI gauges.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSplitter, QFileDialog, QFrame,
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

        # Separator between destructive/export controls and view controls.
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #333;")
        toolbar.addWidget(sep)

        self.cursors_btn = QPushButton("Cursors")
        self.cursors_btn.setCheckable(True)
        self.cursors_btn.setToolTip(
            "Toggle a draggable measurement-cursor pair. "
            "The stats panel switches to showing Δ/min/max/mean between the cursors."
        )
        self.cursors_btn.toggled.connect(self._on_cursors_toggled)
        toolbar.addWidget(self.cursors_btn)

        self.auto_y_btn = QPushButton("Auto-Y")
        self.auto_y_btn.setToolTip("Fit the Y axis once to the data currently on screen.")
        self.auto_y_btn.clicked.connect(lambda: self._plot.auto_y())
        toolbar.addWidget(self.auto_y_btn)

        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.setToolTip("Resume X scrolling and auto-fit Y.")
        self.reset_view_btn.clicked.connect(lambda: self._plot.reset_view())
        toolbar.addWidget(self.reset_view_btn)

        self.stats_btn = QPushButton("Stats")
        self.stats_btn.setCheckable(True)
        self.stats_btn.setToolTip(
            "Show a side panel with per-signal min/max/mean/std for the "
            "visible window (or between cursors when Cursors is on)."
        )
        self.stats_btn.toggled.connect(self._on_stats_toggled)
        toolbar.addWidget(self.stats_btn)

        toolbar.addStretch()

        # Effective sample-rate indicator (right-aligned). Updates on the
        # same 5 Hz tick as the stats panel.
        self.rate_label = QLabel("— Hz")
        self.rate_label.setToolTip(
            "Effective sample rate — samples/sec over the last 2 s. "
            "Verifies the firmware is hitting its task period."
        )
        self.rate_label.setStyleSheet("color: #888; padding: 0 8px;")
        toolbar.addWidget(self.rate_label)

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

        # Stats panel (3rd pane, hidden by default). A single rich-text
        # label rebuilt on each refresh — simpler than a dynamic per-row
        # widget set, and plenty fast for the ~20-channel target.
        self._stats_panel = QWidget()
        stats_layout = QVBoxLayout(self._stats_panel)
        stats_layout.setContentsMargins(8, 8, 8, 8)
        stats_layout.setSpacing(4)
        self._stats_header = QLabel("Stats — visible window")
        self._stats_header.setStyleSheet(
            "color: #bbb; font-weight: bold; padding-bottom: 4px;"
            " border-bottom: 1px solid #333;"
        )
        stats_layout.addWidget(self._stats_header)
        self._stats_body = QLabel(
            '<span style="color:#666;">No visible signals.</span>'
        )
        self._stats_body.setTextFormat(Qt.RichText)
        self._stats_body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._stats_body.setWordWrap(True)
        stats_layout.addWidget(self._stats_body, stretch=1)
        self._stats_panel.setMinimumWidth(220)
        self._stats_panel.setMaximumWidth(360)
        splitter.addWidget(self._stats_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        # Size the 3rd pane before hiding so the splitter remembers the
        # intended width for when the user toggles Stats back on.
        splitter.setSizes([200, 800, 260])
        self._stats_panel.setVisible(False)

        layout.addWidget(splitter, stretch=1)

        # React to channel count changes (auto-discovery)
        self._backend.channelCountChanged.connect(self._on_channels)

        # 5 Hz tick drives the sample-rate label and (when visible) the
        # stats panel. Cheap enough to leave running unconditionally —
        # compute_sample_rate is an O(n_tail) numpy slice.
        self._poll = QTimer(self)
        self._poll.setInterval(200)
        self._poll.timeout.connect(self._refresh_panels)
        self._poll.start()

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

    def _on_cursors_toggled(self, on):
        self._plot.set_cursors_enabled(on)
        # Force an immediate panel refresh so the header switches
        # modes without waiting up to 200 ms for the next tick.
        self._refresh_panels()

    def _on_stats_toggled(self, on):
        self._stats_panel.setVisible(on)
        if on:
            self._refresh_panels()

    def _refresh_panels(self):
        """5 Hz tick: update the sample-rate label and stats panel (if shown)."""
        rate = self._plot.compute_sample_rate()
        self.rate_label.setText(f"{rate:.1f} Hz" if rate > 0 else "— Hz")

        if not self._stats_panel.isVisible():
            return

        if self._plot.cursors_enabled():
            t1, t2 = self._plot.cursor_positions()
            stats = self._plot.compute_stats(t1, t2)
            self._stats_header.setText(f"Stats — cursors  Δt = {t2 - t1:.3f} s")
        else:
            stats = self._plot.compute_stats()
            self._stats_header.setText(
                f"Stats — visible window ({self._plot.window_seconds:.0f} s)"
            )

        if not stats:
            self._stats_body.setText(
                '<span style="color:#666;">No visible signals in range.</span>'
            )
            return

        # Monospace rows keep numeric columns aligned; colored signal
        # name matches the curve's pen so cross-reference is instant.
        rows = []
        for s in stats.values():
            rows.append(
                f'<div style="margin-bottom: 10px;">'
                f'<span style="color:{s["color"]}; font-weight:bold;">{s["name"]}</span>'
                f'<pre style="color:#ddd; margin:2px 0 0 0; font-size:11px;">'
                f'min  {s["min"]:>10.3f}\n'
                f'max  {s["max"]:>10.3f}\n'
                f'mean {s["mean"]:>10.3f}\n'
                f'std  {s["std"]:>10.3f}\n'
                f'Δ    {s["delta"]:>10.3f}   n={s["n"]}'
                f'</pre></div>'
            )
        self._stats_body.setText("".join(rows))
