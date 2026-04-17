"""Real-time scrolling plot widget using pyqtgraph."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout

from plotter.plotter_backend import PlotterBackend


# Dark theme matching the app's look
pg.setConfigOptions(
    background="#16162a",
    foreground="#cccccc",
    antialias=True,
)


class PlotterWidget(QWidget):
    """pyqtgraph-based real-time scrolling plot.

    Refreshes at 30 fps. Each visible signal gets its own PlotDataItem
    curve, updated from the backend's ring buffers with scale+offset applied.
    """

    def __init__(self, backend: PlotterBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._window_seconds = 10.0
        self._curves: dict[int, pg.PlotDataItem] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Value")
        # Enable mouse zoom/pan
        self._plot_widget.setMouseEnabled(x=True, y=True)
        layout.addWidget(self._plot_widget)

        # Crosshair for hover
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ffffff", width=0.5, style=pg.QtCore.Qt.DashLine))
        self._plot_widget.addItem(self._vline, ignoreBounds=True)
        self._vline.setVisible(False)

        # Hover label
        self._hover_label = pg.TextItem(anchor=(0, 1), color="#cccccc")
        self._hover_label.setVisible(False)
        self._plot_widget.addItem(self._hover_label, ignoreBounds=True)

        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Refresh timer — 30 fps
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        self._backend.channelCountChanged.connect(self._rebuild_curves)

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    @window_seconds.setter
    def window_seconds(self, v: float):
        self._window_seconds = max(1.0, v)

    def _rebuild_curves(self, count: int):
        """Add/remove curves to match the current channel count."""
        # Add new curves
        for i in range(count):
            if i not in self._curves:
                cfg = self._backend.configs[i] if i < len(self._backend.configs) else None
                color = cfg.color if cfg else "#ffffff"
                curve = self._plot_widget.plot(
                    pen=pg.mkPen(color, width=2),
                    name=cfg.name if cfg else f"CH{i}",
                )
                self._curves[i] = curve

        # Remove excess curves
        to_remove = [i for i in self._curves if i >= count]
        for i in to_remove:
            self._plot_widget.removeItem(self._curves.pop(i))

    def update_curve_style(self, index: int):
        """Update a curve's pen color and visibility from its config."""
        if index not in self._curves:
            return
        configs = self._backend.configs
        if index >= len(configs):
            return
        cfg = configs[index]
        curve = self._curves[index]
        curve.setPen(pg.mkPen(cfg.color, width=2))
        curve.setVisible(cfg.visible)

    def _refresh(self):
        """Called at 30 fps — update curve data and scroll X axis."""
        if self._backend.paused:
            return
        if not self._backend.check_dirty():
            return

        t_buf = self._backend.time_buffer()
        t_count = t_buf.count
        if t_count == 0:
            return

        # Determine how many samples to show based on window
        t_all = t_buf.get_array()
        latest_t = t_all[-1] if len(t_all) > 0 else 0

        # Find samples within the window
        t_min = latest_t - self._window_seconds
        mask = t_all >= t_min
        t_window = t_all[mask]

        configs = self._backend.configs
        for i, curve in self._curves.items():
            if i >= len(configs):
                continue
            cfg = configs[i]
            if not cfg.visible:
                curve.setVisible(False)
                continue
            curve.setVisible(True)

            ch_buf = self._backend.channel_buffer(i)
            ch_all = ch_buf.get_array()

            # Align lengths (time and channel buffers should match)
            n = min(len(t_all), len(ch_all))
            if n == 0:
                continue
            ch_slice = ch_all[-n:][mask[-n:]] if n <= len(mask) else ch_all
            t_slice = t_window

            # Align after masking
            m = min(len(t_slice), len(ch_slice))
            if m == 0:
                continue

            y = ch_slice[:m] * cfg.scale + cfg.offset
            curve.setData(t_slice[:m], y)

        # Scroll X axis
        self._plot_widget.setXRange(t_min, latest_t, padding=0)

    def _on_mouse_moved(self, pos):
        """Show crosshair + value tooltip on hover."""
        if not self._plot_widget.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._hover_label.setVisible(False)
            return

        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        self._vline.setPos(x)
        self._vline.setVisible(True)

        # Build tooltip with nearest values for each visible channel
        configs = self._backend.configs
        lines = [f"t = {x:.2f}s"]

        t_buf = self._backend.time_buffer()
        t_all = t_buf.get_array()
        if len(t_all) == 0:
            self._hover_label.setVisible(False)
            return

        # Find nearest time index
        idx = np.searchsorted(t_all, x)
        idx = min(idx, len(t_all) - 1)

        for i in range(self._backend.channel_count):
            if i >= len(configs) or not configs[i].visible:
                continue
            ch = self._backend.channel_buffer(i).get_array()
            if idx < len(ch):
                raw = ch[idx]
                scaled = raw * configs[i].scale + configs[i].offset
                lines.append(f"{configs[i].name}: {scaled:.3f}")

        self._hover_label.setText("\n".join(lines))
        self._hover_label.setPos(mouse_point)
        self._hover_label.setVisible(True)

    def clear_plot(self):
        """Remove all curves and reset."""
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        self._curves.clear()
