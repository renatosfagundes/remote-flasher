"""Real-time scrolling plot widget using pyqtgraph."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

from plotter.plotter_backend import PlotterBackend


# Dark theme matching the app's look
pg.setConfigOptions(
    background="#16162a",
    foreground="#cccccc",
    antialias=True,
)


class ClickableLegendItem(pg.LegendItem):
    """LegendItem whose entries emit a signal when clicked."""
    # (curve, label_text) — caught by PlotterWidget to toggle visibility.
    sampleClicked = Signal(object, str)

    def mousePressEvent(self, ev):
        # Determine which legend entry the click hit by walking the layout.
        for sample, label in self.items:
            # sample.sceneBoundingRect() includes the color swatch;
            # label covers the text. Either is a valid hit target.
            rect = sample.sceneBoundingRect().united(label.sceneBoundingRect())
            if rect.contains(ev.scenePos()):
                # `sample.item` is the curve (PlotDataItem) associated with
                # this legend entry — pyqtgraph stores it there.
                curve = getattr(sample, "item", None)
                self.sampleClicked.emit(curve, label.text)
                ev.accept()
                return
        super().mousePressEvent(ev)


class PlotterWidget(QWidget):
    """pyqtgraph-based real-time scrolling plot.

    Refreshes at 30 fps. Each visible signal gets its own PlotDataItem
    curve, updated from the backend's ring buffers with scale+offset applied.
    """
    # Emitted when the user clicks a legend entry — so the SignalListWidget
    # can sync its visibility checkbox for that signal.
    signalVisibilityToggled = Signal(int, bool)  # (index, visible)

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

        plot_item = self._plot_widget.getPlotItem()
        # Ticks + values on all four sides.
        for side in ("top", "right"):
            plot_item.showAxis(side)
            plot_item.getAxis(side).setStyle(showValues=True)

        # Legend — auto-populated from each curve's `name`. Semi-transparent
        # background so it doesn't hide data. Click an entry to hide/show
        # the curve (and keep the side-panel checkbox in sync).
        self._legend = ClickableLegendItem(
            offset=(-10, 10),
            brush=pg.mkBrush("#00000099"),
            pen=pg.mkPen("#555"),
            labelTextColor="#dddddd",
        )
        self._legend.setParentItem(plot_item.vb)
        self._legend.sampleClicked.connect(self._on_legend_clicked)

        # Crosshair for hover
        self._vline = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen("#ffffff", width=0.5, style=pg.QtCore.Qt.DashLine),
        )
        self._plot_widget.addItem(self._vline, ignoreBounds=True)
        self._vline.setVisible(False)

        # Dots marking the (hover_x, y_i) intersection for each visible curve.
        self._hover_dots = pg.ScatterPlotItem(size=9, pen=pg.mkPen("#ffffff", width=1.5))
        self._hover_dots.setVisible(False)
        self._plot_widget.addItem(self._hover_dots, ignoreBounds=True)

        # Hover label — dark background box so numbers stay legible over curves.
        self._hover_label = pg.TextItem(
            anchor=(0, 1),
            color="#ffffff",
            fill=pg.mkBrush("#000000cc"),
            border=pg.mkPen("#888"),
        )
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

    def _on_legend_clicked(self, curve, label_text):
        """Legend entry clicked — toggle that curve's visibility."""
        # Find which config index this curve belongs to.
        for idx, c in self._curves.items():
            if c is curve:
                configs = self._backend.configs
                if idx < len(configs):
                    configs[idx].visible = not configs[idx].visible
                    self._backend.update_config(idx, configs[idx])
                    self.update_curve_style(idx)
                    self.signalVisibilityToggled.emit(idx, configs[idx].visible)
                return

    def update_curve_style(self, index: int):
        """Update a curve's pen color, visibility, and legend entry from config."""
        if index not in self._curves:
            return
        configs = self._backend.configs
        if index >= len(configs):
            return
        cfg = configs[index]
        curve = self._curves[index]
        curve.setPen(pg.mkPen(cfg.color, width=2))
        curve.setVisible(cfg.visible)
        # Rebuild this curve's legend entry — pyqtgraph's LegendItem doesn't
        # track name/visibility changes on its own.
        try:
            self._legend.removeItem(curve)
        except Exception:
            pass
        if cfg.visible:
            self._legend.addItem(curve, cfg.name)
        curve.opts["name"] = cfg.name

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
        """Show crosshair + per-curve dot + value tooltip on hover."""
        if not self._plot_widget.sceneBoundingRect().contains(pos):
            self._vline.setVisible(False)
            self._hover_label.setVisible(False)
            self._hover_dots.setVisible(False)
            return

        mouse_point = self._plot_widget.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        self._vline.setPos(x)
        self._vline.setVisible(True)

        configs = self._backend.configs
        t_all = self._backend.time_buffer().get_array()
        if len(t_all) == 0:
            self._hover_label.setVisible(False)
            self._hover_dots.setVisible(False)
            return

        # Nearest-sample index for the hover x.
        idx = min(np.searchsorted(t_all, x), len(t_all) - 1)
        x_snap = float(t_all[idx])

        dot_spots = []
        lines = [f"t = {x_snap:.2f}s"]
        for i in range(self._backend.channel_count):
            if i >= len(configs) or not configs[i].visible:
                continue
            ch = self._backend.channel_buffer(i).get_array()
            if idx >= len(ch):
                continue
            scaled = float(ch[idx]) * configs[i].scale + configs[i].offset
            lines.append(f"{configs[i].name}: {scaled:.3f}")
            dot_spots.append({
                "pos": (x_snap, scaled),
                "brush": pg.mkBrush(configs[i].color),
            })

        self._hover_dots.setData(dot_spots)
        self._hover_dots.setVisible(bool(dot_spots))
        self._hover_label.setText("\n".join(lines))
        self._hover_label.setPos(mouse_point)
        self._hover_label.setVisible(True)

    def clear_plot(self):
        """Remove all curves and reset."""
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        self._curves.clear()
